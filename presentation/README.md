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

## Speaker flow (~18-22 min + Q&A)

| Slide | Time | Beat |
| --- | --- | --- |
| 1 — Title | 0:30 | Hook + speaker intro |
| 2 — Two motivations | 1:00 | The personal "why" |
| 3 — Three problems | 1:30 | Audience pain framing |
| 4 — The pattern | 1:30 | "own → graph → API → agent" |
| 5 — Why a graph | 1:30 | Causality chains vs tables |
| 6 — Four pillars | 0:45 | What we'll see next |
| 7 — Pillar 1: Agent | 2:00 | 6 tools, agents-as-code |
| 8 — Pillar 2: Dashboard | 1:30 | Whoop UI, BYO data |
| 9 — Pillar 3: GraphQL + Pages | 1:30 | Daily snapshot pipeline |
| 10 — Pillar 4: iPhone | 2:00 | HealthKit → graph → agent |
| 11 — **Live demo** | 3:00 | Sync → ask → answer overlay |
| 12 — Agent as JSON | 1:30 | The deliverable PR-able file |
| 13 — Bug lesson | 1:00 | Why agents-as-code matters |
| 14 — BYO Aura | 0:45 | Privacy posture + 5-min provisioning |
| 15 — Pause lesson | 1:00 | Don't burn credits |
| 16 — Stats | 0:30 | Land the numbers |
| 17 — Apply this pattern | 1:30 | Call to developers |
| 18 — What's open | 1:00 | PRs welcome |
| 19 — Try it | 0:45 | One screen of commands |
| 20 — Thanks / Q&A | open | |

Demo backup: `docs/images/hackathon/08-iphone-agent-answer-overlay-markdown.jpeg` if the iPhone is offline.
