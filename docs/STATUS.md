# Project status — May 2026

Snapshot of what's deployed, what works, where the limits are, and the workarounds in use. Companion to [README.md](../README.md), [DASHBOARD.md](DASHBOARD.md), [HEALTH_ANALYTICS.md](HEALTH_ANALYTICS.md), and [AURA_API_FEEDBACK.md](AURA_API_FEEDBACK.md).

---

## 1. Aura instance

| Field | Value |
|---|---|
| Name | `MyAppleHealthData` |
| Instance ID | `7d4ba607` |
| Bolt URL | `neo4j+s://7d4ba607.databases.neo4j.io` |
| Type | AuraDB Professional |
| Region | GCP `europe-west3` |
| Memory / Storage | 8 GB / 16 GB |
| Project | `326809f3-c351-4eb7-8770-fcf5d0b6adc1` (tenant `ma3u`) |
| Owner | `matthias.buchhorn@web.de` (linked to GitHub `ma3u`) |
| Credentials in | `.env` (gitignored) |

### Data loaded
- **3,087** `:DailySummary` nodes (one per day, 2017-10-29 → 2026-04-15 = 8.5 years)
- **3,180** `:Workout` nodes (multiple activity types, see `Workout.activity_type`)
- **3,087** `:Day` + **443** `:Week` (calendar nodes)
- **86** `:MetricType` (Apple Health metric definitions)
- **78** `:SleepSession` (only nights where the watch was worn)
- **32** `:Device` (every device that contributed data)
- **1** `:Person`
- **1** `:_Neodash_Dashboard` (the Whoop dashboard, written by `scripts/upload_dashboard.py`)

Properties available on `:DailySummary`: `date`, `total_steps`, `total_distance_km`, `workout_count`, `workout_minutes`, `description`, `flights_climbed`, `avg_heart_rate`, `min_heart_rate`, `max_heart_rate`, `resting_heart_rate`, `active_energy_kcal`, `basal_energy_kcal`, `avg_blood_oxygen`, `body_mass_kg`, `hrv_mean`, `vo2max`, `sleep_hours`, `avg_respiratory_rate`.

### Data freshness
The export was generated on **2026-04-15**, so all dashboard queries anchor on the latest available date rather than `date()`. To refresh, re-run `python3 etl/load_to_neo4j.py data/apple_health_export/export.xml` after a new Apple Health export (untracked file).

---

## 2. Dashboards — three renderers, two products

| Renderer | URL | What's there | Update path |
|---|---|---|---|
| Open-source NeoDash | https://neodash.graphapp.io | 6 pages, 44 widgets (Whoop View, Recovery, Strain, Sleep, Health Monitor, Anomalies) | `python3 scripts/upload_dashboard.py` |
| Aura Console Dashboards | console.neo4j.io/.../tools/dashboards | 5 pages, 35 widgets (CLI upload from 2026-05-14, missing the new "Anomalies" page) | Browser-token workaround (see §4 below) |
| Neo4j Desktop NeoDash | local plugin | Whatever JSON you load | *Load Dashboard* → either browse to `neodash/whoop_dashboard.json` or load from Neo4j |

The dashboard JSON lives at `neodash/whoop_dashboard.json` and is the source of truth for both renderers.

### What each page contains
- **Whoop View** (11 widgets) — daily hero card, Recovery 90-day, Strain history + heatmap, HRV/RHR rolling, Sleep performance, Strain vs Recovery scatter
- **Recovery** (6) — HRV by day-of-week, zone distribution, workout impact, best days, baseline drift
- **Strain** (6) — weekly load, monthly trend, activity totals, day-of-week, strain zones
- **Sleep** (5) — duration histogram, by day-of-week, monthly consistency, sleep debt
- **Health Monitor** (7) — VO2max, RHR, HRV, SpO2, respiratory rate, body mass — all on 8.5-year axis
- **Anomalies** (9) — illness signature days, pre-illness warning, HRV regression streaks, overtraining flags, energy anomalies, best HRV days, streaks, activity entropy

