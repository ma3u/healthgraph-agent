# Cronometer → HealthGraph (nutrition + biometrics silo)

The first **real silo** wired onto the `(:Day)` spine after the Document-Intelligence
clinical pilot. It brings your **nutrition** (daily macros + micronutrients) and
**biometrics** (weight, body fat, glucose, HRV, …) into the same graph as your
Apple Health activity and sleep — the core move toward a private EHR.

> Synthetic-first: the repo ships **fake** sample CSVs (`sample/`). Your real
> export is personal data and is **never committed** — keep it under `data/`
> (git-ignored). See the project's no-personal-data rule.

---

## 1. Get your data out (the practical path)

Cronometer has **no public API for individuals** — only a partners-only B2B API
(Everfit / Kalix / Practice Better). Reverse-engineered libraries exist, but
Cronometer's Terms prohibit automated extraction **and specifically forbid
feeding Content to AI/ML/LLM systems** — exactly what an agent pipeline does. The
clean, sanctioned path is the **manual CSV export of your own data**:

1. Open **cronometer.com** on a laptop/desktop (the mobile app can't do the full
   export).
2. **Profile** tab → **gear icon** in *Account Settings*.
3. **Export Data** → choose a **date range**.
4. Export each type you want — one CSV each: **Daily Nutrition**, **Servings**,
   **Biometrics**, Exercises, Notes. (CSV export is **free**; no Gold required.)

This connector uses **Daily Nutrition** and **Biometrics**.

Sources: Cronometer staff on their own forums describe the menu path and confirm
no public API ([export path](https://forums.cronometer.com/discussion/460/exporting-data),
[no API](https://forums.cronometer.com/discussion/1801/cronometer-export-api),
[partners-only](https://cronometer.com/blog/cronometer-pro-faq/)).

---

## 2. Run the connector

From the **repo root**, with `NEO4J_URI` / `NEO4J_PASSWORD` in `.env`:

```bash
# Try it on the synthetic sample first (no DB write):
python etl/load_cronometer.py \
  --daily-nutrition docs/connectors/cronometer/sample/daily-nutrition.csv \
  --biometrics      docs/connectors/cronometer/sample/biometrics.csv \
  --dry-run

# Load your real export (keep it under data/, which is git-ignored):
python etl/load_cronometer.py \
  --daily-nutrition data/cronometer/daily-nutrition.csv \
  --biometrics      data/cronometer/biometrics.csv
```

Flags: `--dry-run` parses + summarizes only; `--no-create-days` links only to
Days that already exist (default creates a `(:Day)` if missing, since nutrition
is dense daily data that legitimately anchors the timeline); `--source NAME`
overrides the `(:Source)` name.

Then sanity-check in Neo4j Browser / Aura Query with
[`validate.cypher`](./validate.cypher).

---

## 3. How it maps onto the graph

Both files become generic `:Observation` nodes (the reusable spine — see
[`../README.md`](../README.md)):

```
(:Source {name:'cronometer'})-[:RECORDED]->(:Observation {date,type,value,unit,…})
(:Observation)-[:ON_DAY]->(:Day {date})
```

### Daily Nutrition (one row/day, wide)

Header: `Date, Completed, Energy (kcal), Protein (g), Carbs (g), Fat (g), …` then
a long micronutrient tail. Each nutrient cell with a value → one
`category:"nutrition"` Observation.

| CSV column | → Observation |
|---|---|
| `Date` | `(:Day {date})` + `Observation.date` |
| `Completed` | *(not imported — a logging-completeness flag, not a measurement)* |
| `Energy (kcal)` | `{type:'Energy', value, unit:'kcal'}` |
| `Protein (g)` / `Carbs (g)` / `Fat (g)` | one each, `unit:'g'` |
| every other nutrient, e.g. `Vitamin C (mg)`, `B12 (Cobalamin) (µg)` | one each; `type` = name, `unit` = parenthetical |

### Biometrics (tidy, one row/measurement)

Header: `Day, Time, Metric, Unit, Amount`. Each row → one `category:"biometric"`
Observation, almost 1:1.

| CSV column | → Observation |
|---|---|
| `Day` | `(:Day {date})` + `Observation.date` |
| `Time` | `Observation.time` |
| `Metric` | `Observation.type` (Weight, Body Fat, Blood Glucose, HRV, …) |
| `Unit` | `Observation.unit` (kg, %, mg/dL, ms, …) |
| `Amount` | `Observation.value` |

Multiple readings of the same metric on one day (e.g. two weigh-ins) are kept
distinct via an internal `seq`; re-importing the same file stays idempotent.

---

## 4. Parser robustness (handled for you)

- **Parse by header name**, never column index — Cronometer appends nutrient
  columns over time (Allulose, Added Sugars, Sugar Alcohol are recent additions).
- **`µg` (U+00B5)** for micrograms — files are read as UTF-8 (BOM-tolerant).
- **Thousands separators** in quoted numbers (`"2,154.5"`) are stripped.
- **Blank cells** are skipped (never written as `0`).
- **Dates** accept ISO and a few locale formats (`MM/DD/YYYY`, `DD.MM.YYYY`, …).

---

## 5. Scope notes

- **Servings** (per-food rows) is intentionally *not* imported in v1 — it needs a
  `(:Food)`/`(:Serving)` sub-model. Daily Nutrition gives the per-day totals that
  join cleanly to the recovery spine. Add Servings later if food-level detail is
  needed.
- The synthetic `sample/daily-nutrition.csv` carries a representative subset of
  columns (incl. a `µg` nutrient, a quoted thousands value, and blanks) — the
  parser handles the full ~65-column real export the same way, by header name.

> Validate the exact micronutrient tail (column names/order) against one real
> export header — it varies slightly by account locale. The leading columns are
> confirmed; the tail is modeled on the Servings nutrient set.
