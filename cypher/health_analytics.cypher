// ============================================================
//  Health analytics — 20 queries for anomaly detection,
//  pattern discovery, and improvement, against the HealthGraph
//  schema (:DailySummary, :SleepSession, :Workout, :Day, :Week).
//
//  Layout:
//    A. Illness / sickness detection  (Q1-Q5)
//    B. Stress / overtraining         (Q6-Q10)
//    C. Pattern discovery             (Q11-Q15)  — Q11,Q12,Q13,Q14,Q15 are GDS recipes
//    D. Improvement / streaks         (Q16-Q19) + predictive (Q20 = GDS)
//
//  All queries anchor on the latest date in the data, so they
//  work even if the export is a few weeks stale.
//
//  See docs/HEALTH_ANALYTICS.md for what each detects + when to use.
// ============================================================


// =====================================================
//  A. ILLNESS / SICKNESS DETECTION
// =====================================================

// Q1: Illness signature days
//   HRV crash + RHR spike + respiratory rate elevated, all vs 30-day baseline.
//   This is the classic acute-illness pattern (autonomic response to infection).
MATCH (s:DailySummary)
WHERE s.hrv_mean IS NOT NULL AND s.resting_heart_rate IS NOT NULL
  AND s.avg_respiratory_rate IS NOT NULL
WITH s
MATCH (b:DailySummary)
WHERE b.date >= s.date - duration({days:30}) AND b.date < s.date
  AND b.hrv_mean IS NOT NULL AND b.resting_heart_rate IS NOT NULL
  AND b.avg_respiratory_rate IS NOT NULL
WITH s, collect(b.hrv_mean) AS hb, collect(b.resting_heart_rate) AS rb, collect(b.avg_respiratory_rate) AS rrb
WHERE size(hb) >= 14
WITH s, hb, rb, rrb,
     reduce(t=0.0,x IN hb|t+x)/size(hb) AS hmu,
     reduce(t=0.0,x IN rb|t+x)/size(rb) AS rmu,
     reduce(t=0.0,x IN rrb|t+x)/size(rrb) AS rrmu
WITH s, hb, rb, rrb, hmu, rmu, rrmu,
     sqrt(reduce(t=0.0,x IN hb|t+(x-hmu)*(x-hmu))/size(hb)) AS hsd,
     sqrt(reduce(t=0.0,x IN rb|t+(x-rmu)*(x-rmu))/size(rb)) AS rsd,
     sqrt(reduce(t=0.0,x IN rrb|t+(x-rrmu)*(x-rrmu))/size(rrb)) AS rrsd
WITH s,
     CASE WHEN hsd>0 THEN (s.hrv_mean-hmu)/hsd ELSE 0 END AS hz,
     CASE WHEN rsd>0 THEN (s.resting_heart_rate-rmu)/rsd ELSE 0 END AS rz,
     CASE WHEN rrsd>0 THEN (s.avg_respiratory_rate-rrmu)/rrsd ELSE 0 END AS rrz
WHERE hz < -1.5 AND rz > 1.0 AND rrz > 0.5
RETURN s.date AS date,
       round(hz*10)/10.0 AS `HRV z`,
       round(rz*10)/10.0 AS `RHR z`,
       round(rrz*10)/10.0 AS `RespRate z`,
       round(s.hrv_mean*10)/10.0 AS `HRV`,
       round(s.resting_heart_rate) AS `RHR`,
       round(s.avg_respiratory_rate*10)/10.0 AS `RespRate`
ORDER BY date DESC;


// Q2: Multi-day illness episodes
//   Group consecutive illness-signature days (≤2 day gap) into episodes.
MATCH (s:DailySummary)
WHERE s.hrv_mean IS NOT NULL AND s.resting_heart_rate IS NOT NULL
WITH s
MATCH (b:DailySummary)
WHERE b.date >= s.date - duration({days:30}) AND b.date < s.date
  AND b.hrv_mean IS NOT NULL AND b.resting_heart_rate IS NOT NULL
WITH s, collect(b.hrv_mean) AS hb, collect(b.resting_heart_rate) AS rb
WHERE size(hb) >= 14
WITH s, hb, rb,
     reduce(t=0.0,x IN hb|t+x)/size(hb) AS hmu,
     reduce(t=0.0,x IN rb|t+x)/size(rb) AS rmu
