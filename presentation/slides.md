---
theme: seriph
title: From Apple Health to Aura Agent
info: |
  ## From Apple Health to Aura Agent
  Build a Whoop-style coach for your own data.
  Escape the vendor lock-in.

  Neo4j Theatre @ WeAreDevelopers Berlin 2026
  Speaker: Matthias Buchhorn-Roth · github.com/ma3u
class: text-center cover-slide
highlighter: shiki
lineNumbers: true
# Hash routing: deep links become /talk/#6 instead of /talk/6. The server
# only ever sees /talk/, so direct links + refreshes work on GitHub Pages
# (a static host with no SPA rewrite and only a site-root 404.html).
routerMode: hash
drawings:
  persist: false
mdc: true
fonts:
  sans: Inter
  mono: 'JetBrains Mono'
transition: fade-out
---

<img src="/cover-bg.jpg" class="absolute inset-0 w-full h-full object-cover z-0" />
<div class="absolute inset-0 z-1" style="background: linear-gradient(180deg, rgba(6,10,17,0.74) 0%, rgba(6,10,17,0.88) 100%)"></div>

<div class="relative z-10">

<div class="kicker">Neo4j Theatre · WeAreDevelopers Berlin 2026</div>

# From Apple Health to Aura Agent

<div class="text-xl opacity-90 mt-4">
  Build a Whoop-style coach for your own data.<br/>
  Escape the vendor lock-in.
</div>

</div>

<div class="absolute bottom-12 left-0 right-0 text-center font-mono text-sm opacity-70 z-10">
  Matthias Buchhorn-Roth · <span class="opacity-90">@ma3u</span>
</div>

<!--
Speaker: Hi everyone. Quick framing: I built this over the hackathon window
to scratch my own itch. By the end of 20 minutes I want you to see a
pattern you can apply to any quantified-self domain, not just health.
-->

---
layout: center
---

<div class="kicker">Two things I wanted</div>

<div class="grid grid-cols-2 gap-12 mt-12">

<div class="flex flex-col gap-4">
  <div class="i-tabler-heartbeat text-6xl text-pink-500" />
  <div class="text-2xl font-semibold">A Whoop dashboard.</div>
  <div class="text-base opacity-70">For my Apple Watch data. Apple has the watch. Whoop has the coach. The data is mine.</div>
</div>

<div class="flex flex-col gap-4">
  <div class="i-tabler-lock-open text-6xl text-indigo-500" />
  <div class="text-2xl font-semibold">Escape vendor lock-in.</div>
  <div class="text-base opacity-70">8.5 years of biometrics. Stop renting them back from any single vendor.</div>
</div>

</div>

<!--
Speaker: I'm an Apple Watch user. Apple shows me charts; it doesn't coach me.
Whoop has the coach UX I want, but their hardware and $239/year subscription.
Both keep my data hostage. I want both, on my own data.
-->

---

# The problem you also have

<div class="grid grid-cols-1 gap-3 mt-4">

<div class="flex items-start gap-4">
  <div class="i-tabler-database text-3xl text-rose-500 mt-1 shrink-0" />
  <div>
    <div class="font-semibold">Your health data lives in a dozen silos.</div>
    <div class="opacity-70 text-sm">Apple Health is just one. I also want blood panels, my gym, my classes, the German ePA. None of them talk to each other:</div>
    <div class="flex flex-wrap gap-1.5 mt-2">
      <span class="chip">Apple Health</span>
      <span class="chip">Aware</span>
      <span class="chip">Blood tests</span>
      <span class="chip">ePA</span>
      <span class="chip">Medical studies</span>
      <span class="chip">eGym</span>
      <span class="chip">Beat81</span>
    </div>
  </div>
</div>

