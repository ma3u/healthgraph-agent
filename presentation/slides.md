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
Speaker: Hi everyone. I'm an Apple Watch user. Apple shows me charts; it
doesn't coach me. Whoop has the coach, but their hardware, their
subscription, their silo. I built the coach on my own data over the
hackathon window. In 15 minutes you'll see a pattern you can apply to any
quantified-self domain.
-->

---

# The problem you also have

<div class="grid grid-cols-1 gap-3 mt-4">

<div class="flex items-start gap-4">
  <div class="i-tabler-database text-3xl text-rose-500 mt-1 shrink-0" />
  <div>
    <div class="font-semibold">Your health data lives in a dozen silos.</div>
    <div class="opacity-70 text-sm">None of them talk to each other:</div>
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
    <div class="opacity-70 text-sm">Workout → sleep → morning HRV → recovery. Tables hide the chain.</div>
  </div>
</div>

<div class="flex items-start gap-4">
  <div class="i-tabler-brain text-3xl text-violet-500 mt-1 shrink-0" />
  <div>
    <div class="font-semibold">An LLM alone won't help.</div>
    <div class="opacity-70 text-sm">"How am I doing?" without grounded data = horoscope.</div>
  </div>
</div>

</div>

<v-click>

<div class="mt-6 text-lg flex items-center gap-3">
  <div class="i-tabler-rocket text-2xl text-amber-500" />
  You're a developer. One graph unifies every silo — and the data stays yours.
</div>

</v-click>

<!--
Speaker: 8.5 years of biometrics, rented back to me by every vendor. And
Apple Health is just one silo — blood panels, the German ePA, eGym, Beat81.
A graph is the one model where all of them share the same :Day and the same
:Person instead of seven disconnected exports.
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
Everything runs on your own Aura instance.
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
Four pillars. Each a Neo4j Aura primitive.
</div>

---

<div class="kicker"><div class="i-tabler-robot inline-block align-text-bottom mr-1" /> 1 · Aura Agent</div>

# HealthGraph Agent

<div class="grid grid-cols-5 gap-6 mt-4">

<div class="col-span-2 text-sm">

A cloud-hosted reasoning layer on top of your Aura graph: pick a tool, run Cypher, answer grounded.

**Tools (6):** Text2Cypher + 5 templates:

- `health_overview` · daily + 30-day baseline
- `workout_recovery` · workout → next-day HRV
- `overtraining_check` · weekly CAUTION flags
- `longevity_trends` · monthly biomarkers
- `exercise_balance` · cardio vs strength

Defined **as code**, MCP enabled, REST-invokable.

<div class="mt-3 font-mono text-xs opacity-70">
console.neo4j.io · Agents tab
</div>

</div>

<div class="col-span-3">

<img src="/images/01-aura-agent-playground-longevity-question.png" class="rounded-lg shadow-xl" />

</div>

</div>

<!--
Speaker: The cloud brain over the graph. Six tools; the five templates are
parameterized Cypher I wrote, Text2Cypher covers the rest.
-->

---

<div class="kicker"><div class="i-tabler-layout-dashboard inline-block align-text-bottom mr-1" /> 2 · Aura Dashboard</div>

# Whoop-style, in Console

<div class="grid grid-cols-5 gap-6 mt-2">

<div class="col-span-2 text-sm">

**5 pages, 35 panels:**

- Daily hero: Recovery % / Strain / Sleep
- Recovery · Strain · Sleep deep-dives
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
Speaker: The Whoop UI I wanted, rebuilt on my own graph. Same scoring
logic Whoop uses. Different data ownership.
-->

---

<div class="kicker"><div class="i-tabler-api inline-block align-text-bottom mr-1" /> 3 · GraphQL Data API + GitHub Pages</div>

# Daily snapshot, automated

<div class="grid grid-cols-5 gap-6 mt-2">

<div class="col-span-2 text-sm">

**GraphQL Data API.** Three `@cypher` MERGE mutations: `ingestDay` · `ingestWorkout` · `ingestSleep`.

**GitHub Actions, daily at 06:30 UTC:**

1. Auto-resume the paused instance
2. Render the Recovery snapshot
3. Commit + push to `/docs/snapshot/`
4. Pause the instance again

Total uptime per day: ~2-3 minutes.

<div class="mt-3 font-mono text-xs opacity-70">
ma3u.github.io/healthgraph-agent/snapshot/
</div>

</div>

<div class="col-span-3">

<img src="/images/05-github-pages-recovery-snapshot.png" class="rounded-lg shadow-xl" />

