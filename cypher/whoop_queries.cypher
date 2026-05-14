// =====================================================================
//  Whoop-style scoring queries
//  See docs/SCORING.md for formula derivations.
//
//  These queries do NOT mutate the graph — they compute scores on the fly
//  from existing :DailySummary / :SleepSession / :Workout properties.
//
//  Tunables (change in each query if needed):
//    HRV / RHR baseline window  = 30 days (rolling, excludes current day)
//    Sleep need                 = 7.5 h
//    Strain target intensity    = 8 kcal/min
//    Strain scaling constant    = 220
//    Strain non-linearity       = 1.92  (Banister exponent)
// =====================================================================


// ----------------------------------------------------------------------
// Q-HERO-A  Latest Recovery %  (today's three-score hero card, score 1/3)
// ----------------------------------------------------------------------
MATCH (s:DailySummary)
WHERE s.hrv_mean IS NOT NULL AND s.resting_heart_rate IS NOT NULL
WITH s ORDER BY s.date DESC LIMIT 1
MATCH (b:DailySummary)
WHERE b.date >= s.date - duration({days:30}) AND b.date < s.date
  AND b.hrv_mean IS NOT NULL AND b.resting_heart_rate IS NOT NULL
WITH s,
     collect(b.hrv_mean) AS hrv_base,
     collect(b.resting_heart_rate) AS rhr_base
WITH s, hrv_base, rhr_base,
     reduce(t=0.0, x IN hrv_base | t+x)/size(hrv_base) AS hrv_mu,
     reduce(t=0.0, x IN rhr_base | t+x)/size(rhr_base) AS rhr_mu
WITH s, hrv_base, rhr_base, hrv_mu, rhr_mu,
     sqrt(reduce(t=0.0, x IN hrv_base | t+(x-hrv_mu)*(x-hrv_mu))/size(hrv_base)) AS hrv_sd,
     sqrt(reduce(t=0.0, x IN rhr_base | t+(x-rhr_mu)*(x-rhr_mu))/size(rhr_base)) AS rhr_sd
WITH s,
     CASE WHEN hrv_sd > 0 THEN (s.hrv_mean - hrv_mu)/hrv_sd ELSE 0 END AS hrv_z,
     CASE WHEN rhr_sd > 0 THEN (s.resting_heart_rate - rhr_mu)/rhr_sd ELSE 0 END AS rhr_z
WITH s,
     CASE WHEN 50 + 25*hrv_z > 100 THEN 100 WHEN 50 + 25*hrv_z < 0 THEN 0 ELSE 50 + 25*hrv_z END AS hrv_c,
     CASE WHEN 50 - 25*rhr_z > 100 THEN 100 WHEN 50 - 25*rhr_z < 0 THEN 0 ELSE 50 - 25*rhr_z END AS rhr_c,
     CASE WHEN s.sleep_hours IS NULL THEN 50
          WHEN s.sleep_hours >= 7.5 THEN 92
          ELSE (s.sleep_hours / 7.5) * 92 END AS sleep_c
RETURN round(0.60*hrv_c + 0.20*rhr_c + 0.20*sleep_c) AS `Recovery %`;


// ----------------------------------------------------------------------
// Q-HERO-B  Latest Strain (0–21)  (hero card, score 2/3)
// ----------------------------------------------------------------------
MATCH (s:DailySummary)
WHERE s.active_energy_kcal IS NOT NULL
WITH s ORDER BY s.date DESC LIMIT 1
WITH s,
     CASE WHEN coalesce(s.workout_minutes,0) > 0
          THEN s.active_energy_kcal / s.workout_minutes
          ELSE s.active_energy_kcal / 480.0  // spread basal-ish activity over 8 waking hours
     END AS intensity,
     CASE WHEN coalesce(s.workout_minutes,0) > 0 THEN s.workout_minutes ELSE 30.0 END AS load_minutes
WITH 21.0 * (1.0 - exp(-(load_minutes * (intensity/8.0)^1.92) / 220.0)) AS strain
RETURN round(strain * 10) / 10.0 AS Strain;


