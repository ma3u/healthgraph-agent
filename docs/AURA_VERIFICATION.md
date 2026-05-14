# Aura connection — verification

Last verified: **2026-05-14**, by running the probe scripts in this document
against the live Aura instance.

## TL;DR

| Check                                  | Status                                                     |
| -------------------------------------- | ---------------------------------------------------------- |
| Aura credentials in `.env`             | ✅ NEO4J_URI / USER / PASSWORD set                         |
| Aura reachable                         | ✅ `neo4j+s://7d4ba607.databases.neo4j.io` (5.27-aura)     |
| Apple Health schema installed          | ✅ all 8 labels + 8 uniqueness constraints + range indexes |
| Apple Health data loaded               | ✅ 3,087 Day nodes, 2017-10-29 → 2026-04-15 (~8.5 years)   |
| Backend translates iOS payload → Aura  | ✅ end-to-end test wrote, read, and cleaned up             |
| Backend HTTP layer (login + ingest)    | ✅ verified via uvicorn + curl                             |
| iOS app login screen renders           | ✅ reads `API_BASE_URL` from Info.plist                    |
| iOS app currently logged in            | ❌ no JWT in Keychain yet (expected — first run)           |
| Backend auth env vars in `.env`        | ❌ `BACKEND_USER`, `BACKEND_PASSWORD_HASH`, `BACKEND_JWT_SECRET` not set yet |

The "❌" rows are the only steps left before a real device run.

## Current Aura state (verbatim from the probe)

```
=== Node labels with counts ===
  Workout: 3,180
  Day: 3,087
  DailySummary: 3,087
  Week: 443
  MetricType: 86
  SleepSession: 78
  Device: 32
  Person: 1
  _Neodash_Dashboard: 1

=== Relationship types with counts ===
  ON_DAY: 3,258
  PART_OF: 3,087
  HAS_SUMMARY: 3,087
  NEXT_DAY: 3,086
  RECORDED: 3,001
  FOLLOWED_BY: 261
  USES: 32

Date range: 3087 Day nodes from 2017-10-29 to 2026-04-15
```

So the iOS app does **not** need to do an initial sync from year zero — the
historical export is already in Aura. **The right first run on the phone is
an Incremental sync** that picks up 2026-04-16 onwards.

## Probe scripts

Both run from the repo root and read `.env` automatically. The backend's
venv is at `backend/.venv` (created in the previous session).

### 1. Connectivity probe

Just confirms the credentials work and Aura is online.

```sh
backend/.venv/bin/python <<'PY'
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('.env'))

from neo4j import GraphDatabase
driver = GraphDatabase.driver(
    os.environ['NEO4J_URI'],
    auth=(os.environ['NEO4J_USER'], os.environ['NEO4J_PASSWORD']),
)
driver.verify_connectivity()
with driver.session() as s:
    rec = s.run(
        "CALL dbms.components() YIELD name, versions, edition "
        "RETURN name, versions, edition"
    ).single()
    print(f'{rec["name"]} {rec["versions"][0]} ({rec["edition"]})')
driver.close()
PY
```

Expected output:

```
Neo4j Kernel 5.27-aura (enterprise)
```

### 2. Schema + data audit

Lists labels, relationships, constraints, indexes, and the date range of
`Day` nodes. Useful to confirm the iOS-side schema assumptions still hold
after any change.

The full script is what the TL;DR above was generated from. It checks for:

- 8 expected labels: `Person, Device, MetricType, Day, Week, DailySummary, Workout, SleepSession`
- 8 expected constraints: `person_name, device_name, metric_type_id, day_date, week_iso, daily_summary_date, workout_id, sleep_session_date`
- Optional `_Neodash_Dashboard` (extra) — fine, that's NeoDash's own state.

If `Missing labels:` or `Missing constraints:` returns anything, run the
existing offline pipeline once with `etl/load_to_neo4j.py` — its
`create_schema()` is idempotent and will install whatever is missing.

### 3. End-to-end ingest test (safe)

Uses a payload dated **2099-01-01** with `source_name="HealthGraphSync-Test"`,
so it can't collide with real data, then deletes everything it created.

```sh
backend/.venv/bin/python <<'PY'
import os, json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('.env'))

from backend.models import IngestPayload
from backend.ingest import ingest_to_aura

with open('backend/samples/aura_test_payload.json') as f:
    payload = IngestPayload.model_validate(json.load(f))

result = ingest_to_aura(payload, dry_run=False)
print('Ingest result:', result)

# Clean up
from neo4j import GraphDatabase
driver = GraphDatabase.driver(
    os.environ['NEO4J_URI'],
    auth=(os.environ['NEO4J_USER'], os.environ['NEO4J_PASSWORD']),
)
with driver.session() as s:
    s.run("MATCH (d:Day) WHERE d.date.year > 2050 DETACH DELETE d")
    s.run("MATCH (s:DailySummary) WHERE s.date.year > 2050 DETACH DELETE s")
    s.run("MATCH (d:Device) WHERE d.name CONTAINS 'HealthGraphSync-Test' DETACH DELETE d")
    s.run("MATCH (w:Week) WHERE NOT (w)<-[:PART_OF]-() DELETE w")
driver.close()
PY
```

