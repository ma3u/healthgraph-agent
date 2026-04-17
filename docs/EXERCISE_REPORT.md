# Exercise Duration Report

_Generated 2026-04-16 from the local Neo4j Desktop 2 graph
(`bolt://127.0.0.1:7687`, 3 180 workouts, 1 392 active days, 2017‑10‑29 → 2026‑04‑15)_

## TL;DR

Raw `Workout.duration_min` cannot be used as a training‑time estimate. Two
classes of error dominate:

| Error class | Example | Impact |
|---|---|---|
| **Runaway Apple Watch sessions** (watch not stopped, end_date drifts) | A "HIIT" on 2022‑12‑15 that logs **17 h 30 m** | ≈ 50 days inflated by 8–25 h each |
| **Cross‑app double tracking** (two apps log the same physical session) | 2025‑08‑19 Komoot **14:42** ride *and* Apple Watch **7:06** for the same ride | ~3 % global, up to 21 h in single months |

After applying two cleaning rules (below), averages drop to credible levels
and **2025 looks like the true high‑volume year — but not the 23 h/week the
raw numbers claim**.

---

## Cleaning rules

All queries in [`cypher/exercise_duration_clean.cypher`](../cypher/exercise_duration_clean.cypher) apply:

**R1 — Clamp each workout at 240 min (4 h).**
Removes the 50+ "watch forgot to stop" sessions where `end_date` drifts to
midnight. 4 h is a realistic ceiling for any individual session, including
long rides.

```cypher
CASE WHEN w.duration_min > 240 THEN 240.0 ELSE w.duration_min END
```

**R2 — Per `(day, activity_type)`, take MAX across sources.**
All observed cross‑source overlaps in the data are same‑activity (Komoot +
Watch cycling, Home Workouts + Watch strength, Runkeeper + Watch running,
BEAT81 + Watch cycling). Legitimate two‑a‑day sessions of the same type are
kept because they come from a single source.

```cypher
WITH day, type, source, sum(mins_clean) AS source_min
WITH day, type, max(source_min) AS type_min
WITH day, sum(type_min) AS day_min
```

**R3 — Sum across activity types** for the day total.

> Known residual: a legitimate second session same‑day/same‑type recorded by
> a *different* app (e.g. a second Komoot ride after a Watch ride) will be
> undercounted. This is a rare pattern in the data.

---

## Yearly trend — cleaned

| Year | Active days | Weeks | Total | Avg/active day | **Avg/week** |
|---:|---:|---:|---:|---:|---:|
| 2021 (Aug–Dec) | 119 | 22 | 208 h 16 m | 01:45 | **09:28** |
| 2022 | 299 | 52 | 719 h 35 m | 02:24 | **13:50** |
| 2023 | 263 | 52 | 686 h 25 m | 02:37 | **13:12** |
| 2024 | 298 | 52 | 700 h 43 m | 02:21 | **13:29** |
| **2025** | 320 | 52 | **1 106 h 56 m** | 03:28 | **21:17** |
| 2026 (Jan–15 Apr) | 93 | 16 | 299 h 54 m | 03:13 | **18:45** |

### Per‑active‑day distribution (cleaned, all years)

| Metric | Value |
|---|---|
| Median | **02:24** |
| p75 | 04:00 |
| p90 | 05:07 |
| p95 | 05:58 |
| p99 | 07:48 |
| max | 11:11 |

The p95 sitting at just under 6 hours on an active day — with no more 15–33 h
outliers — is the sanity check that the cleaning rules work.

---

## Last 12 weeks — cleaned (hh:mm)

| ISO week | Active days | Total | Avg/active day |
|---|---:|---:|---:|
| 2026‑W05 | 7 | 21:46 | 03:07 |
| 2026‑W06 | 7 | 21:08 | 03:01 |
| 2026‑W07 | 6 | 13:23 | 02:14 |
| 2026‑W08 | 2 | 03:50 | 01:55 |
| 2026‑W09 | 7 | 30:06 | 04:18 |
| 2026‑W10 | 6 | 28:20 | 04:43 |
| 2026‑W11 | 6 | 10:46 | 01:48 |
| 2026‑W12 | 5 | 19:34 | 03:55 |
| 2026‑W13 | 7 | 31:27 | 04:30 |
| 2026‑W14 | 7 | 18:40 | 02:40 |
| 2026‑W15 | 7 | 27:15 | 03:54 |
| 2026‑W16 | 3 | 12:13 | 04:04 |

Rolling pattern: ~20 h weeks punctuated by low weeks (W08 = 2 active days)
and bigger blocks (W13, W15 ≈ 30 h). Consistent with structured training
interrupted by travel/rest.

---

## Before / after per year

| Year | Raw total | Cleaned total | Removed | % removed |
|---:|---:|---:|---:|---:|
| 2021 | 239 h 52 m | 208 h 16 m | 31 h 36 m | 13.2 % |
| 2022 | 886 h 34 m | 719 h 35 m | 166 h 59 m | 18.8 % |
| 2023 | 985 h 42 m | 686 h 25 m | 299 h 17 m | 30.4 % |
| 2024 | 858 h 16 m | 700 h 43 m | 157 h 33 m | 18.4 % |
| 2025 | 1 244 h 49 m | 1 106 h 56 m | 137 h 53 m | 11.1 % |
| 2026 (YTD) | 370 h 22 m | 299 h 54 m | 70 h 28 m | 19.0 % |

The 2023 removal rate (30 %) is driven by 11 separate November/December days
where a single Watch HIIT session ran for 13–17 h — the watch was not stopped
after the morning session.