// ----------------------------------------------------------------------
// Q-HERO-C  Latest Sleep Performance %  (hero card, score 3/3)
// ----------------------------------------------------------------------
MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.sleep_hours IS NOT NULL
WITH s, d ORDER BY s.date DESC LIMIT 1
OPTIONAL MATCH (ss:SleepSession {date: d.date})
WITH s, ss,
     coalesce(ss.asleep_minutes, s.sleep_hours * 60) AS asleep_min,
     coalesce(ss.in_bed_minutes, s.sleep_hours * 60 / 0.92) AS in_bed_min
WITH (CASE WHEN asleep_min/450.0 > 1.0 THEN 1.0 ELSE asleep_min/450.0 END) * 100 AS dur_score,
     CASE WHEN in_bed_min > 0 THEN asleep_min/in_bed_min ELSE 0.92 END AS efficiency
RETURN round(dur_score * efficiency) AS `Sleep %`;


// ----------------------------------------------------------------------
// Q-RECOVERY-TREND  Recovery % over last 90 days
// ----------------------------------------------------------------------
MATCH (m:DailySummary) WITH max(m.date) AS anchor
MATCH (s:DailySummary)
WHERE s.hrv_mean IS NOT NULL AND s.resting_heart_rate IS NOT NULL
  AND s.date >= anchor - duration({days:90})
WITH s
MATCH (b:DailySummary)
WHERE b.date >= s.date - duration({days:30}) AND b.date < s.date
  AND b.hrv_mean IS NOT NULL AND b.resting_heart_rate IS NOT NULL
WITH s, collect(b.hrv_mean) AS hrv_base, collect(b.resting_heart_rate) AS rhr_base
WHERE size(hrv_base) >= 7 AND size(rhr_base) >= 7
WITH s, hrv_base, rhr_base,
     reduce(t=0.0, x IN hrv_base | t+x)/size(hrv_base) AS hrv_mu,
     reduce(t=0.0, x IN rhr_base | t+x)/size(rhr_base) AS rhr_mu
WITH s, hrv_base, rhr_base, hrv_mu, rhr_mu,
     sqrt(reduce(t=0.0, x IN hrv_base | t+(x-hrv_mu)*(x-hrv_mu))/size(hrv_base)) AS hrv_sd,
     sqrt(reduce(t=0.0, x IN rhr_base | t+(x-rhr_mu)*(x-rhr_mu))/size(rhr_base)) AS rhr_sd
WITH s,
     CASE WHEN hrv_sd > 0 THEN (s.hrv_mean - hrv_mu)/hrv_sd ELSE 0 END AS hrv_z,
     CASE WHEN rhr_sd > 0 THEN (s.resting_heart_rate - rhr_mu)/rhr_sd ELSE 0 END AS rhr_z
WITH s,
     CASE WHEN 50 + 25*hrv_z > 100 THEN 100 WHEN 50 + 25*hrv_z < 0 THEN 0 ELSE 50 + 25*hrv_z END AS hrv_c,
     CASE WHEN 50 - 25*rhr_z > 100 THEN 100 WHEN 50 - 25*rhr_z < 0 THEN 0 ELSE 50 - 25*rhr_z END AS rhr_c,
     CASE WHEN s.sleep_hours IS NULL THEN 50
          WHEN s.sleep_hours >= 7.5 THEN 92
          ELSE (s.sleep_hours / 7.5) * 92 END AS sleep_c
RETURN s.date AS date,
       round(0.60*hrv_c + 0.20*rhr_c + 0.20*sleep_c) AS `Recovery %`
ORDER BY date;


// ----------------------------------------------------------------------
// Q-STRAIN-HISTORY  Daily Strain over last 30 days
// ----------------------------------------------------------------------
MATCH (m:DailySummary) WITH max(m.date) AS anchor
MATCH (s:DailySummary)
WHERE s.active_energy_kcal IS NOT NULL
  AND s.date >= anchor - duration({days:30})
WITH s,
     CASE WHEN coalesce(s.workout_minutes,0) > 0
          THEN s.active_energy_kcal / s.workout_minutes
          ELSE s.active_energy_kcal / 480.0
     END AS intensity,
     CASE WHEN coalesce(s.workout_minutes,0) > 0 THEN s.workout_minutes ELSE 30.0 END AS load_min