<div class="flex items-start gap-4">
  <div class="i-tabler-topology-star-3 text-3xl text-emerald-500 mt-1 shrink-0" />
  <div>
    <div class="font-semibold">Your data is relational.</div>
    <div class="opacity-70 text-sm">Workout, next night's sleep, morning HRV, recovery. Tables hide the chain.</div>
  </div>
</div>

<div class="flex items-start gap-4">
  <div class="i-tabler-brain text-3xl text-violet-500 mt-1 shrink-0" />
  <div>
    <div class="font-semibold">An LLM alone won't help.</div>
    <div class="opacity-70 text-sm">"How am I doing?" without grounded data = horoscope. The agent needs your graph.</div>
  </div>
</div>

</div>

<v-click>

<div class="mt-6 text-lg flex items-center gap-3">
  <div class="i-tabler-rocket text-2xl text-amber-500" />
  You're a developer. One graph unifies every silo.
</div>

</v-click>

<!--
Speaker: Apple Health was my starting point, but the real vision is broader.
Blood panels, the German ePA (national electronic patient record), the eGym
strength machines, my Beat81 HIIT classes, Aware, even findings from medical
studies. Seven sources, seven silos. A graph is the one model that lets all
of them share nodes — the same :Day, the same :Person — instead of seven
disconnected exports.
-->


<!--
Speaker: Three pains, one developer-shaped solution. Spend the next 20 minutes
with me. By the end you'll see a pattern you can apply to any personal
data domain.
-->

---
layout: center
---

# The pattern

<div class="grid grid-cols-4 gap-6 mt-10 max-w-5xl mx-auto">

<div class="flex flex-col items-center gap-3">
  <div class="i-tabler-folder-open text-5xl text-rose-500" />
  <div class="font-semibold">Own</div>
  <div class="text-xs opacity-70 text-center">Pull your data out (Apple Health export.xml).</div>
</div>

<div class="flex flex-col items-center gap-3">
  <div class="i-tabler-topology-star-3 text-5xl text-emerald-500" />
  <div class="font-semibold">Graph</div>
  <div class="text-xs opacity-70 text-center">Model relationships, not rows (Neo4j Aura).</div>
</div>

<div class="flex flex-col items-center gap-3">
  <div class="i-tabler-api text-5xl text-sky-500" />
  <div class="font-semibold">API</div>
  <div class="text-xs opacity-70 text-center">Typed mutations + queries (Aura GraphQL Data API).</div>
</div>

<div class="flex flex-col items-center gap-3">
  <div class="i-tabler-robot text-5xl text-violet-500" />
  <div class="font-semibold">Agent</div>
  <div class="text-xs opacity-70 text-center">Ground an LLM with Cypher templates (Aura Agent).</div>
</div>

</div>

<div class="mt-12 text-center opacity-60 text-sm">
None require hosting bills. Everything runs on your own Aura instance.
</div>

---

# Why a graph?

<div class="grid grid-cols-2 gap-8 mt-6">

<div>
  <div class="i-tabler-table text-3xl text-gray-500 mb-2" />
  <div class="text-sm opacity-70 mb-2">A flat table can tell you:</div>
  <blockquote class="text-base font-medium border-l-4 border-gray-400 pl-3">
    Your HRV was 31 ms on May 12.
  </blockquote>
</div>

<div>
  <div class="i-tabler-topology-star-3 text-3xl text-emerald-500 mb-2" />
  <div class="text-sm opacity-70 mb-2">A graph can tell you:</div>
  <blockquote class="text-base font-medium border-l-4 border-emerald-500 pl-3">
    Your HRV dropped 8 ms the morning after a 90-min run that followed a 5-hour sleep night, in a week where you trained 28 hours.
  </blockquote>
</div>

</div>

<v-click>

<div class="mt-10 font-mono text-xs opacity-70 text-center">
(:Workout)-[:FOLLOWED_BY]->(:SleepSession)-[:ON_DAY]->(:Day)-[:NEXT_DAY]->(:Day)-[:HAS_SUMMARY]->(:DailySummary)
</div>

