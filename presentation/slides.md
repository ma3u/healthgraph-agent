---
theme: seriph
title: From Apple Health to Aura Agent
info: |
  ## From Apple Health to Aura Agent
  Building a Whoop-style coach for your own data
  — and escaping the vendor lock-in.

  Neo4j Theatre @ WeAreDevelopers Berlin 2026
  Speaker: Matthias Buchhorn-Roth · github.com/ma3u
class: text-center
highlighter: shiki
lineNumbers: true
drawings:
  persist: false
mdc: true
css: ./style.css
fonts:
  sans: Inter
  mono: 'JetBrains Mono'
transition: fade-out
---

<div class="kicker">Neo4j Theatre · WeAreDevelopers Berlin 2026</div>

# From Apple Health to Aura Agent

<div class="text-xl opacity-80 mt-4">
  Build a Whoop-style coach for your own data.<br/>
  Escape the vendor lock-in.
</div>

<div class="absolute bottom-12 left-0 right-0 text-center font-mono text-sm opacity-50">
  Matthias Buchhorn-Roth · <span class="opacity-80">@ma3u</span>
</div>

<!--
Speaker: Hi everyone. Quick framing — I built this over the hackathon window
to scratch my own itch, and I want to leave you with one thing: this pattern
is reusable for any quantified-self domain you care about. Not just health.
-->

---
layout: section
---

<div class="kicker">Two things I wanted</div>

<v-clicks>

# A Whoop dashboard — for my Apple Watch data.

# Escape the vendor lock-in on 8.5 years of health data.

</v-clicks>

<!--
Speaker: I'm an Apple Watch user. Apple shows me charts; it doesn't *coach* me.
Whoop has the coach UX I want — but their hardware. Both keep the data hostage.
8.5 years of biometrics, in a black box.
-->

---

# The problem you also have

<v-clicks depth="2">

- **Your fitness tracker is a silo.** Apple Health shows charts. Whoop, Oura, Garmin all monetize lock-in.
- **Your data is *relational*** — workout → next night's sleep → morning HRV → recovery score. Tables hide that.
- **An LLM alone won't help.** "How am I doing?" without grounded data = horoscope.

</v-clicks>

<v-click>

<div class="mt-8 text-lg">
👉 You're a developer. <strong>You can fix all three.</strong>
</div>

</v-click>

<!--
Speaker: Three pains, one developer-shaped solution. Spend the next 20 minutes
with me — by the end you'll see a pattern you can apply to any personal
data domain.
-->

---
layout: center
---

# The pattern

<div class="text-3xl my-8 font-mono opacity-80">
own your data → graph → API → agent
</div>

<v-clicks>

- 1️⃣ **Own** — pull your data out (Apple Health export.xml)
- 2️⃣ **Graph** — model relationships, not rows (Neo4j Aura)
- 3️⃣ **API** — expose typed mutations + queries (Aura GraphQL Data API)
- 4️⃣ **Agent** — ground an LLM with templated Cypher (Aura Agent)

</v-clicks>

<!--
Speaker: Four steps. None require a hosting bill. Everything runs on your own
Aura instance — BYO infrastructure. The interesting bits start at step 2.
-->

---
layout: two-cols-header
---

# Why a graph?

::left::

A flat table can tell you:

> "Your HRV was 31 ms on May 12."

::right::

A graph can tell you:

> "Your HRV dropped 8 ms the morning **after** a 90-min run that **followed** a 5h sleep night, in a week where you trained 28h."

<v-click>

<div class="mt-8 col-span-2 font-mono text-sm opacity-70">
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

<div class="kicker">What I built · 4 pillars</div>

# Aura Agent · Dashboard · GraphQL API + Pages · iPhone

<div class="opacity-70 mt-4 text-base">
Each one a Neo4j Aura primitive. Each one solving a piece of the pattern.
</div>

---

# 1 · Aura Agent — `HealthGraph Agent`

<div class="grid grid-cols-5 gap-6 mt-4">

<div class="col-span-3">

**6 tools** — Text2Cypher + 5 parameterized Cypher templates:

- `health_overview` — RHR / HRV / steps / sleep + 30-day baseline
- `workout_recovery` — workout → next-day HRV chain
- `overtraining_check` — weeks with `CAUTION` / `HIGH RISK` flags
- `longevity_trends` — month-over-month biomarkers
- `exercise_balance` — cardio vs strength vs flexibility

Defined **as code** via the v2beta1 `/agents` API.<br/>
One script, three modes: `status` / `--pull` / `--push`.

</div>

<div class="col-span-2">

<img src="/images/01-aura-agent-playground-longevity-question.png" class="rounded-lg shadow-xl" />

</div>

</div>

<!--
Speaker: This is the brain. The Console rendering on the right shows the
Agent answering with reasoning + a tool call + a grounded answer.
-->

---

# 2 · Aura Dashboard — Whoop-style, in-Console

<div class="grid grid-cols-5 gap-6 mt-2">

<div class="col-span-2">

**5 pages, 35 panels:**

- Daily hero — Recovery % / Strain / Sleep
- Recovery deep-dive
- Strain deep-dive
- Sleep deep-dive
- 8.5-year Health Monitor