RETURN s.date AS date,
       round(21.0 * (1.0 - exp(-(load_min * (intensity/8.0)^1.92) / 220.0)) * 10) / 10.0 AS Strain
ORDER BY date;


// ----------------------------------------------------------------------
// Q-STRAIN-HEATMAP  Last 365 days of strain (for calendar/heatmap viz)
// ----------------------------------------------------------------------
MATCH (m:DailySummary) WITH max(m.date) AS anchor
MATCH (s:DailySummary)
WHERE s.active_energy_kcal IS NOT NULL
  AND s.date >= anchor - duration({days:365})
WITH s,
     CASE WHEN coalesce(s.workout_minutes,0) > 0
          THEN s.active_energy_kcal / s.workout_minutes
          ELSE s.active_energy_kcal / 480.0
     END AS intensity,
     CASE WHEN coalesce(s.workout_minutes,0) > 0 THEN s.workout_minutes ELSE 30.0 END AS load_min
RETURN s.date AS date,
       round(21.0 * (1.0 - exp(-(load_min * (intensity/8.0)^1.92) / 220.0)) * 10) / 10.0 AS strain
ORDER BY date;


// ----------------------------------------------------------------------
// Q-SLEEP-PERF  Nightly Sleep Performance over last 90 days
// ----------------------------------------------------------------------
MATCH (m:DailySummary) WITH max(m.date) AS anchor
MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.sleep_hours IS NOT NULL
  AND s.date >= anchor - duration({days:90})
OPTIONAL MATCH (ss:SleepSession {date: d.date})
WITH s,
     coalesce(ss.asleep_minutes, s.sleep_hours * 60) AS asleep_min,
     coalesce(ss.in_bed_minutes, s.sleep_hours * 60 / 0.92) AS in_bed_min
WITH s.date AS date,
     (CASE WHEN asleep_min/450.0 > 1.0 THEN 1.0 ELSE asleep_min/450.0 END) * 100 AS dur_score,
     CASE WHEN in_bed_min > 0 THEN asleep_min/in_bed_min ELSE 0.92 END AS efficiency,
     asleep_min/60.0 AS sleep_hours
RETURN date,
       round(dur_score * efficiency) AS `Sleep %`,
       round(sleep_hours * 10)/10.0 AS `Hours asleep`,
       7.5 AS `Need (h)`
ORDER BY date;


// ----------------------------------------------------------------------
// Q-HRV-TREND  HRV with 7-day rolling mean (last 180 days)
// ----------------------------------------------------------------------
MATCH (m:DailySummary) WITH max(m.date) AS anchor
MATCH (s:DailySummary)
WHERE s.hrv_mean IS NOT NULL
  AND s.date >= anchor - duration({days:180})
WITH s
MATCH (b:DailySummary)
WHERE b.date >= s.date - duration({days:6}) AND b.date <= s.date
  AND b.hrv_mean IS NOT NULL
WITH s.date AS date, s.hrv_mean AS daily, collect(b.hrv_mean) AS w
RETURN date,
       round(daily * 10)/10.0 AS `HRV (ms)`,
       round((reduce(t=0.0, x IN w | t+x)/size(w)) * 10)/10.0 AS `7-day avg`
ORDER BY date;


// ----------------------------------------------------------------------
// Q-RHR-TREND  RHR with 7-day rolling mean (last 180 days)
// ----------------------------------------------------------------------
MATCH (m:DailySummary) WITH max(m.date) AS anchor
MATCH (s:DailySummary)
WHERE s.resting_heart_rate IS NOT NULL
  AND s.date >= anchor - duration({days:180})
WITH s
MATCH (b:DailySummary)
WHERE b.date >= s.date - duration({days:6}) AND b.date <= s.date
  AND b.resting_heart_rate IS NOT NULL
WITH s.date AS date, s.resting_heart_rate AS daily, collect(b.resting_heart_rate) AS w
RETURN date,
       round(daily * 10)/10.0 AS `RHR (bpm)`,
       round((reduce(t=0.0, x IN w | t+x)/size(w)) * 10)/10.0 AS `7-day avg`