WITH s, hb, rb, hmu, rmu,
     sqrt(reduce(t=0.0,x IN hb|t+(x-hmu)*(x-hmu))/size(hb)) AS hsd,
     sqrt(reduce(t=0.0,x IN rb|t+(x-rmu)*(x-rmu))/size(rb)) AS rsd
WITH s, CASE WHEN hsd>0 THEN (s.hrv_mean-hmu)/hsd ELSE 0 END AS hz,
        CASE WHEN rsd>0 THEN (s.resting_heart_rate-rmu)/rsd ELSE 0 END AS rz
WHERE hz < -1.5 AND rz > 1.0
WITH collect({date: s.date, hz: hz, rz: rz}) AS bad ORDER BY size(bad)
UNWIND range(0, size(bad)-1) AS i
WITH bad, i, bad[i] AS cur
WITH bad, i, cur,
     CASE WHEN i=0 OR duration.inDays(bad[i-1].date, cur.date).days > 3 THEN 1 ELSE 0 END AS new_ep
WITH bad, i, cur, new_ep,
     reduce(s=0, j IN range(0, i) | s + (CASE WHEN j=0 OR duration.inDays(bad[j-1].date, bad[j].date).days > 3 THEN 1 ELSE 0 END)) AS ep_id
WITH ep_id, collect(cur.date) AS dates
RETURN ep_id AS `Episode #`,
       head(dates) AS `Start`,
       last(dates) AS `End`,
       duration.inDays(head(dates), last(dates)).days + 1 AS `Days`,
       size(dates) AS `Signature days`
ORDER BY ep_id;


// Q3: Pre-illness early warning
//   Days where resp-rate spiked >1σ but HRV and RHR still in normal range —
//   the canary signal before a full illness onset.
MATCH (s:DailySummary)
WHERE s.avg_respiratory_rate IS NOT NULL
WITH s
MATCH (b:DailySummary)
WHERE b.date >= s.date - duration({days:30}) AND b.date < s.date
  AND b.avg_respiratory_rate IS NOT NULL
WITH s, collect(b.avg_respiratory_rate) AS rrb
WHERE size(rrb) >= 14
WITH s, rrb, reduce(t=0.0,x IN rrb|t+x)/size(rrb) AS rrmu
WITH s, rrb, rrmu, sqrt(reduce(t=0.0,x IN rrb|t+(x-rrmu)*(x-rrmu))/size(rrb)) AS rrsd
WITH s, CASE WHEN rrsd>0 THEN (s.avg_respiratory_rate-rrmu)/rrsd ELSE 0 END AS rrz
WHERE rrz > 1.5
RETURN s.date AS date,
       round(rrz*10)/10.0 AS `RespRate z`,
       round(s.avg_respiratory_rate*10)/10.0 AS `RespRate`,
       round(s.hrv_mean*10)/10.0 AS `HRV`,
       round(s.resting_heart_rate) AS `RHR`
ORDER BY rrz DESC LIMIT 20;


// Q4: Recovery duration after illness
//   For each illness-signature day, find the next day where HRV recovers
//   to within 0.5σ of the 30-day baseline.
MATCH (m:DailySummary) WITH max(m.date) AS anchor
MATCH (sick:DailySummary)
WHERE sick.hrv_mean IS NOT NULL AND sick.resting_heart_rate IS NOT NULL
  AND sick.date >= anchor - duration({days:365})
WITH sick
MATCH (b:DailySummary)
WHERE b.date >= sick.date - duration({days:30}) AND b.date < sick.date
  AND b.hrv_mean IS NOT NULL
WITH sick, collect(b.hrv_mean) AS hb WHERE size(hb)>=14
WITH sick, hb,
     reduce(t=0.0,x IN hb|t+x)/size(hb) AS hmu
WITH sick, hb, hmu,
     sqrt(reduce(t=0.0,x IN hb|t+(x-hmu)*(x-hmu))/size(hb)) AS hsd
WITH sick, hmu, hsd,
     CASE WHEN hsd>0 THEN (sick.hrv_mean-hmu)/hsd ELSE 0 END AS hz
WHERE hz < -1.5
OPTIONAL MATCH (rec:DailySummary)
WHERE rec.date > sick.date AND rec.date < sick.date + duration({days:21})
  AND rec.hrv_mean IS NOT NULL AND rec.hrv_mean >= hmu - 0.5*hsd
