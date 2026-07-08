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

<div class="text-base mt-1 opacity-80">I want to see the effect of <strong>everything I do</strong> on my health and performance:</div>

<div class="grid grid-cols-12 gap-4 mt-5 items-center">

<div class="col-span-7 grid grid-cols-2 gap-2.5">
  <div class="factor"><div class="i-tabler-barbell text-2xl text-amber-500 shrink-0" /><div><div class="t">Training</div><div class="s">Apple Watch · eGym · Beat81</div></div></div>
  <div class="factor"><div class="i-tabler-zzz text-2xl text-indigo-500 shrink-0" /><div><div class="t">Sleep</div><div class="s">Apple Health</div></div></div>
  <div class="factor"><div class="i-tabler-salad text-2xl text-emerald-500 shrink-0" /><div><div class="t">Nutrition</div><div class="s">Cronometer</div></div></div>
  <div class="factor"><div class="i-tabler-pill text-2xl text-pink-500 shrink-0" /><div><div class="t">Supplements</div><div class="s">Cronometer</div></div></div>
  <div class="factor"><div class="i-tabler-plane text-2xl text-sky-500 shrink-0" /><div><div class="t">Travelling</div><div class="s">Calendar</div></div></div>
  <div class="factor"><div class="i-tabler-virus text-2xl text-rose-500 shrink-0" /><div><div class="t">Sickness</div><div class="s">ePA · doctor letters</div></div></div>
</div>

<div class="col-span-1 text-center">
  <div class="text-3xl opacity-40">→</div>
  <div class="text-xs opacity-50 mt-1">effect?</div>
</div>

<div class="col-span-4">
  <div class="outcome">
    <div class="i-tabler-heartbeat text-4xl text-rose-500" />
    <div class="font-semibold text-base mt-1">Health &amp; performance</div>
    <div class="font-mono text-xs opacity-60 mt-1">Recovery · HRV · RHR · VO₂max</div>
    <div class="text-xs opacity-70 mt-2">Which lever moved which number?</div>
  </div>
</div>

</div>

<div class="grid grid-cols-3 gap-4 mt-6 text-xs opacity-80">
  <div class="flex items-start gap-2"><div class="i-tabler-database text-lg text-rose-500 shrink-0" /><div>Every factor logs into a <strong>different silo</strong> — none talk to each other.</div></div>
  <div class="flex items-start gap-2"><div class="i-tabler-topology-star-3 text-lg text-emerald-500 shrink-0" /><div>Effects <strong>chain across days</strong> — workout → sleep → HRV. Tables hide the chain.</div></div>
  <div class="flex items-start gap-2"><div class="i-tabler-brain text-lg text-violet-500 shrink-0" /><div>An <strong>LLM alone</strong> can't see any of it — "How am I doing?" = horoscope.</div></div>
</div>

<v-click>

<div class="mt-5 text-base flex items-center gap-3">
  <div class="i-tabler-rocket text-xl text-amber-500" />
  You're a developer. One graph joins every factor on the same timeline — and the data stays yours.
</div>

</v-click>

<!--
Speaker: This is the real question behind the project: I train, I sleep, I
eat, I take supplements, I travel, I get sick — six kinds of events, each
logged in a different app, and I want to know what each one does to my
recovery, HRV, resting heart rate, VO2max. Three reasons I can't answer it
today: the silos don't talk, the effects chain across days so tables hide
them, and an LLM without the data just guesses. One graph on one timeline
is the developer-shaped fix.
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

# Build your daily dashboard with a GitHub Action

<div class="grid grid-cols-5 gap-8 mt-2 items-center">

<div class="col-span-3 text-sm">

One workflow, every morning at 06:30 UTC:

<div class="grid grid-cols-1 gap-2 mt-4">
  <div class="flex items-center gap-3"><span class="step-no">1</span><div><strong>Wake Aura</strong> — <code>aura_lifecycle.py wake</code> resumes the paused instance via the REST API.</div></div>
  <div class="flex items-center gap-3"><span class="step-no">2</span><div><strong>Query the graph</strong> — the GraphQL Data API returns the last 7 days + 30-day baselines.</div></div>
  <div class="flex items-center gap-3"><span class="step-no">3</span><div><strong>Render static HTML</strong> — <code>render_snapshot.py</code> turns it into one Recovery card. No JS, no server.</div></div>
  <div class="flex items-center gap-3"><span class="step-no">4</span><div><strong>Commit to <code>/docs/snapshot/</code></strong> — GitHub Pages redeploys the page for free.</div></div>
  <div class="flex items-center gap-3"><span class="step-no">5</span><div><strong>Pause Aura</strong> — <code>if: always()</code>. Total uptime: ~2-3 minutes a day.</div></div>
