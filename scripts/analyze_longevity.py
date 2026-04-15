#!/usr/bin/env python3
"""
analyze_longevity.py — Personalized longevity health analysis from Neo4j

Queries your health graph, computes longevity-relevant insights, and generates
an actionable report with specific recommendations based on YOUR data.

This is the kind of analysis the Aura Agent will do conversationally.

Usage:
  python3 scripts/analyze_longevity.py                  # full analysis
  python3 scripts/analyze_longevity.py --months 3       # last 3 months
  python3 scripts/analyze_longevity.py --output report.md  # save to file
"""

import os
import sys
import argparse
import logging
from datetime import date, timedelta
from pathlib import Path
from textwrap import dedent

from dotenv import load_dotenv
from neo4j import GraphDatabase

log = logging.getLogger(__name__)


# ── Queries ────────────────────────────────────────────────────────────────

def query_overview(session, start_date):
    where = f"WHERE d.date >= date('{start_date}')" if start_date else ""
    r = session.run(f"""
        MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
        {where}
        RETURN count(d) AS days,
               min(d.date) AS first_date,
               max(d.date) AS last_date,
               round(avg(s.resting_heart_rate), 1) AS avg_rhr,
               round(avg(s.hrv_mean), 1) AS avg_hrv,
               round(avg(s.vo2max), 1) AS avg_vo2max,
               round(avg(s.total_steps), 0) AS avg_steps,
               round(avg(s.sleep_hours), 1) AS avg_sleep,
               round(avg(s.active_energy_kcal), 0) AS avg_active_cal,
               sum(s.workout_count) AS total_workouts,
               round(avg(s.workout_minutes), 1) AS avg_daily_workout_min
    """).single()
    return dict(r)


def query_recent_vs_baseline(session, recent_days=30):
    """Compare last N days vs overall baseline."""
    r = session.run("""
        MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
        WITH avg(s.resting_heart_rate) AS bl_rhr,
             avg(s.hrv_mean) AS bl_hrv,
             avg(s.vo2max) AS bl_vo2max,
             avg(s.total_steps) AS bl_steps,
             avg(s.sleep_hours) AS bl_sleep,
             avg(s.workout_minutes) AS bl_workout_min
        MATCH (d2:Day)-[:HAS_SUMMARY]->(s2:DailySummary)
        WHERE d2.date >= date() - duration('P' + $days + 'D')
        RETURN round(bl_rhr, 1) AS baseline_rhr,
               round(avg(s2.resting_heart_rate), 1) AS recent_rhr,
               round(bl_hrv, 1) AS baseline_hrv,
               round(avg(s2.hrv_mean), 1) AS recent_hrv,
               round(bl_vo2max, 1) AS baseline_vo2max,
               round(avg(s2.vo2max), 1) AS recent_vo2max,
               round(bl_steps, 0) AS baseline_steps,
               round(avg(s2.total_steps), 0) AS recent_steps,
               round(bl_sleep, 1) AS baseline_sleep,
               round(avg(s2.sleep_hours), 1) AS recent_sleep,
               round(bl_workout_min, 1) AS baseline_workout_min,
               round(avg(s2.workout_minutes), 1) AS recent_workout_min
    """, days=str(recent_days)).single()
    return dict(r)


def query_vo2max_trend(session):
    """VO2max first vs last 90 days."""
    r = session.run("""
        MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
        WHERE s.vo2max IS NOT NULL
        WITH min(d.date) AS first_date, max(d.date) AS last_date
        MATCH (d2:Day)-[:HAS_SUMMARY]->(s2:DailySummary)
        WHERE s2.vo2max IS NOT NULL
        WITH first_date, last_date,
             CASE WHEN d2.date <= first_date + duration('P90D') THEN 'early'
                  WHEN d2.date >= last_date - duration('P90D') THEN 'recent'
             END AS period, s2.vo2max AS v
        WHERE period IS NOT NULL
        RETURN period, round(avg(v), 1) AS avg_vo2max, count(*) AS readings
        ORDER BY period
    """)
    return {row["period"]: dict(row) for row in r}