WITH sick, hmu, min(rec.date) AS recovered
RETURN sick.date AS `Bad day`,
       recovered AS `Recovered on`,
       CASE WHEN recovered IS NULL THEN NULL
            ELSE duration.inDays(sick.date, recovered).days END AS `Days to recover`,
       round(hmu*10)/10.0 AS `Baseline HRV`
ORDER BY sick.date DESC LIMIT 20;


// Q5: Post-illness training mistakes
//   Hard workouts (>60 min, > 500 active kcal) in the 7 days following an illness day.
MATCH (sick:DailySummary)
WHERE sick.hrv_mean IS NOT NULL AND sick.resting_heart_rate IS NOT NULL
WITH sick
MATCH (b:DailySummary)
WHERE b.date >= sick.date - duration({days:30}) AND b.date < sick.date
  AND b.hrv_mean IS NOT NULL
WITH sick, collect(b.hrv_mean) AS hb WHERE size(hb)>=14
WITH sick, reduce(t=0.0,x IN hb|t+x)/size(hb) AS hmu, hb
WITH sick, hmu, sqrt(reduce(t=0.0,x IN hb|t+(x-hmu)*(x-hmu))/size(hb)) AS hsd
WHERE hsd>0 AND (sick.hrv_mean-hmu)/hsd < -1.5
MATCH (w:Workout)-[:ON_DAY]->(d:Day)
WHERE d.date > sick.date AND d.date <= sick.date + duration({days:7})
  AND w.duration_min > 60
RETURN sick.date AS `Illness day`,
       d.date AS `Workout date`,
       duration.inDays(sick.date, d.date).days AS `Days post-illness`,
       w.activity_type AS `Activity`,
       round(w.duration_min) AS `Duration (min)`
ORDER BY sick.date DESC, d.date LIMIT 30;


// =====================================================
//  B. STRESS / OVERTRAINING DETECTION
// =====================================================

// Q6: Chronic stress streaks
//   ≥5 consecutive days where HRV is below 30-day baseline AND sleep < 7h.
MATCH (s:DailySummary)
WHERE s.hrv_mean IS NOT NULL AND s.sleep_hours IS NOT NULL
WITH s
MATCH (b:DailySummary)
WHERE b.date >= s.date - duration({days:30}) AND b.date < s.date
  AND b.hrv_mean IS NOT NULL
WITH s, collect(b.hrv_mean) AS hb WHERE size(hb)>=14
WITH s, reduce(t=0.0,x IN hb|t+x)/size(hb) AS hmu
WHERE s.hrv_mean < hmu AND s.sleep_hours < 7.0
WITH collect(s.date) AS bad_dates ORDER BY size(bad_dates)
UNWIND range(0, size(bad_dates)-1) AS i
WITH bad_dates, i,
     reduce(s=0, j IN range(0,i) | s + CASE WHEN j=0 OR duration.inDays(bad_dates[j-1], bad_dates[j]).days > 1 THEN 1 ELSE 0 END) AS ep
WITH ep, collect(bad_dates[i]) AS dates
WHERE size(dates) >= 5
RETURN ep AS `Streak #`,
       head(dates) AS `Start`, last(dates) AS `End`,
       size(dates) AS `Days`
ORDER BY size(dates) DESC LIMIT 15;


// Q7: HRV regression streaks
//   ≥3 consecutive days of HRV decline. Computed via 3-day window walk.
MATCH (s:DailySummary) WHERE s.hrv_mean IS NOT NULL
WITH s ORDER BY s.date
WITH collect(s) AS days
UNWIND range(0, size(days)-1) AS i
WITH days, i,
     [j IN range(0, 6) WHERE i+j < size(days) AND
       (j=0 OR (duration.inDays(days[i+j-1].date, days[i+j].date).days = 1
                AND days[i+j].hrv_mean < days[i+j-1].hrv_mean))
       | days[i+j]] AS run
WHERE size(run) >= 3
WITH days, i, run
WHERE i = 0 OR NOT (duration.inDays(days[i-1].date, run[0].date).days = 1
                    AND run[0].hrv_mean < days[i-1].hrv_mean)