Pushed via one script (idempotent — deterministic UUID per title).
Score formulas open-sourced in `docs/SCORING.md`.

</div>

<div class="col-span-3">

<img src="/images/02-aura-dashboard-whoop-recovery.png" class="rounded-lg shadow-xl" />

</div>

</div>

<!--
Speaker: This is the Whoop UI I wanted, rebuilt on top of *my* graph. Same
scoring logic. Different data ownership.
-->

---

# 3 · GraphQL Data API + GitHub Pages

<div class="grid grid-cols-5 gap-6 mt-2">

<div class="col-span-2 text-sm">

**Curated SDL** with three `@cypher` MERGE mutations:<br/>
`ingestDay` · `ingestWorkout` · `ingestSleep`

Deployed via the `v1beta5` REST endpoint (aura-cli has no `data-api` command yet).

A daily GitHub Actions cron at 06:30 UTC:

1. Auto-resumes the paused instance
2. Renders the Recovery snapshot
3. Commits + pushes
4. **Pauses** again (~2-3 min uptime/day)

</div>

<div class="col-span-3">

<img src="/images/10-graphql-data-api-pipeline.png" class="rounded-lg shadow-xl" />

</div>

</div>

<!--
Speaker: Critical: professional-db tier does NOT auto-pause. Without that final
"pause" step, the instance bleeds ~$10/day. Demo lesson coming up.
-->

---

# 4 · iPhone — HealthKit sync + "Ask your graph"

<div class="img-row mt-4">

<img src="/images/06-iphone-healthkit-sync-delta-upload.jpeg" />
<img src="/images/07-iphone-dashboard-ask-your-graph.jpeg" />
<img src="/images/08-iphone-agent-answer-overlay-markdown.jpeg" />

</div>

<div class="mt-4 text-sm opacity-80 grid grid-cols-3 gap-4">

<div><strong>Sync</strong> — HealthKit → query Aura for max(Day.date) → upload only the delta.</div>
<div><strong>Ask</strong> — 4 chips compute concrete ISO date ranges at tap time.</div>
<div><strong>Answer</strong> — overlay sheet, Markdown rendering, trend arrows.</div>

</div>

<!--
Speaker: This is where it all comes together. Real-device demo coming up in
two slides. Notice the answer overlay — that's actual numbers from my own
graph, queried by the agent's tools, ~15 seconds end-to-end.
-->

---
layout: section
---

<div class="kicker">Live demo · ~3 minutes</div>

# Open the phone, tap "Last week summary"

<div class="opacity-70 mt-4">
HealthKit → Aura graph → Agent invoke → Markdown overlay
</div>

<!--
Speaker (DEMO):
1. Open HealthGraph Sync on the iPhone.
2. Sync tab — show "max(Day.date)" then upload last 7 days delta.
3. Dashboard tab — tap "Last week summary" chip.
4. Show the loading state (~15 s).
5. Answer overlay opens — point out the numbers (RHR vs baseline,
   the → stable arrow, the bullet structure).
6. Drag the sheet down to .medium detent, then up to .large. Done.

If anything fails: have a backup screenshot of the answer overlay ready.
-->

---

# Code: the agent — as JSON

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
<code>scripts/create_aura_agent.py</code> — three modes: <code>status</code> · <code>--pull</code> · <code>--push</code>
</div>

<!--
Speaker: This is the deliverable I'm most excited about. The agent — system
prompt, tools, Cypher templates — is a checked-in JSON file. Diff in PR.
Round-trip via `--pull` to capture Console edits. Push via `--push` to
deploy. Agents-as-code, finally.
-->

---

# Lesson: I caught a copy-paste bug — *because* it's code

<div class="grid grid-cols-2 gap-6 text-sm font-mono mt-2">

<div>

**Before** (broken template, lived in Console for weeks)

```cypher
MATCH (w:Workout)-[:ON_DAY]->(d:Day)
WHERE w.activity_type = $workout_type
//                       ^^^^^^^^^^^^^
// parameters declared: $start_date, $end_date
RETURN ...
```

Agent response: *"It looks like the `health_overview` tool is currently unavailable."*

</div>

<div>

**After** (round-tripped via `--pull`, fixed in code, `--push`-ed live)

```cypher
MATCH (d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
WHERE d.date >= date($start_date)
  AND d.date <= date($end_date)
WITH collect({date: toString(d.date), rhr: s.resting_heart_rate, ...}) AS week
OPTIONAL MATCH (d2:Day)-[:HAS_SUMMARY]->(s2:DailySummary)
WHERE d2.date >= date($start_date) - duration({days: 30}) ...
RETURN week, baseline_30d
```

Agent response: *"Your RHR was 57.7 bpm vs 58.2 baseline → stable, but slightly higher."*

</div>

</div>

<!--
Speaker: When tools live in a console UI, they rot quietly. Round-tripping
to a file means PR review, grep, diff, blame. Took me 5 minutes to find
this once it was a `.json` in my repo.
-->

---

# BYO Aura — no shared backend

<v-clicks>

