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
  <div class="i-mdi-heart-pulse text-6xl text-pink-500" />
  <div class="text-2xl font-semibold">A Whoop dashboard.</div>
  <div class="text-base opacity-70">For my Apple Watch data. Apple has the watch. Whoop has the coach. The data is mine.</div>
</div>

<div class="flex flex-col gap-4">
  <div class="i-mdi-lock-open-outline text-6xl text-indigo-500" />
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
  <div class="i-mdi-database-outline text-3xl text-rose-500 mt-1 shrink-0" />
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
  <div class="i-mdi-graph-outline text-3xl text-emerald-500 mt-1 shrink-0" />
  <div>
    <div class="font-semibold">Your data is relational.</div>
    <div class="opacity-70 text-sm">Workout, next night's sleep, morning HRV, recovery. Tables hide the chain.</div>
  </div>
</div>

<div class="flex items-start gap-4">
  <div class="i-mdi-brain text-3xl text-violet-500 mt-1 shrink-0" />
  <div>
    <div class="font-semibold">An LLM alone won't help.</div>
    <div class="opacity-70 text-sm">"How am I doing?" without grounded data = horoscope. The agent needs your graph.</div>
  </div>
</div>

</div>

<v-click>

<div class="mt-6 text-lg flex items-center gap-3">
  <div class="i-mdi-rocket-launch-outline text-2xl text-amber-500" />
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
  <div class="i-mdi-folder-open-outline text-5xl text-rose-500" />
  <div class="font-semibold">Own</div>
  <div class="text-xs opacity-70 text-center">Pull your data out (Apple Health export.xml).</div>
</div>

<div class="flex flex-col items-center gap-3">
  <div class="i-mdi-graph-outline text-5xl text-emerald-500" />
  <div class="font-semibold">Graph</div>
  <div class="text-xs opacity-70 text-center">Model relationships, not rows (Neo4j Aura).</div>
</div>

<div class="flex flex-col items-center gap-3">
  <div class="i-mdi-api text-5xl text-sky-500" />
  <div class="font-semibold">API</div>
  <div class="text-xs opacity-70 text-center">Typed mutations + queries (Aura GraphQL Data API).</div>
</div>

<div class="flex flex-col items-center gap-3">
  <div class="i-mdi-robot-outline text-5xl text-violet-500" />
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
  <div class="i-mdi-table text-3xl text-gray-500 mb-2" />
  <div class="text-sm opacity-70 mb-2">A flat table can tell you:</div>
  <blockquote class="text-base font-medium border-l-4 border-gray-400 pl-3">
    Your HRV was 31 ms on May 12.
  </blockquote>
</div>

<div>
  <div class="i-mdi-graph-outline text-3xl text-emerald-500 mb-2" />
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
  <div class="i-mdi-robot-outline text-5xl text-violet-500" />
  <div class="font-semibold text-sm">Aura Agent</div>
</div>

<div class="flex flex-col items-center gap-2">
  <div class="i-mdi-view-dashboard-outline text-5xl text-sky-500" />
  <div class="font-semibold text-sm">Aura Dashboard</div>
</div>

<div class="flex flex-col items-center gap-2">
  <div class="i-mdi-api text-5xl text-emerald-500" />
  <div class="font-semibold text-sm">GraphQL API + Pages</div>
</div>

<div class="flex flex-col items-center gap-2">
  <div class="i-mdi-cellphone text-5xl text-pink-500" />
  <div class="font-semibold text-sm">iPhone Sync</div>
</div>

</div>

<div class="opacity-70 mt-10 text-base text-center">
Four pillars. Each a Neo4j Aura primitive. Each solving a piece of the pattern.
</div>

---

<div class="kicker"><div class="i-mdi-robot-outline inline-block align-text-bottom mr-1" /> 1 · Aura Agent</div>

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

**Plus Neo4j Skills for Claude Code:** 21 skills installed via `npx skills add neo4j-contrib/neo4j-skills`. Different layer: Aura Agent runs against *your data*, Skills run against *your IDE*.

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

<div class="kicker"><div class="i-mdi-view-dashboard-outline inline-block align-text-bottom mr-1" /> 2 · Aura Dashboard</div>

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

