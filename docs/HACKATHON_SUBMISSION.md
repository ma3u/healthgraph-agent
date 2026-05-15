# Hackathon submission update — HealthGraph Agent: Apple Health → Aura, end-to-end

Draft for a follow-up post to my original submission on the
[Aura Agent Hackathon thread](https://community.neo4j.com/t/start-here-register-get-aura-credits-aura-agent-hackathon/77191/63).
Paste the section below into the forum.

---

Hi everyone — quick update on my submission ([healthgraph-agent](https://github.com/ma3u/healthgraph-agent)). Since my last post I've added a full set of Neo4j Aura elements on top of the original ETL + longevity-query foundation. The whole stack now runs **end-to-end**: iPhone → Aura graph → Aura Agent → iOS chat.

**README + docs:** https://github.com/ma3u/healthgraph-agent
**Live Pages snapshot:** https://ma3u.github.io/healthgraph-agent/snapshot/

The submission is now built on **four pillars**, each backed by a Neo4j Aura primitive:

## 1. 🤖 Aura Agent (`HealthGraph Agent`)

A longevity-focused assistant with **6 tools** — Text2Cypher + 5 parameterized Cypher templates: `health_overview`, `workout_recovery`, `longevity_trends`, `overtraining_check`, `exercise_balance`. MCP enabled, REST-invokable.

The big addition since my last post: the agent is **defined as code** via the new [Aura v2beta1 `/agents` API](https://neo4j.com/docs/aura/platform/api/specification/?urls.primaryName=Aura%20v2beta1) (thanks to [Ed Sandoval](https://www.linkedin.com/in/edsandoval) for pointing it out). The JSON is committed at [`agents/healthgraph-coach.json`](https://github.com/ma3u/healthgraph-agent/blob/main/agents/healthgraph-coach.json) and reconciled with one script ([`scripts/create_aura_agent.py`](https://github.com/ma3u/healthgraph-agent/blob/main/scripts/create_aura_agent.py)) supporting three modes: `status` (default — diff live vs file), `--pull` (live → file), `--push` (file → live, POST or PUT).

Three real Q&As captured at [`docs/AGENT_DEMO.md`](https://github.com/ma3u/healthgraph-agent/blob/main/docs/AGENT_DEMO.md):

- *"What is my average resting heart rate over the last 30 days, and how does it compare to my all-time baseline?"* — grounded analysis with all-time avg `56.11 bpm` vs last-30 `57.82 bpm`, longevity context, four actionable recommendations.
- *"Am I overtraining?"* — week-by-week breakdown across 12 weeks with `CAUTION` / `OK` flags, deload-week recommendation.
- A "no data" failure case where the agent honestly reports a data gap instead of fabricating.

![Aura Agent playground — longevity question](https://github.com/ma3u/healthgraph-agent/raw/main/docs/images/hackathon/01-aura-agent-playground-longevity-question.png)

## 2. 📊 Aura Dashboard

Whoop-style NeoDash dashboard ([`neodash/whoop_dashboard.json`](https://github.com/ma3u/healthgraph-agent/blob/main/neodash/whoop_dashboard.json)) — **5 pages, 35 panels**: daily hero card (Recovery %, Strain 0–21, Sleep %), Recovery deep-dive, Strain deep-dive, Sleep deep-dive, and 8.5-year Health Monitor. Score formulas at [`docs/SCORING.md`](https://github.com/ma3u/healthgraph-agent/blob/main/docs/SCORING.md).

Pushed into Aura's built-in *Tools → Dashboards* via [`scripts/upload_dashboard.py`](https://github.com/ma3u/healthgraph-agent/blob/main/scripts/upload_dashboard.py) — idempotent (deterministic UUID per title).

![Aura Dashboard — Whoop-style Recovery view](https://github.com/ma3u/healthgraph-agent/raw/main/docs/images/hackathon/02-aura-dashboard-whoop-recovery.png)

## 3. 🔍 Aura GraphQL Data API + GitHub Pages

**GraphQL Data API**: curated SDL with `@cypher` MERGE mutations (`ingestDay` / `ingestWorkout` / `ingestSleep`) at [`cypher/graphql_schema.graphql`](https://github.com/ma3u/healthgraph-agent/blob/main/cypher/graphql_schema.graphql). Deployed against the live tenant via [`scripts/create_aura_data_api.py`](https://github.com/ma3u/healthgraph-agent/blob/main/scripts/create_aura_data_api.py) — `aura-cli` v1.8.0 has no `data-api` commands, so the script hits the `v1beta5` REST endpoints directly. All three mutations smoke-tested + idempotent.

**GitHub Pages**: daily Recovery snapshot rendered by [`scripts/render_snapshot.py`](https://github.com/ma3u/healthgraph-agent/blob/main/scripts/render_snapshot.py), committed by a GitHub Actions workflow on a 06:30 UTC cron (auto-resumes paused Aura instances). Served at **[ma3u.github.io/healthgraph-agent/snapshot/](https://ma3u.github.io/healthgraph-agent/snapshot/)**.

| GraphQL Data API — schema overview | Daily pipeline → renders the Pages dashboard |
| --- | --- |
| ![GraphQL Data API schema](https://github.com/ma3u/healthgraph-agent/raw/main/docs/images/hackathon/03-aura-graphql-data-api-schema.png) | ![Daily GitHub Actions pipeline](https://github.com/ma3u/healthgraph-agent/raw/main/docs/images/hackathon/04-daily-github-actions-pipeline.png) |

![GitHub Pages — daily Recovery snapshot](https://github.com/ma3u/healthgraph-agent/raw/main/docs/images/hackathon/05-github-pages-recovery-snapshot.png)

## 4. 📱 iPhone App — HealthKit sync + "Ask your graph"

`HealthGraphSync` iOS app ([`ios/`](https://github.com/ma3u/healthgraph-agent/tree/main/ios)) — Swift 6 / iOS 26.5 SDK. Reads HealthKit **on-device**, queries Aura for `max(Day.date)`, scans HealthKit since then, presents the per-type delta, then uploads via the three GraphQL `@cypher` mutations. Includes `Rescan last 30 days` and `Rescan last 365 days` flows for backfilling partial days. Verified end-to-end on real **iPhone 17 Pro** — graph grew from 3,087 → 3,117 `:Day` nodes after first sync.

The Dashboard tab embeds the **"Ask your graph"** chat panel: 4 suggestion chips (`Last week summary` / `Overtraining check` / `Best workout day` / `Sleep vs HRV`), text input, scrollable Q&A history persisted to UserDefaults. Hits the same `HealthGraph Agent` invoke endpoint as the REST demo above — OAuth2 client-credentials → Bearer JWT.

| iPhone Sync tab — delta upload to Aura | iPhone Dashboard — "Ask your graph" |
| --- | --- |
| ![iPhone HealthKit sync](https://github.com/ma3u/healthgraph-agent/raw/main/docs/images/hackathon/06-iphone-healthkit-sync-delta-upload.jpeg) | ![iPhone Dashboard Ask your graph](https://github.com/ma3u/healthgraph-agent/raw/main/docs/images/hackathon/07-iphone-dashboard-ask-your-graph.jpeg) |

## BYO Aura

The whole thing is **bring-your-own-Aura**: every installer points the iOS app and the GitHub workflow at their *own* Aura instance. There's no shared backend. Both provisioning scripts (`create_aura_data_api.py`, `create_aura_agent.py`) take `AURA_CLIENT_ID` / `AURA_CLIENT_SECRET` / `AURA_INSTANCEID` from a local `.env` and produce a working stack in <5 min.

## What's open

- **#5** Auth0 production sign-in path (Apple / Google / GitHub / Microsoft → Bearer JWT to the Data API). Currently using dev-mode `x-api-key`; Auth0 work is gated on a manual tenant setup.
- Vector embeddings for similarity search on `DailySummary.description`.
- One bug preserved for round-trip fidelity: `health_overview` tool's template references `$workout_type` but its parameters are `start_date`/`end_date` — will fix in a follow-up `--push`.

## Issues closed during this stretch

- [#2 Apple Health Sync to Aura + In-app Dashboard](https://github.com/ma3u/healthgraph-agent/issues/2)
- [#3 GraphQL Data API for iOS + GitHub Pages personal dashboard](https://github.com/ma3u/healthgraph-agent/issues/3)
- [#4 Aura Agent integration + Neo4j Skills](https://github.com/ma3u/healthgraph-agent/issues/4)
- [#6 HealthGraphCoach as code via Aura v2beta1 `/agents`](https://github.com/ma3u/healthgraph-agent/issues/6)

Feedback welcome 🙏 — particularly on whether the agent's tool selection feels right, and on the `v2beta1` agents-as-code workflow (super useful, please keep going with it).

— Matthias / [@ma3u](https://github.com/ma3u)