ORDER BY date;


// ----------------------------------------------------------------------
// Q-SCATTER  Strain (today) vs Recovery (yesterday)  — last 180 days
// "Did I take it easy when my body said to?"  — Whoop's signature coaching insight
// ----------------------------------------------------------------------
MATCH (m:DailySummary) WITH max(m.date) AS anchor
MATCH (today:DailySummary)
WHERE today.active_energy_kcal IS NOT NULL
  AND today.date >= anchor - duration({days:180})
MATCH (yest:DailySummary {date: today.date - duration({days:1})})
WHERE yest.hrv_mean IS NOT NULL AND yest.resting_heart_rate IS NOT NULL
MATCH (b:DailySummary)
WHERE b.date >= yest.date - duration({days:30}) AND b.date < yest.date
  AND b.hrv_mean IS NOT NULL AND b.resting_heart_rate IS NOT NULL
WITH today, yest, collect(b.hrv_mean) AS hrv_base, collect(b.resting_heart_rate) AS rhr_base
WHERE size(hrv_base) >= 7
WITH today, yest, hrv_base, rhr_base,
     reduce(t=0.0, x IN hrv_base | t+x)/size(hrv_base) AS hrv_mu,
     reduce(t=0.0, x IN rhr_base | t+x)/size(rhr_base) AS rhr_mu
WITH today, yest, hrv_base, rhr_base, hrv_mu, rhr_mu,
     sqrt(reduce(t=0.0, x IN hrv_base | t+(x-hrv_mu)*(x-hrv_mu))/size(hrv_base)) AS hrv_sd,
     sqrt(reduce(t=0.0, x IN rhr_base | t+(x-rhr_mu)*(x-rhr_mu))/size(rhr_base)) AS rhr_sd
WITH today, yest,
     CASE WHEN hrv_sd > 0 THEN (yest.hrv_mean - hrv_mu)/hrv_sd ELSE 0 END AS hrv_z,
     CASE WHEN rhr_sd > 0 THEN (yest.resting_heart_rate - rhr_mu)/rhr_sd ELSE 0 END AS rhr_z
WITH today, yest,
     CASE WHEN 50 + 25*hrv_z > 100 THEN 100 WHEN 50 + 25*hrv_z < 0 THEN 0 ELSE 50 + 25*hrv_z END AS hrv_c,
     CASE WHEN 50 - 25*rhr_z > 100 THEN 100 WHEN 50 - 25*rhr_z < 0 THEN 0 ELSE 50 - 25*rhr_z END AS rhr_c,
     CASE WHEN yest.sleep_hours IS NULL THEN 50
          WHEN yest.sleep_hours >= 7.5 THEN 92
          ELSE (yest.sleep_hours / 7.5) * 92 END AS sleep_c
WITH today,
     round(0.60*hrv_c + 0.20*rhr_c + 0.20*sleep_c) AS recovery_yesterday,
     CASE WHEN coalesce(today.workout_minutes,0) > 0
          THEN today.active_energy_kcal / today.workout_minutes
          ELSE today.active_energy_kcal / 480.0 END AS intensity,
     CASE WHEN coalesce(today.workout_minutes,0) > 0 THEN today.workout_minutes ELSE 30.0 END AS load_min
RETURN recovery_yesterday AS `Recovery yesterday`,
       round(21.0 * (1.0 - exp(-(load_min * (intensity/8.0)^1.92) / 220.0)) * 10) / 10.0 AS `Strain today`;
// ====================================================
// PAGE 2 — RECOVERY DEEP-DIVE
// ====================================================

// R1: HRV by day-of-week (averaged across full history)
MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.hrv_mean IS NOT NULL
WITH d.day_of_week AS dow, avg(s.hrv_mean) AS avg_hrv, count(*) AS n
RETURN
  CASE dow
    WHEN 'Monday' THEN '1-Mon' WHEN 'Tuesday' THEN '2-Tue'
    WHEN 'Wednesday' THEN '3-Wed' WHEN 'Thursday' THEN '4-Thu'
    WHEN 'Friday' THEN '5-Fri' WHEN 'Saturday' THEN '6-Sat'
    WHEN 'Sunday' THEN '7-Sun' END AS day,
  round(avg_hrv * 10)/10.0 AS `Avg HRV (ms)`,
  n AS `Days`
