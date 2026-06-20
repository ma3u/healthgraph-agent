# Hackathon submission update — HealthGraph Agent: Apple Health → Aura, end-to-end

Draft for a follow-up post on the Neo4j community Aura Agent Hackathon thread.
Trimmed to the forum's new-user limits: **4 embedded images, 2 links**.
Paste the section below into the forum.

---

Hi everyone — quick update on my submission. Since my last post I've added a full set of Neo4j Aura elements on top of the original ETL + longevity-query foundation. The whole stack now runs **end-to-end**: iPhone → Aura graph → Aura Agent → iOS chat. Everything is open source and reproducible.

→ Repo + README: https://github.com/ma3u/healthgraph-agent
→ Live daily snapshot: https://ma3u.github.io/healthgraph-agent/snapshot/

The submission is now built on **five pillars**, each backed by a Neo4j Aura primitive:

## 1. 🤖 Aura Agent (`HealthGraph Agent`)

A longevity-focused assistant with **6 tools** — Text2Cypher + 5 parameterized Cypher templates (`health_overview`, `workout_recovery`, `longevity_trends`, `overtraining_check`, `exercise_balance`). MCP enabled, REST-invokable.

The big addition: the agent is **defined as code** via the new Aura v2beta1 `/agents` API (thanks to Ed Sandoval for the pointer). The full agent JSON is committed at `agents/healthgraph-coach.json` and reconciled with one script (`scripts/create_aura_agent.py`) supporting three modes: `status` (default — diff live vs file), `--pull` (live → file), `--push` (file → live, POST or PUT). I keep a screenshot of the Console state in the repo for fidelity.

While wiring the iPhone chat I caught and fixed a copy-paste bug in the `health_overview` Cypher template — it referenced `$workout_type` while the tool parameters were `$start_date`/`$end_date`, so the agent was reporting "tool is currently unavailable". The rewritten template now returns daily metrics (RHR / HRV / steps / sleep_hours / workout_min / kcal / VO2max) for the requested window **plus** a rolling 30-day baseline ending the day before — exactly what the system prompt asks for.

Three real Q&As are captured at `docs/AGENT_DEMO.md` (in the repo): a grounded RHR analysis ("56.11 bpm all-time vs 57.82 bpm last-30"), a 12-week overtraining check with CAUTION flags + deload-week recommendations, and a "no data" failure case where the agent honestly reports a gap instead of fabricating.

