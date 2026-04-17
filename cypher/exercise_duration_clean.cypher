// ─────────────────────────────────────────────────────────────────────────────
//  Exercise duration — CLEANED queries
//
//  Raw `Workout.duration_min` has two data-quality issues:
//
//   A) "Runaway" sessions where an Apple Watch workout was never stopped and
//      keeps running for 12–26 h (seen on 50+ days, mostly HIIT).
//   B) Cross-app double-tracking: the same physical activity is recorded by
//      two sources (e.g. Komoot + Apple Watch for a ride, Home Workouts +
//      Apple Watch for strength). Adds ~3 % overall, concentrated in 2025.
//
//  Cleaning rules applied below:
//
//   R1  Clamp each workout's effective duration at 240 min (4 h ceiling).
//   R2  Per (day, activity_type), take the MAX across sources — assumes that
//       two sources on the same day/type recorded the same session.
//   R3  Sum across activity types to get the day total.
//
//  All queries return hours and minutes separately so NeoDash / the Aura Agent
//  can display "hh:mm" without APOC.
// ─────────────────────────────────────────────────────────────────────────────


// Q1 — Daily exercise duration (cleaned)
MATCH (w:Workout)-[:ON_DAY]->(d:Day)
WITH d.date                                                       AS day,
     w.activity_type                                              AS type,
     w.source_name                                                AS source,
     sum(CASE WHEN w.duration_min > 240 THEN 240.0
              ELSE w.duration_min END)                            AS source_min
WITH day, type, max(source_min) AS type_min
WITH day, sum(type_min) AS day_min
RETURN day,
       toInteger(day_min) / 60 AS h,
       toInteger(day_min) % 60 AS m,
       round(day_min, 1)       AS total_min
ORDER BY day DESC;


// Q2 — Weekly exercise duration (cleaned)
MATCH (w:Workout)-[:ON_DAY]->(d:Day)
WITH d, w,
     CASE WHEN w.duration_min > 240 THEN 240.0 ELSE w.duration_min END AS mins_clean
WITH d.date AS day, w.activity_type AS type, w.source_name AS source,
     sum(mins_clean) AS source_min
WITH day, type, max(source_min) AS type_min
WITH day, sum(type_min) AS day_min
WITH day.year                                   AS yr,
     day.week                                   AS wk,
     date.truncate('week', day)                 AS week_start,
     sum(day_min)                               AS week_min,
     count(DISTINCT day)                        AS active_days
RETURN yr, wk, week_start, active_days,
       toInteger(week_min) / 60 AS h,
       toInteger(week_min) % 60 AS m,
       round(week_min / 60.0, 2) AS hours_float
ORDER BY week_start DESC;


// Q3 — Monthly exercise duration (cleaned)
MATCH (w:Workout)-[:ON_DAY]->(d:Day)
WITH d, w,
     CASE WHEN w.duration_min > 240 THEN 240.0 ELSE w.duration_min END AS mins_clean
WITH d.date AS day, w.activity_type AS type, w.source_name AS source,
     sum(mins_clean) AS source_min
WITH day, type, max(source_min) AS type_min
WITH day, sum(type_min) AS day_min
WITH day.year AS yr, day.month AS mo,
     sum(day_min)        AS month_min,
     count(DISTINCT day) AS active_days
RETURN toString(yr) + '-' +
       right('0' + toString(mo), 2)           AS month,
       active_days,
       toInteger(month_min) / 60              AS h,
       toInteger(month_min) % 60              AS m,
       round(month_min / 60.0, 1)             AS hours_float,
       round(month_min / active_days, 1)      AS avg_min_per_active_day
ORDER BY month;


// Q4 — Yearly trend (cleaned)
MATCH (w:Workout)-[:ON_DAY]->(d:Day)
WITH d, w,
     CASE WHEN w.duration_min > 240 THEN 240.0 ELSE w.duration_min END AS mins_clean
WITH d.date AS day, w.activity_type AS type, w.source_name AS source,
     sum(mins_clean) AS source_min
WITH day, type, max(source_min) AS type_min
WITH day, sum(type_min) AS day_min
WITH day.year AS yr,
     sum(day_min)                   AS year_min,
     count(DISTINCT day)            AS active_days,
     count(DISTINCT day.week)       AS weeks_covered
RETURN yr, active_days, weeks_covered,
       toInteger(year_min) / 60                          AS h,
       toInteger(year_min) % 60                          AS m,
       round(year_min / 60.0, 1)                         AS total_hours,
       round(year_min / active_days, 1)                  AS avg_min_per_active_day,
       round(year_min / weeks_covered / 60.0, 2)         AS avg_hours_per_week
ORDER BY yr;


// Q5 — Audit: raw vs cleaned — shows how much was removed per month
MATCH (w:Workout)-[:ON_DAY]->(d:Day)
WITH d.date.year AS yr, d.date.month AS mo,
     sum(w.duration_min) AS raw_min
MATCH (w2:Workout)-[:ON_DAY]->(d2:Day)
WHERE d2.date.year = yr AND d2.date.month = mo
WITH yr, mo, raw_min, d2, w2,
     CASE WHEN w2.duration_min > 240 THEN 240.0 ELSE w2.duration_min END AS mc
WITH yr, mo, raw_min, d2.date AS day, w2.activity_type AS t, w2.source_name AS s,
     sum(mc) AS src_min
WITH yr, mo, raw_min, day, t, max(src_min) AS tm
WITH yr, mo, raw_min, sum(tm) AS clean_min
RETURN toString(yr) + '-' + right('0' + toString(mo), 2) AS month,
       round(raw_min/60.0, 1)                        AS raw_hours,
       round(clean_min/60.0, 1)                      AS clean_hours,
       round((raw_min - clean_min)/60.0, 1)          AS removed_hours,
       round(100.0 * (raw_min - clean_min) / raw_min, 1) AS removed_pct
ORDER BY month;


// Q6 — Data-quality diagnostics: runaway single workouts (>4 h)
MATCH (w:Workout)-[:ON_DAY]->(d:Day)
WHERE w.duration_min > 240
RETURN d.date                              AS day,
       w.activity_type                     AS type,
       w.source_name                       AS source,
       toInteger(w.duration_min) / 60      AS h,
       toInteger(w.duration_min) % 60      AS m,
       w.start_date                        AS start,
       w.end_date                          AS end
ORDER BY w.duration_min DESC;


// Q7 — Data-quality diagnostics: cross-source overlapping workouts
MATCH (w1:Workout)-[:ON_DAY]->(d:Day)<-[:ON_DAY]-(w2:Workout)
WHERE w1.uid < w2.uid
  AND w1.source_name <> w2.source_name
  AND w1.start_date  <  w2.end_date
  AND w2.start_date  <  w1.end_date
RETURN d.date                                          AS day,
       w1.source_name + ' / ' + w1.activity_type       AS source_a,
       round(w1.duration_min, 1)                       AS a_min,
       w2.source_name + ' / ' + w2.activity_type       AS source_b,
       round(w2.duration_min, 1)                       AS b_min,
       round(
         CASE WHEN w1.duration_min < w2.duration_min
              THEN w1.duration_min
              ELSE w2.duration_min END, 1)              AS deducted_min
ORDER BY day DESC;