ORDER BY day;

// R2: Recovery zone distribution (last 365 days) — pie/bar
MATCH (m:DailySummary) WITH max(m.date) AS anchor
MATCH (s:DailySummary)
WHERE s.hrv_mean IS NOT NULL AND s.resting_heart_rate IS NOT NULL
  AND s.date >= anchor - duration({days:365})
WITH s
MATCH (b:DailySummary)
WHERE b.date >= s.date - duration({days:30}) AND b.date < s.date
  AND b.hrv_mean IS NOT NULL AND b.resting_heart_rate IS NOT NULL
WITH s, collect(b.hrv_mean) AS hrv_base, collect(b.resting_heart_rate) AS rhr_base
WHERE size(hrv_base) >= 7
WITH s, hrv_base, rhr_base,
     reduce(t=0.0, x IN hrv_base | t+x)/size(hrv_base) AS hrv_mu,
     reduce(t=0.0, x IN rhr_base | t+x)/size(rhr_base) AS rhr_mu
WITH s, hrv_base, rhr_base, hrv_mu, rhr_mu,
     sqrt(reduce(t=0.0, x IN hrv_base | t+(x-hrv_mu)*(x-hrv_mu))/size(hrv_base)) AS hrv_sd,
     sqrt(reduce(t=0.0, x IN rhr_base | t+(x-rhr_mu)*(x-rhr_mu))/size(rhr_base)) AS rhr_sd
WITH s,
     CASE WHEN hrv_sd > 0 THEN (s.hrv_mean - hrv_mu)/hrv_sd ELSE 0 END AS hrv_z,
     CASE WHEN rhr_sd > 0 THEN (s.resting_heart_rate - rhr_mu)/rhr_sd ELSE 0 END AS rhr_z
WITH s,
     CASE WHEN 50 + 25*hrv_z > 100 THEN 100 WHEN 50 + 25*hrv_z < 0 THEN 0 ELSE 50 + 25*hrv_z END AS hrv_c,
     CASE WHEN 50 - 25*rhr_z > 100 THEN 100 WHEN 50 - 25*rhr_z < 0 THEN 0 ELSE 50 - 25*rhr_z END AS rhr_c,
     CASE WHEN s.sleep_hours IS NULL THEN 50
          WHEN s.sleep_hours >= 7.5 THEN 92
          ELSE (s.sleep_hours / 7.5) * 92 END AS sleep_c
WITH 0.60*hrv_c + 0.20*rhr_c + 0.20*sleep_c AS recovery
WITH CASE WHEN recovery >= 67 THEN '1-Green (67+)'
          WHEN recovery >= 34 THEN '2-Yellow (34-66)'
          ELSE '3-Red (0-33)' END AS zone
RETURN zone AS `Recovery zone`, count(*) AS `Days`
ORDER BY zone;

// R3: Workout type → next-day HRV impact (top 10)
MATCH (w:Workout)-[:ON_DAY]->(d:Day)
MATCH (next:Day {date: d.date + duration({days:1})})-[:HAS_SUMMARY]->(ns:DailySummary)
WHERE ns.hrv_mean IS NOT NULL
WITH w.activity_type AS activity, ns.hrv_mean AS next_hrv, w
WITH activity, avg(next_hrv) AS avg_next_hrv, count(DISTINCT w) AS sessions
WHERE sessions >= 5
RETURN activity AS `Activity type`,
       round(avg_next_hrv * 10)/10.0 AS `Avg next-day HRV (ms)`,
       sessions AS `Sessions`
ORDER BY avg_next_hrv DESC LIMIT 12;

// R4: Best recovery days (top 10 of last 365)
MATCH (m:DailySummary) WITH max(m.date) AS anchor
MATCH (s:DailySummary)
WHERE s.hrv_mean IS NOT NULL AND s.resting_heart_rate IS NOT NULL
  AND s.date >= anchor - duration({days:365})