</v-click>

<!--
Speaker: Causality chains. That's the value. The graph captures relationships
that time-series tables awkwardly join across.
-->

---
layout: section
---

<div class="kicker">What I built</div>

<div class="grid grid-cols-4 gap-6 mt-10">

<div class="flex flex-col items-center gap-2">
  <div class="i-tabler-robot text-5xl text-violet-500" />
  <div class="font-semibold text-sm">Aura Agent</div>
</div>

<div class="flex flex-col items-center gap-2">
  <div class="i-tabler-layout-dashboard text-5xl text-sky-500" />
  <div class="font-semibold text-sm">Aura Dashboard</div>
</div>

<div class="flex flex-col items-center gap-2">
  <div class="i-tabler-api text-5xl text-emerald-500" />
  <div class="font-semibold text-sm">GraphQL API + Pages</div>
</div>

<div class="flex flex-col items-center gap-2">
  <div class="i-tabler-device-mobile text-5xl text-pink-500" />
  <div class="font-semibold text-sm">iPhone Sync</div>
</div>

</div>

<div class="opacity-70 mt-10 text-base text-center">
Four pillars. Each a Neo4j Aura primitive. Each solving a piece of the pattern.
</div>

---

<div class="kicker"><div class="i-tabler-robot inline-block align-text-bottom mr-1" /> 1 · Aura Agent</div>

# HealthGraph Agent

<div class="grid grid-cols-5 gap-6 mt-4">

<div class="col-span-2 text-sm">

**What it is.** A cloud-hosted reasoning layer sitting on top of your Aura graph. The Agent picks a tool, runs Cypher, reads results, and produces a grounded answer in natural language.

**Tools (6):** Text2Cypher + 5 parameterized templates:

- `health_overview` · daily metrics + 30-day baseline
- `workout_recovery` · workout → next-day HRV
- `overtraining_check` · weekly CAUTION flags
- `longevity_trends` · monthly biomarkers
- `exercise_balance` · cardio vs strength

**Plus Neo4j Skills for Claude Code:** 24 skills installed via `npx skills add neo4j-contrib/neo4j-skills`. Different layer: Aura Agent runs against *your data*, Skills run against *your IDE*. (More on the next slide.)

<div class="mt-3 font-mono text-xs opacity-70">
console.neo4j.io · Agents tab
</div>

</div>

<div class="col-span-3">

<img src="/images/01-aura-agent-playground-longevity-question.png" class="rounded-lg shadow-xl" />

</div>

</div>

<!--
Speaker: Two complementary things. The Aura Agent is the cloud brain over the
graph; Neo4j Skills are a developer accelerator inside your editor. Together
they cover the build-time and run-time AI surfaces.
-->

---

<div class="kicker"><div class="i-tabler-layout-dashboard inline-block align-text-bottom mr-1" /> 2 · Aura Dashboard</div>

# Whoop-style, in Console

<div class="grid grid-cols-5 gap-6 mt-2">

<div class="col-span-2 text-sm">

**5 pages, 35 panels:**

- Daily hero: Recovery % / Strain / Sleep
- Recovery deep-dive
- Strain deep-dive
- Sleep deep-dive
- 8.5-year Health Monitor

Score formulas open-sourced in `docs/SCORING.md`.

<div class="mt-3 font-mono text-xs opacity-70">
Aura Console · Tools · Dashboards
</div>

</div>

<div class="col-span-3">

<img src="/images/02-aura-dashboard-whoop-recovery.png" class="rounded-lg shadow-xl" />

</div>

</div>

<!--
Speaker: This is the Whoop UI I wanted, rebuilt on my own graph. Same scoring
logic Whoop uses. Different data ownership.
-->

---

<div class="kicker"><div class="i-tabler-api inline-block align-text-bottom mr-1" /> 3 · GraphQL Data API + GitHub Pages</div>

# Daily snapshot, automated

