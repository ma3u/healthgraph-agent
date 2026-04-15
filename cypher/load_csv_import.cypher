// ============================================================
// HealthGraph Agent — LOAD CSV Import (Method 2)
// ============================================================
//
// Import health data from CSV files into Neo4j.
// Works with Neo4j Desktop (file:///) and Aura (https:// URLs).
//
// SETUP:
//   Neo4j Desktop: Copy data/csv/ folder into your database's import/ directory
//                  OR set dbms.directories.import in neo4j.conf to point at data/csv/
//   Neo4j Aura:   Upload CSVs to a web server and replace file:/// with the URL
//
// Run each block separately in Neo4j Browser (copy-paste one at a time).
// ============================================================


// ----------------------------------------------------------
// STEP 0: Create schema (constraints + indexes)
// ----------------------------------------------------------

CREATE CONSTRAINT person_name IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE;
CREATE CONSTRAINT device_name IF NOT EXISTS FOR (d:Device) REQUIRE d.name IS UNIQUE;
CREATE CONSTRAINT metric_type_id IF NOT EXISTS FOR (m:MetricType) REQUIRE m.identifier IS UNIQUE;
CREATE CONSTRAINT day_date IF NOT EXISTS FOR (d:Day) REQUIRE d.date IS UNIQUE;
CREATE CONSTRAINT week_iso IF NOT EXISTS FOR (w:Week) REQUIRE w.iso IS UNIQUE;
CREATE CONSTRAINT daily_summary_date IF NOT EXISTS FOR (s:DailySummary) REQUIRE s.date IS UNIQUE;
CREATE CONSTRAINT workout_id IF NOT EXISTS FOR (w:Workout) REQUIRE w.uid IS UNIQUE;
CREATE CONSTRAINT sleep_session_date IF NOT EXISTS FOR (s:SleepSession) REQUIRE s.date IS UNIQUE;

CREATE INDEX day_day_of_week IF NOT EXISTS FOR (d:Day) ON (d.day_of_week);
CREATE INDEX workout_type IF NOT EXISTS FOR (w:Workout) ON (w.activity_type);
CREATE INDEX metric_display IF NOT EXISTS FOR (m:MetricType) ON (m.display_name);


// ----------------------------------------------------------
// STEP 1: Load Person
// ----------------------------------------------------------

LOAD CSV WITH HEADERS FROM 'file:///person.csv' AS row
MERGE (p:Person {name: row.name})
SET p.date_of_birth = row.date_of_birth,
    p.biological_sex = row.biological_sex;


// ----------------------------------------------------------
// STEP 2: Load Devices + USES relationships
// ----------------------------------------------------------

LOAD CSV WITH HEADERS FROM 'file:///devices.csv' AS row
MERGE (d:Device {name: row.name})
WITH d
MATCH (p:Person {name: 'Me'})
MERGE (p)-[:USES]->(d);


// ----------------------------------------------------------
// STEP 3: Load MetricTypes
// ----------------------------------------------------------

LOAD CSV WITH HEADERS FROM 'file:///metric_types.csv' AS row
MERGE (m:MetricType {identifier: row.identifier})
SET m.display_name = row.display_name,
    m.unit = row.unit,
    m.category = row.category;


// ----------------------------------------------------------
// STEP 4: Load Weeks
// ----------------------------------------------------------

LOAD CSV WITH HEADERS FROM 'file:///weeks.csv' AS row
MERGE (w:Week {iso: row.iso})
SET w.year = toInteger(row.year),
    w.week_number = toInteger(row.week_number),
    w.start_date = date(row.start_date);


// ----------------------------------------------------------
// STEP 5: Load Days + DailySummaries
// ----------------------------------------------------------

LOAD CSV WITH HEADERS FROM 'file:///daily_summaries.csv' AS row
MERGE (d:Day {date: date(row.date)})
SET d.day_of_week = row.day_of_week
WITH d, row
MATCH (w:Week {iso: row.week_iso})
MERGE (d)-[:PART_OF]->(w)
WITH d, row
MERGE (s:DailySummary {date: date(row.date)})
SET s.avg_heart_rate = CASE WHEN row.avg_heart_rate <> '' THEN toFloat(row.avg_heart_rate) END,
    s.min_heart_rate = CASE WHEN row.min_heart_rate <> '' THEN toFloat(row.min_heart_rate) END,
    s.max_heart_rate = CASE WHEN row.max_heart_rate <> '' THEN toFloat(row.max_heart_rate) END,
    s.resting_heart_rate = CASE WHEN row.resting_heart_rate <> '' THEN toFloat(row.resting_heart_rate) END,
    s.hrv_mean = CASE WHEN row.hrv_mean <> '' THEN toFloat(row.hrv_mean) END,
    s.total_steps = CASE WHEN row.total_steps <> '' THEN toFloat(row.total_steps) END,
    s.total_distance_km = CASE WHEN row.total_distance_km <> '' THEN toFloat(row.total_distance_km) END,
    s.active_energy_kcal = CASE WHEN row.active_energy_kcal <> '' THEN toFloat(row.active_energy_kcal) END,
    s.basal_energy_kcal = CASE WHEN row.basal_energy_kcal <> '' THEN toFloat(row.basal_energy_kcal) END,
    s.flights_climbed = CASE WHEN row.flights_climbed <> '' THEN toFloat(row.flights_climbed) END,
    s.exercise_minutes = CASE WHEN row.exercise_minutes <> '' THEN toFloat(row.exercise_minutes) END,
    s.stand_hours = CASE WHEN row.stand_hours <> '' THEN toFloat(row.stand_hours) END,
    s.avg_blood_oxygen = CASE WHEN row.avg_blood_oxygen <> '' THEN toFloat(row.avg_blood_oxygen) END,
    s.avg_respiratory_rate = CASE WHEN row.avg_respiratory_rate <> '' THEN toFloat(row.avg_respiratory_rate) END,
    s.body_mass_kg = CASE WHEN row.body_mass_kg <> '' THEN toFloat(row.body_mass_kg) END,
    s.vo2max = CASE WHEN row.vo2max <> '' THEN toFloat(row.vo2max) END,
    s.sleep_hours = CASE WHEN row.sleep_hours <> '' THEN toFloat(row.sleep_hours) END,
    s.workout_count = CASE WHEN row.workout_count <> '' THEN toInteger(row.workout_count) END,
    s.workout_minutes = CASE WHEN row.workout_minutes <> '' THEN toFloat(row.workout_minutes) END,
    s.description = row.description