WITH s
MATCH (b:DailySummary)
WHERE b.date >= s.date - duration({days:30}) AND b.date < s.date
  AND b.hrv_mean IS NOT NULL AND b.resting_heart_rate IS NOT NULL
WITH s, collect(b.hrv_mean) AS hrv_base, collect(b.resting_heart_rate) AS rhr_base
WHERE size(hrv_base) >= 14
WITH s, hrv_base, rhr_base,
     reduce(t=0.0, x IN hrv_base | t+x)/size(hrv_base) AS hrv_mu,
     reduce(t=0.0, x IN rhr_base | t+x)/size(rhr_base) AS rhr_mu
WITH s, hrv_base, rhr_base, hrv_mu, rhr_mu,
     sqrt(reduce(t=0.0, x IN hrv_base | t+(x-hrv_mu)*(x-hrv_mu))/size(hrv_base)) AS hrv_sd,
     sqrt(reduce(t=0.0, x IN rhr_base | t+(x-rhr_mu)*(x-rhr_mu))/size(rhr_base)) AS rhr_sd
WITH s,
     CASE WHEN hrv_sd > 0 THEN (s.hrv_mean - hrv_mu)/hrv_sd ELSE 0 END AS hrv_z,
     CASE WHEN rhr_sd > 0 THEN (s.resting_heart_rate - rhr_mu)/rhr_sd ELSE 0 END AS rhr_z
WITH s,
     CASE WHEN 50 + 25*hrv_z > 100 THEN 100 WHEN 50 + 25*hrv_z < 0 THEN 0 ELSE 50 + 25*hrv_z END AS hrv_c,
     CASE WHEN 50 - 25*rhr_z > 100 THEN 100 WHEN 50 - 25*rhr_z < 0 THEN 0 ELSE 50 - 25*rhr_z END AS rhr_c,
     CASE WHEN s.sleep_hours IS NULL THEN 50
          WHEN s.sleep_hours >= 7.5 THEN 92
          ELSE (s.sleep_hours / 7.5) * 92 END AS sleep_c
RETURN s.date AS date,
       round(0.60*hrv_c + 0.20*rhr_c + 0.20*sleep_c) AS `Recovery %`,
       round(s.hrv_mean * 10)/10.0 AS `HRV`,
       round(s.resting_heart_rate) AS `RHR`,
       round((s.sleep_hours)*10)/10.0 AS `Sleep h`
ORDER BY `Recovery %` DESC LIMIT 10;

// R5: HRV baseline drift — monthly avg HRV over full history
MATCH (s:DailySummary) WHERE s.hrv_mean IS NOT NULL
WITH date.truncate('month', s.date) AS month, avg(s.hrv_mean) AS avg_hrv, count(*) AS days
WHERE days >= 5
RETURN month AS date,
       round(avg_hrv * 10)/10.0 AS `Monthly HRV mean (ms)`
ORDER BY date;


// ====================================================
// PAGE 3 — STRAIN DEEP-DIVE
// ====================================================

// S1: Weekly training load (workout minutes × intensity proxy) last 26 weeks
MATCH (m:DailySummary) WITH max(m.date) AS anchor
MATCH (d:Day)-[:PART_OF]->(w:Week)
MATCH (d)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.active_energy_kcal IS NOT NULL
  AND w.start_date >= anchor - duration({days:182})
WITH w.start_date AS week,
     sum(s.active_energy_kcal) AS active_kcal,
     sum(coalesce(s.workout_minutes,0)) AS workout_min
RETURN week AS date,
       round(active_kcal) AS `Active kcal`,
       round(workout_min) AS `Workout min`
ORDER BY week;

// S2: Monthly strain calendar — avg strain per month
MATCH (s:DailySummary) WHERE s.active_energy_kcal IS NOT NULL AND s.active_energy_kcal > 0
WITH s,
     CASE WHEN coalesce(s.workout_minutes,0) > 0
          THEN s.active_energy_kcal / s.workout_minutes
          ELSE s.active_energy_kcal / 480.0 END AS intensity,
     CASE WHEN coalesce(s.workout_minutes,0) > 0 THEN s.workout_minutes ELSE 30.0 END AS load_min