def query_sleep_analysis(session, start_date):
    where = f"WHERE d.date >= date('{start_date}') AND " if start_date else "WHERE "
    r = session.run(f"""
        MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
        {where} s.sleep_hours IS NOT NULL
        RETURN count(*) AS days_with_sleep,
               round(avg(s.sleep_hours), 1) AS avg_sleep,
               round(stDev(s.sleep_hours), 2) AS sleep_std,
               round(percentileCont(s.sleep_hours, 0.25), 1) AS p25_sleep,
               round(percentileCont(s.sleep_hours, 0.75), 1) AS p75_sleep,
               sum(CASE WHEN s.sleep_hours >= 7 AND s.sleep_hours <= 8 THEN 1 ELSE 0 END) AS optimal_days,
               sum(CASE WHEN s.sleep_hours < 6 THEN 1 ELSE 0 END) AS short_sleep_days,
               sum(CASE WHEN s.sleep_hours > 9 THEN 1 ELSE 0 END) AS long_sleep_days
    """).single()
    return dict(r)


def query_workout_analysis(session, start_date):
    where = f"WHERE d.date >= date('{start_date}')" if start_date else ""
    r = session.run(f"""
        MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
        {where}
        WITH count(d) AS total_days,
             sum(CASE WHEN s.workout_count > 0 THEN 1 ELSE 0 END) AS workout_days,
             sum(s.workout_minutes) AS total_workout_min
        RETURN total_days,
               workout_days,
               total_days - workout_days AS rest_days,
               round(toFloat(workout_days) / total_days * 100, 1) AS workout_pct,
               round(total_workout_min / (total_days / 7.0), 0) AS weekly_avg_min
    """).single()
    return dict(r)


def query_workout_type_balance(session, start_date):
    where = f"WHERE d.date >= date('{start_date}')" if start_date else ""
    results = session.run(f"""
        MATCH (w:Workout)-[:ON_DAY]->(d:Day)
        {where}
        WITH w.activity_type AS type, count(*) AS cnt, sum(w.duration_min) AS total_min
        WITH type, cnt, total_min,
             CASE
                WHEN type IN ['Running', 'Cycling', 'Swimming', 'Walking', 'Elliptical',
                              'Rowing', 'StairClimbing', 'Hiking'] THEN 'cardio'
                WHEN type IN ['TraditionalStrengthTraining', 'FunctionalStrengthTraining',
                              'HighIntensityIntervalTraining', 'CrossTraining'] THEN 'strength'
                WHEN type IN ['Yoga', 'Flexibility', 'Pilates', 'MindAndBody',
                              'CoolDown'] THEN 'flexibility'
                ELSE 'other'
             END AS category
        RETURN category,
               sum(cnt) AS sessions,
               round(sum(total_min), 0) AS total_minutes
        ORDER BY sessions DESC
    """)
    return {row["category"]: dict(row) for row in results}


def query_overtraining_signals(session):
    """Weeks where training was high but HRV was low."""
    results = session.run("""
        MATCH (d:Day)-[:PART_OF]->(w:Week)
        MATCH (d)-[:HAS_SUMMARY]->(s:DailySummary)
        WHERE s.hrv_mean IS NOT NULL
        WITH w,
             sum(s.workout_minutes) AS train_min,
             avg(s.hrv_mean) AS avg_hrv,
             avg(s.resting_heart_rate) AS avg_rhr
        WHERE train_min > 200 AND avg_hrv < 30
        RETURN w.iso AS week,
               round(train_min, 0) AS training_min,
               round(avg_hrv, 1) AS avg_hrv,
               round(avg_rhr, 1) AS avg_rhr
        ORDER BY w.iso DESC
        LIMIT 5
    """)
    return [dict(r) for r in results]