<div class="kicker"><div class="i-mdi-api inline-block align-text-bottom mr-1" /> 3 · GraphQL Data API + GitHub Pages</div>

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
<div class="flex items-center gap-1"><div class="i-mdi-cloud-outline text-base opacity-60" /> console.neo4j.io · GraphQL Data APIs</div>
<div class="flex items-center gap-1"><div class="i-mdi-cog-outline text-base opacity-60" /> github.com/ma3u/healthgraph-agent/actions</div>
<div class="flex items-center gap-1"><div class="i-mdi-web text-base opacity-60" /> ma3u.github.io/healthgraph-agent/snapshot/</div>
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

<div class="kicker"><div class="i-mdi-cellphone inline-block align-text-bottom mr-1" /> 4 · iPhone</div>

# HealthKit sync + "Ask your graph"

<div class="img-row mt-4">

<img src="/images/06-iphone-healthkit-sync-delta-upload.jpeg" />
<img src="/images/07-iphone-dashboard-ask-your-graph.jpeg" />
<img src="/images/08-iphone-agent-answer-overlay-markdown.jpeg" />

</div>

<div class="mt-4 text-sm opacity-80 grid grid-cols-3 gap-4">

<div>
  <div class="i-mdi-cloud-sync-outline text-xl mb-1 text-pink-500" />
  <strong>Sync.</strong> HealthKit → query Aura for max(Day.date) → upload only the delta.
</div>
<div>
  <div class="i-mdi-pencil-outline text-xl mb-1 text-sky-500" />
  <strong>Ask.</strong> Four chips compute concrete ISO date ranges at tap time.
</div>
<div>
  <div class="i-mdi-lightning-bolt-outline text-xl mb-1 text-violet-500" />
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

<div class="kicker"><div class="i-mdi-play-circle-outline inline-block align-text-bottom mr-1" /> Live demo · ~3 minutes</div>

# Open the phone. Tap "Last week summary".

<div class="opacity-70 mt-4 text-base">
HealthKit → Aura graph → Agent invoke → Markdown overlay
</div>

<div class="mt-10 grid grid-cols-2 gap-4 max-w-2xl mx-auto text-sm">

<div class="border border-gray-300 dark:border-gray-700 rounded-lg p-3">
<div class="flex items-center gap-2 font-semibold">
  <div class="i-mdi-cloud-outline" /> Aura Console fallback
</div>
<div class="font-mono text-xs mt-1 opacity-70">console.neo4j.io</div>
</div>

<div class="border border-gray-300 dark:border-gray-700 rounded-lg p-3">
<div class="flex items-center gap-2 font-semibold">
  <div class="i-mdi-web" /> Pages snapshot fallback
</div>
<div class="font-mono text-xs mt-1 opacity-70">ma3u.github.io/healthgraph-agent/snapshot/</div>
</div>

</div>

<!--
Speaker (DEMO):
1. Open HealthGraph Sync on the iPhone.
2. Sync tab: show max(Day.date), then upload last 7 days delta.
3. Dashboard tab: tap "Last week summary" chip.
4. Show loading state (~15s).
5. Answer overlay opens: point out the numbers (RHR vs baseline,
   the → stable arrow, the bullet structure).
6. Drag sheet down to .medium detent, then up to .large. Done.

If anything fails: switch to Aura Console -> Agents -> Playground
and ask the same question there, or open the Pages snapshot in
the browser.
-->

---

<div class="kicker"><div class="i-mdi-code-json inline-block align-text-bottom mr-1" /> Agent as code</div>

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

<div class="kicker"><div class="i-mdi-key-outline inline-block align-text-bottom mr-1" /> BYO Aura</div>

# Your data. Your Aura.

<div class="grid grid-cols-2 gap-12 mt-8">

<div class="flex flex-col gap-3">
  <div class="i-mdi-shield-outline text-5xl text-emerald-500" />
  <div class="text-xl font-semibold">No shared backend.</div>
  <div class="text-sm opacity-70">Your biometrics never leave your Aura instance. Mine never touches yours.</div>
</div>

<div class="flex flex-col gap-3">
  <div class="i-mdi-lightning-bolt-outline text-5xl text-amber-500" />
  <div class="text-xl font-semibold">~5 minutes to running.</div>
  <div class="text-sm opacity-70">Clone, fill .env, run two scripts. Working stack against your own Aura.</div>
</div>

</div>

<!--
Speaker: The trade-off: you bring credits. Which leads to the next slide.
-->

---

<div class="kicker"><div class="i-mdi-piggy-bank-outline inline-block align-text-bottom mr-1" /> Don't burn your credits</div>

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

