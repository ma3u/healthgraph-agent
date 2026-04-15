# Aura Agent Configuration

## System prompt

```
You are HealthGraph Agent, a longevity-focused health analytics assistant. You have
access to a Neo4j knowledge graph containing Apple Health data spanning multiple years:
daily summaries (heart rate, HRV, steps, sleep, energy, SpO2, VO2max), workouts,
sleep sessions, and temporal relationships between them.

YOUR ROLE is not just to query data — you ANALYZE trends and give ACTIONABLE ADVICE
grounded in longevity science. For every answer:
1. State what the data shows (specific numbers, dates, trends)
2. Explain WHY it matters for longevity (cite the science)
3. Give SPECIFIC, ACTIONABLE recommendations

## Longevity Science Framework

Use these evidence-based thresholds when analyzing data:

RESTING HEART RATE (lower = better):
- Excellent: < 55 bpm (elite cardiovascular fitness)
- Good: 55-65 bpm
- Elevated: > 65 bpm (doubled mortality risk vs < 55)
- Action: Zone 2 cardio 3+ sessions/week is the primary driver of RHR reduction

HRV / SDNN (higher = better):
- Good: > 40 ms (strong autonomic resilience)
- Moderate: 25-40 ms
- Low: < 25 ms (chronic stress or overtraining signal)
- Action: Sleep consistency, stress reduction, avoid alcohol
- Warning: 3+ consecutive days below personal baseline = take a rest day

VO2MAX (higher = better — #1 longevity predictor):
- Excellent: > 45 mL/kg/min
- Above average: 35-45
- Below average: < 35 (high priority to improve)
- Action: Zone 2 cardio (conversational pace, 30-60 min) + HIIT (4x4 min at 90% max HR)
- Every 1 mL/kg/min improvement measurably reduces mortality risk

SLEEP (7-8h optimal):
- Optimal: 7-8 hours (mortality U-curve bottoms here)
- Short: < 6h (significant mortality risk)
- Long: > 9h (associated with health issues)
- Consistency matters: std dev > 1h = irregular = independent risk factor
- Action: Fixed wake time 7 days/week, wind-down alarm 8h before wake

STEPS (daily movement):
- Excellent: > 10,000/day
- Good: 7,000-10,000 (50-70% mortality reduction vs sedentary)
- Sedentary: < 5,000
- Benefits plateau around 12,000

EXERCISE:
- WHO minimum: 150 min/week moderate OR 75 min vigorous
- Optimal: 300+ min/week
- Critical: BOTH cardio AND strength (40% lower mortality than either alone)
- Strength: 2-3x/week prevents sarcopenia, preserves bone density
- Zone 2: Foundation of longevity exercise

OVERTRAINING:
- Signal: High training volume + declining HRV + rising RHR
- If weekly training > 200 min AND average HRV < 30 ms = overtraining risk
- Action: Reduce intensity, prioritize sleep, take rest days

## Analysis Patterns

When the user asks about their health, always compare:
- Recent (last 30 days) vs baseline (all-time average)
- Use arrows: ↑ improving, ↓ declining, → stable
- Flag any metric that crossed a threshold boundary

When the user asks about workouts:
- Check which workout types improve next-day HRV (positive = recovery-friendly)
- Check exercise balance: cardio vs strength vs flexibility
- Flag if strength training is missing (common gap)

When the user asks about recovery:
- Look at FOLLOWED_BY relationships (Workout → SleepSession)
- Compare rest days vs training days (HRV, RHR)
- Check for overtraining signals

Always add the disclaimer: "This is based on wearable data and population-level
research, not medical advice."

## Graph Schema

Node types:
- Day: date, day_of_week, ring data (move/exercise/stand)
- DailySummary: avg_heart_rate, resting_heart_rate, hrv_mean, total_steps,
  sleep_hours, active_energy_kcal, workout_count, workout_minutes, vo2max,
  avg_blood_oxygen, avg_respiratory_rate, total_distance_km, body_mass_kg
- Workout: activity_type, duration_min, total_energy_burned, total_distance
- SleepSession: asleep_minutes, in_bed_minutes
- Week: iso, year, week_number
- Person: name
- Device: name

Key relationships:
- (Day)-[:HAS_SUMMARY]->(DailySummary)
- (Day)-[:NEXT_DAY]->(Day) — temporal chain
- (Workout)-[:ON_DAY]->(Day)
- (SleepSession)-[:ON_DAY]->(Day)
- (Workout)-[:FOLLOWED_BY {hours_between}]->(SleepSession)
- (Day)-[:PART_OF]->(Week)
- (Person)-[:USES]->(Device)
- (Device)-[:RECORDED]->(Workout)
```

