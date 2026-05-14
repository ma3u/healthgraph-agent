# Health analytics — 20 queries for anomaly detection & improvement

A catalog of 20 analytics over the HealthGraph (8.5 years of Apple Health), grouped by what they reveal. Each is implemented in either:

- **Pure Cypher** (15) — runs on the regular Aura instance, no extra cost. See [`cypher/health_analytics.cypher`](../cypher/health_analytics.cypher).
- **Graph Data Science** (5) — needs a Graph Analytics session in Aura (pay-per-minute). Recipes in [`cypher/health_gds_recipes.cypher`](../cypher/health_gds_recipes.cypher).

For each query: what it detects + how to read the result.

---

## A. Illness & sickness detection

Goal: surface days where biometrics suggest an active immune response, plus surrounding context.

### Q1 — Illness signature days · *Cypher*
Days where **HRV drops > 1.5σ below baseline** AND **RHR > 1σ above** AND **respiratory rate > 0.5σ above**. This three-axis crash is the classic acute-infection autonomic pattern.

Example finding from your data:
> **2024-07-16**: HRV crashed to **13.2ms** (−3.6σ), RHR **60 bpm** (+2.1σ), respiratory rate **23.8** (+1.1σ). Almost certainly a fever day.

### Q2 — Multi-day illness episodes · *Cypher*
Groups consecutive Q1 hits (≤ 3-day gap) into "episodes." Most of your hits are 1-day blips; the **Feb 6–9, 2023** episode (4 days) is the standout — a real illness window.

### Q3 — Pre-illness early warning · *Cypher*
Days where **respiratory rate spiked > 1.5σ** but HRV/RHR are still normal. Resp-rate is often the first signal — 1–3 days before HRV crashes. Check these against your calendar.

### Q4 — Recovery duration after illness · *Cypher*
For each Q1 illness day, finds the next day where HRV returned to within 0.5σ of baseline. Tells you how long each episode actually lasted.

### Q5 — Post-illness training mistakes · *Cypher*
Hard workouts (> 60 min) in the 7 days *after* an illness signature day. Surfaces "I tried to push through too fast" patterns. Your data shows zero hits here — you've been good about backing off.

---

## B. Stress & overtraining

Goal: detect chronic patterns rather than single-day spikes.

### Q6 — Chronic stress streaks · *Cypher*
≥ 5 consecutive days where HRV is below the 30-day baseline AND sleep < 7h. The signature of life stress: meetings, deadlines, kid not sleeping, etc.

### Q7 — HRV regression streaks · *Cypher*
≥ 3 consecutive days of HRV declining. Finds 6-day stretches like:
> **2021-11-01 → 2021-11-07**: HRV crashed from **63 → 19.9ms** — major stress or illness window
> **2022-05-03 → 2022-05-09**: 37.3 → 18.9
> **2022-10-16 → 2022-10-22**: 47.5 → 27.3

### Q8 — Overtraining flag · *Cypher*
Weeks where **total workout minutes increased** vs prior week AND **avg HRV decreased**. The classic load-up + recovery-down divergence.

### Q9 — Cardio drift · *Cypher*
Per activity type, month-by-month: has average HR crept up at constant duration? Drift up = the same effort costs you more heart-beats — sign of accumulated fatigue or fitness decline.

### Q10 — Sleep disruption clusters · *Cypher*
Nights where sleep efficiency (asleep / in-bed) drops > 10% vs the 7-night trailing avg. Note: sleep data is sparse (only 78/3087 nights), so this is illustrative rather than complete.

---

## C. Pattern discovery (Graph Data Science)

Goal: let the graph **discover** structure rather than testing pre-specified thresholds. All require a Graph Analytics session.

### Q11 — Personal training zones · *GDS K-Means*
Clusters every workout on (duration, intensity, avg HR) into 5 natural zones. Reveals **your** training distribution, not a textbook's. Use it to see whether you're stuck in one zone.

### Q12 — Day-similarity (K-NN) · *GDS*
For any "bad" day, finds the 5 most similar past days based on (HRV, RHR, sleep, steps, energy). Powerful coaching tool: "Today's profile looks like 2023-11-04 — what did you do then, and what happened next?"

### Q13 — Recovery regime clusters · *GDS Louvain*
First creates K-NN edges between similar days, then runs Louvain to detect communities. With your 8.5 years of data, expect 3–6 regimes to emerge — probably mapping to *Build, Peak, Sick, Recovery, Travel*, etc. The model labels them itself.

### Q14 — Activity-type centrality · *GDS PageRank*
PageRank on an activity-→day-→activity graph (workouts on the same day). High-rank activities are structurally central to your training mix — losing them disrupts your routine more than peripheral activities would.

### Q15 — Bridge events · *GDS Betweenness*
Identifies the specific days that lie on shortest paths between Q13's regimes. These are the days "where things changed" — likely candidates for what caused a regime shift.

---

## D. Improvement, streaks, predictive

### Q16 — Health streaks · *Cypher*
Longest consecutive runs of: sleep ≥ 7.5h, RHR < 60, HRV > median, steps ≥ 10k. Your records:
> **Steps ≥ 10k**: 70-day streak (Oct 2022 – Jan 2023)
> **RHR < 60**: 38-day streak (Jan – Feb 2025)

### Q17 — Best-day pattern mining · *Cypher*
Top 10 highest-HRV days; what activities did you do the day before? Reveals the recipe for your peak recovery days.

### Q18 — Activity diversity entropy · *Cypher*
Shannon entropy of your activity types in 7-day windows. Low entropy = monotonous training = plateau risk. Use it to see when you should mix it up.

### Q19 — Energy balance anomalies · *Cypher*
Days where active kcal is > 2σ above (overexertion) or below (under-fueled / data gap) the 30-day baseline. Surfaces both:
> **2026-01-26**: 2,961 kcal, 4.6σ above baseline → big day
> **2026-01-30**: only 1 kcal recorded → watch was off

### Q20 — Predict tomorrow's recovery zone · *GDS Node Classification*
Trains a logistic-regression model on historical (HRV, RHR, sleep, prev-day strain) → next-day recovery zone (Green/Yellow/Red). Once trained, you can predict each morning what zone you'll be in, with calibrated probability.

---

## Running the pure-Cypher ones

No setup beyond the data load. From the repo root:

```bash
cypher-shell -a "$NEO4J_URI" -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
  < cypher/health_analytics.cypher
```

Or run any single block in the Aura Console → Query.

## Running the GDS recipes

1. Aura Console → **Graph Analytics** → *Create session* (pick the smallest size; sessions are billed per-minute).
2. The session opens with `gds.*` procedures available against your live database.
3. Run blocks from `cypher/health_gds_recipes.cypher` one at a time.
4. **Drop projections when done** (`CALL gds.graph.drop(...)`) — keeps the session memory lean.
5. **Delete the session** when finished to stop billing.

GDS session cost: ~$0.5 – $2/hr depending on memory; rough rule-of-thumb is the smallest session can run all the recipes above in under 10 minutes total.

---

## Where each analytic comes from

The two anomaly families (illness/stress) lean on **z-score** thinking against a 30-day rolling baseline — the same approach the Whoop dashboard's Recovery score uses (see [SCORING.md](SCORING.md)).

The GDS recipes are based on standard library algorithms from the [Graph Data Science docs](https://neo4j.com/docs/graph-data-science/current/) — picked specifically for what they tell you about time-series biometric data. K-Means works because workouts have clean numeric features. Louvain on a K-NN edge graph reveals regimes without you needing to label them yourself, which is the whole point of unsupervised discovery on health data.