<div class="grid grid-cols-5 gap-6 mt-2">

<div class="col-span-2 text-sm">

**GraphQL Data API.** Three `@cypher` MERGE mutations: `ingestDay` · `ingestWorkout` · `ingestSleep`. Deployed via the v1beta5 REST endpoint.

**GitHub Actions, daily at 06:30 UTC:**

1. Auto-resume the paused instance
2. Render the Recovery snapshot
3. Commit + push to `/docs/snapshot/`
4. Pause the instance again

Total uptime per day: ~2-3 minutes.

<div class="mt-3 grid grid-cols-1 gap-1 font-mono text-xs">
<div class="flex items-center gap-1"><div class="i-tabler-cloud text-base opacity-60" /> console.neo4j.io · GraphQL Data APIs</div>
<div class="flex items-center gap-1"><div class="i-tabler-settings text-base opacity-60" /> github.com/ma3u/healthgraph-agent/actions</div>
<div class="flex items-center gap-1"><div class="i-tabler-world text-base opacity-60" /> ma3u.github.io/healthgraph-agent/snapshot/</div>
</div>

</div>

<div class="col-span-3">

<img src="/images/05-github-pages-recovery-snapshot.png" class="rounded-lg shadow-xl" />

</div>

</div>

<!--
Speaker: Critical lesson: professional-db tier does NOT auto-pause. Without
that final pause step, the instance bleeds ~$10/day. Save your credits.
-->

---

<div class="kicker"><div class="i-tabler-device-mobile inline-block align-text-bottom mr-1" /> 4 · iPhone</div>

# HealthKit sync + "Ask your graph"

<div class="img-row mt-4">

<img src="/images/06-iphone-healthkit-sync-delta-upload.jpeg" />
<img src="/images/07-iphone-dashboard-ask-your-graph.jpeg" />
<img src="/images/08-iphone-agent-answer-overlay-markdown.jpeg" />

</div>

<div class="mt-4 text-sm opacity-80 grid grid-cols-3 gap-4">

<div>
  <div class="i-tabler-cloud-data-connection text-xl mb-1 text-pink-500" />
  <strong>Sync.</strong> HealthKit → query Aura for max(Day.date) → upload only the delta.
</div>
<div>
  <div class="i-tabler-pencil text-xl mb-1 text-sky-500" />
  <strong>Ask.</strong> Four chips compute concrete ISO date ranges at tap time.
</div>
<div>
  <div class="i-tabler-bolt text-xl mb-1 text-violet-500" />
  <strong>Answer.</strong> Overlay sheet, Markdown rendering, trend arrows.
</div>

</div>

<!--
Speaker: This is where it all comes together. Real-device demo coming up next.
The answer overlay has actual numbers from my own graph, queried by the
agent's tools, about 15 seconds end-to-end.
-->

---
layout: section
---

<div class="kicker"><div class="i-tabler-player-play inline-block align-text-bottom mr-1" /> Live demo · ~5 minutes</div>

# Run it live — Xcode + iPhone 17 Pro Simulator

<div class="opacity-70 mt-1 text-sm">
HealthKit (Simulator) → Aura graph → Agent invoke → Markdown overlay. Then click straight into the live cloud:
</div>

<div class="demo-links mt-4">

<a href="https://console.neo4j.io/projects/326809f3-c351-4eb7-8770-fcf5d0b6adc1/agents" target="_blank" class="demo-link">
  <div class="i-tabler-robot text-2xl text-violet-500 shrink-0" />
  <div><div class="font-semibold">Aura Agent</div><div class="u">console.neo4j.io · agents</div></div>
</a>

<a href="https://console.neo4j.io/projects/326809f3-c351-4eb7-8770-fcf5d0b6adc1/tools/dashboards/6nK3b74oETnBKqZVcYFJ?page=5fVoFTJ0Md1BnHmN8p5X" target="_blank" class="demo-link">
  <div class="i-tabler-layout-dashboard text-2xl text-sky-500 shrink-0" />
  <div><div class="font-semibold">Aura Dashboard</div><div class="u">console.neo4j.io · Whoop view</div></div>
