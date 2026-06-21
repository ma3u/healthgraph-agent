# Document Intelligence Pilot — Runbook

**Issue:** [#10 — Evaluate Aura Document Intelligence for Apple HealthGraph and clarify API/CLI availability](https://github.com/ma3u/healthgraph-agent/issues/10)

A step-by-step runbook for ingesting the **clinical documents that the Apple Health
ETL ignores today** (`export_cda.xml`, `electrocardiograms/`, `clinical-records/`)
into the existing health graph using **Neo4j Aura Document Intelligence (DI)**, and
linking the extracted entities onto the day-by-day timeline so the Aura Agent can
answer hybrid questions the structured-only graph can't.

---

> ## ⚠️ NEVER upload real clinical data
>
> Per this repo's **no-personal-data policy**, you must **never upload real Apple
> Health clinical documents, real lab panels, real ECG PDFs, or any real
> provider records** to Document Intelligence — these leave your machine and are
> processed by an LLM.
>
> **Use only the obviously SYNTHETIC / fictional documents in
> [`sample-docs/`](sample-docs/).** They are clearly marked as synthetic and
> contain no real person's data. If you adapt this pilot to your own export, you
> are responsible for anonymizing first. When in doubt, do not upload it.

---

## Preview / AS-IS caveat

Document Intelligence is in **Preview** and documented by Neo4j as **AS-IS, for
internal/development use — not production-critical workflows** (launch blog,
2026-06-01). Treat the generated model as a starting point that **you must review
and correct** before importing. Behaviour, tier availability, and limits may change.

## Console-only — no API / CLI / MCP yet

DI is **console/UI-only today**. The whole workflow (Graph models / Cloud data
sources / Import jobs) is triggered from the Aura Console "Run import" button or the
in-console Document Intelligence Agent. **There is no DI API endpoint, CLI command
group, or MCP server** — so this pilot **cannot be scripted under `scripts/`** and
can't join `run_pipeline.sh` yet. Neo4j's launch blog explicitly places
**"API, CLI, and MCP server endpoints" on the roadmap**, so the steps below are
manual on purpose. Revisit automation once that ships (open questions tracked in #10).

---

## Goal

Assess whether DI can enrich the Apple Health graph with clinically meaningful
entities (lab results, conditions, medications, ECG findings, providers) **while
preserving traceability** back to the source document, and connect those entities to
the existing `(:Day)` timeline so clinical findings correlate with that day's
`DailySummary` metrics (RHR / HRV / sleep / respiratory rate).

## Deliverables (mirrors #10)

- [x] DI pilot dataset definition — synthetic docs in [`sample-docs/`](sample-docs/)
- [x] Proposed graph-model mapping (DI output → existing schema, incl. `Day`
      linkage by date) — see [`MODEL.md`](MODEL.md)
- [x] Validation query set — [`validate_clinical.cypher`](validate_clinical.cypher)
- [x] Link script (DI entities → `:Day`) — [`link_clinical_to_days.cypher`](link_clinical_to_days.cypher)
- [x] Aura Agent made provenance-aware (conditional, no-fabrication guardrails) —
      `agents/healthgraph-coach.json`

## Validation

- Manual precision/recall-style check on the small synthetic set.
- Verify no harmful duplication in core domain entities (tune `key` properties).
- Confirm extracted entities linked to the correct `(:Day)`.
- Run representative Aura Agent questions and compare answer grounding
  before/after enrichment.

---

## Prerequisites

1. **An AuraDB instance** with the structured health graph already loaded
   (`(:Day)`, `(:DailySummary)`, `(:Workout)`, `(:SleepSession)`). The day-linking
   step needs existing `(:Day {date})` nodes to attach clinical entities to.
   > Per the BYO-Aura policy, use **your own** AuraDB instance — the dev instance
   > is dev-only and never a default.
2. **A supported tier.** The DI Quick Start lists **AuraDB Free, Professional, and
   Business Critical**.
   - On **Professional / Business Critical** you must enable
     **"Tool authentication with Aura user"** for the instance before DI can run.
   - **Free** works without that toggle.
3. **The 4 synthetic documents** in [`sample-docs/`](sample-docs/), downloaded
   locally (DI uploads from local files for this pilot).
4. **The companion files** in this folder, open and ready to paste:
   - [`MODEL.md`](MODEL.md) — the focus instructions + target schema to paste into
     the DI model editor.
   - [`link_clinical_to_days.cypher`](link_clinical_to_days.cypher) — connects
     extracted entities to `(:Day)`.
   - [`validate_clinical.cypher`](validate_clinical.cypher) — post-import checks.

### Limits to respect

- **≤ 20 local documents per graph-model run** (this pilot uses 4).
- Local file uploads are **temporary until import completes** — re-upload if you
  restart.
- Supported formats: **PDF, MD, DOCX, TXT, EPUB**.
- Deduplication matches on the model's **`key` property, lower-cased** — so key
  design matters (covered in `MODEL.md`).

---

## Steps

### (a) Open Document Intelligence in the console

1. Sign in to the [Aura Console](https://console.neo4j.io) with the correct account.
2. Select the AuraDB instance holding your health graph.
3. (Pro / Business Critical only) confirm **Tool authentication with Aura user** is
   enabled for the instance.
4. Open **Document Intelligence** from the sidebar. You'll see the
   **Graph models**, **Cloud data sources**, and **Import jobs** tabs.

### (b) Upload the 4 synthetic docs

1. Start a new graph model (**+ New** under Graph models).
2. Choose **local files** as the source and upload all 4 documents from
   [`sample-docs/`](sample-docs/) (all synthetic, all Markdown — a supported format):
   - [`lab-panel.md`](sample-docs/lab-panel.md) — synthetic lipid / metabolic / CBC
     panel (collected 2026-03-12)
   - [`physician-letter.md`](sample-docs/physician-letter.md) — synthetic physician
     summary letter with a medication table (visit 2026-03-18)
   - [`ecg-report.md`](sample-docs/ecg-report.md) — synthetic 12-lead ECG report
     (study 2026-04-02)
   - [`discharge-note.md`](sample-docs/discharge-note.md) — synthetic urgent-care
     visit / discharge note (encounter 2026-05-09)
3. Confirm 4 documents are staged (well under the 20-doc cap).
   > Re-confirm these are the **synthetic** files — never a real export.

### (c) Paste the focus instructions from `MODEL.md`

1. In the model editor, paste the **focus / extraction instructions** from
   [`MODEL.md`](MODEL.md) into the AI assistant prompt. They steer extraction toward
   the six target labels: `Biomarker`, `LabResult`, `Condition`, `Medication`,
   `Provider`, `ClinicalEvent`.
2. They also specify the **`key` property** for each entity (used for dedup,
   matched lower-cased) and that any entity with an associated date should carry a
   normalized `date` (ISO `YYYY-MM-DD`) so it can join `(:Day)` later.
3. Let DI generate the candidate model.

### (d) Review + fix the generated model

DI's first model is a draft — **correct it before importing**:

1. Confirm the **labels** match the target set (rename/merge stray labels).
2. Confirm each entity's **`key`** is a stable, low-cardinality identifier
   (e.g. `Biomarker.key = name`), so the same biomarker across docs dedupes to one
   node instead of duplicating.
3. Confirm date-bearing entities expose a normalized `date` property.
4. Drop noise labels you don't want in the graph.
5. See [`MODEL.md`](MODEL.md) for the exact target schema and the DI → health-schema
   mapping.

### (e) Run import

1. Click **Run import**. DI chunks each document, runs schema-guided LLM extraction
   per chunk, dedups by the lower-cased `key`, and writes:
   - domain nodes (each also labelled `__Entity__`),
   - the provenance layer: `__Document__` (with a `path`), `__Chunk__`, and rels
     `__CHUNK_TO_DOCUMENT__`, `__NEXT_CHUNK__`, `__NODE_TO_CHUNK__`.
2. Wait for the **Import jobs** tab to show the run as complete.

### (f) Run `link_clinical_to_days.cypher` in Query

1. Open the **Query** tab.
2. Paste and run [`link_clinical_to_days.cypher`](link_clinical_to_days.cypher). It
   matches each date-bearing clinical entity to the existing `(:Day {date})` and
   creates `(entity)-[:ON_DAY]->(:Day)`, weaving the imported clinical layer onto the
   structured temporal graph. It leaves the DI provenance layer untouched.

### (g) Run `validate_clinical.cypher`

1. In the **Query** tab, run each statement in
   [`validate_clinical.cypher`](validate_clinical.cypher):
   - provenance counts (`__Document__` should be **4**, `__Chunk__` ≥ 4,
     `__Entity__` > 0),
   - per-domain label counts,
   - how many entities linked to a `:Day` (coverage %),
   - a provenance traversal (entity → chunk → document `path`),
   - the **hybrid** query joining a clinical finding to that day's `DailySummary`.
2. Spot-check precision/recall against the synthetic source text, and confirm no
   harmful duplicate domain nodes (if you see dupes, fix the `key` in step (d) and
   re-import).

### (h) Ask the Aura Agent a hybrid question

1. Open the **Aura Agent** (the provenance-aware `HealthGraph Agent` in
   `agents/healthgraph-coach.json`).
2. Ask something only the enriched graph can answer, e.g.:
   - *"On 2026-03-12 my lipid panel was drawn — what were my RHR and HRV that day,
     and cite the source document."* (the lab panel flagged LDL 138 / Total
     cholesterol 212 as High)
   - *"Show clinical findings that fall near days with elevated resting heart rate."*
   - *"What medications was I started on, and on what date — cite the document."*
     (atorvastatin 10 mg + vitamin D3 2000 IU, from the physician letter dated
     2026-03-18)
3. Confirm the agent **cites the `__Document__.path`**, correlates with the matching
   `Day`, and **does not fabricate** values. (If no clinical nodes existed, it should
   say so and answer from structured data only — that's the built-in guardrail.)

---

## Recommendation (to record in #10)

After running the pilot, note in issue #10 whether to **adopt DI now for
exploratory/grounding workflows** vs **defer until the public API/CLI/MCP lands**.
The strongest argument for adopting now is provenance-grounded hybrid Q&A; the main
reason to defer is that, being console-only and Preview/AS-IS, it can't yet be
scripted into the repo's pipeline.
