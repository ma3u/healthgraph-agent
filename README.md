# Apple HealthGraph Agent

**[Neo4j Aura Agent Hackathon 2026](https://community.neo4j.com/t/start-here-register-get-aura-credits-aura-agent-hackathon-2026/77191) — Submission**

> _My Apple Health data, finally connected to Neo4j Aura. An AI agent that reasons over your health as a knowledge graph._

<p align="center">
  <img src="docs/app-icon-1024.png" alt="HealthGraphSync app icon" width="160" />
</p>

## Table of contents

- [Hackathon achievements](#-hackathon-achievements)
  - [🤖 Aura Agent](#1--aura-agent)
  - [📊 Aura Dashboard](#2--aura-dashboard)
  - [🔍 Aura GraphQL Data API + GitHub Page](#3--aura-graphql-data-api--github-page)
  - [📱 iPhone App — Apple Health → Aura sync](#4--iphone-app--apple-health--aura-sync)
- [Linked documentation](#linked-documentation)
- [Status & links](#status--links)
- [The idea](#the-idea)
- [Why a graph?](#why-a-graph)
- [Two ways to import your data](#two-ways-to-import-your-data)
- [Synthetic test data](#synthetic-test-data)
- [20 Longevity Cypher queries](#20-longevity-cypher-queries)
- [Architecture](#architecture)
- [Longevity Dashboard](#longevity-dashboard)
- [Repo structure](#repo-structure)
- [Getting started](#getting-started)
- [Key health metrics](#key-health-metrics)
- [Privacy & data handling](#privacy--data-handling)
- [Tech stack](#tech-stack)
- [Hackathon checklist](#hackathon-checklist)


---

## 🏆 Hackathon achievements

Submission for the [**Neo4j Aura Agent Hackathon 2026**](https://community.neo4j.com/t/start-here-register-get-aura-credits-aura-agent-hackathon-2026/77191) (Apr 15 – Jun 15, 2026).

End-to-end longevity stack across four pillars.

### 1. 🤖 Aura Agent

`HealthGraph Agent`: a longevity-focused assistant with **6 tools** (Text2Cypher + 5 parameterized Cypher templates: `health_overview`, `workout_recovery`, `longevity_trends`, `overtraining_check`, `exercise_balance`), MCP enabled, REST-invokable. Defined **as code** via the [Aura v2beta1 `/agents` API](https://neo4j.com/docs/aura/platform/api/specification/?urls.primaryName=Aura%20v2beta1) — the agent's JSON lives in [`agents/healthgraph-coach.json`](agents/healthgraph-coach.json) and is reconciled with one script ([`scripts/create_aura_agent.py`](scripts/create_aura_agent.py), three modes: status / `--pull` / `--push`). Tracked in [#4](https://github.com/ma3u/healthgraph-agent/issues/4) and [#6](https://github.com/ma3u/healthgraph-agent/issues/6).

The `health_overview` Cypher template was rewritten so the tool actually returns daily metrics (RHR / HRV / steps / sleep_hours / workout_min / kcal / VO2max) for a `$start_date`..`$end_date` window **plus** a rolling 30-day baseline ending the day before the window — exactly what the system prompt asks for. Three captured Q&As in [`docs/AGENT_DEMO.md`](docs/AGENT_DEMO.md) show the agent grounding longevity advice in real numbers ("57.7 bpm RHR this week vs 58.2 bpm baseline → stable, but slightly higher") and honestly reporting "no data" when the graph lacks coverage.

![Aura Agent playground — longevity question](docs/images/hackathon/01-aura-agent-playground-longevity-question.png)

---
### 2. 📊 Aura Dashboard

Whoop-style NeoDash dashboard in [`neodash/whoop_dashboard.json`](neodash/whoop_dashboard.json) — **5 pages, 35 panels**: daily hero card (Recovery %, Strain 0–21, Sleep %), Recovery deep-dive, Strain deep-dive, Sleep deep-dive, and 8.5-year Health Monitor. Score formulas in [`docs/SCORING.md`](docs/SCORING.md). Pushed into Aura's built-in *Tools → Dashboards* via [`scripts/upload_dashboard.py`](scripts/upload_dashboard.py) (idempotent: deterministic UUID per title).

![Aura Dashboard — Whoop-style Recovery view](docs/images/hackathon/02-aura-dashboard-whoop-recovery.png)

---
### 3. 🔍 Aura GraphQL Data API + GitHub Page

**GraphQL Data API**: curated SDL with `@cypher` MERGE mutations (`ingestDay` / `ingestWorkout` / `ingestSleep`) — [`cypher/graphql_schema.graphql`](cypher/graphql_schema.graphql). Deployed against the live tenant via [`scripts/create_aura_data_api.py`](scripts/create_aura_data_api.py) (hits `v1beta5` Aura platform REST directly; aura-cli has no `data-api` command). All three mutations smoke-tested + idempotent ([`scripts/test_aura_mutations.py`](scripts/test_aura_mutations.py)).

![GraphQL Data API schema (top) and the daily GitHub Actions pipeline that runs against it (bottom)](docs/images/hackathon/10-graphql-data-api-pipeline.png)

**GitHub Page**: daily Recovery snapshot rendered by [`scripts/render_snapshot.py`](scripts/render_snapshot.py), committed by [`.github/workflows/snapshot.yml`](.github/workflows/snapshot.yml) on a 06:30 UTC cron (auto-resumes paused Aura instances), served at **[`ma3u.github.io/healthgraph-agent/snapshot/`](https://ma3u.github.io/healthgraph-agent/snapshot/)**. Tracked in [#3](https://github.com/ma3u/healthgraph-agent/issues/3).

![GitHub Pages — daily Recovery snapshot](docs/images/hackathon/05-github-pages-recovery-snapshot.png)

---
### 4. 📱 iPhone App — Apple Health → Aura sync + "Ask your graph"

`HealthGraphSync` iOS app ([`ios/`](ios/)) — Swift 6 / iOS 26.5 SDK. Reads HealthKit on-device, queries Aura for `max(Day.date)`, scans HealthKit since then, presents the per-type delta, then uploads via the three GraphQL `@cypher` mutations. Includes `Rescan last 30 days` + `Rescan last 365 days` flows for backfilling partial days. Verified end-to-end on **real iPhone 17 Pro** — 3,087 → 3,117 `:Day` nodes, `max(Day.date)` advancing daily. Tracked in [#2](https://github.com/ma3u/healthgraph-agent/issues/2). One command to build + sign + install:

```sh
bash scripts/build_ios.sh
```

The Dashboard tab embeds an **"Ask your graph"** panel ([`AgentChatView.swift`](ios/HealthGraphSync/Sources/HealthGraphSync/AgentChatView.swift)) that talks to the Pillar 1 Aura Agent's `/invoke` endpoint via OAuth client-credentials. Four suggestion chips compute concrete date ranges at tap time (ISO Mon–Sun for "Last week summary", last 12 weeks for overtraining, last 30 / 60 days for workout-HRV correlations) so the agent always gets specific dates — not vague phrases. The fresh answer auto-opens in a draggable sheet overlay (`.medium` / `.large` detents) on top of the dashboard, with full Markdown rendering — paragraphs, `*`/`-` bullets, `N.` numbered lists, inline `**bold**` / `*italic*` / `` `code` `` via `AttributedString(markdown:)`, plus trend arrows (↑ improving, ↓ declining, → stable) the agent emits in its longevity analysis.

![iPhone HealthGraphSync end-to-end — HealthKit delta upload to Aura, "Ask your graph" Dashboard panel, and the auto-opening answer overlay with Markdown rendering and trend arrows](docs/images/hackathon/09-iphone-trio-sync-ask-answer.jpeg)

---

### Linked documentation

| Doc | What it covers |
| --- | --- |
| [`docs/IOS_APP.md`](docs/IOS_APP.md) | iOS app architecture, sync flow, configuration |
| [`docs/IOS_PLAN.md`](docs/IOS_PLAN.md) | Phase-by-phase build plan and status |
| [`docs/IOS_DEVICE_INSTALL.md`](docs/IOS_DEVICE_INSTALL.md) | Apple Development cert + device deploy steps |
| [`docs/AUTH_RESEARCH.md`](docs/AUTH_RESEARCH.md) | Why we don't reuse `login.neo4j.com`; what Neo4j actually supports |
| [`docs/AUTH_SETUP.md`](docs/AUTH_SETUP.md) | Auth0 + Aura JWKS one-time setup (~15 min) |
| [`docs/AURA_VERIFICATION.md`](docs/AURA_VERIFICATION.md) | How to probe your Aura instance, schema audit |
| [`docs/DASHBOARD.md`](docs/DASHBOARD.md) | Dashboard panels & longevity science behind each metric |
| [`docs/HEALTH_ANALYTICS.md`](docs/HEALTH_ANALYTICS.md) | Analytics query catalog |
| [`docs/SCORING.md`](docs/SCORING.md) | Recovery / Strain / Sleep score formulas |
| [`docs/STATUS.md`](docs/STATUS.md) | Project status & rollout plan |
| [`docs/AURA_API_FEEDBACK.md`](docs/AURA_API_FEEDBACK.md) | Open feedback for the Neo4j Aura team |
| [`cypher/README.md`](cypher/README.md) | Cypher & GraphQL files: what's where, how to deploy |
| [`backend/README.md`](archive/backend-legacy/README.md) (archived) | Original FastAPI sync service — superseded by direct Aura GraphQL |

### Status & links

**Current status (2026-05-16):** all four pillars are live end-to-end against a real Aura instance. Four of five tracked issues are closed; only Auth0 production sign-in (#5) remains open. The Aura instance has been cost-optimized to a 1 GB professional tier, and the talk deck is published on GitHub Pages.

- ✅ Issue [#2 — Apple Health Sync to Aura + In-app Dashboard](https://github.com/ma3u/healthgraph-agent/issues/2) (closed)
- ✅ Issue [#3 — GraphQL Data API for iOS + GitHub Pages personal dashboard](https://github.com/ma3u/healthgraph-agent/issues/3) (closed)
- ✅ Issue [#4 — Aura Agent integration + Neo4j Skills](https://github.com/ma3u/healthgraph-agent/issues/4) (closed)
- 📌 Issue [#5 — Auth0 sign-in + Bearer JWT path for iOS](https://github.com/ma3u/healthgraph-agent/issues/5) (open — only remaining work)
- ✅ Issue [#6 — HealthGraphCoach as code via Aura v2beta1 `/agents`](https://github.com/ma3u/healthgraph-agent/issues/6) (closed)
- 🏆 [Neo4j Aura Agent Hackathon 2026 — Apr 15 – Jun 15](https://community.neo4j.com/t/start-here-register-get-aura-credits-aura-agent-hackathon-2026/77191)
- 🎤 Talk deck: [ma3u.github.io/healthgraph-agent/talk](https://ma3u.github.io/healthgraph-agent/talk/)
- 🌐 Live site: [ma3u.github.io/healthgraph-agent](https://ma3u.github.io/healthgraph-agent/)

---

## The idea

Apple Health collects thousands of data points daily like heart rate, HRV, steps, sleep, workouts, respiratory rate, blood oxygen, but stores them as flat, disconnected time series. You can see _what_ happened, but never _why_ or _how things relate_.

**HealthGraph Agent** transforms your Apple Health XML export into a Neo4j knowledge graph that captures the relationships _between_ your health metrics, then deploys a Neo4j Aura Agent that can reason over those relationships to answer longevity questions like:

- "How does my sleep quality correlate with workout intensity?"
- "Show me weeks where my HRV was low — what happened before?"
- "What's my VO2max trend — am I improving my cardiorespiratory fitness?"
- "Am I overtraining? Show me training load vs recovery balance."
- "Find my best recovery days — what did I do differently?"

## Why a graph?

Health data is inherently relational. A flat table can show you your heart rate over time, but a graph can show you that _this specific workout_ on _this specific day_ preceded _this specific HRV drop_ during _this sleep session_, which correlated with _this elevated resting heart rate_ the next morning. The graph captures causality chains that tables cannot.

```
(:Person)-[:USES]->(:Device)-[:RECORDS]->(:MetricType)-[:HAS]->(:Measurement)
(:Measurement)-[:MEASURED_ON]->(:Day)-[:PART_OF]->(:Week)
(:Workout)-[:ON_DAY]->(:Day)<-[:ON_DAY]-(:SleepSession)
(:Day)-[:HAS_SUMMARY]->(:DailySummary {avg_hr, total_steps, hrv_mean, sleep_hours})
(:Workout)-[:FOLLOWED_BY]->(:SleepSession)
(:DailySummary)-[:CORRELATES_WITH]->(:DailySummary) // cross-metric correlations
```

---

## Two ways to import your data

### Method 1: Python ETL (recommended)

Direct Python pipeline that parses, transforms, and loads into Neo4j in one step. Works with both **Neo4j Desktop** and **Neo4j Aura**.

```bash
# Configure connection
cp .env.example .env
# Edit .env:
#   Desktop: NEO4J_URI=bolt://localhost:7687
#   Aura:    NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io

# Run with your own Apple Health data
bash scripts/run_pipeline.sh data/export.xml

# Or generate synthetic data and load
GENERATE=1 PERSONA=biohacker bash scripts/run_pipeline.sh
```

### Method 2: CSV + LOAD CSV (no Python needed at runtime)

Export data to CSV files, then import via pure Cypher in Neo4j Browser. Ideal for users who prefer working directly in the Neo4j Browser UI.

```bash
# Step 1: Export to CSV (one-time Python step)
METHOD=csv bash scripts/run_pipeline.sh data/export.xml

# Step 2: Copy CSVs into Neo4j Desktop import/ directory
#   Neo4j Desktop → Database → ... → Open folder → Import
#   Copy all files from data/csv/ into that folder

# Step 3: Open Neo4j Browser and run cypher/load_csv_import.cypher
#   Paste each block one at a time
```

**For Aura**: Upload CSVs to a public URL, then replace `file:///` with your URL prefix in `load_csv_import.cypher`.

---

## Synthetic test data

Don't have Apple Health data? Generate realistic 12-month synthetic datasets:

```bash
cd etl
python generate_test_data.py --persona athlete --days 365 --output ../data/export.xml
```

| Persona      | RHR  | HRV  | Steps/day | Sleep | VO2Max | Workouts/week |
|-------------|------|------|-----------|-------|--------|---------------|
| `default`   | 64   | 42ms | 8,000     | 7.2h  | 38     | 3.8           |
| `athlete`   | 52   | 65ms | 12,000    | 7.8h  | 48     | 5.6           |
| `sedentary` | 74   | 28ms | 4,500     | 6.5h  | 30     | 1.4           |
| `biohacker` | 58   | 55ms | 10,000    | 7.5h  | 42     | 4.6           |

---

## 20 Longevity Cypher queries

The file `cypher/longevity_queries.cypher` contains 20 ready-to-run queries focused on longevity science biomarkers:

| #  | Query                                | Longevity relevance                                      |
|----|--------------------------------------|----------------------------------------------------------|
| 1  | VO2max trend over time               | Strongest predictor of all-cause mortality                |
| 2  | Monthly VO2max with exercise context | Zone 2 and HIIT drive VO2max improvement                 |
| 3  | Resting heart rate trend             | RHR > 75 doubles mortality risk vs < 55                  |
| 4  | HRV weekly trend                     | Autonomic resilience declines with age                    |
| 5  | Sleep duration distribution          | U-shaped mortality curve; 7-8h optimal                   |
| 6  | Exercise variety and consistency     | Cardio + strength = 40% lower mortality vs either alone   |
| 7  | Zone 2 proxy (walks + easy cardio)   | Foundation of longevity exercise: 150+ min/week           |
| 8  | Recovery quality after hard training | Where adaptation happens                                  |
| 9  | Strength training frequency          | Prevents sarcopenia, preserves bone density               |
| 10 | Cardio training volume               | 150 min/week minimum; 300+ for extra benefit              |
| 11 | Sleep consistency                    | Irregular sleep is an independent mortality risk          |
| 12 | Compound longevity score per day     | Multi-marker "green days" assessment                      |
| 13 | Daily steps (NEAT)                   | 7,000-10,000 steps reduces mortality 50-70%               |
| 14 | Blood oxygen trends                  | Catches respiratory/cardiovascular decline early          |
| 15 | Workout impact on next-day HRV       | Training adaptation signal                                |
| 16 | Training load vs recovery balance    | Overtraining detection                                    |
| 17 | Rest day quality                     | Active recovery effectiveness                             |
| 18 | Weekly energy balance                | Metabolic health proxy                                    |
| 19 | Month-over-month longevity dashboard | High-level trend across all key biomarkers                |
| 20 | Personal bests and milestones        | Progress tracking across HRV, RHR, VO2max, steps, sleep  |

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────────────┐     ┌─────────────┐
│ Apple Health │────>│  Python ETL  │────>│  Neo4j Desktop / Aura   │────>│ Aura Agent  │
│  export.xml  │     │  parse/load  │     │                         │     │  MCP + REST │
└─────────────┘     └──────┬───────┘     └─────────────────────────┘     └─────────────┘
                           │                        ▲
                           │  CSV export            │ LOAD CSV
                           └──> data/csv/ ──────────┘
```

### Graph model

| Node            | Properties                                        | Source                          |
|-----------------|---------------------------------------------------|---------------------------------|
| `Person`        | `name`                                            | export.xml `<Me>` tag           |
| `Device`        | `name`, `manufacturer`, `model`, `sw_version`     | `sourceName`, `device` attrs    |
| `MetricType`    | `identifier`, `display_name`, `unit`, `category`  | `type` attr (cleaned)           |
| `Workout`       | `activity_type`, `duration`, `energy_burned`, `distance` | `<Workout>` elements     |
| `SleepSession`  | `in_bed_start`, `in_bed_end`, `asleep_duration`   | SleepAnalysis records           |
| `Day`           | `date`, `day_of_week`                             | Derived from timestamps         |
| `Week`          | `year`, `week_number`, `start_date`               | Derived from timestamps         |
| `DailySummary`  | `avg_hr`, `hrv_mean`, `total_steps`, `active_cal`, `sleep_hours` | Aggregated     |

| Relationship         | From → To                       | Properties              |
|----------------------|---------------------------------|-------------------------|
| `USES`               | Person → Device                 |                         |
| `RECORDS`            | Device → MetricType             |                         |
| `HAS`                | MetricType → Measurement        |                         |
| `MEASURED_ON`        | Measurement → Day               |                         |
| `ON_DAY`             | Workout / SleepSession → Day    |                         |
| `PART_OF`            | Day → Week                      |                         |
| `HAS_SUMMARY`        | Day → DailySummary              |                         |
| `FOLLOWED_BY`        | Workout → SleepSession          | `hours_between`         |
| `NEXT_DAY`           | Day → Day                       |                         |
| `CORRELATES_WITH`    | DailySummary → DailySummary     | `correlation_score`     |

### Aura Agent tools

| Tool              | Type            | Purpose                                            |
|-------------------|-----------------|-----------------------------------------------------|
| Weekly overview   | Cypher Template | "Show me last week's health summary"                |
| Workout impact    | Cypher Template | "How did my workout affect my sleep/HRV?"           |
| Trend finder      | Text2Cypher     | Free-form questions about health patterns           |
| Pattern match     | Similarity Search | Find similar days/weeks by health metric embeddings |

---

## Longevity Dashboard

Two visualization options for exploring your health data:

### Python Charts

```bash
# Generate all charts (full history)
python3 scripts/visualize_longevity.py

# Last 6 months only
python3 scripts/visualize_longevity.py --months 6
```

Generates an 8-panel dashboard and individual high-res charts with longevity zone coloring:

| Chart | What it shows |
|-------|--------------|
| Resting Heart Rate | Trend with zones: green (< 55), yellow (55-65), red (> 65 bpm) |
| HRV (SDNN) | Autonomic resilience: green (> 40ms), yellow (25-40), red (< 25) |
| VO2max | #1 longevity predictor: green (> 45), yellow (35-45), red (< 35) |
| Daily Steps | Bar chart with 7k minimum and 10k target lines |
| Sleep Duration | Green optimal zone at 7-9 hours |
| Workout Volume | Monthly minutes, green when exceeding 150 min/week target |
| Workout Types | Distribution of activity types |
| Composite Trend | All metrics normalized, higher = better |

![Python Longevity Dashboard](docs/images/python_dashboard.png)

See [docs/DASHBOARD.md](docs/DASHBOARD.md) for detailed documentation and longevity science behind each metric.

### Health Analysis Report

Beyond charts, generate a personalized analysis with actionable advice:

```bash
python3 scripts/analyze_longevity.py
```

See the latest report: **[Longevity Health Analysis Report](docs/HEALTH_REPORT.md)** — includes trend analysis, exercise balance, overtraining detection, workout-HRV impact ranking, and specific action items.

For a deep-dive on **exercise-duration data quality** (runaway watch sessions, cross-app double tracking, and the cleaning rules used to produce credible weekly totals) see **[Exercise Duration Report](docs/EXERCISE_REPORT.md)** and the corresponding Cypher in [`cypher/exercise_duration_clean.cypher`](cypher/exercise_duration_clean.cypher). The NeoDash dashboard now includes a dedicated **Exercise Duration (Cleaned)** page with weekly/monthly/yearly cleaned trends and a raw-vs-cleaned audit.

### Interactive Dashboards

Two dashboards are bundled:

1. `neodash/longevity_dashboard.json` — 4 pages of longevity biomarkers (RHR/HRV/VO2max/sleep/workout trends, recovery analysis, cleaned exercise duration, graph exploration).
2. `neodash/whoop_dashboard.json` — **5 pages, 35 panels** in a Whoop-style layout: daily hero card (Recovery %, Strain 0–21, Sleep %), Recovery deep-dive, Strain deep-dive, Sleep deep-dive, Health Monitor (8.5-year trends). Formulas: [docs/SCORING.md](docs/SCORING.md). Panel-by-panel: [docs/DASHBOARD.md](docs/DASHBOARD.md).

Both files are exported in NeoDash JSON v2.5, which is the format that **both** the open-source NeoDash app and Aura's built-in Dashboards can consume.

#### Three ways to view them

**A. Open-source NeoDash (fastest, no install)**

```bash
# 1. Upload the dashboard into your graph as a _Neodash_Dashboard node
python3 scripts/upload_dashboard.py
```

Then open https://neodash.graphapp.io → connect with your `.env` credentials → *Load Dashboard from Neo4j* → pick *HealthGraph — Whoop-style View*. The dashboard renders directly from the node we just inserted.

The script is idempotent (deterministic UUID per title — re-running updates rather than duplicates).

**B. Aura's built-in Dashboards (web Console)**

Aura's *Tools → Dashboards* feature stores dashboards in its own managed service (separate from your graph), so the CLI upload above isn't enough — you have to *import* once via the UI:

1. Aura Console → Tools → **Dashboards** → **Import**
2. Either drag in `neodash/whoop_dashboard.json` or choose *"Select from database"* (it will find the node `scripts/upload_dashboard.py` wrote)

After the one-time import, the dashboard lives in Aura's storage and reopens instantly.

**C. NeoDash via Neo4j Desktop**

1. Install **NeoDash** from the Desktop plugin gallery
2. *Load Dashboard* → browse to `neodash/whoop_dashboard.json` (or run the upload script and pick from DB)

![NeoDash Longevity Dashboard](docs/images/neodash_dashboard.png)

#### Why two products?

Aura's built-in Dashboards (`/tools/dashboards`) is a separate, newer product from the legacy NeoDash. The two have different storage and APIs but share the same JSON import format. We can fully automate option A via `cypher-shell` + the upload script; option B requires one UI click because Aura's managed-storage endpoints aren't exposed to service-account tokens.

---

## Repo structure

```
healthgraph-agent/
├── README.md
├── .gitignore
├── .env.example                     # Connection config for Desktop + Aura
│
├── docs/
│   ├── export_instructions.md       # How to export from iPhone
│   ├── DASHBOARD.md                 # Dashboard documentation + longevity science
│   └── SCORING.md                   # Whoop-equivalent Recovery / Strain / Sleep formulas
│
├── etl/
│   ├── requirements.txt             # lxml, neo4j, python-dotenv, tqdm
│   ├── parse_health_xml.py          # Streaming XML parser (handles 2GB+)
│   ├── transform.py                 # Aggregate daily summaries, build relationships
│   ├── load_to_neo4j.py             # Method 1: Direct batch load via Bolt driver
│   ├── export_to_csv.py             # Method 2: Export to CSV for LOAD CSV import
│   └── generate_test_data.py        # Synthetic data generator (4 personas)
│
├── cypher/
│   ├── sample_queries.cypher        # 7 general-purpose Aura Agent templates
│   ├── longevity_queries.cypher     # 20 longevity-focused analysis queries
│   ├── whoop_queries.cypher         # Recovery/Strain/Sleep score Cypher (standalone)
│   ├── exercise_duration_clean.cypher
│   └── load_csv_import.cypher       # Method 2: LOAD CSV import script
│
├── scripts/
│   ├── run_pipeline.sh              # End-to-end orchestration (both methods)
│   ├── upload_dashboard.py          # Push a NeoDash JSON into Aura as _Neodash_Dashboard
│   ├── analyze_longevity.py         # Generates docs/HEALTH_REPORT.md from the live graph
│   └── visualize_longevity.py       # Python chart generator (8 panels + individual)
│
├── neodash/
│   ├── longevity_dashboard.json     # Interactive NeoDash dashboard (4 pages)
│   └── whoop_dashboard.json         # Whoop-style dashboard (5 pages, 35 panels)
│
└── agent/
    └── agent_config.md              # Aura Agent system prompt + tool definitions
```
---

## Getting started

### Prerequisites

- Python 3.11+
- Neo4j Desktop (free) OR Neo4j Aura account (free tier available)

### Quick start

```bash
# 1. Clone
git clone https://github.com/ma3u/healthgraph-agent.git
cd healthgraph-agent

# 2. Install dependencies
pip install -r etl/requirements.txt

# 3. Get your health data (pick one):

#    A) Export from iPhone:
#       Health → Profile → Export All Health Data
#       Unzip and place export.xml in data/

#    B) Generate synthetic data:
GENERATE=1 bash scripts/run_pipeline.sh

# 4. Configure Neo4j connection
cp .env.example .env
# Edit .env with your Neo4j URI and password

# 5. Import (pick a method):

#    Method 1 — Python ETL (direct load):
bash scripts/run_pipeline.sh

#    Method 2 — CSV + LOAD CSV:
METHOD=csv bash scripts/run_pipeline.sh
#    Then run cypher/load_csv_import.cypher in Neo4j Browser

# 6. Run longevity queries
#    Open cypher/longevity_queries.cypher in Neo4j Browser
```

---

## Key health metrics

### From Apple Watch
- Heart rate (resting, walking, workout)
- Heart rate variability (SDNN)
- Blood oxygen (SpO2)
- Respiratory rate
- Active/basal energy burned
- Stand hours, exercise minutes

### From iPhone
- Step count
- Walking + running distance
- Flights climbed

### Derived (computed in ETL)
- Daily longevity score (composite of HRV, RHR, sleep, steps, exercise)
- Recovery patterns (workout → sleep → next-day HRV chains)
- Training load balance (volume vs recovery markers)
- Sleep consistency (standard deviation across weeks)

---

## Privacy & data handling

- **All data stays local** during ETL — no third-party APIs for parsing
- Apple Health export contains PII — `.gitignore` excludes all XML/CSV data files
- Neo4j connection via encrypted Bolt protocol (Aura) or local-only (Desktop)
- No health data committed to the repository — only code and schema

---

## Tech stack

| Component    | Technology                     | License     |
|-------------|-------------------------------|-------------|
| ETL         | Python 3.11+, lxml, neo4j-driver | Apache 2.0 |
| Database    | Neo4j Desktop or AuraDB       | Commercial  |
| Agent       | Neo4j Aura Agent (Gemini 2.5 Flash) | Commercial |
| Embeddings  | Vertex AI `gemini-embedding-001` | Commercial |

---



## 🎤 Neo4j Theatre session proposal at the WeAreDevelopers conference, Berlin 2026

The [Talk deck](https://ma3u.github.io/healthgraph-agent/talk/) was built for a **Neo4j Theatre session proposal at the WeAreDevelopers conference, Berlin 2026** — proposed talk _"From Apple Health to Aura Agent"_: a live demo of the full pipeline (Apple Health export → ETL → Aura graph → 6-page dashboard → AI agent reasoning over the graph), preferred slot Thursday 9 July, morning. The proposal is submitted — fingers crossed for the spot. 🤞

---

## Hackathon checklist

- [x] Complete [Building Agents in Neo4j Aura Course](https://dev.neo4j.com/aura-agent-hackathon-community) (by May 15)
- [x] Register for [$100 Aura Credits](https://dev.neo4j.com/credit-claim-aura-agent-hackathon-2026)
- [x] Build ETL pipeline (Method 1: Python, Method 2: CSV)
- [x] Synthetic test data generator (4 personas)
- [x] 20 longevity-focused Cypher queries
- [x] Load health data into Aura (3,117 days, 4,061 workouts — 10,854 nodes, 16,754 relationships)
- [x] Longevity dashboard (Python charts + NeoDash)
- [x] Deploy Aura GraphQL Data API via `scripts/create_aura_data_api.py` ([#3](https://github.com/ma3u/healthgraph-agent/issues/3))
- [x] iPhone app — HealthKit → delta scan → GraphQL upload, verified on real device ([#2](https://github.com/ma3u/healthgraph-agent/issues/2))
- [x] GitHub Pages daily snapshot live ([#3](https://github.com/ma3u/healthgraph-agent/issues/3))
- [x] Configure Aura Agent with tools — `HealthGraph Agent`, 6 tools, MCP enabled ([#4](https://github.com/ma3u/healthgraph-agent/issues/4))
- [x] Agent-as-code via v2beta1 `/agents` — `agents/healthgraph-coach.json` + `scripts/create_aura_agent.py` ([#6](https://github.com/ma3u/healthgraph-agent/issues/6))
- [x] iOS "Ask your graph" panel — OAuth + invoke endpoint wired ([#4](https://github.com/ma3u/healthgraph-agent/issues/4))
- [x] Install Neo4j Skills for Claude Code ([#4](https://github.com/ma3u/healthgraph-agent/issues/4))
- [x] Test agent with longevity questions — REST smoke-test passed ([#6](https://github.com/ma3u/healthgraph-agent/issues/6))
- [x] Capture demo Q&As in [`docs/AGENT_DEMO.md`](docs/AGENT_DEMO.md) — three grounded answers from the live agent
- [x] Screenshots in `docs/images/hackathon/` wired into the [Hackathon achievements](#-hackathon-achievements) table
- [x] Cost-optimize the Aura instance — resized 8 GB → 1 GB professional; daily workflow auto-pauses it
- [x] Build the talk deck (Slidev) and publish it to GitHub Pages at [`/talk/`](https://ma3u.github.io/healthgraph-agent/talk/)
- [x] Submit the [WeAreDevelopers Berlin 2026 Neo4j Theatre proposal](#-neo4j-theatre-session-proposal-at-the-wearedevelopers-conference-berlin-2026)
- [x] Submit to the [hackathon community thread](https://community.neo4j.com/t/start-here-register-get-aura-credits-aura-agent-hackathon-2026/77191)
- [ ] Auth0 production sign-in path — last open item ([#5](https://github.com/ma3u/healthgraph-agent/issues/5))
- [ ] Generate vector embeddings for similarity search (needs a bring-your-own embedding model)

