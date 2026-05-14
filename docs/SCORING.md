# Whoop-equivalent scoring formulas

The three Whoop hallmark scores (Recovery %, Strain 0–21, Sleep Performance %) are not formally documented by Whoop. The formulas below are open approximations using only fields already on `:DailySummary`, `:SleepSession`, and `:Workout` in this graph — no schema changes required.

All thresholds are tunable. Defaults are tuned for a generally healthy adult; calibrate after seeing your own distributions.

## Recovery Score (0–100)

Whoop's score is dominated by HRV deviation from a personal baseline, with smaller contributions from resting HR and prior-night sleep. We mirror that weighting.

```
Recovery = 0.60 * HRV_component
         + 0.20 * RHR_component
         + 0.20 * Sleep_component
```

**HRV component:**
```
hrv_z = (today_hrv - baseline_30d_mean) / baseline_30d_std
HRV_component = clamp( 50 + 25 * hrv_z , 0, 100 )
```
A z-score of 0 = baseline = 50; +2 SD ≈ 100 (excellent recovery); −2 SD ≈ 0 (poor).

**RHR component (inverted — lower is better):**
```
rhr_z = (today_rhr - baseline_30d_mean) / baseline_30d_std
RHR_component = clamp( 50 - 25 * rhr_z , 0, 100 )
```

**Sleep component:**
```
Sleep_component = Sleep_Performance  (see below)
```

The 30-day rolling baseline excludes the current day, so a single bad night doesn't drag its own baseline down.

**Zones:**
| Recovery | Zone   | Coaching cue                         |
|---------:|--------|--------------------------------------|
| 67–100   | GREEN  | Body is primed — train hard          |
| 34–66    | YELLOW | Maintain — moderate session          |
| 0–33     | RED    | Recovery is compromised — back off   |

---

## Strain Score (0–21)

Whoop's Strain is a logarithmic cardiac-load score inspired by Banister's TRIMP (TRaining IMPulse). We don't have intra-workout HR samples, so we approximate from daily energy expenditure and workout duration weighted by intensity (`active_energy_kcal / workout_minutes` as a proxy for intensity).

```
intensity = active_energy_kcal / max(workout_minutes, 1)     # kcal/min during activity
raw_load  = workout_minutes * (intensity / target_intensity) ^ 1.92
Strain    = 21 * (1 - exp(-raw_load / scaling_constant))
```

- `target_intensity = 8` kcal/min — roughly moderate cardio.
- `scaling_constant = 220` — calibrated so 60 min at target intensity ≈ Strain 14 (a typical hard session).
- The `^1.92` exponent recreates Banister's non-linear penalty for high intensity, so a hard 30-min session scores well above a 60-min walk.

If no workout: `raw_load = max(0, basal_above_normal)` — light activity day. Strain rarely exceeds 8 on rest days.

**Zones:**
| Strain | Zone        |
|-------:|-------------|
| 0–9    | Light       |
| 10–13  | Moderate    |
| 14–17  | Strenuous   |
| 18–21  | All-out     |

---

## Sleep Performance (0–100)

```
need_hours       = 7.5                                    # adjust per age/training load
duration_score   = min(asleep_minutes / (need_hours * 60), 1.0) * 100
efficiency       = asleep_minutes / in_bed_minutes        # 0..1
Sleep_Performance = duration_score * efficiency
```

Falls back to `DailySummary.sleep_hours` (no in-bed data) with `efficiency = 0.92` assumed when no `:SleepSession` exists.

Apple Health's REM/Core/Deep stage data is not currently parsed into the graph; adding stage-aware scoring would require re-ingestion with a parser change.

---

## Why no skin temperature or SpO₂ nocturnal trend?

- `avg_blood_oxygen` is on DailySummary as a daily average (Q14 already uses it). A Whoop-style overnight SpO₂ trend would need per-measurement data, which isn't aggregated into the graph by design.
- Apple Watch wrist temperature is recorded but not currently mapped into the schema.

Both are deferred — out of scope for this dashboard.