</a>

<a href="https://console.neo4j.io/projects/326809f3-c351-4eb7-8770-fcf5d0b6adc1/data-api" target="_blank" class="demo-link">
  <div class="i-tabler-api text-2xl text-emerald-500 shrink-0" />
  <div><div class="font-semibold">Aura GraphQL Data API</div><div class="u">console.neo4j.io · data-api</div></div>
</a>

<a href="https://github.com/ma3u/healthgraph-agent/actions/workflows/snapshot.yml" target="_blank" class="demo-link">
  <div class="i-tabler-rocket text-2xl text-amber-500 shrink-0" />
  <div><div class="font-semibold">Snapshot pipeline</div><div class="u">github.com · Actions</div></div>
</a>

<a href="https://ma3u.github.io/healthgraph-agent/snapshot/" target="_blank" class="demo-link">
  <div class="i-tabler-world text-2xl text-rose-500 shrink-0" />
  <div><div class="font-semibold">GitHub Pages snapshot</div><div class="u">ma3u.github.io · snapshot</div></div>
</a>

</div>

<div class="text-xs opacity-55 text-center mt-3">
No physical phone on stage — the iPhone 17 Pro Simulator in Xcode runs the same build. Every card above is a live link: click it during the talk.
</div>

<!--
Speaker (DEMO ~5 min):
1. Xcode is already open with the iPhone 17 Pro Simulator booted and the
   HealthGraphSync app installed. Run it.
2. Sync tab: show max(Day.date), upload the last days' delta.
3. Dashboard tab: tap "Last week summary" — answer overlay opens (~15s),
   point out RHR vs baseline, the → arrow, the bullet structure.
4. Click "Aura Agent" → Console Agents → Playground: ask the same
   question, show it's the SAME agent the app called.
5. Click "Aura Dashboard" → the Whoop-style NeoDash view.
6. Click "Aura GraphQL Data API" → the deployed Data API.
7. Click "Snapshot pipeline" → the green daily GitHub Actions run.
8. Click "GitHub Pages snapshot" → today's rendered Recovery card.

All five cards are real clickable links — no typing URLs on stage.
-->


---

<div class="kicker"><div class="i-tabler-json inline-block align-text-bottom mr-1" /> Agent as code</div>

# The agent is one JSON file

```json {2-7,10-19|all}
{
  "name": "HealthGraph Agent",
  "dbid": "7d4ba607",
  "is_private": false,
  "is_mcp_enabled": true,
  "system_prompt": "You are a longevity-focused health analytics assistant...",
  "tools": [
    {
      "type": "cypherTemplate",
      "name": "health_overview",
      "description": "Daily metrics + 30-day baseline for a date range.",
      "config": {
        "parameters": [
          { "name": "start_date", "data_type": "string", "description": "YYYY-MM-DD" },
          { "name": "end_date",   "data_type": "string", "description": "YYYY-MM-DD" }
        ],
        "template": "MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary) WHERE d.date >= date($start_date) ..."
      }
    }
  ]
}
```

<div class="mt-2 text-sm opacity-70">
<code>scripts/create_aura_agent.py</code> via Aura v2beta1 <code>/agents</code> API. Three modes: <code>status</code> · <code>--pull</code> · <code>--push</code>.
</div>

<!--
Speaker: System prompt, tools, Cypher templates — all in one checked-in JSON.
Diff in PR. Round-trip via `--pull` to capture Console edits. Push via
`--push` to deploy. Agents-as-code, finally.
-->

---

<div class="kicker"><div class="i-tabler-tools inline-block align-text-bottom mr-1" /> How this was built</div>

# Neo4j Skills for Claude Code

