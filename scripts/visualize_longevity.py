#!/usr/bin/env python3
"""
visualize_longevity.py — Generate longevity trend charts from Neo4j health graph

Produces a multi-panel PNG dashboard with key longevity biomarkers:
  - Resting Heart Rate trend
  - HRV (Heart Rate Variability) trend
  - VO2max progression
  - Daily steps
  - Sleep duration
  - Weekly workout volume
  - Longevity score heatmap
  - Monthly composite dashboard

Usage:
  python scripts/visualize_longevity.py                    # all time
  python scripts/visualize_longevity.py --months 6         # last 6 months
  python scripts/visualize_longevity.py --output charts/   # custom output dir
"""

import os
import sys
import argparse
import logging
from datetime import date, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from neo4j import GraphDatabase

log = logging.getLogger(__name__)

# ── Style ──────────────────────────────────────────────────────────────────

plt.rcParams.update({
    "figure.facecolor": "#0e1117",
    "axes.facecolor": "#0e1117",
    "axes.edgecolor": "#333333",
    "axes.labelcolor": "#cccccc",
    "text.color": "#cccccc",
    "xtick.color": "#888888",
    "ytick.color": "#888888",
    "grid.color": "#222222",
    "grid.alpha": 0.6,
    "font.size": 10,
    "axes.titlesize": 13,
    "figure.titlesize": 16,
})

COLORS = {
    "rhr": "#ef4444",
    "hrv": "#22c55e",
    "vo2max": "#3b82f6",
    "steps": "#f59e0b",
    "sleep": "#8b5cf6",
    "workout": "#06b6d4",
    "energy": "#f97316",
    "spo2": "#ec4899",
    "score": "#10b981",
    "trend": "#ffffff",
    "zone_good": "#22c55e33",
    "zone_warn": "#f59e0b33",
    "zone_bad": "#ef444433",
}


# ── Neo4j queries ──────────────────────────────────────────────────────────

def query_weekly_trends(session, start_date=None):
    where = f"WHERE d.date >= date('{start_date}')" if start_date else ""
    result = session.run(f"""
        MATCH (d:Day)-[:PART_OF]->(w:Week)
        MATCH (d)-[:HAS_SUMMARY]->(s:DailySummary)
        {where}
        RETURN w.iso AS week,
               w.start_date AS week_start,
               round(avg(s.resting_heart_rate), 1) AS avg_rhr,
               round(avg(s.hrv_mean), 1) AS avg_hrv,
               round(avg(s.vo2max), 1) AS avg_vo2max,
               round(avg(s.total_steps), 0) AS avg_steps,
               round(avg(s.sleep_hours), 1) AS avg_sleep,
               round(sum(s.workout_minutes), 0) AS workout_min,
               sum(s.workout_count) AS workout_count,
               round(avg(s.active_energy_kcal), 0) AS avg_active_cal,
               round(avg(s.avg_blood_oxygen), 1) AS avg_spo2,
               count(*) AS days
        ORDER BY w.iso
    """)
    return pd.DataFrame([dict(r) for r in result])


def query_daily_data(session, start_date=None):
    where = f"WHERE d.date >= date('{start_date}')" if start_date else ""
    result = session.run(f"""
        MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
        {where}
        RETURN d.date AS date,
               d.day_of_week AS day_of_week,
               s.resting_heart_rate AS rhr,
               s.hrv_mean AS hrv,
               s.vo2max AS vo2max,
               s.total_steps AS steps,
               s.sleep_hours AS sleep,
               s.workout_count AS workouts,
               s.workout_minutes AS workout_min,
               s.active_energy_kcal AS active_cal,
               s.avg_blood_oxygen AS spo2
        ORDER BY d.date
    """)
    df = pd.DataFrame([dict(r) for r in result])
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"].apply(str))
    return df


def query_monthly_dashboard(session, start_date=None):
    where = f"WHERE d.date >= date('{start_date}')" if start_date else ""
    result = session.run(f"""
        MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
        {where}
        WITH d.date.year AS year, d.date.month AS month, s
        RETURN year + '-' + right('0' + toString(month), 2) AS month,
               round(avg(s.resting_heart_rate), 1) AS avg_rhr,
               round(avg(s.hrv_mean), 1) AS avg_hrv,
               round(avg(s.vo2max), 1) AS avg_vo2max,
               round(avg(s.sleep_hours), 1) AS avg_sleep,
               round(avg(s.total_steps), 0) AS avg_steps,
               sum(s.workout_count) AS total_workouts,
               round(sum(s.workout_minutes), 0) AS total_workout_min,
               count(*) AS days
        ORDER BY month
    """)
    return pd.DataFrame([dict(r) for r in result])


