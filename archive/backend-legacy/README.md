# HealthGraph Sync Backend (ARCHIVED)

> **Status:** archived 2026-05-14. The iOS app now talks **directly** to the
> user's Aura GraphQL Data API with an Auth0 JWT — no FastAPI middleman.
> See [`../../docs/AUTH_RESEARCH.md`](../../docs/AUTH_RESEARCH.md) for the
> reasoning. This directory is kept for reference only.

A small FastAPI service that the **HealthGraphSync** iOS app talks to. Reuses
the existing `etl/` code so HealthKit JSON deltas land as the same graph shape
the offline `run_pipeline.sh` produces.

```
[iPhone HealthKit] --POST JSON--> [FastAPI /ingest/healthkit] --MERGE--> [Neo4j Aura]
                                            |
                                            +-- reuses etl/transform.py + etl/load_to_neo4j.py
```

## Endpoints

| Method | Path                | Auth | Purpose                                        |
| ------ | ------------------- | ---- | ---------------------------------------------- |
| GET    | `/health`           | no   | Liveness probe.                                |
| POST   | `/auth/login`       | no   | Form `username` + `password` -> JWT.           |
| GET    | `/sync/state`       | yes  | Last server anchor / sync timestamp.           |
| POST   | `/ingest/healthkit` | yes  | Accept a batch of HealthKit samples + workouts.|

## Env

Add these to the repo-root `.env` (next to the existing `NEO4J_*`):

```ini
BACKEND_USER=you@example.com
BACKEND_PASSWORD_HASH=$2b$12$...
BACKEND_JWT_SECRET=change-me-long-random
BACKEND_JWT_TTL_HOURS=720
# Optional: skip Aura writes for smoke tests
BACKEND_DRY_RUN=0
```

Generate the bcrypt hash:

```sh
cd backend
python -c "from passlib.hash import bcrypt; import getpass; print(bcrypt.hash(getpass.getpass('pw: ')))"
```

## Run locally

```sh
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload --app-dir ..
```

The `--app-dir ..` part makes `backend` importable as a package.

## Smoke test

```sh
# 1. liveness
curl http://localhost:8000/health

# 2. login (form-encoded, OAuth2 password flow)
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -d "username=$BACKEND_USER&password=YOUR_PW" | jq -r .access_token)

# 3. dry-run ingest (set BACKEND_DRY_RUN=1 in the shell that runs uvicorn)
curl -X POST http://localhost:8000/ingest/healthkit \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @samples/example_payload.json
```

## Deploying

For the hackathon, the cheapest path is to run uvicorn on a small VM (Fly,
Render, Railway, or a Mac with [Tailscale Funnel](https://tailscale.com/kb/1223/funnel))
and point the iOS app's `API_BASE_URL` at it. Do not expose without HTTPS.

## Architecture notes

- **Ingest is idempotent.** Every write is `MERGE`. Re-sending the same day's
  samples is safe — it overwrites the day's `DailySummary` with the recomputed
  aggregates.
- **Full-day contract.** The iOS app re-sends the FULL day of samples for any
  date it touches in incremental sync. The backend trusts the payload as the
  source of truth for the days it covers and recomputes summaries from scratch.
- **Single-user auth.** The hackathon scope is one Aura instance, one user.
  When you need multi-user, swap the env-backed auth for a real user store and
  scope writes by `Person.name`.