<div class="grid grid-cols-5 gap-6 mt-4">

<div class="col-span-2 text-sm">

Installable knowledge packages for AI coding agents — Claude Code, Cursor, Cline, Gemini CLI. One command:

```bash
npx skills add neo4j-contrib/neo4j-skills
```

**Progressive disclosure** keeps the context window lean: the agent reads a ~50-token summary, pulls the full ~2k-token protocol only when a task matches, and opens deep reference files on demand.

It **auto-picks** the skill from the task — *"optimize this Cypher"* loads `neo4j-cypher-skill`; *"build a GraphRAG pipeline"* loads `neo4j-graphrag-skill`.

</div>

<div class="col-span-3 text-sm">

<div class="font-semibold mb-3">Where the 24 installed skills carried this build:</div>

<div class="flex flex-col gap-2">
  <div class="flex items-start gap-2"><div class="i-tabler-code text-lg text-sky-500 mt-0.5 shrink-0" /><div><code>cypher</code> — the agent's 5 Cypher templates + 20 longevity queries</div></div>
  <div class="flex items-start gap-2"><div class="i-tabler-api text-lg text-emerald-500 mt-0.5 shrink-0" /><div><code>graphql</code> — the <code>@cypher</code> SDL behind the Data API</div></div>
  <div class="flex items-start gap-2"><div class="i-tabler-topology-star-3 text-lg text-violet-500 mt-0.5 shrink-0" /><div><code>modeling</code> — the Day / Workout / Sleep graph model</div></div>
  <div class="flex items-start gap-2"><div class="i-tabler-cloud text-lg text-rose-500 mt-0.5 shrink-0" /><div><code>aura-provisioning</code> — the <code>create_aura_*.py</code> scripts</div></div>
  <div class="flex items-start gap-2"><div class="i-tabler-database-search text-lg text-amber-500 mt-0.5 shrink-0" /><div><code>vector-index</code> + <code>graphrag</code> — the open similarity-search work</div></div>
  <div class="flex items-start gap-2"><div class="i-tabler-plug-connected text-lg text-cyan-500 mt-0.5 shrink-0" /><div><code>mcp</code> — the agent's MCP endpoint</div></div>
</div>

</div>

</div>

<!--
Speaker: This is the build-time half of the AI story. The Aura Agent reasons
over my data at runtime; Neo4j Skills made Claude Code fluent in Neo4j while
I was writing the Cypher templates, the GraphQL SDL, the provisioning
scripts. 24 skills, one install, zero config — the agent loads whichever one
the task needs, and unloads it after. Not Claude-Code-only: skills run in
any Agent-Skills-compatible tool — Cursor, Cline, Gemini CLI, Codex.
-->

---

<div class="kicker"><div class="i-tabler-key inline-block align-text-bottom mr-1" /> BYO Aura</div>

# Your data. Your Aura.

<div class="grid grid-cols-2 gap-12 mt-8">

<div class="flex flex-col gap-3">
  <div class="i-tabler-shield text-5xl text-emerald-500" />
  <div class="text-xl font-semibold">No shared backend.</div>
  <div class="text-sm opacity-70">Your biometrics never leave your Aura instance. Mine never touches yours.</div>
</div>

<div class="flex flex-col gap-3">
  <div class="i-tabler-bolt text-5xl text-amber-500" />
  <div class="text-xl font-semibold">~5 minutes to running.</div>
  <div class="text-sm opacity-70">Clone, fill .env, run two scripts. Working stack against your own Aura.</div>
</div>

</div>

<!--
Speaker: The trade-off: you bring credits. Which leads to the next slide.
-->

---

<div class="kicker"><div class="i-tabler-pig-money inline-block align-text-bottom mr-1" /> Don't burn your credits</div>

# Professional-db does not auto-pause

<div class="grid grid-cols-2 gap-8 mt-6">

<div>

