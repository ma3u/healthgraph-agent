// ============================================================
// HealthGraph Agent — 20 Longevity-Focused Cypher Queries
// ============================================================
//
// These queries explore the key biomarkers and patterns that
// longevity science links to healthspan and lifespan:
//   - HRV (autonomic resilience)
//   - Resting heart rate (cardiovascular efficiency)
//   - VO2max (cardiorespiratory fitness — strongest predictor)
//   - Sleep quality and consistency
//   - Exercise volume and variety
//   - Recovery capacity
//   - Metabolic health (energy balance)
//
// Each query includes a comment explaining the longevity relevance.
// ============================================================


// ----------------------------------------------------------
// Q1: VO2max trend over time (strongest longevity predictor)
//
// VO2max is the single strongest predictor of all-cause mortality.
// Moving from "low" to "above average" reduces mortality risk ~50%.
// Track whether yours is improving, stable, or declining.
// ----------------------------------------------------------

MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.vo2max IS NOT NULL
RETURN d.date AS date,
       s.vo2max AS vo2max,
       d.day_of_week AS day
ORDER BY d.date;


// ----------------------------------------------------------
// Q2: Monthly VO2max progression with exercise context
//
// VO2max improves with Zone 2 and high-intensity training.
// This shows monthly averages alongside training volume.
// ----------------------------------------------------------

MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.vo2max IS NOT NULL
WITH d.date.year AS year, d.date.month AS month, s
RETURN year + '-' + right('0' + toString(month), 2) AS month,
       round(avg(s.vo2max), 1) AS avg_vo2max,
       round(avg(s.workout_minutes), 0) AS avg_daily_workout_min,
       round(avg(s.total_steps), 0) AS avg_daily_steps,
       count(*) AS readings
ORDER BY month;


// ----------------------------------------------------------
// Q3: Resting heart rate trend (cardiovascular efficiency)
//
// Lower RHR correlates with longevity. Elite athletes: 40-50 bpm.
// RHR > 75 bpm is associated with doubled mortality risk vs < 55.
// ----------------------------------------------------------

MATCH (d:Day)-[:PART_OF]->(w:Week)
MATCH (d)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.resting_heart_rate IS NOT NULL
RETURN w.iso AS week,
       round(avg(s.resting_heart_rate), 1) AS avg_resting_hr,
       round(min(s.resting_heart_rate), 1) AS min_resting_hr,
       round(max(s.resting_heart_rate), 1) AS max_resting_hr,
       count(*) AS days
ORDER BY w.iso;


// ----------------------------------------------------------
// Q4: HRV trend (autonomic nervous system resilience)
//
// Higher HRV indicates greater parasympathetic tone and stress
// resilience. HRV declines with age; maintaining it is protective.
// ----------------------------------------------------------

MATCH (d:Day)-[:PART_OF]->(w:Week)
MATCH (d)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.hrv_mean IS NOT NULL
RETURN w.iso AS week,
       round(avg(s.hrv_mean), 1) AS avg_hrv,
       round(min(s.hrv_mean), 1) AS min_hrv,
       round(max(s.hrv_mean), 1) AS max_hrv,
       count(*) AS days
ORDER BY w.iso;


// ----------------------------------------------------------
// Q5: Sleep duration distribution (longevity sweet spot: 7-8h)
//
// Both short (<6h) and long (>9h) sleep are associated with
// increased mortality. The U-shaped curve bottoms at 7-8 hours.
// ----------------------------------------------------------

MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.sleep_hours IS NOT NULL
WITH CASE
    WHEN s.sleep_hours < 5 THEN '< 5h (severe deficit)'
    WHEN s.sleep_hours < 6 THEN '5-6h (short)'
    WHEN s.sleep_hours < 7 THEN '6-7h (slightly short)'
    WHEN s.sleep_hours < 8 THEN '7-8h (optimal)'
    WHEN s.sleep_hours < 9 THEN '8-9h (good)'
    ELSE '9h+ (long)'
  END AS sleep_bucket,
  s