- Every installer points at **their own** Aura instance
- Two provisioning scripts read from `.env` and create everything:
  - `create_aura_data_api.py` — the GraphQL Data API + SDL
  - `create_aura_agent.py` — the agent definition + tools
- iPhone app reads HealthKit, writes to **your** Aura, queries **your** agent
- The dev's instance is dev-only — never a default

</v-clicks>

<v-click>

<div class="mt-6 text-base">
**~5 minutes** from <code>git clone</code> to a working stack against your own Aura.
</div>

</v-click>

<!--
Speaker: This is the privacy posture: nothing of yours touches my infra.
The trade-off: you bring credits. Which leads to the next lesson...
-->

---

# Lesson: professional-db does **not** auto-pause

<div class="grid grid-cols-2 gap-8 mt-6">

<div>

| Tier | Auto-pause? | Burn rate |
| --- | --- | --- |
| **Free** | Yes (3 days idle) | $0 |
| **AuraDS** | Yes | varies |
| **Professional** | **No** | ~$0.30–0.40/hr |

If your workflow only *resumes*, your instance lives forever.

</div>

<div>

The fix — one extra step in the daily cron:

```yaml
- name: Pause Aura instance
  if: always()
  env:
    AURA_INSTANCEID: ${{ secrets.AURA_INSTANCEID }}
    AURA_CLIENT_ID:  ${{ secrets.AURA_CLIENT_ID }}
    AURA_CLIENT_SECRET: ${{ secrets.AURA_CLIENT_SECRET }}
  run: bash scripts/aura_pause.sh pause
```

Total uptime/day after: ~2-3 min.

</div>

</div>

<!--
Speaker: This is the kind of thing you only learn by running out of credits
mid-build. The Aura management API takes one POST to /pause. Add it to
your daily cron's last step. Save a hundred dollars.
-->

---
layout: center
---

# Stats

<div class="grid grid-cols-3 gap-12 mt-8">

<div class="stat"><div class="n">3,117</div><div class="l">Day nodes in Aura</div></div>
<div class="stat"><div class="n">3,180</div><div class="l">workouts modeled</div></div>
<div class="stat"><div class="n">8.5 yr</div><div class="l">of biometrics</div></div>

<div class="stat"><div class="n">6</div><div class="l">agent tools (5 Cypher + Text2Cypher)</div></div>
<div class="stat"><div class="n">21</div><div class="l">Neo4j Skills for Claude</div></div>
<div class="stat"><div class="n">&lt;5 min</div><div class="l">provisioning time, from clone</div></div>

</div>

<!--
Speaker: Numbers to anchor. 3 minutes of stats, lands the credibility.
-->

---
layout: section
---

<div class="kicker">Take this back to your work</div>

# The pattern works for anything quantified

<v-clicks>

- 💰 **Finance** — transactions → entities → tax-year summaries → "where did my money go?"
- 📚 **Learning** — flashcards → concepts → progress → "what should I review tonight?"
- 💻 **Productivity** — commits → projects → focus blocks → "am I context-switching too much?"
- 🌱 **Anything you measure** — model the relationships, ground the LLM, kill the silo.

</v-clicks>

<!--
Speaker: This is the call. Health was my pain. Pick yours. The four-pillar
stack — graph, API, dashboard, agent — costs about a weekend on Aura free
or hackathon credits.
-->

---

# What's still open (PRs welcome 🙏)

<v-clicks>

- **Auth0 production sign-in** — Apple / Google / GitHub / Microsoft → Bearer JWT to the Data API. Currently dev-mode `x-api-key`.
- **Vector embeddings** for similarity search on `DailySummary.description` — "find me days that felt like *that*".
- **Background HealthKit sync** via `BGAppRefreshTask` + `HKObserverQuery`.
- **HealthKit deletion handling** — when a sample is deleted on-device, propagate.

</v-clicks>

<v-click>

<div class="mt-6 font-mono opacity-70">
github.com/ma3u/healthgraph-agent · issues #5, #7+
</div>

</v-click>

---
layout: center
---

# Try it

<div class="font-mono text-2xl mt-6 mb-8">
github.com/ma3u/healthgraph-agent
</div>

```bash
git clone https://github.com/ma3u/healthgraph-agent
cd healthgraph-agent
cp .env.example .env   # fill in AURA_CLIENT_ID / SECRET / INSTANCEID
/tmp/aura-venv/bin/python scripts/create_aura_data_api.py
/tmp/aura-venv/bin/python scripts/create_aura_agent.py
bash scripts/build_ios.sh
```

<div class="mt-6 opacity-70 text-sm">
Live daily snapshot: <code>ma3u.github.io/healthgraph-agent/snapshot/</code>
</div>

<!--
Speaker: One screen of commands. Five minutes start to finish if your Aura
account is already set up. Hand the link to one person near you when this
slide goes up.
-->

---
layout: center
class: text-center
---

# Thanks 🙏

<div class="text-xl opacity-70 mt-6">
  Questions?
</div>

<div class="absolute bottom-12 left-0 right-0 text-center font-mono text-sm opacity-50">
  Matthias Buchhorn-Roth · <span class="opacity-80">@ma3u</span> · github.com/ma3u/healthgraph-agent
</div>