---

## 3. Scoring & analytics — what's computable today

All from pure Cypher against the live instance, no GDS session needed.

| File | Queries | Purpose |
|---|---|---|
| `cypher/whoop_queries.cypher` | 10 score + page queries | Recovery/Strain/Sleep per day + dashboard backing queries |
| `cypher/health_analytics.cypher` | 15 Cypher analytics | Illness detection, stress streaks, overtraining, streaks, anomalies |
| `cypher/health_gds_recipes.cypher` | 5 GDS recipes | K-Means zones, K-NN day-similarity, Louvain regimes, PageRank, Node Classification (need GA session) |
| `cypher/longevity_queries.cypher` | 20 longevity queries | Pre-existing biomarker analyses |
| `cypher/sample_queries.cypher` | 7 templates | General Aura Agent tool examples |
| `cypher/exercise_duration_clean.cypher` | cleaned exercise pipeline | Removes runaway watch sessions, cross-source dupes |

### Formulas
- Recovery % = `0.60·HRV_z + 0.20·RHR_z + 0.20·Sleep_perf` against a 30-day rolling baseline
- Strain 0–21 = TRIMP-inspired `21·(1 − exp(−load/220))` with `load = minutes · (intensity/8)^1.92`
- Sleep % = `clamp(asleep_min/450, 0, 1) · (asleep/in_bed) · 100`

Full derivation in [SCORING.md](SCORING.md). The 30-day rolling baseline pattern is reused throughout the anomaly queries.

### Notable findings from the actual data
- 2024-07-16 — clear fever day (HRV 13.2 ms = −3.6σ, RHR +2.1σ, resp-rate +1.1σ)
- 2021-11-01 → 11-07 — 6-day HRV crash from 63 → 19.9 ms
- 70-day steps≥10k streak (Oct 2022 – Jan 2023)
- 38-day RHR<60 streak (Jan – Feb 2025)
- 0 hard workouts in the 7 days after any illness signature day — good post-illness discipline

---

## 4. Where automation hits walls (and the workarounds)

### Aura public API — what's exposed

```
api.neo4j.io/v1/
  ├── instances      ← full CRUD + pause/resume   ✅ service-account works
  └── tenants        ← list only                  ✅ service-account works
```

Everything else (`dashboards`, `agents`, `projects`, `cmek-keys`, …) returns HTTP 403 from the public gateway. The official `neo4j/aura-cli` mirrors the same surface — no `dashboard` or `agent` subcommand exists.

### Aura Console internal API — exists but service-account is rejected

The browser console talks to a separate internal API:

```
console.neo4j.io/api/shared-storage/v1/dashboards/dashboards
                                       └── full CRUD (POST/GET/PATCH/DELETE)
                                       └── plus /pages and /widgets sub-resources
```

That API **does** accept the operations we need (verified by reverse-engineering the JS bundle and successfully uploading a 35-widget dashboard with 1 POST + 5 page POSTs + 35 widget POSTs).

But it only trusts tokens issued by `login.neo4j.com` (audience `https://console.neo4j.io`) from the **interactive OIDC flow**. Service-account tokens from `api.neo4j.io/oauth/token` are rejected with `"token-invalid"` — same audience, different signer, no trust relationship between the two Auth0 tenants.

### The browser-token workaround (currently the only path)

1. Log into https://console.neo4j.io in Chrome (already done)
2. Open DevTools → Console tab
3. Run:
   ```js
   (() => {
     const k = Object.keys(localStorage).find(k => k.startsWith('oidc.user:'));
     copy(JSON.parse(localStorage.getItem(k)).access_token);
     console.log('✓ copied');
   })();
   ```
4. Export to env: `export AURA_SESSION_TOKEN=eyJ...`
5. Run `python3 scripts/upload_aura_dashboard.py`

**Caveats:**
- Token TTL is **15 minutes** — paste-and-run fast; don't go on tangents between snippets (we lost two tokens to this)
- The script is otherwise idempotent: it always creates a NEW dashboard. To update, delete the old `dashboardId` first via API
- Token grants full user-level access for that 15 min — never share or commit