# Stats

<div class="grid grid-cols-3 gap-12 mt-6">

<div class="stat"><div class="n">3,117</div><div class="l">Day nodes in Aura</div></div>
<div class="stat"><div class="n">3,180</div><div class="l">workouts modeled</div></div>
<div class="stat"><div class="n">8.5 yr</div><div class="l">of biometrics</div></div>

<div class="stat"><div class="n">6</div><div class="l">agent tools</div></div>
<div class="stat"><div class="n">21</div><div class="l">Neo4j Skills for Claude</div></div>
<div class="stat"><div class="n">&lt; 5 min</div><div class="l">provisioning, from clone</div></div>

</div>

<div class="mt-10 max-w-4xl mx-auto">

| Instance size | Fits this graph? | Cost ≈ (paused / running) |
| --- | --- | --- |
| **Free 1 GB** | Yes (recommended for personal use) | $0 / $0 |
| Professional 2 GB | Yes, comfortable | ~$1 / $95 per month |
| Professional 4 GB | Plenty of headroom | ~$2 / $145 per month |
| Professional 8 GB (dev) | Overkill for one person | ~$3 / $220 per month |

</div>

<div class="mt-4 text-xs opacity-60 text-center">
Running cost is 24/7. Paused tier is ~20 % of running and what daily-cron + scripts/aura_pause.sh gets you.
</div>

<!--
Speaker: Numbers to anchor. For your own use: Free 1GB is enough. Pro 8GB
is for a multi-user / multi-year-of-headroom setup. Don't over-provision.
-->

---
layout: section
---

<div class="kicker">Take this back to your work</div>

# The pattern works for anything quantified

<div class="grid grid-cols-2 gap-8 mt-8 max-w-4xl mx-auto">

<div class="flex items-start gap-3">
  <div class="i-mdi-cash-multiple text-3xl text-emerald-500 mt-1 shrink-0" />
  <div>
    <div class="font-semibold">Finance</div>
    <div class="text-sm opacity-70">Transactions, entities, tax-year summaries. "Where did my money go?"</div>
  </div>
</div>

<div class="flex items-start gap-3">
  <div class="i-mdi-school-outline text-3xl text-sky-500 mt-1 shrink-0" />
  <div>
    <div class="font-semibold">Learning</div>
    <div class="text-sm opacity-70">Flashcards, concepts, progress. "What should I review tonight?"</div>
  </div>
</div>

<div class="flex items-start gap-3">
  <div class="i-mdi-code-tags text-3xl text-violet-500 mt-1 shrink-0" />
  <div>
    <div class="font-semibold">Productivity</div>
    <div class="text-sm opacity-70">Commits, projects, focus blocks. "Am I context-switching too much?"</div>
  </div>
</div>

<div class="flex items-start gap-3">
  <div class="i-mdi-leaf text-3xl text-amber-500 mt-1 shrink-0" />
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
  <div class="i-mdi-key-variant text-2xl text-rose-500 mt-1 shrink-0" />
  <div>
    <div class="font-semibold">Auth0 production sign-in.</div>
    <div class="opacity-70">Apple / Google / GitHub / Microsoft → Bearer JWT to the Data API. Currently dev-mode <code>x-api-key</code>.</div>
  </div>
</div>

<div class="flex items-start gap-3">
  <div class="i-mdi-database-search-outline text-2xl text-emerald-500 mt-1 shrink-0" />
  <div>
    <div class="font-semibold">Vector embeddings for similarity search.</div>
    <div class="opacity-70">Embed <code>DailySummary.description</code> to find "days that felt like that". Requires bringing your own LLM model (OpenAI, Vertex, etc.) — Aura's similarity-search tool takes the provider as config.</div>
  </div>
</div>

<div class="flex items-start gap-3">
  <div class="i-mdi-cellphone-check text-2xl text-sky-500 mt-1 shrink-0" />
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
    <div class="i-mdi-link-variant text-lg opacity-70" />
    <span class="font-mono">linkedin.com/in/mbuchhorn</span>
  </div>
  <div class="flex items-center gap-2 text-sm opacity-75">
    <div class="i-mdi-code-tags text-lg opacity-70" />
    <span class="font-mono">github.com/ma3u</span>
  </div>
  <div class="flex items-center gap-2 text-sm opacity-75">
    <div class="i-mdi-folder-outline text-lg opacity-70" />
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