</div>

</div>

<!--
Speaker: The dashboard you can look at while the database sleeps. And the
pause step at the end is what keeps the credits alive — more on that soon.
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
  <strong>Sync.</strong> HealthKit → upload only the delta.
</div>
<div>
  <div class="i-tabler-pencil text-xl mb-1 text-sky-500" />
  <strong>Ask.</strong> Chips compute ISO date ranges at tap time.
</div>
<div>
  <div class="i-tabler-bolt text-xl mb-1 text-violet-500" />
  <strong>Answer.</strong> Markdown overlay, ~15 s end-to-end.
</div>

</div>

<!--
Speaker: This is where it all comes together — and it's the live demo, now.
-->

---
layout: section
---

<div class="kicker"><div class="i-tabler-player-play inline-block align-text-bottom mr-1" /> Live demo · ~4 minutes</div>

# Simulator → Aura → GitHub

<div class="demo-links mt-6">

<div class="demo-link">
  <div class="i-tabler-brand-apple text-2xl text-gray-700 shrink-0" />
  <div><div class="font-semibold">iPhone Simulator: sync + ask</div><div class="u">HealthGraphSync · runs the same build</div></div>
</div>

<a href="https://console.neo4j.io/projects/326809f3-c351-4eb7-8770-fcf5d0b6adc1/agents" target="_blank" class="demo-link">
  <div class="i-tabler-robot text-2xl text-violet-500 shrink-0" />
  <div><div class="font-semibold">Aura Agent</div><div class="u">console.neo4j.io · agents</div></div>
</a>

<a href="https://console.neo4j.io/projects/326809f3-c351-4eb7-8770-fcf5d0b6adc1/tools/dashboards/6nK3b74oETnBKqZVcYFJ?page=5fVoFTJ0Md1BnHmN8p5X" target="_blank" class="demo-link">
  <div class="i-tabler-layout-dashboard text-2xl text-sky-500 shrink-0" />
  <div><div class="font-semibold">Aura Dashboard</div><div class="u">console.neo4j.io · Whoop view</div></div>
</a>

<a href="https://ma3u.github.io/healthgraph-agent/snapshot/" target="_blank" class="demo-link">
  <div class="i-tabler-world text-2xl text-rose-500 shrink-0" />
  <div><div class="font-semibold">GitHub Pages snapshot</div><div class="u">ma3u.github.io · snapshot</div></div>
</a>

</div>

<!--
Speaker (DEMO ~4 min, 4 stops):
1. Xcode is already open with the iPhone 17 Pro Simulator booted and the
   HealthGraphSync app installed. Sync tab: show max(Day.date), upload the
   last days' delta.
2. Dashboard tab: tap "Last week summary" — answer overlay opens (~15s),
   point out RHR vs baseline, the → arrow, the bullet structure.
3. Click "Aura Agent" → Console Playground: it's the SAME agent the app
   called. Click "Aura Dashboard" → the Whoop-style view.
4. Click "GitHub Pages snapshot" → today's rendered Recovery card from the
   06:30 GitHub Actions run.

All cards are real clickable links — no typing URLs on stage.
Backup if the demo dies: docs/images/hackathon/08-iphone-agent-answer-
overlay-markdown.jpeg.
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
<code>scripts/create_aura_agent.py</code> via Aura v2beta1 <code>/agents</code> API: <code>status</code> · <code>--pull</code> · <code>--push</code>.
</div>

<!--
Speaker: System prompt, tools, Cypher templates — one checked-in JSON.
Diff in PR, round-trip Console edits with --pull, deploy with --push.
Agents-as-code, finally.
-->

---

<div class="kicker"><div class="i-tabler-pig-money inline-block align-text-bottom mr-1" /> BYO Aura · don't burn your credits</div>

# Your data. Your Aura. Your bill.

<div class="grid grid-cols-2 gap-8 mt-6">

<div>

**No shared backend.** Your biometrics never leave your Aura instance. Clone, fill `.env`, two scripts — ~5 minutes to running.

**The catch:** Professional-db never auto-pauses at ~$0.30–0.40/hr. If your workflow only resumes, your instance lives forever.

</div>

<div>

The fix — one extra step in the daily cron:

```yaml
- name: Pause Aura instance
  if: always()
  run: bash scripts/aura_pause.sh pause
```

Plus a 30-min idle watchdog + app-triggered wake:<br/>
**~$520 → ~$120/mo (−77%).**

</div>

</div>