RETURN sleep_bucket,
       count(*) AS days,
       round(avg(s.hrv_mean), 1) AS avg_hrv_in_bucket,
       round(avg(s.resting_heart_rate), 1) AS avg_rhr_in_bucket,
       round(avg(s.active_energy_kcal), 0) AS avg_active_cal
ORDER BY sleep_bucket;


// ----------------------------------------------------------
// Q6: Exercise variety and consistency (anti-fragility)
//
// Longevity benefits from BOTH cardio AND strength training.
// People who do both have 40% lower mortality than either alone.
// ----------------------------------------------------------

MATCH (w:Workout)-[:ON_DAY]->(d:Day)
WITH d.date.year AS year, d.date.month AS month, w
RETURN year + '-' + right('0' + toString(month), 2) AS month,
       count(*) AS total_workouts,
       count(DISTINCT w.activity_type) AS workout_types,
       collect(DISTINCT w.activity_type) AS types,
       round(sum(w.duration_min), 0) AS total_minutes,
       round(avg(w.duration_min), 1) AS avg_duration
ORDER BY month;


// ----------------------------------------------------------
// Q7: Zone 2 proxy — walks and easy cardio volume
//
// Zone 2 training (low-intensity steady state) is the foundation
// of longevity exercise. Walking is accessible Zone 2 for most.
// Goal: 150-180+ minutes/week of Zone 2.
// ----------------------------------------------------------

MATCH (d:Day)-[:PART_OF]->(w:Week)
MATCH (d)-[:HAS_SUMMARY]->(s:DailySummary)
OPTIONAL MATCH (walk:Workout {activity_type: 'Walking'})-[:ON_DAY]->(d)
WITH w, d, s,
     count(walk) AS walks,
     sum(COALESCE(walk.duration_min, 0)) AS walk_minutes
RETURN w.iso AS week,
       sum(s.total_steps) AS total_steps,
       round(sum(s.total_distance_km), 1) AS total_km,
       sum(walks) AS walk_sessions,
       round(sum(walk_minutes), 0) AS walk_minutes,
       round(sum(s.exercise_minutes), 0) AS total_exercise_min
ORDER BY w.iso;


// ----------------------------------------------------------
// Q8: Recovery quality — sleep after hard training days
//
// Recovery is where adaptation happens. Good sleepers after
// hard training days get stronger; poor sleepers break down.
// ----------------------------------------------------------

MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.workout_minutes > 45
OPTIONAL MATCH (d)-[:NEXT_DAY]->(d2:Day)-[:HAS_SUMMARY]->(s2:DailySummary)
WHERE s2.sleep_hours IS NOT NULL
RETURN d.date AS training_date,
       s.workout_minutes AS workout_min,
       s.workout_count AS workouts,
       s.active_energy_kcal AS active_cal,
       s2.sleep_hours AS sleep_after,
       s2.hrv_mean AS hrv_next_day,
       s2.resting_heart_rate AS rhr_next_day
ORDER BY d.date DESC
LIMIT 30;


// ----------------------------------------------------------
// Q9: Strength training frequency and consistency
//
// Strength training 2-3x/week preserves muscle mass (sarcopenia
// prevention), bone density, and insulin sensitivity with age.
// ----------------------------------------------------------

MATCH (w:Workout)-[:ON_DAY]->(d:Day)-[:PART_OF]->(wk:Week)
WHERE w.activity_type IN ['TraditionalStrengthTraining', 'FunctionalStrengthTraining',
                           'HighIntensityIntervalTraining', 'CrossTraining']
RETURN wk.iso AS week,
       count(*) AS strength_sessions,
       collect(w.activity_type) AS types,
       round(sum(w.duration_min), 0) AS total_minutes,
       round(avg(w.total_energy_burned), 0) AS avg_calories
ORDER BY wk.iso;


// ----------------------------------------------------------
// Q10: Cardio training volume (weekly aerobic minutes)
//
// 150 min/week moderate OR 75 min/week vigorous is the minimum.
// 300+ min/week provides additional mortality reduction.
// ----------------------------------------------------------

