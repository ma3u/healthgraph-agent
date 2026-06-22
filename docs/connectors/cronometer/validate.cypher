// ============================================================
// HealthGraph Agent — validate the Cronometer silo
// ============================================================
// Read-only sanity checks to run AFTER:
//   python etl/load_cronometer.py --daily-nutrition <file> --biometrics <file>
//
// Paste each block into Neo4j Browser / Aura Query. Nothing here writes.
// ============================================================


// ------------------------------------------------------------
// 1. The source landed, and how many observations of each kind.
// ------------------------------------------------------------
MATCH (:Source {name: 'cronometer'})-[:RECORDED]->(o:Observation)
RETURN o.category AS category, count(*) AS observations
ORDER BY observations DESC;


// ------------------------------------------------------------
// 2. Coverage: how many days got Cronometer data, and the span.
// ------------------------------------------------------------
MATCH (o:Observation {source: 'cronometer'})-[:ON_DAY]->(d:Day)
RETURN count(DISTINCT d) AS days_with_data,
       min(d.date) AS first_day,
       max(d.date) AS last_day;


// ------------------------------------------------------------
// 3. Daily macros for the most recent 7 logged days (pivot-ish).
// ------------------------------------------------------------
MATCH (o:Observation {source: 'cronometer', category: 'nutrition'})-[:ON_DAY]->(d:Day)
WHERE o.type IN ['Energy', 'Protein', 'Carbs', 'Fat']
WITH d.date AS day, collect([o.type, o.value]) AS macros
RETURN day,
       [m IN macros WHERE m[0] = 'Energy'  | m[1]][0] AS kcal,
       [m IN macros WHERE m[0] = 'Protein' | m[1]][0] AS protein_g,
       [m IN macros WHERE m[0] = 'Carbs'   | m[1]][0] AS carbs_g,
       [m IN macros WHERE m[0] = 'Fat'     | m[1]][0] AS fat_g
ORDER BY day DESC
LIMIT 7;


// ------------------------------------------------------------
// 4. Latest body weight (most recent Weight biometric).
// ------------------------------------------------------------
MATCH (o:Observation {source: 'cronometer', type: 'Weight'})-[:ON_DAY]->(d:Day)
RETURN d.date AS day, o.time AS time, o.value AS weight, o.unit AS unit
ORDER BY day DESC, time DESC
LIMIT 1;


// ------------------------------------------------------------
// 5. THE EHR PAYOFF — join nutrition to the recovery spine.
//    "On days I ate more protein, how did my recovery / resting HR look?"
//    Requires the Apple-Health ETL to have loaded DailySummary nodes.
// ------------------------------------------------------------
MATCH (o:Observation {source: 'cronometer', type: 'Protein'})-[:ON_DAY]->(d:Day)
MATCH (d)-[:HAS_SUMMARY]->(s:DailySummary)
RETURN d.date AS day,
       o.value AS protein_g,
       s.resting_heart_rate AS resting_hr,
       s.hrv_mean AS hrv
ORDER BY day DESC
LIMIT 14;


// ------------------------------------------------------------
// 6. Idempotency proof: no duplicate keys (re-running the load is safe).
// ------------------------------------------------------------
MATCH (o:Observation {source: 'cronometer'})
WITH o.key AS key, count(*) AS n
WHERE n > 1
RETURN key, n
ORDER BY n DESC;
// Expected: zero rows.