<!--
Speaker: Bring-your-own-Aura is the privacy posture AND the cost story.
The hard lesson: Professional tier does not auto-pause. On-demand resume,
an idle watchdog, and the pause step in the cron cut my bill by ~77%.
-->

---
layout: center
---

<HealthGraph3D class="hg3d-fill" />

<div class="hg-top">
  <div class="kicker">8.5 years, as a graph</div>
  <div class="hg-stats">
    <span><b>10,854</b> nodes</span>
    <span><b>16,754</b> relationships</span>
    <span><b>4,061</b> workouts</span>
    <span><b>3,117</b> daily records</span>
  </div>
</div>

<div class="hg-bottom">
  <div class="flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs">
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
</div>

<!--
Speaker: The whole point in one picture — 8.5 years of Apple Health as a
connected graph. The agent walks these edges: Workout FOLLOWED_BY
SleepSession, Day NEXT_DAY Day. ~11k nodes, ~17k relationships, on a
1 GB Aura instance.
-->


---

<div class="kicker"><div class="i-tabler-file-text inline-block align-text-bottom mr-1" /> Document Intelligence · the next silo</div>

# Clinical docs → graph → a private EHR

<div class="grid grid-cols-5 gap-6 mt-2">

<div class="col-span-2 text-sm">

**Aura Document Intelligence** turns the clinical docs the export already bundles — lab panels, ECG reports, physician letters — into graph entities, **no extraction code**.

From 4 docs: **Biomarker · LabResult · Medication · Condition · Provider · ClinicalEvent**, each with source-chunk provenance, dated entities on the same `(:Day)` timeline.

<div class="mt-3 opacity-90 font-semibold">One graph, every silo → my own private electronic health record.</div>

</div>

<div class="col-span-3">

<img src="/images/11-document-intelligence-clinical-model.png" class="rounded-lg shadow-xl" />

</div>

</div>

<!--
Speaker: This is where the "dozen silos" slide pays off. DI reads the
clinical PDFs the ETL ignored and wires them onto the same daily timeline.
That's the path from a Whoop clone to a private EHR. Model generated from
four documents in about a minute.
-->

---

<div class="kicker"><div class="i-tabler-bulb inline-block align-text-bottom mr-1" /> What I've learned (so far)</div>

# Four lessons from the build

<div class="grid grid-cols-2 gap-x-8 gap-y-4 mt-4 text-sm">

<div class="flex items-start gap-3">
  <div class="i-tabler-cloud-off text-2xl text-sky-500 mt-0.5 shrink-0" />
  <div>
    <div class="font-semibold">Decouple the view from the DB.</div>
    <div class="opacity-70">A static daily snapshot renders while Aura sleeps. Offline-first makes aggressive pausing usable.</div>
  </div>
</div>

<div class="flex items-start gap-3">
  <div class="i-tabler-shield-lock text-2xl text-rose-500 mt-0.5 shrink-0" />
  <div>
    <div class="font-semibold">Gate the AI.</div>
    <div class="opacity-70">An AI "shortcut" PR logged the DB password in plaintext. Pre-commit (gitleaks) + isolated-DB E2E tests now catch it before merge.</div>
  </div>
</div>

<div class="flex items-start gap-3">
  <div class="i-tabler-license text-2xl text-emerald-500 mt-0.5 shrink-0" />
  <div>
    <div class="font-semibold">Borrow the science, keep the graph.</div>
    <div class="opacity-70">Re-implement the cited scoring (Tanaka, Banister TRIMP); the graph + agent is the moat.</div>
  </div>
</div>

<div class="flex items-start gap-3">
  <div class="i-tabler-chart-dots text-2xl text-cyan-500 mt-0.5 shrink-0" />
  <div>
    <div class="font-semibold">A graph is only as good as what you logged.</div>
    <div class="opacity-70">Sleep existed on ~78 of 3,117 days. Instrument collection first.</div>
  </div>
</div>

</div>

<!--
Speaker: Four things I'd tell myself at the start. Security bit scariest —
an AI-generated PR leaked the DB password; pre-commit plus isolated-DB
tests now gate every change. And the data lesson is humbling: the graph
only reasons over what your devices actually recorded.
-->

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
The pattern works for anything quantified — finance, learning, productivity.<br/>
PRs welcome: Auth0 sign-in · vector similarity · sleep stages · DI on the real export (issues #5, #10).
</div>

<!--
Speaker: Same pattern for any personal data domain: own the export, model
the relationships, type the API, ground the agent. Clone it, bring your own
Aura, and if you want to hack on it — the open issues are right there.
-->

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