---

## Known data quality issues

### Runaway single workouts (> 4 h), top 10

| Day | Type | Source | Duration |
|---|---|---|---:|
| 2026‑04‑08 | MindAndBody | TwoBreath | 25 h 58 m |
| 2023‑11‑28 | HIIT | Apple Watch | 17 h 41 m |
| 2022‑12‑15 | HIIT | Apple Watch | 17 h 30 m |
| 2023‑12‑01 | HIIT | Apple Watch | 16 h 31 m |
| 2022‑12‑07 | HIIT | Apple Watch | 15 h 53 m |
| 2024‑06‑05 | HIIT | Apple Watch | 15 h 43 m |
| 2025‑05‑31 | Swimming | Health | 15 h 40 m |
| 2022‑09‑13 | HIIT | Apple Watch | 15 h 36 m |
| 2023‑12‑13 | HIIT | Apple Watch | 15 h 31 m |
| 2023‑11‑14 | HIIT | Apple Watch | 15 h 09 m |

> The TwoBreath record spans three calendar days — clearly a metadata bug in
> the import from that app. All Apple Watch HIIT runaways end at 20:30–23:40
> local time, consistent with "I started a HIIT workout in the morning and
> only ended it when I noticed at night".

### Cross‑source overlap clusters (sample)

| Day | Pair | Overlap |
|---|---|---:|
| 2025‑08‑19 | Komoot Cycling 14 h 42 m ⇔ Watch Cycling 7 h 06 m | 7 h 22 m |
| 2025‑11‑06 | Watch Cycling 4 h 07 m ⇔ Komoot Cycling 3 h 08 m | 3 h 47 m |
| 2025‑10‑25 | Watch Cycling 2 h 32 m ⇔ BEAT81 Cycling 0 h 45 m | 0 h 45 m |
| 2026‑04‑12 | Watch Cycling 0 h 52 m ⇔ BEAT81 Cycling 0 h 45 m | 0 h 45 m |
| 2026‑01‑07 | Home Workouts 0 h 43 m ⇔ Watch HIIT 1 h 14 m | 0 h 43 m |

**Source contribution to the 3 180 workouts:**

| Source | Workouts | Raw hours | First seen | Last seen |
|---|---:|---:|---|---|
| Apple Watch von Matthias | 2 756 | 4 061 h 53 m | 2021‑08‑04 | 2026‑01‑08 |
| Matthias's Apple Watch | 227 | 304 h 37 m | 2026‑01‑12 | 2026‑04‑15 |
| Runkeeper | 101 | 93 h 09 m | 2021‑08‑04 | 2025‑09‑18 |
| Komoot | 11 | 36 h 53 m | 2025‑07‑04 | 2026‑04‑04 |
| Health (iCloud import) | 2 | 30 h 32 m | 2025‑05‑31 | 2025‑05‑31 |
| Home Workouts | 67 | 26 h 47 m | 2025‑01‑02 | 2026‑01‑21 |
| TwoBreath | 7 | 26 h 24 m | 2026‑04‑07 | 2026‑04‑11 |
| BEAT81 | 7 | 5 h 15 m | 2023‑04‑14 | 2026‑04‑12 |
| SmartGym | 1 | 4 m | 2025‑03‑10 | 2025‑03‑10 |
| Fitness (Apple) | 1 | 1 m | 2024‑12‑25 | 2024‑12‑25 |

---

## Activity mix (raw, all time)

| Type | Sessions | Total (raw) |
|---|---:|---:|
| HIIT | 1 110 | 1 970 h |
| Cycling | 898 | 1 190 h |
| Running | 422 | 554 h |
| Walking | 189 | 307 h |
| TraditionalStrength | 68 | 113 h |
| Swimming | 131 | 97 h |
| Rowing | 137 | 83 h |
| Yoga | 61 | 69 h |
| FunctionalStrength | 90 | 53 h |
| Hiking | 10 | 48 h |

HIIT dominates raw minutes almost entirely because of the runaway‑session
bug — the clamp at 4 h removes most of that inflation.

---

## Interpretation

1. **2025 was a genuine step up**, even after cleaning: ~1 107 h vs
   ~700 h in 2022–2024. That is consistent with the addition of multi‑hour
   rides tracked via Komoot starting July 2025.
2. **2022–2024 sit in a stable 13–14 h/week band** — your maintenance level.
3. **Sub‑two‑hour median day, ~4 h on top‑25 % days** is the realistic
   shape of the weekly training distribution.
4. The **22 h/week in 2025 is still optimistic**: the 4 h clamp cuts real
   6–8 h rides down to 4 h. If you care about exact ride length, fix this at
   the ETL level by preferring Komoot's duration over Apple Watch's for
   overlapping sessions (Komoot terminates cleanly; Watch often doesn't).

---

## Recommended next fixes (ETL, not query)

1. During `load_to_neo4j.py`, drop or clamp any workout where
   `(end_date − start_date) > duration_min × 2` — catches watch‑not‑stopped
   cases.
2. Prefer the source with the **shorter** interval when two sources overlap
   on the same activity type on the same day. Apple Watch tends to trail;
   third‑party apps (Komoot, Runkeeper) tend to finalize correctly.
3. Add a `quality_flag` property to `Workout` so the raw record survives for
   auditing but only "clean" records feed `DailySummary.workout_minutes`.

See `cypher/exercise_duration_clean.cypher` for all queries used here, and
the "Exercise Duration (Cleaned)" page in the NeoDash dashboard.