RETURN head(run).date AS `Streak start`,
       last(run).date AS `Streak end`,
       round(head(run).hrv_mean*10)/10.0 AS `HRV start`,
       round(last(run).hrv_mean*10)/10.0 AS `HRV end`,
       size(run) AS `Days`
ORDER BY `Days` DESC LIMIT 15;


// Q8: Overtraining flag — 7-day rolling load up AND HRV trending down
//   Compare each week's avg HRV and total workout minutes vs the prior week.
MATCH (s:DailySummary)
WHERE s.hrv_mean IS NOT NULL AND s.workout_minutes IS NOT NULL
WITH date.truncate('week', s.date) AS week,
     avg(s.hrv_mean) AS hrv,
     sum(coalesce(s.workout_minutes, 0)) AS load
WITH collect({w: week, h: hrv, l: load}) AS weeks ORDER BY weeks[0].w
UNWIND range(1, size(weeks)-1) AS i
WITH weeks, i,
     weeks[i].w AS week,
     weeks[i].h - weeks[i-1].h AS hrv_delta,
     weeks[i].l - weeks[i-1].l AS load_delta,
     round(weeks[i].h * 10)/10.0 AS hrv,
     weeks[i].l AS load
WHERE hrv_delta < 0 AND load_delta > 60
RETURN week AS `Week`,
       hrv AS `Avg HRV`,
       round(hrv_delta*10)/10.0 AS `HRV Δ vs prev wk`,
       load AS `Workout min`,
       load_delta AS `Load Δ`
ORDER BY week DESC LIMIT 25;


