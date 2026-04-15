# Longevity Health Dashboard

HealthGraph Agent provides two visualization approaches for exploring your health data as longevity biomarkers: a **Python-generated chart dashboard** and an **interactive NeoDash dashboard** running inside Neo4j.

For a personalized analysis with actionable health advice, see the **[Longevity Health Analysis Report](HEALTH_REPORT.md)**.

---

## Python Chart Dashboard

Generate a multi-panel PNG dashboard and individual high-res charts directly from your Neo4j graph.

### Quick start

```bash
# Generate all charts (full history)
python3 scripts/visualize_longevity.py

# Last 6 months only
python3 scripts/visualize_longevity.py --months 6

# Custom output directory
python3 scripts/visualize_longevity.py --output my_charts/
```

### Requirements

```bash
pip3 install matplotlib pandas neo4j python-dotenv
```

### Output

Charts are saved to `data/charts/` by default:

| File | Description |
|------|-------------|
| `longevity_dashboard.png` | 8-panel overview (all charts in one image) |
| `rhr_trend.png` | Resting heart rate with longevity zones |
| `hrv_trend.png` | Heart rate variability trend |
| `vo2max_trend.png` | VO2max progression |
| `steps_trend.png` | Daily steps with 7k/10k targets |
| `sleep_trend.png` | Sleep duration with 7-8h optimal zone |
| `workout_volume.png` | Monthly workout minutes with 150 min/week target |
| `composite_trend.png` | Normalized composite of all key metrics |

### Dashboard preview

![Longevity Dashboard](images/python_dashboard.png)

### Dashboard panels explained

#### 1. Resting Heart Rate (lower = better)

Tracks your resting heart rate over time. Color zones:
- **Green (< 55 bpm)**: Excellent cardiovascular fitness
- **Yellow (55-65 bpm)**: Good
- **Red (> 65 bpm)**: Elevated — associated with higher mortality risk

RHR > 75 bpm is associated with doubled all-cause mortality risk compared to < 55 bpm. The white trend line shows your rolling average.

**Longevity science**: Lower RHR reflects greater cardiac efficiency — the heart pumps more blood per beat, requiring fewer beats at rest. Regular aerobic exercise is the primary driver of RHR reduction.

#### 2. Heart Rate Variability (higher = better)

HRV (SDNN) measures the variation in time between heartbeats — a proxy for autonomic nervous system health. Color zones:
- **Green (> 40 ms)**: Good parasympathetic tone
- **Yellow (25-40 ms)**: Moderate
- **Red (< 25 ms)**: Low — reduced stress resilience

**Longevity science**: Higher HRV indicates greater parasympathetic (rest-and-digest) activity. HRV naturally declines with age, but maintaining it through sleep quality, stress management, and exercise is protective. Acute drops often signal illness, overtraining, or poor sleep.

#### 3. VO2max — #1 Longevity Predictor (higher = better)

VO2max measures your body's maximum oxygen uptake during exercise. It is the single strongest predictor of all-cause mortality. Color zones:
- **Green (> 45)**: Excellent / superior
- **Yellow (35-45)**: Good / above average
- **Red (< 35)**: Below average

**Longevity science**: Moving from "low" to "above average" VO2max reduces mortality risk by ~50%. Every 1 mL/kg/min improvement matters. VO2max is improved through Zone 2 training (long, easy cardio) and high-intensity intervals (HIIT).

#### 4. Daily Steps (7k-10k+ optimal)

Daily step count with reference lines:
- **Dashed green**: 10,000 steps/day target
- **Dotted yellow**: 7,000 steps/day minimum for longevity benefit

**Longevity science**: 7,000-10,000 steps/day reduces all-cause mortality by 50-70% compared to sedentary levels. Benefits plateau above ~12,000 steps. Steps capture NEAT (non-exercise activity thermogenesis) — the daily movement that matters independent of formal exercise.

#### 5. Sleep Duration (7-8h optimal zone)

