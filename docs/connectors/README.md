# Silo connectors — adding a data source to the private EHR

The graph's whole point is **aggregation**: Apple Health activity & sleep,
clinical documents (via Aura Document Intelligence), and now external silos all
hang off **one timeline** — the `(:Day)` spine. This folder is the recipe for
adding the next silo.

Every silo, no matter how different its export looks, reduces to the same shape:

```
(:Source {name})-[:RECORDED]->(:Observation {key,date,type,value,unit,…})
(:Observation)-[:ON_DAY]->(:Day {date})
```

`ON_DAY` is the **same** edge Workouts and SleepSessions already use, so a new
silo needs **no schema migration** — it just lands on the existing timeline and
becomes joinable to everything else (recovery, sleep, clinical labs).

This long/tidy, FHIR-ish "one measurement per node" model is what lets a single
loader absorb both wide exports (Cronometer's daily-nutrition CSV, melted to one
row per nutrient) and already-tidy ones (Cronometer's biometrics CSV).

---

## The reusable spine: `etl/observation_model.py`

- **`Observation`** — a dataclass: `source, category, date, type, value, unit,
  time?, seq?, day_of_week?`. Its `.key` (`source|category|date|type[|seq]`) is
  the idempotency handle.
- **`load_observations(driver, observations, create_days=True)`** — writes them
  with `MERGE` (re-imports update in place, never duplicate). `create_days=True`
  MERGEs the `(:Day)`; `False` only links to Days that already exist.
- **`get_driver()`** — self-contained Neo4j connection (reads `NEO4J_URI` /
  `NEO4J_PASSWORD`); honors `NEO4J_DATABASE` for isolated test databases.

You do **not** touch this file to add a silo — you only write a parser that
returns `list[Observation]`.

---

## Recipe: add a new silo in 3 steps

1. **Export** the source's data (prefer a sanctioned manual/CSV export over a
   fragile or ToS-violating scraped API — see the Cronometer notes).
2. **Write a parser** `etl/load_<silo>.py` that reads the file(s) and returns
   `list[Observation]`. Map each measurement to a `type` + `unit` + `value` on a
   `date`. Reuse the spine:
   ```python
   from observation_model import Observation, get_driver, load_observations
   ```
3. **Add a tiny CLI** (`--dry-run`, file args) + **synthetic sample(s)** under
   `docs/connectors/<silo>/sample/` + a `validate.cypher`. Add a parser unit test
   and an `e2e_db` load test (see `tests/test_cronometer_connector.py`).

### Conventions worth keeping

- **Parse by header name, never column index** — exporters add/reorder columns.
- **Skip blanks** (don't write `0`); read files as **UTF-8** (units like `µg`).
- **Idempotent** — give repeating same-day measurements a stable `seq`.
- **Privacy** — only **synthetic** samples go in the repo; real exports live
  under `data/` (git-ignored) and are run against your own instance.

---

## Worked example

- **[`cronometer/`](./cronometer/)** — nutrition (daily macros + micronutrients)
  and biometrics (weight, body fat, glucose, HRV). Code:
  `etl/load_cronometer.py`. This is the template to copy for the next source
  (eGym, Beat81, ePA, blood panels, …).