![Aura Agent playground — longevity question](https://github.com/ma3u/healthgraph-agent/raw/main/docs/images/hackathon/01-aura-agent-playground-longevity-question.png)

## 2. 📊 Aura Dashboard

Whoop-style NeoDash dashboard at `neodash/whoop_dashboard.json` — **5 pages, 35 panels**: daily hero card (Recovery %, Strain 0–21, Sleep %), Recovery deep-dive, Strain deep-dive, Sleep deep-dive, and 8.5-year Health Monitor. Score formulas in `docs/SCORING.md`. Pushed into Aura's built-in *Tools → Dashboards* via `scripts/upload_dashboard.py` — idempotent (deterministic UUID per title).

![Aura Dashboard — Whoop-style Recovery view](https://github.com/ma3u/healthgraph-agent/raw/main/docs/images/hackathon/02-aura-dashboard-whoop-recovery.png)

## 3. 🔍 Aura GraphQL Data API + GitHub Pages

**GraphQL Data API**: curated SDL with `@cypher` MERGE mutations (`ingestDay` / `ingestWorkout` / `ingestSleep`) at `cypher/graphql_schema.graphql`. Deployed against the live tenant via `scripts/create_aura_data_api.py` — `aura-cli` v1.8.0 has no `data-api` commands, so the script hits the `v1beta5` REST endpoints directly. All three mutations smoke-tested + idempotent.

**GitHub Pages**: daily Recovery snapshot rendered by `scripts/render_snapshot.py`, committed by a GitHub Actions workflow on a 06:30 UTC cron (auto-resumes paused Aura instances). The live link is in the header above.

![GitHub Pages — daily Recovery snapshot rendered from the Aura graph](https://github.com/ma3u/healthgraph-agent/raw/main/docs/images/hackathon/05-github-pages-recovery-snapshot.png)

## 4. 📱 iPhone App — HealthKit sync + "Ask your graph"

`HealthGraphSync` iOS app — Swift 6 / iOS 26.5 SDK. Reads HealthKit **on-device**, queries Aura for `max(Day.date)`, scans HealthKit since then, presents the per-type delta, then uploads via the three GraphQL `@cypher` mutations. Includes `Rescan last 30 days` and `Rescan last 365 days` flows. Verified end-to-end on real **iPhone 17 Pro** — graph grew from 3,087 → 3,117 `:Day` nodes after first sync.

The Dashboard tab embeds an **"Ask your graph"** panel that calls the same `HealthGraph Agent` `/invoke` endpoint via OAuth2 client-credentials. Four suggestion chips compute concrete date ranges at tap time (ISO Mon–Sun for "last week", last 12 weeks for overtraining, last 30 / 60 days for workout-HRV correlations) so the agent always gets specific dates. The fresh answer auto-opens in a draggable overlay (`.medium` / `.large` detents) on top of the dashboard, with full Markdown rendering via `AttributedString(markdown:)` — paragraphs, bullets, numbered lists, inline `**bold**` / `*italic*` / `` `code` ``, and the trend arrows (↑ improving, ↓ declining, → stable) the agent emits.

![iPhone HealthGraphSync end-to-end — HealthKit delta upload, "Ask your graph" Dashboard panel, and the auto-opening answer overlay with Markdown rendering, trend arrows, and real numbers from the fixed health_overview tool](https://github.com/ma3u/healthgraph-agent/raw/main/docs/images/hackathon/09-iphone-trio-sync-ask-answer.jpeg)

## 5. 💰 On-demand Aura — cost-efficient by design

A graph you only pay for when you use it. The iPhone app **wakes** the Aura instance each morning — one resume covers the HealthKit sync + dashboard refresh + a few agent questions — and a watchdog **auto-pauses** it after 30 minutes of no database activity. That's a *real* sliding-TTL idle window (every sync/agent query stamps `lastActivityAt`), not just an in-flight check. Backbone: `scripts/aura_lifecycle.py` (`wake` / `touch` / `pause-if-idle --minutes 30` + a reference `/aura/wake` proxy), built on the same Aura API client-credentials as the rest.

The math on an 8 GB AuraDB Professional: always-on ≈ **$520/mo**; paused bills at ~20%. Waking it ~1 h/day on demand ≈ **$120/mo — about 77% cheaper**. Because this is bring-your-own-Aura, that turns "run your own backend" from a ~$500/mo commitment into pocket money — the difference between a one-off demo and something installers actually keep running. (Hackathon credits today; real runway after.)

## BYO Aura

The whole thing is **bring-your-own-Aura**: every installer points the iOS app and the GitHub workflow at their *own* Aura instance. There's no shared backend. Both provisioning scripts (`create_aura_data_api.py`, `create_aura_agent.py`) take `AURA_CLIENT_ID` / `AURA_CLIENT_SECRET` / `AURA_INSTANCEID` from a local `.env` and produce a working stack in <5 min.

## What's open

- **#5** Auth0 production sign-in path (Apple / Google / GitHub / Microsoft → Bearer JWT to the Data API). Currently using dev-mode `x-api-key`; Auth0 work is gated on a manual tenant setup.
- Vector embeddings for similarity search on `DailySummary.description`.

## Issues closed during this stretch

`#2` Apple Health Sync to Aura + In-app Dashboard · `#3` GraphQL Data API + Pages dashboard · `#4` Aura Agent integration + Neo4j Skills · `#6` HealthGraphCoach as code via Aura v2beta1 `/agents`.

Feedback welcome 🙏 — particularly on whether the agent's tool selection feels right, and on the `v2beta1` agents-as-code workflow (super useful, please keep going with it).

— Matthias / @ma3u
