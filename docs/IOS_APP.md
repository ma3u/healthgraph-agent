# iOS app — HealthGraphSync

Replaces the manual "export Apple Health → unzip → run `etl/`" loop with a
native iOS app that reads HealthKit on-device and syncs incrementally to
Neo4j Aura via a small FastAPI backend.

## Architecture at a glance

```
┌──────────────────────────┐
│  HealthGraphSync.app     │  reads HKQuantitySample / HKCategorySample /
│  (iPhone, Apple Watch)   │  HKWorkout via HealthKit. Stores per-type
│                          │  HKQueryAnchor in UserDefaults for incremental
│  - LoginView             │  sync.
│  - SyncView              │
│  - DashboardView (WKWeb) │
│  - SettingsView          │
└────────────┬─────────────┘
             │ HTTPS, Bearer JWT
             │ JSON: { quantity_samples, category_samples, workouts, ... }
             ▼
┌──────────────────────────┐
│  backend/ (FastAPI)      │  Translates JSON → HealthRecord / WorkoutRecord
│                          │  dataclasses, builds a HealthExport, runs
│  - /auth/login           │  etl/transform.py, then etl/load_to_neo4j.py
│  - /ingest/healthkit     │  load_all() to MERGE into Aura.
│  - /sync/state           │
└────────────┬─────────────┘
             │ neo4j+s://
             ▼
┌──────────────────────────┐
│  Neo4j Aura              │  Same graph the offline run_pipeline.sh produces:
│                          │  Person, Device, MetricType, Day, Week, DailySummary,
│                          │  Workout, SleepSession + temporal relationships.
└────────────┬─────────────┘
             │ Cypher
             ▼
┌──────────────────────────┐
│  NeoDash dashboard       │  Embedded in the app's Dashboard tab via WKWebView.
│  (your existing one)     │
└──────────────────────────┘
```

## Why this shape

- **Backend reuses `etl/`.** `backend/ingest.py` builds the same dataclasses
  the offline parser produces and calls `etl/load_to_neo4j.load_all`. So the
  iOS path produces exactly the same graph the existing pipeline does — no
  schema drift, no duplicated MERGE logic.
- **No Neo4j credentials on the phone.** Aura connection lives in the backend
  `.env`. The phone only holds a JWT issued by the backend.
- **Idempotent ingest.** Every write is MERGE. The iOS app re-sends the FULL
  day of samples for any date touched in incremental sync; the backend
  recomputes that day's `DailySummary` from scratch.
- **NeoDash via WebView.** Less native, but reuses the dashboards you already
  built (`neodash/longevity_dashboard.json`, `whoop_dashboard.json`).

## Sync flow

### Initial sync

1. User taps **Initial sync** in `SyncView`.
2. `HealthKitService.initialSyncPayloads` walks history month-by-month from
   ~10 years ago to now. Yields one `IngestPayload` per month.
3. For each payload, `APIClient.ingest` POSTs to `/ingest/healthkit`.
4. Backend translates → transforms → MERGEs.

### Incremental sync

1. For each tracked HK type, `HealthKitService.anchoredFetchDates` uses
   `HKAnchoredObjectQuery` with the saved anchor (stored in `UserDefaults`
   under `hk.anchor.<typeKey>`). Returns the set of YYYY-MM-DD dates with
   new/modified samples since last sync, and saves the new anchor.
2. For each touched date, fetch the FULL day of samples with a plain
   `HKSampleQuery`.
3. POST one payload covering all touched dates.

### Why "full day, not just deltas"

The existing `etl/` pipeline aggregates to `DailySummary` nodes (no per-sample
nodes). If we sent only the new samples for a day, the backend would compute
a partial summary and `MERGE` would overwrite the full-day summary. By
sending the full day, the summary is always correct after each sync.

### Trade-off — deletions are ignored

`HKAnchoredObjectQuery` does surface deletions, but we don't know the
deletion's original date (Apple gives us only a UUID). For v1, deletions are
dropped on the floor. If you need delete-fidelity:

1. Add a per-sample node `(:Sample {uuid, ...})` in the schema.
2. Store the UUID alongside DailySummary contributions.
3. On delete, MATCH the sample by UUID, DETACH DELETE, then recompute the
   affected day's summary.

## Configuration

### Backend `.env`

```ini
# Existing
NEO4J_URI=neo4j+s://....databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=...

# New for the sync backend
BACKEND_USER=you@example.com
BACKEND_PASSWORD_HASH=$2b$12$...
BACKEND_JWT_SECRET=...
BACKEND_JWT_TTL_HOURS=720
BACKEND_DRY_RUN=0
```

### iOS `Info.plist`

`ios/project.yml` writes these for you; verify after `xcodegen generate`:

| Key                            | Type   | Example                                  |
| ------------------------------ | ------ | ---------------------------------------- |
| `API_BASE_URL`                 | String | `https://healthgraph.example.com`        |
| `NEODASH_URL`                  | String | `https://neodash.example.com/?...`       |
| `NSHealthShareUsageDescription`| String | (already populated)                      |
| `NSHealthUpdateUsageDescription`| String| (already populated)                      |

## Verifying the Aura side

For a step-by-step check that Aura is reachable and the schema is installed,
see [`AURA_VERIFICATION.md`](AURA_VERIFICATION.md). It includes copy-paste
probe scripts and a safe end-to-end ingest test (test date `2099-01-01`,
cleaned up after).

## Running end-to-end

1. **Backend**: see `backend/README.md`. For local testing, run with `BACKEND_DRY_RUN=1`.
2. **Tunnel** the backend so the phone can reach it (Tailscale Funnel is one
   one-line option, ngrok another). Update `API_BASE_URL` accordingly.
3. **Generate the Xcode project**: `cd ios && xcodegen generate && open HealthGraphSync.xcodeproj`.
4. **Build & run** on a real iPhone (HealthKit is unavailable on iPad and
   most simulator runtimes don't have any HealthKit data).
5. **Permissions prompt** appears on first `Initial sync` — grant read access.

## What this doesn't cover yet

- **Background sync.** All syncs are user-triggered. Add `HKObserverQuery` +
  `enableBackgroundDelivery` and a background task identifier if you want the
  app to sync without the user opening it.
- **Multi-user.** Single user. See `backend/README.md` for the upgrade path.
- **Robust deletion semantics.** As above.
- **Pagination.** Initial sync sends one POST per month. For users with a lot
  of high-frequency data (e.g. several years of continuous HRV), some months
  may produce large payloads. Adding `HKSampleQuery` pagination is the fix.