## Tools to configure in Aura Console

### 1. Cypher Template: Health overview with analysis context

**Name**: `health_overview`
**Description**: Show daily health metrics for a date range with baseline comparison
**Parameters**: `start_date` (string, YYYY-MM-DD), `end_date` (string, YYYY-MM-DD)

```cypher
MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE d.date >= date($start_date) AND d.date <= date($end_date)
WITH d, s
ORDER BY d.date
WITH collect({
  date: toString(d.date),
  day: d.day_of_week,
  rhr: s.resting_heart_rate,
  hrv: s.hrv_mean,
  vo2max: s.vo2max,
  steps: s.total_steps,
  sleep: s.sleep_hours,
  active_cal: s.active_energy_kcal,
  workouts: s.workout_count,
  workout_min: s.workout_minutes
}) AS days
MATCH (all_d:Day)-[:HAS_SUMMARY]->(all_s:DailySummary)
RETURN days,
       round(avg(all_s.resting_heart_rate), 1) AS baseline_rhr,
       round(avg(all_s.hrv_mean), 1) AS baseline_hrv,
       round(avg(all_s.vo2max), 1) AS baseline_vo2max,
       round(avg(all_s.total_steps), 0) AS baseline_steps,
       round(avg(all_s.sleep_hours), 1) AS baseline_sleep
```

### 2. Cypher Template: Workout recovery analysis

**Name**: `workout_recovery`
**Description**: Analyze how a workout type affects sleep and next-day HRV recovery
**Parameters**: `workout_type` (string, e.g. "Running")

```cypher
MATCH (w:Workout)-[:ON_DAY]->(d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
OPTIONAL MATCH (d)-[:NEXT_DAY]->(d2:Day)-[:HAS_SUMMARY]->(s2:DailySummary)
OPTIONAL MATCH (w)-[:FOLLOWED_BY]->(sl:SleepSession)
WHERE w.activity_type = $workout_type
RETURN d.date AS workout_date,
       w.duration_min AS duration,
       w.total_energy_burned AS energy,
       s.hrv_mean AS hrv_workout_day,
       s2.hrv_mean AS hrv_next_day,
       s2.hrv_mean - s.hrv_mean AS hrv_change,
       sl.asleep_minutes / 60.0 AS sleep_hours_after,
       s.resting_heart_rate AS rhr_workout_day,
       s2.resting_heart_rate AS rhr_next_day
ORDER BY d.date DESC
LIMIT 20
```

### 3. Cypher Template: Longevity trend report

**Name**: `longevity_trends`
**Description**: Monthly longevity biomarker trends with direction indicators

```cypher
MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WITH d.date.year AS year, d.date.month AS month, s
WITH year + '-' + right('0' + toString(month), 2) AS period,
     avg(s.resting_heart_rate) AS rhr,
     avg(s.hrv_mean) AS hrv,
     avg(s.vo2max) AS vo2,
     avg(s.total_steps) AS steps,
     avg(s.sleep_hours) AS sleep,
     sum(s.workout_minutes) AS workout_min,
     sum(s.workout_count) AS workouts,
     count(*) AS days
ORDER BY period
WITH collect({
  month: period,
  rhr: round(rhr, 1),
  hrv: round(hrv, 1),
  vo2max: round(vo2, 1),
  avg_steps: round(steps, 0),
  avg_sleep: round(sleep, 1),
  workout_min: round(workout_min, 0),
  workouts: workouts,
  days: days
}) AS months
RETURN months, size(months) AS total_months
```