def query_workout_hrv_impact(session):
    results = session.run("""
        MATCH (w:Workout)-[:ON_DAY]->(d1:Day)-[:HAS_SUMMARY]->(s1:DailySummary)
        MATCH (d1)-[:NEXT_DAY]->(d2:Day)-[:HAS_SUMMARY]->(s2:DailySummary)
        WHERE s1.hrv_mean IS NOT NULL AND s2.hrv_mean IS NOT NULL
        WITH w.activity_type AS type, count(*) AS n,
             avg(s2.hrv_mean - s1.hrv_mean) AS hrv_delta
        WHERE n >= 5
        RETURN type, n AS occurrences,
               round(hrv_delta, 1) AS avg_hrv_change
        ORDER BY hrv_delta DESC
    """)
    return [dict(r) for r in results]


def query_best_days(session):
    """Days with highest compound longevity score."""
    results = session.run("""
        MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
        WHERE s.hrv_mean IS NOT NULL AND s.resting_heart_rate IS NOT NULL
        WITH avg(s.hrv_mean) AS med_hrv, avg(s.resting_heart_rate) AS med_rhr
        MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
        WITH d, s, med_hrv, med_rhr,
             CASE WHEN s.hrv_mean > med_hrv THEN 1 ELSE 0 END +
             CASE WHEN s.resting_heart_rate < med_rhr THEN 1 ELSE 0 END +
             CASE WHEN s.sleep_hours >= 7 THEN 1 ELSE 0 END +
             CASE WHEN s.total_steps >= 8000 THEN 1 ELSE 0 END +
             CASE WHEN s.workout_count > 0 THEN 1 ELSE 0 END AS score
        WHERE score >= 4
        RETURN count(*) AS green_days,
               round(avg(score), 1) AS avg_score
    """).single()
    return dict(results)


def query_step_distribution(session, start_date):
    where = f"WHERE d.date >= date('{start_date}') AND " if start_date else "WHERE "
    r = session.run(f"""
        MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
        {where} s.total_steps IS NOT NULL
        RETURN count(*) AS total_days,
               sum(CASE WHEN s.total_steps >= 10000 THEN 1 ELSE 0 END) AS days_10k,
               sum(CASE WHEN s.total_steps >= 7000 AND s.total_steps < 10000 THEN 1 ELSE 0 END) AS days_7k,
               sum(CASE WHEN s.total_steps < 5000 THEN 1 ELSE 0 END) AS sedentary_days
    """).single()
    return dict(r)


# ── Analysis & Advice ──────────────────────────────────────────────────────

