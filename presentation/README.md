# HealthGraph Agent — Theatre Talk

Modern minimalist [Slidev](https://sli.dev) deck for the **Neo4j Theatre @ WeAreDevelopers Berlin 2026** session.

Talk: *From Apple Health to Aura Agent — Build a Whoop-style coach for your own data, escape the vendor lock-in.*

## Run locally

```sh
cd presentation
npm install        # one-time
npm run dev        # opens http://localhost:3030
```

Slidev shortcuts during presentation:

- `Space` / `→` — next step / slide
- `←` — back
- `O` — overview (slide grid)
- `D` — toggle dark mode
- `F` — fullscreen
- `B` — black-out (presenter mode)
- `Alt+R` — recorder
- `?` — full help

The browser also serves `/presenter` (notes + timer + next-slide preview) on the same port.

## Export

```sh
npm run export-pdf   # → dist/healthgraph-agent-talk.pdf
npm run build        # → dist/   static HTML deck
```

## Structure

```
presentation/
├── slides.md           ← the deck content (markdown + Vue directives)
├── style.css           ← minimalist overrides on the `seriph` theme
├── package.json
├── public/
│   └── images/         ← symlink → ../../docs/images/hackathon
└── README.md           ← you are here
```

Images live in [`docs/images/hackathon/`](../docs/images/hackathon/) and are symlinked into `public/` so a single source of truth feeds both the README and the deck.

## Speaker flow (15 min + Q&A)

| Slide | Time | Beat |
| --- | --- | --- |
| 1 — Title | 0:45 | Hook + speaker intro + personal "why" |
| 2 — The problem | 1:15 | Silos · relational data · ungrounded LLMs |
| 3 — The pattern | 1:00 | "own → graph → API → agent" |
| 4 — Why a graph | 1:00 | Causality chains vs tables |
| 5 — Four pillars | 0:30 | What we'll see next |
| 6 — Pillar 1: Agent | 1:15 | 6 tools, agents-as-code |
| 7 — Pillar 2: Dashboard | 0:45 | Whoop UI, BYO data |
| 8 — Pillar 3: GraphQL + Pages | 0:45 | Daily snapshot pipeline |
| 9 — Pillar 4: iPhone | 0:30 | Bridge into the demo |
| 10 — **Live demo** | 4:00 | Sync → ask → agent → snapshot (4 stops) |
| 11 — Agent as JSON | 1:00 | The deliverable PR-able file |
| 12 — BYO Aura + credits | 1:00 | Privacy posture + don't burn credits |
| 13 — 3D graph | 0:30 | Land the numbers |
| 14 — Document Intelligence | 0:45 | The next silo → private EHR |
| 15 — Aura features → EHR | 1:00 | Each feature = one layer of the record + its lesson |
| 16 — Try it | 0:30 | Commands + PRs welcome |
| 17 — Thanks / Q&A | open | |

Demo backup: `docs/images/hackathon/08-iphone-agent-answer-overlay-markdown.jpeg` if the iPhone is offline.
