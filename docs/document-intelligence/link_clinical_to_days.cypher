// ============================================================
// HealthGraph Agent — Link Document-Intelligence clinical
// entities onto the existing temporal graph (:Day {date})
// ============================================================
//
// WHAT THIS DOES
//   Run this AFTER an Aura Document Intelligence (DI) run has imported the
//   clinical documents (lab panels, ECG reports, physician letters). DI has
//   created domain nodes (Biomarker, LabResult, Medication, Condition,
//   Provider, ClinicalEvent) — each also labelled __Entity__ and carrying a
//   `key`. Many of them carry a `date` (specimen date / ECG study date /
//   visit date). This script attaches every dated clinical entity to the
//   existing (:Day {date}) node via:
//
//       MERGE (e)-[:ON_DAY]->(d)
//
//   ON_DAY is the SAME relationship the rest of the graph already uses
//   ((:Workout)-[:ON_DAY]->(:Day), (:SleepSession)-[:ON_DAY]->(:Day)), so
//   clinical facts land on the same temporal spine as activity & sleep.
//
// SAFETY / IDEMPOTENCY
//   - NON-DESTRUCTIVE: this script never CREATEs a Day, never DELETEs or
//     DETACHes anything, and never overwrites existing properties.
//   - Days are MATCHed, not MERGEd — if no (:Day {date}) exists for an
//     entity's date, that entity is simply SKIPPED (no orphan Day is made).
//   - MERGE on the relationship makes re-runs idempotent: running this twice
//     produces the same single ON_DAY edge, not duplicates.
//   - Dates are parsed defensively: anything that is not a clean ISO
//     YYYY-MM-DD value is filtered out before we touch the graph.
//
// HOW TO RUN
//   Paste each block separately into Neo4j Browser / Aura Query, OR run the
//   whole file with cypher-shell. Requires Cypher 25 (Aura 2025.x+).
//
// PRE-REQ (run once; harmless if it already exists)
//   CREATE CONSTRAINT clinical_entity_key IF NOT EXISTS
//     FOR (e:__Entity__) REQUIRE e.key IS UNIQUE;
//   CREATE CONSTRAINT day_date IF NOT EXISTS
//     FOR (d:Day) REQUIRE d.date IS UNIQUE;   // already created by the ETL
// ============================================================


// ------------------------------------------------------------
// 0. (Optional) Sanity check — what carries a date and will link?
//    Read-only preview. Run this first to see what block 1/2 will affect.
// ------------------------------------------------------------
// MATCH (e:__Entity__)
// WHERE e.date IS NOT NULL
// RETURN labels(e) AS labels, e.key AS key, e.date AS raw_date,
//        count(*) AS n
// ORDER BY n DESC;


// ------------------------------------------------------------
// 1. PRIMARY: link domain-labelled clinical entities to their Day.
//
//    Targets the explicit domain labels from MODEL.md that represent a
//    point-in-time clinical fact. Biomarker / Provider are intentionally
//    EXCLUDED here because they are reusable definitions, not dated events
//    (a Biomarker's dated reading is the LabResult, which IS included).
// ------------------------------------------------------------
MATCH (e)
WHERE (e:LabResult OR e:ClinicalEvent OR e:Condition OR e:Medication)
  AND e.date IS NOT NULL

// --- safe date parsing -------------------------------------------------
// Accept only values whose first 10 chars look like YYYY-MM-DD (covers a
// bare "2026-03-12" and an ISO datetime "2026-03-12T08:05:00"). Anything
// else (free text, partial dates like "March 2027", nulls) is dropped.
WITH e, toString(e.date) AS ds
WHERE ds =~ '\\d{4}-\\d{2}-\\d{2}.*'
WITH e, date(left(ds, 10)) AS d_date          // throws-safe: regex guaranteed valid prefix

// --- match an EXISTING Day only (never create one) ---------------------
MATCH (d:Day {date: d_date})

// --- idempotent, non-destructive link ----------------------------------
MERGE (e)-[r:ON_DAY]->(d)
RETURN labels(e) AS entity_labels, e.key AS key, d.date AS linked_day,
       count(r) AS links
ORDER BY linked_day;


// ------------------------------------------------------------
// 2. GUARDED VARIANT: match on the __Entity__ label + a `date` property.
//
//    Use this if DI did not (or only partially) applied your domain labels,
//    or to catch any dated entity the block above missed. It is broader:
//    it links ANY __Entity__ that has a parseable `date` and a matching Day.
//    Still non-destructive and idempotent (MATCH the Day, MERGE the rel).
//
//    Run block 1 OR block 2 (or both — MERGE means block 2 will not
//    duplicate edges block 1 already made).
// ------------------------------------------------------------
MATCH (e:__Entity__)
WHERE e.date IS NOT NULL

// safe parse: require an ISO YYYY-MM-DD prefix, then take only those 10 chars
WITH e, toString(e.date) AS ds
WHERE ds =~ '\\d{4}-\\d{2}-\\d{2}.*'
WITH e, date(left(ds, 10)) AS d_date

// existing Day only — skip silently if none
MATCH (d:Day {date: d_date})

MERGE (e)-[r:ON_DAY]->(d)
RETURN e.key AS key, labels(e) AS labels, d.date AS linked_day,
       count(r) AS links
ORDER BY linked_day;


// ------------------------------------------------------------
// 3. (Optional) Report: dated entities that could NOT be linked because no
//    matching Day exists yet. Purely diagnostic — changes nothing.
//    (Days are created by the health ETL; a clinical doc may pre-date or
//    post-date the activity data you've loaded.)
// ------------------------------------------------------------
// MATCH (e:__Entity__)
// WHERE e.date IS NOT NULL
//   AND toString(e.date) =~ '\\d{4}-\\d{2}-\\d{2}.*'
// WITH e, date(left(toString(e.date), 10)) AS d_date
// WHERE NOT EXISTS { MATCH (:Day {date: d_date}) }
// RETURN d_date AS missing_day, collect(e.key) AS unlinked_entities
// ORDER BY missing_day;


// ------------------------------------------------------------
// 4. (Optional) Verify the links + provenance is intact end-to-end.
// ------------------------------------------------------------
// MATCH (e:__Entity__)-[:ON_DAY]->(d:Day)
// OPTIONAL MATCH (e)-[:__NODE_TO_CHUNK__]->(:__Chunk__)
//                  -[:__CHUNK_TO_DOCUMENT__]->(doc:__Document__)
// RETURN d.date AS day, labels(e) AS entity, e.key AS key,
//        doc.path AS source_document
// ORDER BY day;