def generate_report(overview, recent_vs_bl, vo2max_trend, sleep, workout,
                    type_balance, overtraining, hrv_impact, best_days,
                    step_dist, start_date):
    """Generate the full analysis report."""

    sections = []
    sections.append("# Longevity Health Analysis Report\n")
    sections.append(f"*Analysis period: {overview.get('first_date', 'N/A')} to "
                    f"{overview.get('last_date', 'N/A')} "
                    f"({overview.get('days', 0):,} days)*\n")

    # ── Executive Summary ──
    sections.append("## Executive Summary\n")
    findings = []
    actions = []

    # RHR assessment
    rhr = overview.get("avg_rhr")
    if rhr:
        if rhr < 55:
            findings.append(f"- **Resting heart rate ({rhr} bpm)**: Excellent. "
                          "This puts you in the top cardiovascular fitness tier.")
        elif rhr < 65:
            findings.append(f"- **Resting heart rate ({rhr} bpm)**: Good. "
                          "Room to improve with more aerobic base training.")
            actions.append("- Increase Zone 2 cardio (easy pace, can hold conversation) to 3+ sessions/week")
        else:
            findings.append(f"- **Resting heart rate ({rhr} bpm)**: Elevated. "
                          "Associated with higher cardiovascular risk.")
            actions.append("- Priority: add 30 min daily walking and 2-3 easy cardio sessions/week")

    # HRV assessment
    hrv = overview.get("avg_hrv")
    if hrv:
        if hrv > 40:
            findings.append(f"- **HRV ({hrv} ms)**: Good autonomic balance and stress resilience.")
        elif hrv > 25:
            findings.append(f"- **HRV ({hrv} ms)**: Moderate. Could improve with better sleep "
                          "and stress management.")
            actions.append("- Focus on sleep consistency (same bed/wake time daily) to improve HRV")
            actions.append("- Consider breathing exercises or meditation (even 5 min/day raises HRV)")
        else:
            findings.append(f"- **HRV ({hrv} ms)**: Low. Suggests chronic stress, poor recovery, "
                          "or overtraining.")
            actions.append("- Reduce training intensity for 1-2 weeks and prioritize sleep")
            actions.append("- Check for stressors: work, poor sleep, alcohol, illness")

    # VO2max assessment
    vo2 = overview.get("avg_vo2max")
    if vo2:
        if vo2 > 45:
            findings.append(f"- **VO2max ({vo2} mL/kg/min)**: Excellent cardiorespiratory fitness. "
                          "Strong longevity predictor.")
        elif vo2 > 35:
            findings.append(f"- **VO2max ({vo2} mL/kg/min)**: Above average. "
                          "Aiming for 45+ would significantly reduce mortality risk.")
            actions.append("- Add 1-2 HIIT sessions/week (4x4 min at 90% max HR) to push VO2max up")
        else:
            findings.append(f"- **VO2max ({vo2} mL/kg/min)**: Below average. "
                          "This is your highest-leverage improvement area for longevity.")
            actions.append("- Start with 3x/week Zone 2 cardio (30-60 min at conversational pace)")
            actions.append("- Every 1 mL/kg/min improvement in VO2max reduces mortality risk measurably")

    # Steps assessment
    steps = overview.get("avg_steps")
    if steps:
        if steps >= 10000:
            findings.append(f"- **Daily steps ({int(steps):,})**: Excellent daily movement. "
                          "Well above longevity thresholds.")
        elif steps >= 7000:
            findings.append(f"- **Daily steps ({int(steps):,})**: Good. "
                          "Meets the longevity minimum. Pushing to 10k+ adds more benefit.")
        else:
            findings.append(f"- **Daily steps ({int(steps):,})**: Below the 7,000 longevity threshold.")
            actions.append("- Add a 20-min morning or evening walk to bring steps above 7,000")

    # Sleep assessment
    sleep_h = overview.get("avg_sleep")
    if sleep_h:
        if 7 <= sleep_h <= 8:
            findings.append(f"- **Sleep ({sleep_h} h)**: Optimal for longevity.")
        elif 6 <= sleep_h < 7:
            findings.append(f"- **Sleep ({sleep_h} h)**: Slightly short. "
                          "7-8 hours is the sweet spot.")
            actions.append("- Move bedtime 30 min earlier to reach the 7-8h optimal window")
        elif sleep_h < 6:
            findings.append(f"- **Sleep ({sleep_h} h)**: Short sleep is a significant "
                          "mortality risk factor.")
            actions.append("- Sleep is your highest priority fix — aim for 7h minimum")
            actions.append("- Set a non-negotiable 'wind down' alarm 8h before your wake time")
        else:
            findings.append(f"- **Sleep ({sleep_h} h)**: Adequate duration.")

    sections.append("### Key findings\n")
    sections.append("\n".join(findings))
    if actions:
        sections.append("\n### Top action items\n")
        sections.append("\n".join(actions))

    # ── Trend Analysis (recent vs baseline) ──
    sections.append("\n\n## Trend Analysis: Last 30 Days vs Baseline\n")
    if recent_vs_bl:
        trend_lines = []
        for metric, bl_key, rc_key, unit, better in [
            ("Resting HR", "baseline_rhr", "recent_rhr", "bpm", "lower"),
            ("HRV", "baseline_hrv", "recent_hrv", "ms", "higher"),
            ("VO2max", "baseline_vo2max", "recent_vo2max", "mL/kg/min", "higher"),
            ("Steps", "baseline_steps", "recent_steps", "", "higher"),
            ("Sleep", "baseline_sleep", "recent_sleep", "h", "optimal"),
            ("Workout min/day", "baseline_workout_min", "recent_workout_min", "min", "higher"),
        ]:
            bl = recent_vs_bl.get(bl_key)
            rc = recent_vs_bl.get(rc_key)
            if bl and rc:
                delta = rc - bl
                if abs(delta) < 0.1:
                    arrow = "→"
                    assessment = "stable"
                elif (better == "higher" and delta > 0) or (better == "lower" and delta < 0):
                    arrow = "↑" if delta > 0 else "↓"
                    assessment = "**improving**"
                elif better == "optimal":
                    arrow = "↑" if delta > 0 else "↓"
                    assessment = "changed"
                else:
                    arrow = "↑" if delta > 0 else "↓"
                    assessment = "**declining**"
                bl_str = f"{int(bl):,}" if isinstance(bl, float) and bl > 100 else str(bl)
                rc_str = f"{int(rc):,}" if isinstance(rc, float) and rc > 100 else str(rc)
                trend_lines.append(
                    f"| {metric} | {bl_str} {unit} | {rc_str} {unit} | "
                    f"{arrow} {delta:+.1f} | {assessment} |"
                )

        sections.append("| Metric | Baseline | Last 30d | Change | Status |")
        sections.append("|--------|----------|----------|--------|--------|")
        sections.append("\n".join(trend_lines))

    # ── VO2max Deep Dive ──
    if vo2max_trend:
        sections.append("\n\n## VO2max Progression (Strongest Longevity Predictor)\n")
        early = vo2max_trend.get("early", {})
        recent = vo2max_trend.get("recent", {})
        if early and recent:
            e_val = early.get("avg_vo2max", 0)
            r_val = recent.get("avg_vo2max", 0)
            delta = r_val - e_val
            sections.append(f"- First 90 days average: **{e_val}** mL/kg/min")
            sections.append(f"- Last 90 days average: **{r_val}** mL/kg/min")
            sections.append(f"- Change: **{delta:+.1f}** mL/kg/min")
            if delta > 1:
                sections.append("\nYour VO2max is trending up — great work. "
                              "This is the single most impactful change for longevity.")
            elif delta < -1:
                sections.append("\nYour VO2max is declining. Consider adding more cardio, "
                              "especially Zone 2 (long, easy) and HIIT (short, intense) sessions.")
            else:
                sections.append("\nVO2max is stable. To push it higher, add 1-2 dedicated HIIT "
                              "sessions (4x4 min at 85-90% max HR with 3 min recovery).")

    # ── Sleep Deep Dive ──
    if sleep and sleep.get("days_with_sleep", 0) > 0:
        sections.append("\n\n## Sleep Analysis\n")
        total = sleep["days_with_sleep"]
        optimal = sleep.get("optimal_days", 0)
        short = sleep.get("short_sleep_days", 0)
        std = sleep.get("sleep_std", 0)
        sections.append(f"- Days tracked: {total}")
        sections.append(f"- Average: {sleep.get('avg_sleep', 'N/A')}h "
                       f"(range: {sleep.get('p25_sleep', '?')}-{sleep.get('p75_sleep', '?')}h)")
        sections.append(f"- Optimal nights (7-8h): **{optimal}** ({optimal/total*100:.0f}% of nights)")
        sections.append(f"- Short sleep nights (<6h): **{short}** ({short/total*100:.0f}% of nights)")
        sections.append(f"- Consistency (std dev): **{std}h**")

        if std and std > 1.0:
            sections.append("\n**Sleep consistency is irregular** (std dev > 1h). "
                          "Irregular sleep is an independent cardiovascular risk factor, "
                          "even when average duration is adequate.")
            sections.append("- Set a fixed wake time 7 days/week (yes, weekends too)")
            sections.append("- Limit weekend sleep-in to max 30 min difference")

    # ── Exercise Balance ──
    sections.append("\n\n## Exercise Balance\n")
    if workout:
        weekly = workout.get("weekly_avg_min", 0)
        pct = workout.get("workout_pct", 0)
        sections.append(f"- Weekly average: **{int(weekly)} min/week** "
                       f"(target: 150 min minimum, 300+ optimal)")
        sections.append(f"- Workout days: {pct}% of all days")

        if weekly < 150:
            sections.append("\n**Below WHO minimum of 150 min/week.** "
                          "This is a high-priority improvement area.")
        elif weekly >= 300:
            sections.append("\n**Exceeds optimal exercise volume.** "
                          "Focus shifts to quality, recovery, and variety.")

    if type_balance:
        sections.append("\n### Cardio vs Strength balance\n")
        cardio = type_balance.get("cardio", {})
        strength = type_balance.get("strength", {})
        flex = type_balance.get("flexibility", {})
        c_sess = cardio.get("sessions", 0)
        s_sess = strength.get("sessions", 0)
        f_sess = flex.get("sessions", 0)
        total_sess = c_sess + s_sess + f_sess or 1

        sections.append(f"| Type | Sessions | % of total | Minutes |")
        sections.append(f"|------|----------|-----------|---------|")
        for name, data in [("Cardio", cardio), ("Strength", strength), ("Flexibility", flex)]:
            sess = data.get("sessions", 0)
            mins = data.get("total_minutes", 0)
            sections.append(f"| {name} | {sess} | {sess/total_sess*100:.0f}% | {int(mins)} |")

        if s_sess == 0:
            sections.append("\n**No strength training detected.** This is a major gap. "
                          "Strength training 2-3x/week prevents sarcopenia (muscle loss), "
                          "preserves bone density, and improves insulin sensitivity.")
            sections.append("- Start with 2x/week full-body strength sessions (even 20-30 min)")
        elif s_sess < c_sess * 0.3:
            sections.append("\nStrength training is underrepresented. "
                          "People who do both cardio AND strength have 40% lower mortality "
                          "than either alone.")
            sections.append("- Aim for at least 2 strength sessions per week")

        if f_sess == 0:
            sections.append("\n*Consider adding mobility/flexibility work (yoga, stretching) "
                          "1-2x/week for joint health and injury prevention.*")

    # ── Workout → HRV Impact ──
    if hrv_impact:
        sections.append("\n\n## Which Workouts Help Your Recovery?\n")
        sections.append("Workout types ranked by next-day HRV change "
                       "(positive = HRV improves after that workout type):\n")
        sections.append("| Workout Type | Occurrences | Avg HRV Change (next day) |")
        sections.append("|-------------|-------------|--------------------------|")
        for row in hrv_impact[:8]:
            delta = row["avg_hrv_change"]
            emoji = "+" if delta > 0 else ""
            sections.append(f"| {row['type']} | {row['occurrences']} | "
                          f"{emoji}{delta} ms |")

        best = hrv_impact[0] if hrv_impact else None
        worst = hrv_impact[-1] if hrv_impact else None
        if best and worst:
            sections.append(f"\n**Best for recovery**: {best['type']} "
                          f"(HRV +{best['avg_hrv_change']} ms next day)")
            sections.append(f"**Most taxing**: {worst['type']} "
                          f"(HRV {worst['avg_hrv_change']} ms next day)")
            if worst["avg_hrv_change"] < -3:
                sections.append(f"\nAfter {worst['type']}, ensure adequate sleep "
                              "and consider a lighter training day the following day.")

    # ── Overtraining Signals ──
    if overtraining:
        sections.append("\n\n## Overtraining Risk Signals\n")
        sections.append(f"Found **{len(overtraining)} weeks** with high training load "
                       "(> 200 min) combined with low HRV (< 30 ms):\n")
        sections.append("| Week | Training Min | Avg HRV | Avg RHR |")
        sections.append("|------|-------------|---------|---------|")
        for row in overtraining:
            sections.append(f"| {row['week']} | {int(row['training_min'])} | "
                          f"{row['avg_hrv']} | {row['avg_rhr']} |")
        sections.append("\nThese weeks suggest your body wasn't recovering from the training load. "
                       "When HRV is suppressed, your autonomic nervous system is under stress.")
        sections.append("- In future high-training weeks, monitor HRV daily")
        sections.append("- If HRV drops below your baseline for 3+ consecutive days, take a rest day")

    # ── Step Activity ──
    if step_dist and step_dist.get("total_days", 0) > 0:
        sections.append("\n\n## Daily Movement (Steps)\n")
        total = step_dist["total_days"]
        d10k = step_dist.get("days_10k", 0)
        d7k = step_dist.get("days_7k", 0)
        sed = step_dist.get("sedentary_days", 0)
        sections.append(f"- Days over 10,000 steps: **{d10k}** ({d10k/total*100:.0f}%)")
        sections.append(f"- Days 7,000-10,000: **{d7k}** ({d7k/total*100:.0f}%)")
        sections.append(f"- Sedentary days (<5,000): **{sed}** ({sed/total*100:.0f}%)")

        if sed / total > 0.2:
            sections.append(f"\n**{sed/total*100:.0f}% of days are sedentary.** "
                          "Even a 15-min walk can move a day from sedentary to moderate.")

    # ── Longevity Score ──
    if best_days and best_days.get("green_days", 0) > 0:
        sections.append("\n\n## Longevity Score (Compound Metric)\n")
        sections.append("Days scoring 4+ out of 5 on: HRV above median, RHR below median, "
                       "7+ hours sleep, 8,000+ steps, any workout.\n")
        sections.append(f"- Green days (score 4-5): **{best_days['green_days']}** "
                       f"out of {overview.get('days', '?')} "
                       f"({best_days['green_days']/max(overview.get('days',1),1)*100:.0f}%)")

    # ── Disclaimer ──
    sections.append("\n\n---\n")
    sections.append("*This analysis is based on consumer wearable data and population-level "
                   "longevity research. It is not medical advice. Consult a healthcare provider "
                   "for personal health decisions. Correlation in the data does not prove causation.*")

    return "\n".join(sections)


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Generate longevity health analysis from Neo4j")
    parser.add_argument("--months", "-m", type=int, help="Only analyze last N months")
    parser.add_argument("--output", "-o", help="Save report to file (default: print to stdout)")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    load_dotenv(project_root / ".env")

    uri = os.environ.get("NEO4J_URI")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")
    if not uri or not password:
        print("Error: Set NEO4J_URI and NEO4J_PASSWORD in .env")
        sys.exit(1)

    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()

    start_date = None
    if args.months:
        start_date = (date.today() - timedelta(days=args.months * 30)).isoformat()

    log.info("Querying health data from Neo4j...")
    with driver.session() as session:
        overview = query_overview(session, start_date)
        recent_vs_bl = query_recent_vs_baseline(session)
        vo2max_trend = query_vo2max_trend(session)
        sleep = query_sleep_analysis(session, start_date)
        workout = query_workout_analysis(session, start_date)
        type_balance = query_workout_type_balance(session, start_date)
        overtraining = query_overtraining_signals(session)
        hrv_impact = query_workout_hrv_impact(session)
        best_days = query_best_days(session)
        step_dist = query_step_distribution(session, start_date)

    driver.close()

    log.info("Generating report...")
    report = generate_report(overview, recent_vs_bl, vo2max_trend, sleep, workout,
                            type_balance, overtraining, hrv_impact, best_days,
                            step_dist, start_date)

    if args.output:
        out_path = project_root / args.output
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report)
        print(f"Report saved to: {out_path}")
    else:
        print(report)


if __name__ == "__main__":
    main()