MATCH (w:Workout)-[:ON_DAY]->(d:Day)-[:PART_OF]->(wk:Week)
WHERE w.activity_type IN ['Running', 'Cycling', 'Swimming', 'Walking',
                           'Elliptical', 'Rowing', 'StairClimbing']
RETURN wk.iso AS week,
       count(*) AS cardio_sessions,
       round(sum(w.duration_min), 0) AS total_cardio_min,
       round(sum(w.total_distance), 2) AS total_distance,
       round(sum(w.total_energy_burned), 0) AS total_calories,
       CASE WHEN sum(w.duration_min) >= 150 THEN 'GOAL MET' ELSE 'BELOW GOAL' END AS status
ORDER BY wk.iso;


// ----------------------------------------------------------
// Q11: Sleep consistency (regularity is as important as duration)
//
// Irregular sleep patterns are an independent mortality risk factor.
// Social jet lag (weekend vs weekday sleep differences) harms health.
// ----------------------------------------------------------

MATCH (d:Day)-[:PART_OF]->(w:Week)
MATCH (d)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.sleep_hours IS NOT NULL
WITH w, collect({day: d.day_of_week, hours: s.sleep_hours}) AS days,
     avg(s.sleep_hours) AS avg_sleep,
     stDev(s.sleep_hours) AS sleep_variability
RETURN w.iso AS week,
       round(avg_sleep, 1) AS avg_sleep_hours,
       round(sleep_variability, 2) AS sleep_std_dev,
       CASE WHEN sleep_variability < 0.5 THEN 'Consistent'
            WHEN sleep_variability < 1.0 THEN 'Moderate variation'
            ELSE 'Irregular (risk factor)' END AS consistency,
       size(days) AS days_tracked
ORDER BY w.iso;


// ----------------------------------------------------------
// Q12: Days with optimal longevity markers (compound score)
//
// "Green days" = days hitting multiple longevity targets:
//   HRV > personal median, RHR < personal median,
//   7+ hours sleep, 8000+ steps, any workout.
// ----------------------------------------------------------

MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.hrv_mean IS NOT NULL AND s.resting_heart_rate IS NOT NULL
WITH avg(s.hrv_mean) AS median_hrv, avg(s.resting_heart_rate) AS median_rhr
MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WITH d, s, median_hrv, median_rhr,
     CASE WHEN s.hrv_mean > median_hrv THEN 1 ELSE 0 END +
     CASE WHEN s.resting_heart_rate < median_rhr THEN 1 ELSE 0 END +
     CASE WHEN s.sleep_hours >= 7 THEN 1 ELSE 0 END +
     CASE WHEN s.total_steps >= 8000 THEN 1 ELSE 0 END +
     CASE WHEN s.workout_count > 0 THEN 1 ELSE 0 END AS longevity_score
RETURN d.date AS date,
       d.day_of_week AS day,
       longevity_score AS score_out_of_5,
       s.hrv_mean AS hrv,
       s.resting_heart_rate AS rhr,
       s.sleep_hours AS sleep,
       s.total_steps AS steps,
       s.workout_count AS workouts
ORDER BY longevity_score DESC, d.date DESC
LIMIT 30;


// ----------------------------------------------------------
// Q13: Steps and daily movement (NEAT — non-exercise activity)
//
// Daily step count is a strong longevity signal independent of
// formal exercise. 7,000-10,000 steps/day reduces mortality 50-70%.
// ----------------------------------------------------------

MATCH (d:Day)-[:PART_OF]->(w:Week)
MATCH (d)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.total_steps IS NOT NULL
RETURN w.iso AS week,
       round(avg(s.total_steps)) AS avg_daily_steps,
       min(s.total_steps) AS min_steps,
       max(s.total_steps) AS max_steps,
       sum(CASE WHEN s.total_steps >= 10000 THEN 1 ELSE 0 END) AS days_over_10k,
       sum(CASE WHEN s.total_steps < 5000 THEN 1 ELSE 0 END) AS sedentary_days,
       count(*) AS days