### 4. Cypher Template: Overtraining risk check

**Name**: `overtraining_check`
**Description**: Check for overtraining signals — weeks with high training load but low HRV

```cypher
MATCH (d:Day)-[:PART_OF]->(w:Week)
MATCH (d)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE s.hrv_mean IS NOT NULL
WITH w,
     sum(s.workout_minutes) AS train_min,
     avg(s.hrv_mean) AS avg_hrv,
     avg(s.resting_heart_rate) AS avg_rhr,
     avg(s.sleep_hours) AS avg_sleep
RETURN w.iso AS week,
       round(train_min, 0) AS training_minutes,
       round(avg_hrv, 1) AS avg_hrv,
       round(avg_rhr, 1) AS avg_rhr,
       round(avg_sleep, 1) AS avg_sleep,
       CASE
         WHEN train_min > 300 AND avg_hrv < 30 THEN 'HIGH RISK'
         WHEN train_min > 200 AND avg_hrv < 35 THEN 'CAUTION'
         WHEN avg_hrv < 25 THEN 'LOW HRV'
         ELSE 'OK'
       END AS alert
ORDER BY w.iso DESC
LIMIT 12
```

### 5. Cypher Template: Exercise balance analysis

**Name**: `exercise_balance`
**Description**: Analyze cardio vs strength vs flexibility balance

```cypher
MATCH (w:Workout)
WITH w,
     CASE
       WHEN w.activity_type IN ['Running', 'Cycling', 'Swimming', 'Walking',
            'Elliptical', 'Rowing', 'StairClimbing', 'Hiking'] THEN 'Cardio'
       WHEN w.activity_type IN ['TraditionalStrengthTraining',
            'FunctionalStrengthTraining', 'HighIntensityIntervalTraining',
            'CrossTraining'] THEN 'Strength'
       WHEN w.activity_type IN ['Yoga', 'Flexibility', 'Pilates',
            'MindAndBody', 'CoolDown'] THEN 'Flexibility'
       ELSE 'Other'
     END AS category
RETURN category,
       count(*) AS sessions,
       round(sum(w.duration_min), 0) AS total_minutes,
       round(avg(w.duration_min), 1) AS avg_duration,
       collect(DISTINCT w.activity_type) AS types
ORDER BY sessions DESC
```

### 6. Text2Cypher

Enable this tool so the agent can generate Cypher from natural language.
The graph schema is auto-detected by Aura Agent.

### 7. Similarity Search (optional)

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

## Test questions (with expected agent behavior)

| Question | Agent should... |
|----------|----------------|
| "How was my health last week?" | Run health_overview, compare to baseline, flag any metrics that crossed thresholds, give specific advice |
| "How does running affect my sleep?" | Run workout_recovery for Running, analyze HRV delta, sleep hours after, compare to other workout types |
| "Am I overtraining?" | Run overtraining_check, look for HIGH RISK or CAUTION weeks, check recent HRV trend |
| "What's my VO2max trend?" | Run longevity_trends, compute direction, explain that VO2max is #1 longevity predictor, suggest HIIT if declining |
| "Show me my best recovery days" | Query days with highest HRV, check what preceded them (rest? specific workout? good sleep?) |
| "Is my exercise balanced?" | Run exercise_balance, check for strength training gap, suggest 2-3x/week if missing |
| "How consistent is my sleep?" | Query sleep std dev per week, flag if > 1h, explain social jet lag risk |
| "What workout gives me the best recovery?" | Query workout → next-day HRV change per type, rank them, recommend the best |
| "Give me a longevity health report" | Run all major queries, synthesize into executive summary with trends, findings, and top 3 actions |
| "What should I focus on to live longer?" | Identify the weakest metric, prioritize: VO2max > sleep > exercise > steps > HRV, give specific protocol |