| Tier | Auto-pause? | Burn rate |
| --- | --- | --- |
| Free | Yes (3 days idle) | $0 |
| AuraDS | Yes | varies |
| **Professional** | **No** | **~$0.30 – $0.40 /hr** |

If your workflow only resumes, your instance lives forever.

</div>

<div>

The fix. One extra step in the daily cron:

```yaml
- name: Pause Aura instance
  if: always()
  env:
    AURA_INSTANCEID: ${{ secrets.AURA_INSTANCEID }}
    AURA_CLIENT_ID:  ${{ secrets.AURA_CLIENT_ID }}
    AURA_CLIENT_SECRET: ${{ secrets.AURA_CLIENT_SECRET }}
  run: bash scripts/aura_pause.sh pause
```

Total uptime per day after: ~2-3 minutes.

</div>

</div>

---
layout: center
---

# 8.5 years, as a graph

<div class="grid grid-cols-4 gap-6 mt-1">

<div class="stat"><div class="n">10,854</div><div class="l">nodes (entities)</div></div>
<div class="stat"><div class="n">16,754</div><div class="l">relationships</div></div>
<div class="stat"><div class="n">4,061</div><div class="l">workouts</div></div>
<div class="stat"><div class="n">3,117</div><div class="l">daily records</div></div>

</div>

<div class="hg3d-stage">
  <HealthGraph3D />
</div>

<div class="flex flex-wrap justify-center gap-x-4 gap-y-1 mt-1 text-xs">
  <span><span class="dot" style="background:#ec4899" /> Person · 1</span>
  <span><span class="dot" style="background:#94a3b8" /> Device · 32</span>
  <span><span class="dot" style="background:#f59e0b" /> Workout · 4,061</span>
  <span><span class="dot" style="background:#10b981" /> Day · 3,117</span>
  <span><span class="dot" style="background:#38bdf8" /> DailySummary · 3,117</span>
  <span><span class="dot" style="background:#6366f1" /> SleepSession · 79</span>
  <span><span class="dot" style="background:#a855f7" /> Week · 447</span>
</div>

<div class="text-xs opacity-60 text-center mt-1">
7 node types · 7 relationship types · 2017-10-29 → 2026-05-15 (8.54 years) · live on a 1&nbsp;GB Aura instance
</div>

<!--
Speaker: This is the whole point — 8.5 years of Apple Health, not a flat
export but a connected graph you can rotate and walk. ~11k entities, ~17k
relationships. The agent walks these edges: Workout FOLLOWED_BY
SleepSession, Day NEXT_DAY Day. The cloud here is a representative slice;
the four numbers up top are the real totals. And it all fits on a 1 GB
Aura instance — the value is in the relationships, not the volume.
-->


---
layout: section
---

<div class="kicker">Take this back to your work</div>

# The pattern works for anything quantified

<div class="grid grid-cols-2 gap-8 mt-8 max-w-4xl mx-auto">

<div class="flex items-start gap-3">
  <div class="i-tabler-cash text-3xl text-emerald-500 mt-1 shrink-0" />
  <div>
    <div class="font-semibold">Finance</div>
    <div class="text-sm opacity-70">Transactions, entities, tax-year summaries. "Where did my money go?"</div>
  </div>
</div>

<div class="flex items-start gap-3">
  <div class="i-tabler-school text-3xl text-sky-500 mt-1 shrink-0" />
  <div>
    <div class="font-semibold">Learning</div>
    <div class="text-sm opacity-70">Flashcards, concepts, progress. "What should I review tonight?"</div>
  </div>
</div>

<div class="flex items-start gap-3">
  <div class="i-tabler-code text-3xl text-violet-500 mt-1 shrink-0" />
  <div>
    <div class="font-semibold">Productivity</div>
    <div class="text-sm opacity-70">Commits, projects, focus blocks. "Am I context-switching too much?"</div>
  </div>
</div>