ORDER BY w.iso;


// ----------------------------------------------------------
// Q14: Blood oxygen saturation trends (respiratory health)
//
// Chronic low SpO2 (<95%) can indicate respiratory or
// cardiovascular issues. Tracking trends catches decline early.
// ----------------------------------------------------------

MATCH (d:Day)-[:PART_OF]->(w:Week)
MATCH (d)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.avg_blood_oxygen IS NOT NULL
RETURN w.iso AS week,
       round(avg(s.avg_blood_oxygen), 1) AS avg_spo2,
       round(min(s.avg_blood_oxygen), 1) AS min_spo2,
       sum(CASE WHEN s.avg_blood_oxygen < 95 THEN 1 ELSE 0 END) AS low_spo2_days,
       count(*) AS readings
ORDER BY w.iso;


// ----------------------------------------------------------
// Q15: Workout impact on next-day HRV (training adaptation)
//
// After a hard workout, HRV should dip then recover within 24-48h.
// Persistent HRV suppression signals overtraining / poor recovery.
// ----------------------------------------------------------

MATCH (w:Workout)-[:ON_DAY]->(d1:Day)-[:HAS_SUMMARY]->(s1:DailySummary)
MATCH (d1)-[:NEXT_DAY]->(d2:Day)-[:HAS_SUMMARY]->(s2:DailySummary)
WHERE s1.hrv_mean IS NOT NULL AND s2.hrv_mean IS NOT NULL
RETURN w.activity_type AS workout_type,
       count(*) AS occurrences,
       round(avg(s1.hrv_mean), 1) AS avg_hrv_workout_day,
       round(avg(s2.hrv_mean), 1) AS avg_hrv_next_day,
       round(avg(s2.hrv_mean - s1.hrv_mean), 1) AS avg_hrv_change,
       round(avg(w.duration_min), 1) AS avg_duration_min
ORDER BY avg_hrv_change DESC;


// ----------------------------------------------------------
// Q16: Training load vs recovery balance (overtraining check)
//
// High training load with declining HRV = overtraining risk.
// This finds weeks where training was high but recovery suffered.
// ----------------------------------------------------------

MATCH (d:Day)-[:PART_OF]->(w:Week)
MATCH (d)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.hrv_mean IS NOT NULL
WITH w,
     sum(s.workout_minutes) AS weekly_training_min,
     avg(s.hrv_mean) AS weekly_avg_hrv,
     avg(s.resting_heart_rate) AS weekly_avg_rhr,
     avg(s.sleep_hours) AS weekly_avg_sleep
RETURN w.iso AS week,
       round(weekly_training_min, 0) AS training_minutes,
       round(weekly_avg_hrv, 1) AS avg_hrv,
       round(weekly_avg_rhr, 1) AS avg_rhr,
       round(weekly_avg_sleep, 1) AS avg_sleep,
       CASE
         WHEN weekly_training_min > 300 AND weekly_avg_hrv < 30 THEN 'OVERTRAINING RISK'
         WHEN weekly_training_min > 200 AND weekly_avg_hrv < 35 THEN 'CAUTION'
         ELSE 'OK'
       END AS alert
ORDER BY w.iso;


// ----------------------------------------------------------
// Q17: Rest day quality (active recovery effectiveness)
//
// True rest days (no formal workout) should show HRV recovery.
// If HRV stays suppressed on rest days, systemic stress is high.
// ----------------------------------------------------------

MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.workout_count = 0 AND s.hrv_mean IS NOT NULL
OPTIONAL MATCH (d_prev:Day)-[:NEXT_DAY]->(d)
OPTIONAL MATCH (d_prev)-[:HAS_SUMMARY]->(s_prev:DailySummary)
RETURN d.date AS rest_day,
       s.hrv_mean AS hrv,
       s.resting_heart_rate AS rhr,
       s.sleep_hours AS sleep,
       s.total_steps AS steps,
       s_prev.workout_count AS prev_day_workouts,
       s_prev.workout_minutes AS prev_day_training_min,
       s.hrv_mean - COALESCE(s_prev.hrv_mean, s.hrv_mean) AS hrv_recovery_delta