</div>

<div class="mt-5 font-medium">The dashboard is always on — the database almost never is.</div>

<div class="mt-2 font-mono text-xs opacity-70">
ma3u.github.io/healthgraph-agent/snapshot/ · .github/workflows/snapshot.yml
</div>

</div>

<div class="col-span-2 flex justify-center">

<img src="/images/05-github-pages-recovery-snapshot.png" class="rounded-lg shadow-xl" style="max-height: 400px; width: auto;" />

</div>

</div>

<!--
Speaker: This is the recipe for a free, zero-hosting daily dashboard. A
scheduled GitHub Action wakes the database, pulls the numbers through the
GraphQL Data API, renders one static HTML card, commits it, and GitHub
Pages serves it. Then it pauses the database again — the dashboard is
always available, the database ran three minutes. Same Data API also has
the ingest mutations the iPhone app writes through.
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
Speaker: This is where it all comes together. Sync pulls only the delta
since Aura's latest day, the chips build concrete date ranges, and the
answer overlay shows the agent's grounded reply — about 15 seconds
end-to-end. These are real screenshots from the running app.
-->

---

<div class="kicker"><div class="i-tabler-json inline-block align-text-bottom mr-1" /> Agent as code</div>

# The agent is one JSON file — no click-ops

```json {2-6,9-18|all}
{
  "name": "HealthGraph Agent",
  "dbid": "7d4ba607",
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

<div class="grid grid-cols-3 gap-4 mt-4 text-sm">
  <div class="flex items-start gap-2"><div class="i-tabler-git-pull-request text-xl text-violet-500 mt-0.5 shrink-0" /><div><strong>Review it like code.</strong> <span class="opacity-70">System prompt + Cypher tools live in git — every change is a diff in a PR.</span></div></div>
  <div class="flex items-start gap-2"><div class="i-tabler-rocket text-xl text-emerald-500 mt-0.5 shrink-0" /><div><strong>Reproducible.</strong> <span class="opacity-70"><code>--push</code> deploys the same coach to <em>your</em> Aura — that's what makes BYO work.</span></div></div>
  <div class="flex items-start gap-2"><div class="i-tabler-refresh text-xl text-sky-500 mt-0.5 shrink-0" /><div><strong>Round-trip.</strong> <span class="opacity-70"><code>--pull</code> captures Console edits back into git. Nothing is lost in the UI.</span></div></div>
</div>

<!--
Speaker: Why this slide matters: the whole reasoning layer — system prompt,
tools, Cypher templates — is one checked-in JSON, driven through the Aura
v2beta1 /agents API by create_aura_agent.py. Three benefits: you review
agent changes like code in a PR; anyone can --push the identical coach to
their own Aura, which is what makes bring-your-own-instance real; and
--pull round-trips Console experiments back into git, so no click-ops
drift. Agents-as-code, finally.
-->

---

<div class="kicker"><div class="i-tabler-pig-money inline-block align-text-bottom mr-1" /> BYO Aura · don't burn your credits</div>

# Your data. Your Aura. Your bill.

<div class="mt-6 text-base">
This whole demo runs on the <strong>smallest AuraDB Professional: 1&nbsp;GB ≈ $65/mo</strong> always-on — and Professional <strong>never auto-pauses</strong>. So a pipeline pauses it for you:
</div>

<div class="flow-row mt-8">
  <div class="flow-step"><div class="i-tabler-brand-github text-3xl text-gray-600" /><div class="t">GitHub Actions</div><div class="s">cron 06:30 UTC</div></div>
  <div class="flow-arrow">→</div>
  <div class="flow-step"><div class="i-tabler-player-play text-3xl text-emerald-500" /><div class="t">Resume</div><div class="s">Aura REST API</div></div>
  <div class="flow-arrow">→</div>
  <div class="flow-step"><div class="i-tabler-refresh text-3xl text-sky-500" /><div class="t">Sync + snapshot</div><div class="s">~2-3 min of uptime</div></div>
  <div class="flow-arrow">→</div>
  <div class="flow-step"><div class="i-tabler-player-pause text-3xl text-rose-500" /><div class="t">Pause</div><div class="s">if:&nbsp;always()</div></div>
</div>

<div class="mt-8 grid grid-cols-2 gap-8 text-sm opacity-80">
<div>
Paused bills ~20% of running. The iPhone app <strong>wakes it on demand</strong>; a second workflow pauses it again after 30 idle minutes.
</div>
<div>
Result: <strong>~$65 → ~$15/mo (−77%)</strong>.<br/>
<span class="font-mono text-xs opacity-70">aura_lifecycle.py wake · aura_pause.sh pause</span>
</div>
</div>

<!--
Speaker: Bring-your-own-Aura is the privacy posture AND the cost story.
The smallest Professional instance — 1 GB, about $65 a month always-on —
holds all 8.5 years. It never auto-pauses, so a GitHub Actions cron drives
the Aura REST API: resume, do the day's sync and snapshot, pause again —
if: always(), so a failed render still pauses. The app wakes it on demand
and an idle watchdog pauses it after 30 minutes. Net: about 77% cheaper.
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

# How the Aura features add up to a private EHR

<div class="grid grid-cols-1 gap-4 mt-6 text-sm max-w-4xl">

<div class="flex items-start gap-4">
  <div class="i-tabler-robot text-3xl text-violet-500 mt-0.5 shrink-0" />
  <div>
    <div><span class="font-semibold text-violet-500">Aura Agent</span> <span class="font-semibold">→ a coach that knows my record.</span> <span class="opacity-70">Cypher templates ground the LLM in my graph — no horoscope answers.</span></div>
    <div class="opacity-60 text-xs mt-0.5">Lesson: gate AI-written code — pre-commit (gitleaks) caught a PR that logged the DB password.</div>
  </div>
</div>

<div class="flex items-start gap-4">
  <div class="i-tabler-api text-3xl text-emerald-500 mt-0.5 shrink-0" />
  <div>
    <div><span class="font-semibold text-emerald-500">GraphQL Data API</span> <span class="font-semibold">→ the phone writes straight into the record.</span> <span class="opacity-70">Three typed mutations, zero backend to host.</span></div>
    <div class="opacity-60 text-xs mt-0.5">Lesson: decouple the view — a static snapshot renders while Aura sleeps, so pausing costs nothing.</div>
  </div>
</div>

<div class="flex items-start gap-4">
  <div class="i-tabler-layout-dashboard text-3xl text-sky-500 mt-0.5 shrink-0" />
  <div>
    <div><span class="font-semibold text-sky-500">Aura Dashboards</span> <span class="font-semibold">→ the Whoop view of the record, no subscription.</span> <span class="opacity-70">35 panels straight on the graph.</span></div>
    <div class="opacity-60 text-xs mt-0.5">Lesson: borrow the published science (Tanaka, TRIMP) — the graph + agent is the moat.</div>
  </div>
</div>

<div class="flex items-start gap-4">
  <div class="i-tabler-file-text text-3xl text-amber-500 mt-0.5 shrink-0" />
  <div>
    <div><span class="font-semibold text-amber-500">Document Intelligence</span> <span class="font-semibold">→ clinical documents join the record.</span> <span class="opacity-70">Lab panels and doctor letters become graph entities on the same timeline — no extraction code.</span></div>
    <div class="opacity-60 text-xs mt-0.5">Lesson: a graph only knows what you logged — sleep existed on 78 of 3,117 days. Instrument collection first.</div>
  </div>
</div>

</div>

<!--
Speaker: The takeaway in one slide. Each Aura feature covers one layer of a
private electronic health record: the Agent answers from it, the Data API
feeds it, Dashboards show it, Document Intelligence extends it to clinical
documents. Under each: the hard-won lesson from that layer — the leaked
password, the pause economics, the borrowed science, and the humbling one:
the graph only reasons over what your devices actually recorded.
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
