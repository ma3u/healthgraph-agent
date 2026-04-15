# Aura Agent configuration

## System prompt

```
You are HealthGraph Agent, a personal health analytics assistant. You have access
to a Neo4j knowledge graph containing Apple Health data: daily summaries (heart rate,
HRV, steps, sleep, energy, SpO2), workouts, sleep sessions, and temporal relationships
between them.

Your role is to help the user understand patterns in their health data by querying the
graph. You can:
- Show weekly/monthly health overviews
- Analyze how workouts affect sleep and recovery (HRV)
- Find correlations between health metrics
- Identify best and worst recovery days
- Compare health trends over time

When answering, explain what the data shows and why the graph relationships matter.
Use specific numbers and dates from the query results. If the user asks about
causation, remind them that correlation in the data doesn't prove causation.

The graph has these key node types:
- Day: date, day_of_week, ring data (move/exercise/stand)
- DailySummary: avg_heart_rate, resting_heart_rate, hrv_mean, total_steps,
  sleep_hours, active_energy_kcal, workout_count, workout_minutes, vo2max, etc.
- Workout: activity_type, duration_min, total_energy_burned, total_distance
- SleepSession: asleep_minutes, in_bed_minutes
- Week: iso, year, week_number

Key relationships:
- (Day)-[:HAS_SUMMARY]->(DailySummary)
- (Day)-[:NEXT_DAY]->(Day)
- (Workout)-[:ON_DAY]->(Day)
- (SleepSession)-[:ON_DAY]->(Day)
- (Workout)-[:FOLLOWED_BY {hours_between}]->(SleepSession)
- (Day)-[:PART_OF]->(Week)
```

## Tools to configure in Aura Console

### 1. Cypher Template: Weekly overview

**Name**: `weekly_overview`
**Description**: Show daily health metrics for a given date range
**Parameters**: `start_date` (string, YYYY-MM-DD), `end_date` (string, YYYY-MM-DD)

```cypher
MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE d.date >= date($start_date) AND d.date <= date($end_date)
RETURN d.date AS date, d.day_of_week AS day,
       s.total_steps AS steps, s.avg_heart_rate AS avg_hr,
       s.resting_heart_rate AS resting_hr, s.hrv_mean AS hrv,
       s.sleep_hours AS sleep_h, s.active_energy_kcal AS active_kcal,
       s.workout_count AS workouts, s.workout_minutes AS workout_min
ORDER BY d.date
```

### 2. Cypher Template: Workout impact

**Name**: `workout_sleep_impact`
**Description**: Analyze how a workout type affects sleep and next-day recovery
**Parameters**: `workout_type` (string, e.g. "Running")

```cypher
MATCH (w:Workout)-[:FOLLOWED_BY]->(sl:SleepSession)
MATCH (w)-[:ON_DAY]->(d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
OPTIONAL MATCH (d)-[:NEXT_DAY]->(d2:Day)-[:HAS_SUMMARY]->(s2:DailySummary)
WHERE w.activity_type = $workout_type
RETURN d.date AS workout_date, w.duration_min AS duration,
       w.total_energy_burned AS energy, sl.asleep_minutes / 60.0 AS sleep_after,
       s.hrv_mean AS hrv_workout_day, s2.hrv_mean AS hrv_next_day
ORDER BY d.date DESC LIMIT 20
```

### 3. Text2Cypher

Enable this tool so the agent can generate Cypher from natural language.
The graph schema is auto-detected by Aura Agent.

### 4. Similarity Search (optional)

**Requires**: Vector index on `DailySummary.description`
**Embedding model**: `gemini-embedding-001` or `text-embedding-3-small`

Create vector index:
```cypher
CREATE VECTOR INDEX daily_summary_embedding IF NOT EXISTS
FOR (s:DailySummary)
ON s.embedding
OPTIONS {indexConfig: {
  `vector.dimensions`: 768,
  `vector.similarity_function`: 'cosine'
}}
```

## Test questions

After setting up the agent, test with these:

1. "How was my health last week?"
2. "How does running affect my sleep?"
3. "Show me my best recovery days — what did I do the day before?"
4. "What are my weekly step trends for the last 3 months?"
5. "On days where my HRV was above 50ms, how much did I sleep?"
6. "Compare my workout intensity across different activity types"