ORDER BY d.date DESC
LIMIT 30;


// ----------------------------------------------------------
// Q18: Weekly energy balance (metabolic health proxy)
//
// Consistent active energy expenditure supports metabolic health.
// Large swings may indicate feast/famine patterns.
// ----------------------------------------------------------

MATCH (d:Day)-[:PART_OF]->(w:Week)
MATCH (d)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.active_energy_kcal IS NOT NULL
RETURN w.iso AS week,
       round(avg(s.active_energy_kcal), 0) AS avg_daily_active_cal,
       round(avg(s.basal_energy_kcal), 0) AS avg_daily_basal_cal,
       round(avg(s.active_energy_kcal) + avg(s.basal_energy_kcal), 0) AS avg_total_cal,
       round(stDev(s.active_energy_kcal), 0) AS cal_variability,
       count(*) AS days
ORDER BY w.iso;


// ----------------------------------------------------------
// Q19: Month-over-month longevity dashboard
//
// High-level monthly view of the key longevity biomarkers.
// Track whether you're trending in the right direction.
// ----------------------------------------------------------

MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WITH d.date.year AS year, d.date.month AS month, s
RETURN year + '-' + right('0' + toString(month), 2) AS month,
       round(avg(s.resting_heart_rate), 1) AS avg_rhr,
       round(avg(s.hrv_mean), 1) AS avg_hrv,
       round(avg(s.vo2max), 1) AS avg_vo2max,
       round(avg(s.sleep_hours), 1) AS avg_sleep,
       round(avg(s.total_steps), 0) AS avg_steps,
       round(sum(s.workout_minutes), 0) AS total_workout_min,
       sum(s.workout_count) AS total_workouts,
       round(avg(s.avg_blood_oxygen), 1) AS avg_spo2,
       count(*) AS days_tracked
ORDER BY month;


// ----------------------------------------------------------
// Q20: Personal bests and progress milestones
//
// Tracking improvements over time reinforces healthy behaviors.
// This finds your best performances across key longevity metrics.
// ----------------------------------------------------------

// Best HRV day
MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.hrv_mean IS NOT NULL
WITH d, s ORDER BY s.hrv_mean DESC LIMIT 1
RETURN 'Highest HRV' AS milestone, d.date AS date,
       s.hrv_mean + ' ms' AS value, s.sleep_hours AS sleep_context

UNION

// Lowest resting HR
MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.resting_heart_rate IS NOT NULL
WITH d, s ORDER BY s.resting_heart_rate ASC LIMIT 1
RETURN 'Lowest Resting HR' AS milestone, d.date AS date,
       s.resting_heart_rate + ' bpm' AS value, s.sleep_hours AS sleep_context

UNION

// Highest VO2max
MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.vo2max IS NOT NULL
WITH d, s ORDER BY s.vo2max DESC LIMIT 1
RETURN 'Highest VO2max' AS milestone, d.date AS date,
       s.vo2max + ' mL/kg/min' AS value, s.sleep_hours AS sleep_context

UNION

// Most steps in a day
MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.total_steps IS NOT NULL
WITH d, s ORDER BY s.total_steps DESC LIMIT 1
RETURN 'Most Steps' AS milestone, d.date AS date,
       s.total_steps + ' steps' AS value, s.sleep_hours AS sleep_context

UNION

// Best sleep night
MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.sleep_hours IS NOT NULL AND s.sleep_hours <= 10
WITH d, s ORDER BY s.sleep_hours DESC LIMIT 1
RETURN 'Longest Quality Sleep' AS milestone, d.date AS date,
       s.sleep_hours + ' hours' AS value, s.hrv_mean AS sleep_context;