WITH s, intensity, load_min,
     CASE WHEN intensity > 0 THEN load_min * (intensity/8.0)^1.92 ELSE 0 END AS raw_load
WITH date.truncate('month', s.date) AS month,
     21.0 * (1.0 - exp(-raw_load / 220.0)) AS daily_strain
WHERE daily_strain = daily_strain
WITH month, avg(daily_strain) AS avg_strain
RETURN month AS date,
       round(avg_strain * 10)/10.0 AS `Avg daily strain`
ORDER BY date;

// S3: Activity type total volume — top 12 lifetime
MATCH (w:Workout)
WHERE w.duration_min IS NOT NULL
WITH w.activity_type AS activity, sum(w.duration_min)/60.0 AS hours, count(*) AS sessions
WHERE sessions >= 5
RETURN activity AS `Activity type`,
       round(hours * 10)/10.0 AS `Total hours`,
       sessions AS `Sessions`
ORDER BY hours DESC LIMIT 12;

// S4: Strain by day-of-week (full history)
MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.active_energy_kcal IS NOT NULL AND s.active_energy_kcal > 0
WITH d.day_of_week AS dow, s,
     CASE WHEN coalesce(s.workout_minutes,0) > 0
          THEN s.active_energy_kcal / s.workout_minutes
          ELSE s.active_energy_kcal / 480.0 END AS intensity,
     CASE WHEN coalesce(s.workout_minutes,0) > 0 THEN s.workout_minutes ELSE 30.0 END AS load_min
WITH dow, intensity, load_min,
     CASE WHEN intensity > 0 THEN load_min * (intensity/8.0)^1.92 ELSE 0 END AS raw_load
WITH dow, 21.0 * (1.0 - exp(-raw_load / 220.0)) AS strain
WHERE strain = strain  // exclude NaN
WITH dow, avg(strain) AS avg_strain, count(*) AS days
RETURN
  CASE dow
    WHEN 'Monday' THEN '1-Mon' WHEN 'Tuesday' THEN '2-Tue'
    WHEN 'Wednesday' THEN '3-Wed' WHEN 'Thursday' THEN '4-Thu'
    WHEN 'Friday' THEN '5-Fri' WHEN 'Saturday' THEN '6-Sat'
    WHEN 'Sunday' THEN '7-Sun' END AS day,
  round(avg_strain * 10)/10.0 AS `Avg strain`
ORDER BY day;

// S5: Strain zone distribution (last 365 days)
MATCH (m:DailySummary) WITH max(m.date) AS anchor
MATCH (s:DailySummary)
WHERE s.active_energy_kcal IS NOT NULL
  AND s.date >= anchor - duration({days:365})
WITH s,
     CASE WHEN coalesce(s.workout_minutes,0) > 0
          THEN s.active_energy_kcal / s.workout_minutes
          ELSE s.active_energy_kcal / 480.0 END AS intensity,
     CASE WHEN coalesce(s.workout_minutes,0) > 0 THEN s.workout_minutes ELSE 30.0 END AS load_min
WITH 21.0 * (1.0 - exp(-(load_min * (intensity/8.0)^1.92) / 220.0)) AS strain
WITH CASE WHEN strain >= 18 THEN '4-All-out (18-21)'
          WHEN strain >= 14 THEN '3-Strenuous (14-17)'
          WHEN strain >= 10 THEN '2-Moderate (10-13)'
          ELSE '1-Light (0-9)' END AS zone
RETURN zone AS `Strain zone`, count(*) AS Days
ORDER BY zone;


// ====================================================
// PAGE 4 — SLEEP DEEP-DIVE
// ====================================================

// SL1: Sleep duration histogram (1h buckets)
MATCH (s:DailySummary) WHERE s.sleep_hours IS NOT NULL
WITH toInteger(floor(s.sleep_hours)) AS bucket
WITH bucket, count(*) AS n
RETURN
  toString(bucket) + '-' + toString(bucket+1) + 'h' AS `Sleep duration`,
  n AS Nights
ORDER BY bucket;