def query_workout_types(session, start_date=None):
    where = f"WHERE d.date >= date('{start_date}')" if start_date else ""
    result = session.run(f"""
        MATCH (w:Workout)-[:ON_DAY]->(d:Day)
        {where}
        RETURN w.activity_type AS type,
               count(*) AS count,
               round(avg(w.duration_min), 1) AS avg_duration,
               round(sum(w.total_energy_burned), 0) AS total_energy
        ORDER BY count DESC
        LIMIT 10
    """)
    return pd.DataFrame([dict(r) for r in result])


# ── Chart helpers ──────────────────────────────────────────────────────────

def _add_trend_line(ax, x, y, color=COLORS["trend"], alpha=0.4):
    """Add a rolling average trend line."""
    if len(y) < 8:
        return
    window = max(4, len(y) // 12)
    trend = pd.Series(y).rolling(window=window, center=True, min_periods=2).mean()
    ax.plot(x, trend, color=color, linewidth=2.5, alpha=alpha, zorder=5)


def _add_zone(ax, ymin, ymax, color):
    """Add a horizontal zone band."""
    ax.axhspan(ymin, ymax, color=color, zorder=0)


def _format_date_axis(ax):
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")


# ── Main charts ────────────────────────────────────────────────────────────

def plot_rhr_trend(ax, df):
    """Resting heart rate with longevity zones."""
    data = df.dropna(subset=["rhr"])
    if data.empty:
        ax.text(0.5, 0.5, "No RHR data", transform=ax.transAxes, ha="center", color="#666")
        return
    ax.scatter(data["date"], data["rhr"], s=4, alpha=0.3, color=COLORS["rhr"], zorder=3)
    _add_trend_line(ax, data["date"], data["rhr"], color=COLORS["rhr"])
    _add_zone(ax, 40, 55, COLORS["zone_good"])    # excellent
    _add_zone(ax, 55, 65, COLORS["zone_warn"])    # good
    _add_zone(ax, 65, 80, COLORS["zone_bad"])     # elevated
    ax.set_ylabel("BPM")
    ax.set_title("Resting Heart Rate (lower = better)")
    ax.set_ylim(max(35, data["rhr"].min() - 5), min(90, data["rhr"].max() + 5))
    _format_date_axis(ax)
    ax.grid(True, axis="y", linewidth=0.5)


def plot_hrv_trend(ax, df):
    """HRV trend with longevity zones."""
    data = df.dropna(subset=["hrv"])
    if data.empty:
        ax.text(0.5, 0.5, "No HRV data", transform=ax.transAxes, ha="center", color="#666")
        return
    ax.scatter(data["date"], data["hrv"], s=4, alpha=0.3, color=COLORS["hrv"], zorder=3)
    _add_trend_line(ax, data["date"], data["hrv"], color=COLORS["hrv"])
    _add_zone(ax, 40, 120, COLORS["zone_good"])   # good
    _add_zone(ax, 25, 40, COLORS["zone_warn"])    # moderate
    _add_zone(ax, 0, 25, COLORS["zone_bad"])      # low
    ax.set_ylabel("ms (SDNN)")
    ax.set_title("Heart Rate Variability (higher = better)")
    ax.set_ylim(max(0, data["hrv"].min() - 10), data["hrv"].max() + 10)
    _format_date_axis(ax)
    ax.grid(True, axis="y", linewidth=0.5)


def plot_vo2max_trend(ax, df):
    """VO2max progression — the #1 longevity predictor."""
    data = df.dropna(subset=["vo2max"])
    if data.empty:
        ax.text(0.5, 0.5, "No VO2max data", transform=ax.transAxes, ha="center", color="#666")
        return
    ax.scatter(data["date"], data["vo2max"], s=8, alpha=0.5, color=COLORS["vo2max"], zorder=3)
    _add_trend_line(ax, data["date"], data["vo2max"], color=COLORS["vo2max"])
    # Fitness categories (male, approximate)
    _add_zone(ax, 45, 60, COLORS["zone_good"])    # excellent
    _add_zone(ax, 35, 45, COLORS["zone_warn"])    # good
    _add_zone(ax, 20, 35, COLORS["zone_bad"])     # below average
    ax.set_ylabel("mL/kg/min")
    ax.set_title("VO2max — #1 Longevity Predictor (higher = better)")
    ax.set_ylim(max(20, data["vo2max"].min() - 3), data["vo2max"].max() + 3)
    _format_date_axis(ax)
    ax.grid(True, axis="y", linewidth=0.5)


def plot_steps_trend(ax, df):
    """Daily steps with target zones."""
    data = df.dropna(subset=["steps"])
    if data.empty:
        ax.text(0.5, 0.5, "No step data", transform=ax.transAxes, ha="center", color="#666")
        return
    ax.bar(data["date"], data["steps"], width=1, alpha=0.4, color=COLORS["steps"], zorder=3)
    _add_trend_line(ax, data["date"], data["steps"], color=COLORS["steps"])
    ax.axhline(y=10000, color=COLORS["score"], linestyle="--", linewidth=1, alpha=0.5, label="10k target")
    ax.axhline(y=7000, color=COLORS["steps"], linestyle=":", linewidth=1, alpha=0.4, label="7k minimum")
    ax.set_ylabel("Steps")
    ax.set_title("Daily Steps (7k-10k+ optimal for longevity)")
    _format_date_axis(ax)
    ax.legend(loc="upper left", fontsize=8, framealpha=0.3)
    ax.grid(True, axis="y", linewidth=0.5)


def plot_sleep_trend(ax, df):
    """Sleep duration with optimal zone."""
    data = df.dropna(subset=["sleep"])
    if data.empty:
        ax.text(0.5, 0.5, "No sleep data", transform=ax.transAxes, ha="center", color="#666")
        return
    ax.bar(data["date"], data["sleep"], width=1, alpha=0.5, color=COLORS["sleep"], zorder=3)
    _add_trend_line(ax, data["date"], data["sleep"], color=COLORS["sleep"])
    _add_zone(ax, 7, 9, COLORS["zone_good"])  # optimal
    ax.set_ylabel("Hours")
    ax.set_title("Sleep Duration (7-8h optimal zone)")
    ax.set_ylim(0, min(12, data["sleep"].max() + 1))
    _format_date_axis(ax)
    ax.grid(True, axis="y", linewidth=0.5)


def plot_workout_volume(ax, monthly):
    """Monthly workout minutes as bar chart."""
    if monthly.empty or "total_workout_min" not in monthly.columns:
        ax.text(0.5, 0.5, "No workout data", transform=ax.transAxes, ha="center", color="#666")
        return
    data = monthly.dropna(subset=["total_workout_min"])
    x = range(len(data))
    bars = ax.bar(x, data["total_workout_min"], alpha=0.7, color=COLORS["workout"], zorder=3)
    # Color bars above 600 min/month (150/week) green
    for i, bar in enumerate(bars):
        if data.iloc[i]["total_workout_min"] >= 600:
            bar.set_color(COLORS["score"])
    ax.axhline(y=600, color=COLORS["score"], linestyle="--", linewidth=1, alpha=0.5,
               label="150 min/week target")
    ax.set_xticks(x)
    ax.set_xticklabels(data["month"], rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Minutes")
    ax.set_title("Monthly Workout Volume (600+ min = 150/week target)")
    ax.legend(loc="upper left", fontsize=8, framealpha=0.3)
    ax.grid(True, axis="y", linewidth=0.5)


def plot_workout_types(ax, workout_df):
    """Workout type distribution as horizontal bar."""
    if workout_df.empty:
        ax.text(0.5, 0.5, "No workout data", transform=ax.transAxes, ha="center", color="#666")
        return
    data = workout_df.head(8)
    colors = plt.cm.Set2(np.linspace(0, 1, len(data)))
    bars = ax.barh(range(len(data)), data["count"], color=colors, alpha=0.8)
    ax.set_yticks(range(len(data)))
    ax.set_yticklabels(data["type"], fontsize=9)
    ax.set_xlabel("Count")
    ax.set_title("Workout Type Distribution")
    ax.invert_yaxis()
    # Add count labels
    for bar, count in zip(bars, data["count"]):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                str(int(count)), va="center", fontsize=8, color="#cccccc")
    ax.grid(True, axis="x", linewidth=0.5)


def plot_monthly_composite(ax, monthly):
    """Monthly composite showing normalized trends of key metrics."""
    if monthly.empty:
        return
    metrics = {
        "RHR (inverted)": ("avg_rhr", True, COLORS["rhr"]),
        "HRV": ("avg_hrv", False, COLORS["hrv"]),
        "VO2max": ("avg_vo2max", False, COLORS["vo2max"]),
        "Steps": ("avg_steps", False, COLORS["steps"]),
    }
    x = range(len(monthly))
    for label, (col, invert, color) in metrics.items():
        if col not in monthly.columns:
            continue
        vals = monthly[col].astype(float)
        if vals.isna().all():
            continue
        # Normalize to 0-1
        vmin, vmax = vals.min(), vals.max()
        if vmax == vmin:
            continue
        norm = (vals - vmin) / (vmax - vmin)
        if invert:
            norm = 1 - norm
        ax.plot(x, norm, label=label, color=color, linewidth=2, alpha=0.8)
    ax.set_xticks(x[::max(1, len(x) // 12)])
    ax.set_xticklabels([monthly.iloc[i]["month"] for i in x[::max(1, len(x) // 12)]],
                       rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Normalized (higher = better)")
    ax.set_title("Monthly Longevity Composite (all metrics, higher = better)")
    ax.legend(loc="lower left", fontsize=8, framealpha=0.3, ncol=2)
    ax.set_ylim(-0.05, 1.05)
    ax.grid(True, axis="y", linewidth=0.5)


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Generate longevity trend charts from Neo4j")
    parser.add_argument("--months", "-m", type=int, help="Only show last N months")
    parser.add_argument("--output", "-o", default="data/charts",
                        help="Output directory (default: data/charts)")
    args = parser.parse_args()

    # Connect
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
    log.info(f"Connected to Neo4j at {uri}")

    start_date = None
    if args.months:
        start_date = (date.today() - timedelta(days=args.months * 30)).isoformat()
        log.info(f"Filtering to last {args.months} months (from {start_date})")

    # Query data
    with driver.session() as session:
        log.info("Querying daily data...")
        daily = query_daily_data(session, start_date)
        log.info(f"  {len(daily)} days")

        log.info("Querying monthly data...")
        monthly = query_monthly_dashboard(session, start_date)
        log.info(f"  {len(monthly)} months")

        log.info("Querying workout types...")
        workout_types = query_workout_types(session, start_date)

    driver.close()

    if daily.empty:
        print("No data found in Neo4j. Run the import pipeline first.")
        sys.exit(1)

    # ── Generate charts ────────────────────────────────────────────────────

    out_dir = project_root / args.output
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Main longevity dashboard (8-panel)
    log.info("Generating longevity dashboard...")
    fig, axes = plt.subplots(4, 2, figsize=(20, 22))
    fig.suptitle("Longevity Health Dashboard", fontsize=20, fontweight="bold", y=0.98)

    plot_rhr_trend(axes[0, 0], daily)
    plot_hrv_trend(axes[0, 1], daily)
    plot_vo2max_trend(axes[1, 0], daily)
    plot_steps_trend(axes[1, 1], daily)
    plot_sleep_trend(axes[2, 0], daily)
    plot_workout_volume(axes[2, 1], monthly)
    plot_workout_types(axes[3, 0], workout_types)
    plot_monthly_composite(axes[3, 1], monthly)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    dashboard_path = out_dir / "longevity_dashboard.png"
    fig.savefig(dashboard_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info(f"  Saved: {dashboard_path}")

    # 2. Individual high-res charts
    individual_charts = [
        ("rhr_trend.png", plot_rhr_trend, "Resting Heart Rate"),
        ("hrv_trend.png", plot_hrv_trend, "Heart Rate Variability"),
        ("vo2max_trend.png", plot_vo2max_trend, "VO2max"),
        ("steps_trend.png", plot_steps_trend, "Daily Steps"),
        ("sleep_trend.png", plot_sleep_trend, "Sleep Duration"),
    ]

    for filename, plot_fn, title in individual_charts:
        fig, ax = plt.subplots(figsize=(14, 5))
        plot_fn(ax, daily)
        plt.tight_layout()
        path = out_dir / filename
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        log.info(f"  Saved: {path}")

    # 3. Workout volume chart
    fig, ax = plt.subplots(figsize=(14, 5))
    plot_workout_volume(ax, monthly)
    plt.tight_layout()
    fig.savefig(out_dir / "workout_volume.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 4. Composite trend
    fig, ax = plt.subplots(figsize=(14, 5))
    plot_monthly_composite(ax, monthly)
    plt.tight_layout()
    fig.savefig(out_dir / "composite_trend.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(f"\nCharts saved to: {out_dir}/")
    print(f"  longevity_dashboard.png  (8-panel overview)")
    for fn, _, _ in individual_charts:
        print(f"  {fn}")
    print(f"  workout_volume.png")
    print(f"  composite_trend.png")


if __name__ == "__main__":
    main()