<div class="flex items-start gap-3">
  <div class="i-tabler-leaf text-3xl text-amber-500 mt-1 shrink-0" />
  <div>
    <div class="font-semibold">Anything you measure</div>
    <div class="text-sm opacity-70">Model relationships, ground the LLM, kill the silo.</div>
  </div>
</div>

</div>

---

# What's still open (PRs welcome 🙏)

<div class="grid grid-cols-1 gap-4 mt-4 text-sm">

<div class="flex items-start gap-3">
  <div class="i-tabler-key text-2xl text-rose-500 mt-1 shrink-0" />
  <div>
    <div class="font-semibold">Auth0 production sign-in.</div>
    <div class="opacity-70">Apple / Google / GitHub / Microsoft → Bearer JWT to the Data API. Currently dev-mode <code>x-api-key</code>.</div>
  </div>
</div>

<div class="flex items-start gap-3">
  <div class="i-tabler-database-search text-2xl text-emerald-500 mt-1 shrink-0" />
  <div>
    <div class="font-semibold">Vector embeddings for similarity search.</div>
    <div class="opacity-70">Embed <code>DailySummary.description</code> to find "days that felt like that". Requires bringing your own LLM model (OpenAI, Vertex, etc.) — Aura's similarity-search tool takes the provider as config.</div>
  </div>
</div>

<div class="flex items-start gap-3">
  <div class="i-tabler-device-mobile-check text-2xl text-sky-500 mt-1 shrink-0" />
  <div>
    <div class="font-semibold">Background HealthKit sync.</div>
    <div class="opacity-70"><code>BGAppRefreshTask</code> + <code>HKObserverQuery</code> so the iPhone syncs without opening the app.</div>
  </div>
</div>

</div>

<div class="mt-6 font-mono opacity-70 text-xs">
github.com/ma3u/healthgraph-agent · issues #5, #7+
</div>

---
layout: center
---

# Try it

<div class="font-mono text-2xl mt-4 mb-6">
github.com/ma3u/healthgraph-agent
</div>

```bash
git clone https://github.com/ma3u/healthgraph-agent
cd healthgraph-agent
cp .env.example .env          # add your Aura API credentials
pip install -r requirements.txt

python scripts/create_aura_data_api.py   # GraphQL Data API
python scripts/create_aura_agent.py      # Aura Agent
bash scripts/build_ios.sh                # iPhone app
```

<div class="mt-6 opacity-70 text-sm">
Live daily snapshot: <code>ma3u.github.io/healthgraph-agent/snapshot/</code>
</div>

---
layout: center
class: text-center
---

# Thanks 🙏

<div class="text-xl opacity-70 mt-2">
  Questions?
</div>

<div class="flex items-center justify-center gap-10 mt-10">

<img src="/linkedin-photo.png" class="w-32 h-32 rounded-full shadow-lg" />

<div class="text-left flex flex-col gap-2">
  <div class="text-lg font-semibold">Matthias Buchhorn-Roth</div>
  <div class="flex items-center gap-2 text-sm opacity-75">
    <div class="i-tabler-link text-lg opacity-70" />
    <span class="font-mono">linkedin.com/in/mbuchhorn</span>
  </div>
  <div class="flex items-center gap-2 text-sm opacity-75">
    <div class="i-tabler-code text-lg opacity-70" />
    <span class="font-mono">github.com/ma3u</span>
  </div>
  <div class="flex items-center gap-2 text-sm opacity-75">
    <div class="i-tabler-folder text-lg opacity-70" />
    <span class="font-mono">github.com/ma3u/healthgraph-agent</span>
  </div>
</div>

<div class="flex flex-col items-center gap-2">
  <div class="bg-white p-3 rounded-xl shadow-lg">
    <img src="/linkedin-qr.png" class="w-40 h-40" />
  </div>
  <div class="text-xs font-semibold opacity-70">Connect on LinkedIn</div>
</div>

</div>