// SL2: Avg sleep hours by day-of-week
MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.sleep_hours IS NOT NULL
WITH d.day_of_week AS dow, avg(s.sleep_hours) AS avg_h, count(*) AS n
RETURN
  CASE dow
    WHEN 'Monday' THEN '1-Mon' WHEN 'Tuesday' THEN '2-Tue'
    WHEN 'Wednesday' THEN '3-Wed' WHEN 'Thursday' THEN '4-Thu'
    WHEN 'Friday' THEN '5-Fri' WHEN 'Saturday' THEN '6-Sat'
    WHEN 'Sunday' THEN '7-Sun' END AS day,
  round(avg_h * 10)/10.0 AS `Avg sleep (h)`,
  n AS Nights
ORDER BY day;

// SL3: Monthly avg sleep — full history with rolling consistency
MATCH (s:DailySummary) WHERE s.sleep_hours IS NOT NULL
WITH date.truncate('month', s.date) AS month, collect(s.sleep_hours) AS hrs
WITH month, hrs,
     reduce(t=0.0, x IN hrs | t+x)/size(hrs) AS mu
WITH month, hrs, mu,
     sqrt(reduce(t=0.0, x IN hrs | t+(x-mu)*(x-mu))/size(hrs)) AS sd, size(hrs) AS n
WHERE n >= 3
RETURN month AS date,
       round(mu * 10)/10.0 AS `Avg sleep (h)`,
       round(sd * 100)/100.0 AS `Std dev (h)`
ORDER BY date;

// SL4: Cumulative sleep debt vs 7.5h need (last 90 nights of data)
MATCH (s:DailySummary) WHERE s.sleep_hours IS NOT NULL
WITH s ORDER BY s.date DESC LIMIT 90
WITH s ORDER BY s.date ASC
WITH collect({date: s.date, h: s.sleep_hours}) AS rows
UNWIND range(0, size(rows)-1) AS i
WITH rows[i] AS row,
     reduce(t=0.0, j IN range(0,i) | t + (rows[j].h - 7.5)) AS cum_debt
RETURN row.date AS date,
       round(row.h * 10)/10.0 AS `Hours`,
       round(cum_debt * 10)/10.0 AS `Cumulative vs 7.5h`
ORDER BY date;


// ====================================================
// PAGE 5 — HEALTH MONITOR (full history)
// ====================================================

// H1: VO2max — monthly over full history
MATCH (s:DailySummary) WHERE s.vo2max IS NOT NULL
WITH date.truncate('month', s.date) AS month, avg(s.vo2max) AS v
RETURN month AS date, round(v * 10)/10.0 AS `VO2max`
ORDER BY date;

// H2: RHR with 30-day rolling (full history, sampled monthly)
MATCH (s:DailySummary) WHERE s.resting_heart_rate IS NOT NULL
WITH date.truncate('month', s.date) AS month, avg(s.resting_heart_rate) AS v
RETURN month AS date, round(v * 10)/10.0 AS `RHR (bpm)`
ORDER BY date;

// H3: HRV monthly — full history
MATCH (s:DailySummary) WHERE s.hrv_mean IS NOT NULL
WITH date.truncate('month', s.date) AS month, avg(s.hrv_mean) AS v
RETURN month AS date, round(v * 10)/10.0 AS `HRV (ms)`
ORDER BY date;

// H4: SpO2 monthly — full history
MATCH (s:DailySummary) WHERE s.avg_blood_oxygen IS NOT NULL
WITH date.truncate('month', s.date) AS month, avg(s.avg_blood_oxygen) AS v
RETURN month AS date, round(v * 100)/100.0 AS `SpO2 (%)`
ORDER BY date;

// H5: Respiratory rate monthly — full history
MATCH (s:DailySummary) WHERE s.avg_respiratory_rate IS NOT NULL
WITH date.truncate('month', s.date) AS month, avg(s.avg_respiratory_rate) AS v
RETURN month AS date, round(v * 10)/10.0 AS `Respiratory rate (brpm)`
ORDER BY date;

// H6: Body mass monthly — full history
MATCH (s:DailySummary) WHERE s.body_mass_kg IS NOT NULL
WITH date.truncate('month', s.date) AS month, avg(s.body_mass_kg) AS v
RETURN month AS date, round(v * 10)/10.0 AS `Body mass (kg)`
ORDER BY date;