### Aura Agents — same gap

The Aura Agent feature (Text2Cypher, Similarity Search) has identical limitations: no public API or CLI, only console UI. We use it via the browser for now. If you want a reproducible agent setup, you currently have to click through the UI per environment.

### What was filed for upstream fix

Drafted in [AURA_API_FEEDBACK.md](AURA_API_FEEDBACK.md):
- GitHub issue body targeting `neo4j/aura-cli` asking for `dashboard` and `agent` subcommands
- LinkedIn comment for Ari Waller (Neo4j DevRel) with the hackathon-blocker framing

Not yet posted — both are waiting for the hackathon submission window to close.

---

## 5. Cost controls

### Auto-pause crontab (installed)

```cron
0 23 * * * cd ~/projects/healthgraph-agent && ./scripts/aura_pause.sh pause   >> /tmp/aura_pause.log 2>&1
0 8  * * * cd ~/projects/healthgraph-agent && ./scripts/aura_pause.sh resume  >> /tmp/aura_pause.log 2>&1
```

- Pauses at 23:00 local (CEST/CET), resumes at 08:00
- Paused instances bill at **20%** of running cost (Neo4j's official figure)
- 9h/day paused → ~37% monthly compute savings on the $5.40/mo instance
- Log at `/tmp/aura_pause.log`

### What paused-mode does NOT do
- Aura paused instances do NOT auto-resume on connection attempt. If you query during the pause window, the query fails. Either wait for 08:00 or run `scripts/aura_pause.sh resume` first.
- Aura DOES auto-resume after 30 days for security patching (not configurable)

### Manual controls

```bash
./scripts/aura_pause.sh status            # current state + full instance JSON
./scripts/aura_pause.sh pause             # pause now
./scripts/aura_pause.sh resume            # resume now
./scripts/aura_pause.sh pause-if-idle 0   # pause only if no active queries
```

### Other cost levers
- **Graph Analytics sessions** are pay-per-minute, billed separately from the instance. Spin one up only to run `cypher/health_gds_recipes.cypher`, then *Delete session* to stop the meter.
- **Aura API client credentials** (in `.env` as `AURA_CLIENT_ID` / `AURA_CLIENT_SECRET`) are free; only API calls that change instance state cost (and pause/resume themselves are free).
- The 8-GB instance is one tier larger than needed for 3,087 days of summaries. Could be downsized to 4 GB if the next workload (vector embeddings) doesn't materialize.

---

## 6. Scripts inventory

| Script | What it does | Auth needed |
|---|---|---|
| `scripts/run_pipeline.sh` | End-to-end ETL: parse Apple Health XML → transform → load to Neo4j | `.env` Neo4j creds |
| `etl/load_to_neo4j.py` | Direct Python loader (called by `run_pipeline.sh`) | `.env` Neo4j creds |
| `etl/export_to_csv.py` | Alt Method 2: export to CSVs for `LOAD CSV` | none (writes locally) |
| `etl/generate_test_data.py` | Synthetic data for personas (athlete/biohacker/etc.) | none |
| `scripts/upload_dashboard.py` | Push `whoop_dashboard.json` → `_Neodash_Dashboard` node | `.env` Neo4j creds |
| `scripts/upload_aura_dashboard.py` | Push dashboard → Aura Console via shared-storage API | Fresh user-session JWT (15 min TTL) |
| `scripts/aura_pause.sh` | Status / pause / resume / pause-if-idle | `.env` Aura API creds |
| `scripts/analyze_longevity.py` | Generates `docs/HEALTH_REPORT.md` from the live graph | `.env` Neo4j creds |
| `scripts/visualize_longevity.py` | Python chart export to `data/charts/` (8 PNGs) | `.env` Neo4j creds |

---

## 6.5. Public GitHub Pages snapshot

A daily-refreshing **Recovery-only** snapshot page, hosted on GitHub Pages from this repo.

### What's on the page
- Recovery % (0–100)
- Recovery zone (GREEN / YELLOW / RED)
- Date of the data snapshot
- Current streak counts: Sleep ≥ 7.5h, Steps ≥ 10k, RHR < 60, HRV ≥ 38

**Not** on the page (per the personal-data rule): raw HRV/RHR values, sleep hours, kcal, strain, workout details, anything else. The HTML file is grep-checked before commit.

### Pieces

| File | Role |
|---|---|
| `scripts/render_snapshot.py` | Queries Aura via Bolt, computes scores, writes `docs/snapshot/index.html`. Auto-resumes the instance if paused (best effort, needs `AURA_*` secrets) |
| `.github/workflows/snapshot.yml` | Daily cron at 06:30 UTC + manual trigger. Runs the script, commits the new HTML if it changed |
| `docs/snapshot/index.html` | The page itself — self-contained, no external assets, `noindex` meta tag |

### One-time setup (you do this in GitHub)

```bash
# 1. Add repository secrets (Settings → Secrets and variables → Actions):
gh secret set NEO4J_URI            --body "neo4j+s://7d4ba607.databases.neo4j.io"
gh secret set NEO4J_USER           --body "neo4j"
gh secret set NEO4J_PASSWORD       --body "<from .env>"
gh secret set AURA_INSTANCEID      --body "7d4ba607"
gh secret set AURA_CLIENT_ID       --body "<from .env>"
gh secret set AURA_CLIENT_SECRET   --body "<from .env>"

# 2. Enable Pages from /docs on main branch:
#    Repo → Settings → Pages → Source: "Deploy from a branch"
#                            Branch: main, folder: /docs
#    URL becomes https://ma3u.github.io/healthgraph-agent/snapshot/

# 3. Trigger the workflow manually once to verify:
gh workflow run "Daily Recovery snapshot"
gh run watch
```

### Privacy notes baked into the design
- Workflow file (`snapshot.yml`) has `permissions: contents: write` only — no extra scopes
- Snapshot HTML contains a `<meta name="robots" content="noindex,nofollow">` (won't appear in Google)
- The page URL is shareable but not discoverable; treat it as "low-friction private"
- Raw biometric values are queried by the runner and exist only in memory during the run; the committed HTML has only the four approved fields

### If you want to take it down later
- Disable Pages in repo Settings, or
- Delete `docs/snapshot/` folder, or
- Delete the workflow file (the page will go stale but remain accessible until you remove the HTML or disable Pages)

---

## 7. Known incomplete / future work

1. **Aura Console dashboard sync** — the version in Aura Console is still the 5-page snapshot; the 6-page (with Anomalies) lives only in `neodash/whoop_dashboard.json` and the `_Neodash_Dashboard` node. Push needs a fresh user-session token.
2. **Aura Agent setup** — Text2Cypher tool is configured manually via UI; not reproducible from CLI yet. See [agent/agent_config.md](../agent/agent_config.md) for the intended setup.
3. **Vector index / Similarity Search Tool** — explicitly deferred. The semantic-similarity-search use case is weak for structured numeric time-series data; Text2Cypher answers most questions better.
4. **Graph Analytics recipes** — 5 GDS recipes in `cypher/health_gds_recipes.cypher` are documented but not yet run. Requires creating a GA session (pay-per-minute).
5. **Talk submission** — *Neo4j Theatre Sessions @ WeAreDevelopers Berlin 2026*; title draft and abstract are decided but the form is not yet submitted.

---

## 8. Deployment hold — hackathon day

**Nothing is committed, pushed, deployed, or posted yet.** All work lives in the local working tree only. The user is timing every public artifact to land together on the **Aura Agent Hackathon submission day (2026-05-15)** so the activity is concentrated when Neo4j DevRel is watching.

### What's waiting

| Artifact | Status today | Hackathon-day step |
|---|---|---|
| Repo source (cypher, scripts, neodash, docs) | Untracked / modified in working tree | `git add` selectively, `git commit`, `git push` |
| GitHub Pages snapshot site | Rendered locally in `docs/snapshot/index.html` | Enable Pages from `/docs`, add GH secrets, trigger workflow |
| LinkedIn comment to Ari Waller | Drafted in [AURA_API_FEEDBACK.md](AURA_API_FEEDBACK.md) | Paste into comment, post |
| GitHub issue at `neo4j/aura-cli` | Drafted in [AURA_API_FEEDBACK.md](AURA_API_FEEDBACK.md) | `gh issue create` with the body |
| Talk submission for WeAreDevelopers Berlin 2026 | Title + abstract decided | Submit Google Form |
| Aura Console dashboard sync (6 pages) | NeoDash node has all 6; Console has only 5 | Browser-token workaround → `scripts/upload_aura_dashboard.py` |

### Hackathon-day checklist (run in order)

1. **Verify nothing personal is staged**
   ```bash
   git status --short
   git check-ignore data/apple_health_export.zip data/apple_health_export/ .env
   # all three must be ignored or absent
   ```

2. **Commit the public-safe artifacts in one push.** Name files explicitly — no `git add .` (the personal-data rule applies regardless of hackathon timing):
   ```bash
   git add cypher/health_analytics.cypher cypher/health_gds_recipes.cypher \
           cypher/whoop_queries.cypher \
           docs/AURA_API_FEEDBACK.md docs/HEALTH_ANALYTICS.md docs/SCORING.md \
           docs/STATUS.md docs/DASHBOARD.md \
           neodash/whoop_dashboard.json \
           scripts/aura_pause.sh scripts/render_snapshot.py \
           scripts/upload_aura_dashboard.py scripts/upload_dashboard.py \
           .github/workflows/snapshot.yml \
           README.md scripts/run_pipeline.sh
   git commit -m "Aura Agent Hackathon: Whoop dashboard, anomaly analytics, public snapshot, auto-pause"
   git push origin main
   ```

3. **Add GitHub Actions secrets** (one-time, see §6.5 for the full list):
   ```bash
   for k in NEO4J_URI NEO4J_USER NEO4J_PASSWORD \
            AURA_INSTANCEID AURA_CLIENT_ID AURA_CLIENT_SECRET; do
     gh secret set "$k" --body "$(grep "^$k=" .env | cut -d= -f2-)"
   done
   ```

4. **Enable Pages** — repo Settings → Pages → *Deploy from a branch* → `main` → `/docs`. Initial deploy takes ~30s. URL: `https://ma3u.github.io/healthgraph-agent/snapshot/`.

5. **Trigger the snapshot workflow once** to verify end-to-end:
   ```bash
   gh workflow run "Daily Recovery snapshot"
   gh run watch
   ```

6. **Re-sync the Aura Console dashboard to 6 pages** (only if you want Console to match NeoDash):
   - Grab a fresh 15-min user-session JWT from the Aura Console browser
   - `export AURA_SESSION_TOKEN=eyJ...`
   - Delete the old 5-page version, then `python3 scripts/upload_aura_dashboard.py`

7. **File the upstream feedback**:
   ```bash
   gh issue create --repo neo4j/aura-cli \
     --title "Add dashboard and agent subcommands so we can automate Aura's new managed tools" \
     --body-file docs/AURA_API_FEEDBACK.md   # paste only the GitHub-issue section
   ```
   Then post the LinkedIn comment under Ari Waller's hackathon post.

8. **Submit the hackathon entry** with the repo URL, the Aura Console dashboard URL, and the Pages snapshot URL.

9. **Submit the WeAreDevelopers Berlin talk** with the title + abstract from the earlier conversation.

### What stays NEVER-public, even on hackathon day
- `data/apple_health_export.zip` (260 MB real Apple Health export)
- `data/apple_health_export/` (extracted, 3.45 GB `export.xml`)
- `.env` (passwords + API client secrets)
- Anything derived from the real export that could re-identify the user

The `.gitignore` covers all of those already; the rule is to never override `.gitignore` with `git add -f` for any of those paths.
