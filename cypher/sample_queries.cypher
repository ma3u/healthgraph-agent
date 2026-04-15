// ============================================================
// HealthGraph Agent — Cypher Template Queries
// For use as Aura Agent Cypher Template tools
// ============================================================


// ----------------------------------------------------------
// TOOL 1: Weekly health overview
// Parameters: $start_date, $end_date (YYYY-MM-DD strings)
// ----------------------------------------------------------

// Show daily health summaries for a date range with activity ring completion
MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE d.date >= date($start_date) AND d.date <= date($end_date)
RETURN d.date AS date,
       d.day_of_week AS day,
       s.total_steps AS steps,
       s.avg_heart_rate AS avg_hr,
       s.resting_heart_rate AS resting_hr,
       s.hrv_mean AS hrv,
       s.sleep_hours AS sleep_h,
       s.active_energy_kcal AS active_kcal,
       s.workout_count AS workouts,
       s.workout_minutes AS workout_min,
       d.ring_move AS move_cal,
       d.ring_move_goal AS move_goal
ORDER BY d.date


// ----------------------------------------------------------
// TOOL 2: Workout → sleep impact analysis
// Parameters: $workout_type (e.g. "Running", "TraditionalStrengthTraining")
// ----------------------------------------------------------

// Show how workouts of a given type affect the following night's sleep and next-day HRV
MATCH (w:Workout)-[:FOLLOWED_BY]->(sl:SleepSession)
MATCH (w)-[:ON_DAY]->(d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
OPTIONAL MATCH (d)-[:NEXT_DAY]->(d2:Day)-[:HAS_SUMMARY]->(s2:DailySummary)
WHERE w.activity_type = $workout_type
RETURN d.date AS workout_date,
       w.duration_min AS duration_min,
       w.total_energy_burned AS energy_burned,
       sl.asleep_minutes / 60.0 AS sleep_hours_after,
       s.hrv_mean AS hrv_workout_day,
       s2.hrv_mean AS hrv_next_day,
       s2.resting_heart_rate AS resting_hr_next_day
ORDER BY d.date DESC
LIMIT 20


// ----------------------------------------------------------
// TOOL 3: Best and worst recovery days
// ----------------------------------------------------------

// Find the top 10 highest-HRV days and what preceded them
MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.hrv_mean IS NOT NULL
OPTIONAL MATCH (d_prev:Day)-[:NEXT_DAY]->(d)
OPTIONAL MATCH (d_prev)-[:HAS_SUMMARY]->(s_prev:DailySummary)
OPTIONAL MATCH (w:Workout)-[:ON_DAY]->(d_prev)
RETURN d.date AS date,
       s.hrv_mean AS hrv,
       s.resting_heart_rate AS resting_hr,
       s.sleep_hours AS sleep,
       s_prev.workout_count AS prev_day_workouts,
       s_prev.workout_minutes AS prev_day_workout_min,
       s_prev.total_steps AS prev_day_steps,
       collect(DISTINCT w.activity_type) AS prev_day_workout_types
ORDER BY s.hrv_mean DESC
LIMIT 10


// ----------------------------------------------------------
// TOOL 4: Weekly trends comparison
// ----------------------------------------------------------

// Compare weekly averages across multiple dimensions
MATCH (d:Day)-[:PART_OF]->(w:Week)
MATCH (d)-[:HAS_SUMMARY]->(s:DailySummary)
RETURN w.iso AS week,
       w.start_date AS week_start,
       round(avg(s.total_steps)) AS avg_steps,
       round(avg(s.avg_heart_rate), 1) AS avg_hr,
       round(avg(s.hrv_mean), 1) AS avg_hrv,
       round(avg(s.sleep_hours), 1) AS avg_sleep,
       round(avg(s.active_energy_kcal), 0) AS avg_active_kcal,
       sum(s.workout_count) AS total_workouts,
       round(sum(s.workout_minutes), 0) AS total_workout_min
ORDER BY w.iso DESC
LIMIT 12


// ----------------------------------------------------------
// TOOL 5: Correlation finder — sleep vs next-day HRV
// ----------------------------------------------------------

// Show the relationship between sleep duration and next-day HRV
MATCH (d1:Day)-[:NEXT_DAY]->(d2:Day)
MATCH (d1)-[:HAS_SUMMARY]->(s1:DailySummary)
MATCH (d2)-[:HAS_SUMMARY]->(s2:DailySummary)
WHERE s1.sleep_hours IS NOT NULL AND s2.hrv_mean IS NOT NULL
RETURN d1.date AS sleep_date,
       s1.sleep_hours AS sleep_hours,
       s2.hrv_mean AS next_day_hrv,
       s2.resting_heart_rate AS next_day_resting_hr,
       s1.workout_count AS workout_count
ORDER BY d1.date DESC
LIMIT 90


// ----------------------------------------------------------
// TOOL 6: Workout type breakdown
// ----------------------------------------------------------

MATCH (w:Workout)
RETURN w.activity_type AS type,
       count(*) AS total,
       round(avg(w.duration_min), 1) AS avg_duration,
       round(avg(w.total_energy_burned), 0) AS avg_energy,
       round(avg(w.total_distance), 2) AS avg_distance
ORDER BY total DESC


// ----------------------------------------------------------
// TOOL 7: Device contribution
// ----------------------------------------------------------

MATCH (d:Device)-[:USES]-(p:Person)
OPTIONAL MATCH (d)-[:RECORDED]->(w:Workout)
RETURN d.name AS device,
       count(w) AS workouts_recorded
ORDER BY workouts_recorded DESC


// ----------------------------------------------------------
// EXPLORATION: Full graph schema overview
// ----------------------------------------------------------

// CALL db.schema.visualization()