// Q9: Cardio drift
//   Same activity type — has the average HR been creeping up over months?
//   Drift up at constant duration = cardiovascular decline / fatigue.
MATCH (w:Workout)-[:ON_DAY]->(d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE w.duration_min >= 20 AND s.avg_heart_rate IS NOT NULL
WITH w.activity_type AS act,
     date.truncate('month', d.date) AS month,
     avg(s.avg_heart_rate) AS avg_hr,
     count(*) AS sessions
WHERE sessions >= 3
RETURN act AS `Activity`, month AS `Month`,
       round(avg_hr*10)/10.0 AS `Avg HR`,
       sessions AS `Sessions`
ORDER BY act, month;


// Q10: Sleep disruption clusters
//   For nights with :SleepSession data, find runs of nights where efficiency
//   drops > 10% vs the trailing 7-night average.
MATCH (ss:SleepSession)
WHERE ss.asleep_minutes IS NOT NULL AND ss.in_bed_minutes IS NOT NULL
  AND ss.in_bed_minutes > 0
WITH ss, ss.asleep_minutes*1.0 / ss.in_bed_minutes AS eff
WITH ss, eff
MATCH (prev:SleepSession)
WHERE prev.date >= ss.date - duration({days:7}) AND prev.date < ss.date
  AND prev.in_bed_minutes > 0
WITH ss, eff,
     avg(prev.asleep_minutes*1.0 / prev.in_bed_minutes) AS base_eff
WHERE base_eff IS NOT NULL AND eff < base_eff - 0.10
RETURN ss.date AS date,
       round(eff*100)/100.0 AS `Efficiency`,
       round(base_eff*100)/100.0 AS `7-night avg`,
       round((eff - base_eff)*100)/100.0 AS `Drop`
ORDER BY date DESC LIMIT 20;


// =====================================================
//  C. PATTERN DISCOVERY
//     (Q11-Q15 are GDS recipes — see docs/HEALTH_ANALYTICS.md)
// =====================================================

// Q11: Personal training zones (GDS K-Means)  — see docs

// Q12: Day similarity for any bad day (GDS K-NN) — see docs

// Q13: Recovery regime clusters (GDS Louvain) — see docs

// Q14: Activity-type centrality (GDS PageRank) — see docs

// Q15: Bridge events (GDS Betweenness) — see docs


// =====================================================
//  D. IMPROVEMENT / STREAKS / PREDICTIVE
// =====================================================

// Q16: Health streaks
//   Longest consecutive runs of "good day" for several metrics.
MATCH (s:DailySummary)
WHERE s.hrv_mean IS NOT NULL OR s.resting_heart_rate IS NOT NULL
   OR s.sleep_hours IS NOT NULL OR s.total_steps IS NOT NULL
WITH s ORDER BY s.date
WITH collect(s) AS days
UNWIND ['HRV>median', 'RHR<60', 'Sleep>=7.5h', 'Steps>=10k'] AS metric
WITH days, metric,
     [d IN days WHERE
        (metric='HRV>median' AND d.hrv_mean IS NOT NULL AND d.hrv_mean >= 38) OR
        (metric='RHR<60' AND d.resting_heart_rate IS NOT NULL AND d.resting_heart_rate < 60) OR
        (metric='Sleep>=7.5h' AND d.sleep_hours IS NOT NULL AND d.sleep_hours >= 7.5) OR
        (metric='Steps>=10k' AND d.total_steps IS NOT NULL AND d.total_steps >= 10000)
      | d.date] AS hits
UNWIND range(0, size(hits)-1) AS i
WITH metric, hits, i,
     reduce(s=0, j IN range(0,i) |
       CASE WHEN j=0 OR duration.inDays(hits[j-1], hits[j]).days > 1
            THEN s+1 ELSE s END) AS group_id
WITH metric, group_id, collect(hits[i]) AS run
RETURN metric AS `Metric`,
       head(run) AS `Start`, last(run) AS `End`,
       size(run) AS `Days`
ORDER BY size(run) DESC LIMIT 8;


// Q17: Best-day pattern mining
//   Top 10 highest-HRV days — what activities and what was the prior night's sleep?
MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.hrv_mean IS NOT NULL
WITH d, s ORDER BY s.hrv_mean DESC LIMIT 10
OPTIONAL MATCH (yest:Day {date: d.date - duration({days:1})})-[:HAS_SUMMARY]->(ys:DailySummary)
OPTIONAL MATCH (w:Workout)-[:ON_DAY]->(yest)
WITH d, s, ys, collect(DISTINCT w.activity_type) AS prev_acts
RETURN d.date AS `Best day`,
       round(s.hrv_mean*10)/10.0 AS `HRV`,
       round(s.resting_heart_rate) AS `RHR`,
       round(ys.sleep_hours*10)/10.0 AS `Prev sleep`,
       prev_acts AS `Prev day workouts`
ORDER BY s.hrv_mean DESC;


// Q18: Activity diversity entropy (7-day rolling)
//   Shannon entropy of workout activity types — low entropy = monotonous training.
MATCH (m:DailySummary) WITH max(m.date) AS anchor
MATCH (w:Workout)-[:ON_DAY]->(d:Day)
WHERE d.date >= anchor - duration({days:90})
WITH date.truncate('week', d.date) AS week, w.activity_type AS act, count(*) AS n
WITH week, collect({act: act, n: n}) AS counts, sum(n) AS total
WITH week, total, counts,
     reduce(e=0.0, c IN counts |
       e - ((c.n*1.0/total) * log(c.n*1.0/total))
     ) AS entropy
RETURN week AS `Week`,
       round(entropy*100)/100.0 AS `Diversity entropy`,
       total AS `Workouts`,
       size(counts) AS `Distinct activities`
ORDER BY week DESC;


// Q19: Energy balance anomalies
//   Days with active_kcal > 2σ above OR > 2σ below their own 30-day baseline.
MATCH (s:DailySummary) WHERE s.active_energy_kcal IS NOT NULL AND s.active_energy_kcal > 0
WITH s
MATCH (b:DailySummary)
WHERE b.date >= s.date - duration({days:30}) AND b.date < s.date
  AND b.active_energy_kcal IS NOT NULL
WITH s, collect(b.active_energy_kcal) AS eb WHERE size(eb)>=14
WITH s, reduce(t=0.0,x IN eb|t+x)/size(eb) AS mu, eb
WITH s, mu, sqrt(reduce(t=0.0,x IN eb|t+(x-mu)*(x-mu))/size(eb)) AS sd
WHERE sd > 0 AND abs((s.active_energy_kcal - mu)/sd) > 2.0
RETURN s.date AS date,
       round(s.active_energy_kcal) AS `Active kcal`,
       round(mu) AS `30d baseline`,
       round((s.active_energy_kcal-mu)/sd*10)/10.0 AS `Z-score`,
       CASE WHEN s.active_energy_kcal > mu THEN 'overexert' ELSE 'underfueled' END AS `Pattern`
ORDER BY date DESC LIMIT 30;


// Q20: Predict tomorrow's recovery zone (GDS Node Regression) — see docs
