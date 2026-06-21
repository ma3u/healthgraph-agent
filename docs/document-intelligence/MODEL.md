# Document Intelligence Pilot — Graph Model Spec

> Pilot for [issue #10](https://github.com/ma3u/healthgraph-agent/issues/10) — turn the clinical documents Apple Health
> bundles (`export_cda.xml`, `electrocardiograms/`, `clinical-records/`) into graph
> entities and link them onto the existing temporal health graph.

**Status of the tool.** Aura Document Intelligence (DI) is **PREVIEW** and
**console / UI-only** — there is no API or CLI yet. Everything in this spec is driven
from the Aura Console DI panel: you upload documents, paste an extraction schema +
focus instructions, run the extraction, then run the post-import linking Cypher in
[`link_clinical_to_days.cypher`](link_clinical_to_days.cypher).

> [!IMPORTANT]
> **No real personal data, ever.** The only documents in
> [`sample-docs/`](sample-docs/) are obviously **SYNTHETIC / fictional** (patient
> "Alex Sample", clinic "Northwind Health"). Use those to dry-run the pipeline. When
> you point DI at a *real* Apple Health export, do it on your own Aura instance and
> never commit the source documents or the extracted personal nodes back to this repo.

---

## 1. How Aura DI builds the graph (background)

DI ingests up to **20 local documents per run** (PDF / MD / DOCX / TXT / EPUB),
splits each into chunks, and runs a **schema-guided LLM extraction per chunk**. Two
layers result:

1. **Provenance / lexical layer** (DI creates this automatically — you do not model it):
   | Label | Meaning | Key property |
   |---|---|---|
   | `__Document__` | one source file | `path` |
   | `__Chunk__` | a text span of a document | (DI-internal id) |
   | `__Entity__` | **every** extracted domain entity *also* gets this label | `key` (lower-cased) |

   Relationships:
   | Relationship | From → To |
   |---|---|
   | `__CHUNK_TO_DOCUMENT__` | `__Chunk__` → `__Document__` |
   | `__NEXT_CHUNK__` | `__Chunk__` → `__Chunk__` (reading order) |
   | `__NODE_TO_CHUNK__` | `__Entity__` → `__Chunk__` (which chunk an entity came from) |

2. **Domain layer** (this spec defines it) — the medical entities we want
   (`Biomarker`, `LabResult`, `Medication`, …). Each domain node carries **both** its
   domain label *and* `__Entity__`, so every domain node is reachable through the
   provenance layer.

**Dedup.** Within a run, DI merges any two extracted entities that share the same
`key` property (compared **lower-cased**). So `key` is the *identity* of an entity —
it is the single most important property to design well (see §5).

---

## 2. Domain node labels

Six domain labels. Each row lists the **dedup key** (the `key` property DI compares,
lower-cased) and the other properties we want extracted onto the node.

| Label | `key` (lower-cased identity) | Other properties |
|---|---|---|
| **Biomarker** | `lower(name)` — the canonical analyte, e.g. `ldl cholesterol`, `hba1c`, `qtc` | `name`, `category` (lipid / metabolic / cbc / thyroid / vitamin / ecg), `unit` |
| **LabResult** | `lower(biomarker + '@' + date)` — one measured value of a biomarker on a date, e.g. `ldl cholesterol@2026-03-12` | `biomarker`, `value` (number), `unit`, `reference_range`, `flag` (normal/high/low), `date` (collection/study date), `panel`, `source_document` |
| **Medication** | `lower(name)` — the drug/supplement, e.g. `atorvastatin`, `vitamin d3` | `name`, `dose`, `frequency`, `route`, `purpose`, `start_date`, `status` (active/stopped) |
| **Condition** | `lower(name)` — the assessment/diagnosis, e.g. `borderline ldl cholesterol`, `vitamin d insufficiency` | `name`, `status`, `note`, `date` (date asserted) |
| **Provider** | `lower(name)` — the clinician, e.g. `dr. robin meadows` | `name`, `role` (e.g. internal medicine, cardiology), `organization` |
| **ClinicalEvent** | `lower(type + '@' + date)` — a dated encounter/study, e.g. `ecg@2026-04-02`, `annual physical@2026-03-18` | `type` (visit / ecg / lab order / letter), `title`, `date`, `summary`, `source_document` |

Design notes:

- **`LabResult` and `ClinicalEvent` keys embed the date** so the *same* biomarker or
  event type measured on *different* days stays distinct (you want a time series, not a
  single overwritten node). `Biomarker` / `Medication` / `Condition` / `Provider` keys
  **omit the date** so repeated mentions of "LDL cholesterol" or "Atorvastatin" across
  documents collapse to **one** reusable node.
- **`LabResult` → `Biomarker`** is the value-vs-definition split: `Biomarker` is the
  reusable analyte ("LDL cholesterol", unit mg/dL); `LabResult` is one dated reading of
  it (138 mg/dL on 2026-03-12, flagged High). Same idea as the existing
  `Day`/`DailySummary` split in the health graph.
- Every node above is also a `__Entity__` and carries `key`; the linking Cypher and the
  guarded variant both rely on that.

### Optional intra-document relationships

DI can also be asked (via the focus instructions) to relate the domain entities to each
other. These are nice-to-have for the pilot but the temporal linking in §6 does **not**
depend on them:

| Relationship | From → To | Meaning |
|---|---|---|
| `MEASURES` | `LabResult` → `Biomarker` | this reading is of that analyte |
| `PRESCRIBED_BY` / `ORDERED_BY` | `Medication` / `ClinicalEvent` → `Provider` | who prescribed / ordered |
| `ASSESSED` | `ClinicalEvent` → `Condition` | a visit asserted a condition |
| `FOR_CONDITION` | `Medication` → `Condition` | why a drug was started |

---

## 3. Field mapping from the sample documents

The synthetic docs in [`sample-docs/`](sample-docs/) all describe the same fictional
patient. The three worked examples below show exactly which document field becomes which
node + property. Other sample docs (e.g. an urgent-care discharge note) map to the **same
six labels** — a discharge note is just another `visit`-type `ClinicalEvent` with its
own `Provider`, `Condition`, and `Medication` nodes — so the model is doc-type-agnostic
rather than tied to these three files.

### `lab-panel.md` — Northwind Health Laboratory Report

| Source field | Node | Properties |
|---|---|---|
| "Specimen Collected: 2026-03-12" | `ClinicalEvent` | `type=lab order`, `date=2026-03-12`, `title=Laboratory Report` |
| "Ordering Provider: Dr. Robin Meadows, MD" | `Provider` | `name=Dr. Robin Meadows`, `role=Internal Medicine` |
| each table row, e.g. "LDL Cholesterol \| 138 \| mg/dL \| < 100 \| High" | `Biomarker` + `LabResult` | Biomarker: `name=LDL Cholesterol`, `category=lipid`, `unit=mg/dL`. LabResult: `value=138`, `unit=mg/dL`, `reference_range=< 100`, `flag=High`, `date=2026-03-12`, `panel=Lipid Panel` |
| "Interpretation Summary: Borderline-elevated total and LDL cholesterol…" | `Condition` | `name=Borderline LDL cholesterol`, `date=2026-03-12` |

Every numeric table row (Lipid / Metabolic / CBC / Thyroid / Vitamins) yields one
`Biomarker` + one dated `LabResult`. The collection date `2026-03-12` is what later
links these to `(:Day {date: 2026-03-12})`.

### `ecg-report.md` — Electrocardiogram (ECG) Report

| Source field | Node | Properties |
|---|---|---|
| "Study Date: 2026-04-02" + "Study Type: 12-Lead Resting ECG" | `ClinicalEvent` | `type=ecg`, `title=12-Lead Resting ECG`, `date=2026-04-02`, `summary=Normal ECG` |
| "Reading Cardiologist: Dr. Priya Aster, MD" | `Provider` | `name=Dr. Priya Aster`, `role=Cardiology` |
| measurement rows, e.g. "QTc (Bazett) \| 401 \| ms" | `Biomarker` + `LabResult` | Biomarker: `name=QTc`, `category=ecg`, `unit=ms`. LabResult: `value=401`, `unit=ms`, `reference_range=< 450`, `flag=Normal`, `date=2026-04-02` |
| "Overall: Normal ECG." | `Condition` | `name=Normal sinus rhythm`, `date=2026-04-02` |

The ECG `date=2026-04-02` links the study (and its measurements) to
`(:Day {date: 2026-04-02})`.

### `physician-letter.md` — Physician Summary Letter

| Source field | Node | Properties |
|---|---|---|
| "Visit Date: 2026-03-18" + "Visit Type: Routine annual physical" | `ClinicalEvent` | `type=visit`, `title=Routine annual physical`, `date=2026-03-18` |
| "Provider: Dr. Robin Meadows, MD" | `Provider` | `name=Dr. Robin Meadows`, `role=Internal Medicine` |
| Assessment bullets ("Borderline LDL cholesterol", "Mild vitamin D insufficiency", …) | `Condition` | `name=…`, `date=2026-03-18` |
| Medications table rows | `Medication` | e.g. `name=Atorvastatin`, `dose=10 mg`, `frequency=once daily (PM)`, `purpose=LDL cholesterol lowering`, `start_date=2026-03-18`, `status=active` |

> Note: "Dr. Robin Meadows" appears in **both** the lab panel and the letter. Because
> `Provider.key = lower(name)` omits the date, DI collapses both mentions into **one**
> `Provider` node — that's the dedup design working as intended.

---

## 4. Focus instructions — *paste this into DI's instruction box*

The instruction box is the **single most important field** in DI: it tells the LLM what
entities to look for, what to use as the dedup `key`, and how to normalise dates. Paste
the block below verbatim (it is plain text, not Cypher).

```text
These are synthetic clinical documents (lab reports, ECG reports, and physician
letters) for a personal health knowledge graph. Extract the following entities.
For EVERY entity set a `key` property used for deduplication (it is matched
case-insensitively / lower-cased), plus the listed fields. Normalise every date to
ISO format YYYY-MM-DD.

1. Biomarker — a measurable clinical analyte (e.g. LDL Cholesterol, HbA1c, Fasting
   Glucose, TSH, Vitamin D, and ECG parameters such as PR Interval, QRS Duration,
   QTc). key = the analyte name, lower-cased. Fields: name, category (one of: lipid,
   metabolic, cbc, thyroid, vitamin, ecg), unit. Create ONE Biomarker per distinct
   analyte and reuse it.

2. LabResult — a single measured value of a Biomarker on a date. key = "<biomarker
   name>@<date>" lower-cased (e.g. "ldl cholesterol@2026-03-12"). Fields: biomarker,
   value (numeric), unit, reference_range, flag (Normal / High / Low), date (the
   specimen collection date or ECG study date), panel, source_document (the file name).

3. Medication — a drug or supplement the patient takes. key = medication name,
   lower-cased (e.g. "atorvastatin"). Fields: name, dose, frequency, route, purpose,
   start_date, status (active / stopped).

4. Condition — an assessment, diagnosis, or finding (e.g. "Borderline LDL
   cholesterol", "Vitamin D insufficiency", "Normal sinus rhythm"). key = condition
   name, lower-cased. Fields: name, status, note, date (date it was asserted).

5. Provider — a clinician. key = provider name, lower-cased (e.g. "dr. robin
   meadows"). Fields: name, role (specialty/department), organization. Reuse the same
   Provider node when the same name appears in multiple documents.

6. ClinicalEvent — a dated encounter or study: an office visit, a lab order, an ECG
   study, or a physician letter. key = "<type>@<date>" lower-cased (e.g.
   "ecg@2026-04-02", "visit@2026-03-18"). Fields: type (visit / ecg / lab order /
   letter), title, date, summary, source_document.

Dates are the most important field to capture: always extract the specimen collection
date, ECG study date, and visit date as a `date` property in YYYY-MM-DD form, because
these entities will be linked to daily records by date. If a field is absent, omit it
rather than guessing. Do not invent values.
```

Why the date emphasis: the post-import Cypher (§6) links any extracted entity that
carries a `date` to the existing `(:Day {date})` nodes. An entity with no clean
ISO `date` cannot be placed on the timeline, so date extraction is what makes the whole
pilot work.

---

## 5. Dedup key design (why `key` is the whole game)

DI merges entities by `key`, lower-cased. Two principles:

1. **Reusable definitions → date-free keys.** `Biomarker.key = lower(name)`,
   `Medication.key = lower(name)`, `Provider.key = lower(name)`,
   `Condition.key = lower(name)`. Across all 20 documents, every mention of
   "Atorvastatin" / "LDL Cholesterol" / "Dr. Robin Meadows" collapses to a **single**
   node. This is what lets you ask "every document that mentions atorvastatin" or
   "all readings of LDL over time".

2. **Time-series facts → date-bearing keys.**
   `LabResult.key = lower(biomarker + '@' + date)` and
   `ClinicalEvent.key = lower(type + '@' + date)`. The same biomarker measured on two
   dates produces two `LabResult` nodes (one per `Day`), not one overwritten node — so
   you keep a trend. Re-running DI on the same document is **idempotent**: the same
   value on the same date yields the same `key` and merges instead of duplicating.

Pitfalls the key design avoids:

- *Case drift* — "Atorvastatin" vs "atorvastatin" → same `key` (lower-cased). ✓
- *Cross-doc duplication* — provider named in lab + letter → one `Provider`. ✓
- *Time-series collapse* — would happen if `LabResult.key` omitted the date; embedding
  the date prevents it. ✓

**Recommended constraint** (run once on the Aura instance so the domain keys are
enforced and indexed):

```cypher
CREATE CONSTRAINT clinical_entity_key IF NOT EXISTS
  FOR (e:__Entity__) REQUIRE e.key IS UNIQUE;
```

DI manages `__Entity__.key` itself; the constraint just guarantees no accidental
duplicate identities and gives the linking queries an index to seek on.

---

## 6. Provenance & traceability

Because every domain node is also an `__Entity__`, you can always answer *"where did
this come from?"* — which document, which chunk, which sentence:

```cypher
// From any extracted clinical fact back to its source document + chunk text.
MATCH (e:__Entity__ {key: 'ldl cholesterol@2026-03-12'})
      -[:__NODE_TO_CHUNK__]->(c:__Chunk__)
      -[:__CHUNK_TO_DOCUMENT__]->(doc:__Document__)
RETURN doc.path AS source_file, c.text AS evidence;
```

This is what makes the pilot trustworthy for health data: every `LabResult`,
`Medication`, and `Condition` is one hop from the exact chunk of the exact file it was
read from (`__Document__.path`), and chunks are ordered via `__NEXT_CHUNK__` so you can
recover surrounding context.

**Full picture after a run + linking:**

```
(:__Document__ {path})
   ^                                    provenance layer (DI builds it)
   | __CHUNK_TO_DOCUMENT__
(:__Chunk__) <-[:__NEXT_CHUNK__]- (:__Chunk__)
   ^
   | __NODE_TO_CHUNK__
(:__Entity__:LabResult {key,value,date,...})   domain layer (this spec)
   |
   | ON_DAY            <-- added by link_clinical_to_days.cypher
   v
(:Day {date}) --[:HAS_SUMMARY]--> (:DailySummary)   existing temporal graph
   |  \
   |   `--[:ON_DAY]<-- (:Workout) / (:SleepSession)
   | NEXT_DAY
   v
(:Day {date+1})
```

After linking, a single query spans both worlds — e.g. "what were my workouts and
sleep on the day of my ECG?":

```cypher
MATCH (e:__Entity__:ClinicalEvent {type: 'ecg'})-[:ON_DAY]->(d:Day)
OPTIONAL MATCH (w:Workout)-[:ON_DAY]->(d)
OPTIONAL MATCH (s:SleepSession)-[:ON_DAY]->(d)
RETURN d.date, e.title, collect(DISTINCT w.activity_type) AS workouts, s.asleep_minutes;
```

---

## 7. Run order (checklist)

1. (Once) Create the key constraint in §5 on your Aura instance.
2. Aura Console → **Document Intelligence** (PREVIEW) → new run.
3. Upload the docs (≤20). For a dry run use [`sample-docs/`](sample-docs/).
4. Paste the **focus instructions** from §4 into the instruction box.
5. Run extraction; review the `__Document__` / `__Entity__` nodes it produced.
6. Run [`link_clinical_to_days.cypher`](link_clinical_to_days.cypher) to attach dated
   entities to existing `(:Day {date})` nodes (idempotent, non-destructive).
7. Verify with the traceability + cross-domain queries in §6.

> Reminder: steps 3–7 against a **real** export must run only on your own Aura
> instance, and nothing personal gets committed to this repo.