Sleep hours per night with the green optimal zone (7-9 hours).

**Longevity science**: Both short sleep (< 6h) and long sleep (> 9h) are associated with increased mortality in a U-shaped curve. The sweet spot is 7-8 hours. Sleep consistency (regular bed/wake times) is an independent factor — irregular sleepers have higher cardiovascular risk even at adequate duration.

#### 6. Monthly Workout Volume

Total workout minutes per month. Bars turn green when exceeding 600 minutes/month (equivalent to 150 minutes/week).

**Longevity science**: 150 min/week of moderate exercise (or 75 min vigorous) is the WHO minimum. 300+ min/week provides additional mortality reduction. Both cardio AND strength training are important — people who do both have 40% lower mortality than either alone.

#### 7. Workout Type Distribution

Horizontal bar chart showing the breakdown of workout types by count. Helps assess exercise variety — longevity benefits from a mix of cardio, strength, flexibility, and zone 2 training.

#### 8. Monthly Longevity Composite

All key metrics normalized to 0-1 scale (higher = better for all lines, RHR is inverted). This shows how your biomarkers move together or diverge over time:
- **RHR (inverted)** — red line
- **HRV** — green line
- **VO2max** — blue line
- **Steps** — yellow line

When lines converge upward: everything is trending well. When they diverge: something is off (e.g., high training volume but declining HRV = overtraining).

---

## NeoDash Interactive Dashboard

For an interactive, browser-based experience with clickable charts and graph visualizations.

![NeoDash Dashboard](images/neodash_dashboard.png)

### Setup

1. Open Neo4j Desktop
2. Go to the **Graph Apps** sidebar
3. Install **NeoDash** (free, from Neo4j Labs)
4. Open NeoDash and connect to your database
5. Click **Load Dashboard** and import `neodash/longevity_dashboard.json`

### Pages

#### Page 1: Longevity Overview
- Weekly RHR trend (line chart)
- Weekly HRV trend (line chart)
- VO2max progression (line chart)
- Weekly avg steps (bar chart)
- Monthly workout volume (bar chart)
- Weekly sleep duration (line chart)
- Workout type distribution (pie chart)
- Monthly longevity table (sortable data)

#### Page 2: Recovery & Training
- Workout impact on next-day HRV (table showing which workout types help/hurt recovery)
- Training load vs recovery balance (dual-axis: training minutes + HRV)
- Rest day recovery analysis (HRV on non-workout days)
- Overtraining risk alerts (weekly red/yellow/green status)

#### Page 3: Graph Exploration
- Interactive graph visualization of the last 7 days (Day → Workout → Sleep → Summary nodes)
- Person → Device → Workout network (which devices recorded which activities)

### Customizing queries

All NeoDash queries can be edited directly in the dashboard. Click the edit (pencil) icon on any panel to modify the Cypher query. Common modifications:
- Add `WHERE d.date >= date('2025-01-01')` to filter by date range
- Change `LIMIT` values to show more/fewer results
- Add parameters with `$param_name` for interactive filtering

---

## Longevity zones reference

| Metric | Excellent | Good | Needs attention |
|--------|-----------|------|-----------------|
| Resting HR | < 55 bpm | 55-65 bpm | > 65 bpm |
| HRV (SDNN) | > 40 ms | 25-40 ms | < 25 ms |
| VO2max | > 45 | 35-45 | < 35 |
| Sleep | 7-8h | 6-7h or 8-9h | < 6h or > 9h |
| Steps | > 10,000 | 7,000-10,000 | < 7,000 |
| Exercise | > 300 min/wk | 150-300 min/wk | < 150 min/wk |

*Note: Zones are approximate and vary by age, sex, and fitness level. These are based on population-level longevity research.*

---

## Regenerating charts

Charts are generated from live Neo4j data. After importing new health data, regenerate:

```bash
# Full history
python3 scripts/visualize_longevity.py

# Recent focus
python3 scripts/visualize_longevity.py --months 3
```