Expected:

```
Ingest result: {'accepted_samples': 2, 'accepted_workouts': 0, 'days_affected': ['2099-01-01']}
```

### 4. HTTP layer test (uvicorn + curl)

Exercises `/auth/login` and `/ingest/healthkit` exactly as the iOS app will,
writing to real Aura, then cleans up.

```sh
PWHASH=$(backend/.venv/bin/python -c "from passlib.hash import bcrypt; print(bcrypt.hash('aura-test-pw'))")

BACKEND_USER=mabu.mate@gmail.com \
BACKEND_PASSWORD_HASH="$PWHASH" \
BACKEND_JWT_SECRET=local-aura-test-secret-do-not-ship \
BACKEND_DRY_RUN=0 \
  backend/.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000 &
UVICORN_PID=$!
sleep 3

curl -sS http://127.0.0.1:8000/health
TOKEN=$(curl -sS -X POST http://127.0.0.1:8000/auth/login \
  -d "username=mabu.mate@gmail.com&password=aura-test-pw" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "Token acquired."

curl -sS -X POST http://127.0.0.1:8000/ingest/healthkit \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d @backend/samples/aura_test_payload.json | python3 -m json.tool

kill $UVICORN_PID
# Then run cleanup block from script 3.
```

Expected ingest response:

```json
{
  "accepted_samples": 2,
  "accepted_workouts": 0,
  "days_affected": ["2099-01-01"],
  "server_anchor": "..."
}
```

## "Is the user logged in?"

There are two distinct "logged in" states:

| Context              | Where                          | Verified by                                                 |
| -------------------- | ------------------------------ | ----------------------------------------------------------- |
| Aura DB credentials  | `.env` at repo root            | Probe script #1 succeeds.                                   |
| iOS app session JWT  | iPhone Keychain (key `auth.token` under service `io.healthgraph.sync`) | Tap **Sign in** in the app; on success the Sync/Dashboard/Settings tabs appear instead of the login screen. |

**Today (2026-05-14):**

- Aura DB: **logged in** (script #1 returned `Neo4j Kernel 5.27-aura`).
- iOS app: **not logged in yet**. The simulator screenshot confirms the
  Login view is what renders, and `Server` shows `http://localhost:8000`,
  meaning `AppConfig.apiBaseURL` is correctly reading from Info.plist.

To complete the iOS login, you still need to:

1. Add `BACKEND_USER`, `BACKEND_PASSWORD_HASH`, `BACKEND_JWT_SECRET`,
   `BACKEND_DRY_RUN=0` to `.env`. The example block is in `.env.example`.
2. Start the backend (`uvicorn` command in the HTTP layer test above).
3. In the iOS app, enter the `BACKEND_USER` email and the plaintext password
   you generated the bcrypt hash from, then tap **Sign in**.

## "Is an Aura instance for Apple Health installed?"

**Yes.** See the audit results above. The instance has:

- All 8 schema constraints required by `etl/load_to_neo4j.py`.
- 3,087 days of Apple Health data covering 2017-10-29 → 2026-04-15.
- A `_Neodash_Dashboard` node (NeoDash's own state — separate from the
  health graph).

If you ever connect a fresh Aura instance, the offline pipeline's
`create_schema()` (called automatically by `load_all`) will install
everything on first ingest.

## What we DID NOT test

- **Real HealthKit data on a real iPhone.** HealthKit is restricted on
  simulators and requires a paid Apple developer account for device
  signing. That step is gated on the Apple Developer Team ID and is the
  remaining Phase 1 item in `docs/IOS_PLAN.md`.
- **Backend reachable from the phone.** `http://localhost:8000` only works
  from the iOS Simulator (which shares the host's network). For a real
  device, expose the backend via Tailscale / ngrok / a deployment.
- **Deletions.** `HKAnchoredObjectQuery` reports deletions but v1 ignores
  them. See `docs/IOS_APP.md` "What this doesn't cover yet".

## Related docs

- [`docs/IOS_APP.md`](IOS_APP.md) — architecture, sync flow, configuration.
- [`docs/IOS_PLAN.md`](IOS_PLAN.md) — phase-by-phase build plan.
- [`backend/README.md`](../backend/README.md) — running the backend locally
  or in production.