MERGE (d)-[:HAS_SUMMARY]->(s);


// ----------------------------------------------------------
// STEP 6: Load Workouts
// ----------------------------------------------------------

LOAD CSV WITH HEADERS FROM 'file:///workouts.csv' AS row
MERGE (w:Workout {uid: row.uid})
SET w.activity_type = row.activity_type,
    w.source_name = row.source_name,
    w.duration_min = CASE WHEN row.duration_min <> '' THEN toFloat(row.duration_min) END,
    w.total_distance = CASE WHEN row.total_distance <> '' THEN toFloat(row.total_distance) END,
    w.total_distance_unit = row.total_distance_unit,
    w.total_energy_burned = CASE WHEN row.total_energy_burned <> '' THEN toFloat(row.total_energy_burned) END,
    w.total_energy_burned_unit = row.total_energy_burned_unit,
    w.start_date = CASE WHEN row.start_date <> '' THEN datetime(row.start_date) END,
    w.end_date = CASE WHEN row.end_date <> '' THEN datetime(row.end_date) END,
    w.device = row.device
WITH w, row
WHERE row.date <> ''
MATCH (d:Day {date: date(row.date)})
MERGE (w)-[:ON_DAY]->(d);


// ----------------------------------------------------------
// STEP 7: Load Sleep Sessions
// ----------------------------------------------------------

LOAD CSV WITH HEADERS FROM 'file:///sleep_sessions.csv' AS row
MERGE (s:SleepSession {date: date(row.date)})
SET s.asleep_minutes = toFloat(row.asleep_minutes),
    s.in_bed_minutes = toFloat(row.in_bed_minutes),
    s.source_name = row.source_name
WITH s, row
MATCH (d:Day {date: date(row.date)})
MERGE (s)-[:ON_DAY]->(d);


// ----------------------------------------------------------
// STEP 8: Load NEXT_DAY relationships
// ----------------------------------------------------------

LOAD CSV WITH HEADERS FROM 'file:///temporal_rels.csv' AS row
WITH row WHERE row.rel_type = 'NEXT_DAY'
MATCH (d1:Day {date: date(row.from_id)})
MATCH (d2:Day {date: date(row.to_id)})
MERGE (d1)-[:NEXT_DAY]->(d2);


// ----------------------------------------------------------
// STEP 9: Load FOLLOWED_BY relationships (Workout → Sleep)
// ----------------------------------------------------------

LOAD CSV WITH HEADERS FROM 'file:///temporal_rels.csv' AS row
WITH row WHERE row.rel_type = 'FOLLOWED_BY'
MATCH (w:Workout {uid: row.from_id})
MATCH (s:SleepSession {date: date(row.to_id)})
MERGE (w)-[r:FOLLOWED_BY]->(s)
SET r.hours_between = CASE WHEN row.hours_between <> '' THEN toFloat(row.hours_between) END;


// ----------------------------------------------------------
// STEP 10: Load Activity Summaries (ring data onto Day nodes)
// ----------------------------------------------------------

LOAD CSV WITH HEADERS FROM 'file:///activity_summaries.csv' AS row
MATCH (d:Day {date: date(row.date)})
SET d.ring_move = CASE WHEN row.active_energy_burned <> '' THEN toFloat(row.active_energy_burned) END,
    d.ring_move_goal = CASE WHEN row.active_energy_burned_goal <> '' THEN toFloat(row.active_energy_burned_goal) END,
    d.ring_exercise = CASE WHEN row.apple_exercise_time <> '' THEN toFloat(row.apple_exercise_time) END,
    d.ring_exercise_goal = CASE WHEN row.apple_exercise_time_goal <> '' THEN toFloat(row.apple_exercise_time_goal) END,
    d.ring_stand = CASE WHEN row.apple_stand_hours <> '' THEN toFloat(row.apple_stand_hours) END,
    d.ring_stand_goal = CASE WHEN row.apple_stand_hours_goal <> '' THEN toFloat(row.apple_stand_hours_goal) END;


// ----------------------------------------------------------
// STEP 11: Link Workouts to Devices
// ----------------------------------------------------------

LOAD CSV WITH HEADERS FROM 'file:///workouts.csv' AS row
WITH row WHERE row.device <> ''
MATCH (w:Workout {uid: row.uid})
MATCH (d:Device {name: row.device})
MERGE (d)-[:RECORDED]->(w);


// ----------------------------------------------------------
// VERIFY: Count nodes and relationships
// ----------------------------------------------------------

MATCH (n)
RETURN labels(n)[0] AS label, count(*) AS count
ORDER BY count DESC;

// MATCH ()-[r]->()
// RETURN type(r) AS type, count(*) AS count
// ORDER BY count DESC;
