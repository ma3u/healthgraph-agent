// ============================================================
//  validate_clinical.cypher
//  Post-import validation for the Aura Document Intelligence (DI)
//  clinical-documents pilot — issue #10.
//
//  Run these AFTER:
//    1. DI "Run import" has completed in the Aura Console, and
//    2. link_clinical_to_days.cypher has connected the extracted
//       clinical entities onto the existing temporal graph (:Day).
//
//  Existing health schema (structured ETL):
//    (:Day {date})-[:HAS_SUMMARY]->(:DailySummary {date, hrv_mean,
//        resting_heart_rate, avg_respiratory_rate, sleep_hours, ...})
//    (:Workout)-[:ON_DAY]->(:Day), (:SleepSession)-[:ON_DAY]->(:Day)
//
//  DI provenance (lexical) layer — note the DOUBLE underscores:
//    Labels: __Document__ (has `path`), __Chunk__, __Entity__
//            (every extracted entity ALSO carries __Entity__ on top
//             of its domain label, e.g. :LabResult:__Entity__).
//    Rels:   (:__Chunk__)-[:__CHUNK_TO_DOCUMENT__]->(:__Document__)
//            (:__Chunk__)-[:__NEXT_CHUNK__]->(:__Chunk__)
//            (:__Entity__)-[:__NODE_TO_CHUNK__]->(:__Chunk__)
//
//  Pilot link relationship (created by link_clinical_to_days.cypher):
//    (clinical :__Entity__)-[:ON_DAY]->(:Day)
//
//  Run each statement separately in the Aura Console → Query tab.
//  All statements are READ-ONLY.
// ============================================================


// ------------------------------------------------------------
//  1. Lexical / provenance layer counts
//     Confirms the import actually wrote the DI structure.
//     Expect: __Document__ = number of docs imported (4 for the pilot),
//             __Chunk__ >= __Document__, __Entity__ > 0.
// ------------------------------------------------------------
// 1a. Provenance node counts
MATCH (d:__Document__) WITH count(d) AS documents
MATCH (c:__Chunk__)    WITH documents, count(c) AS chunks
MATCH (e:__Entity__)   RETURN documents, chunks, count(e) AS entities;

// 1b. Provenance relationship counts (sanity-check the lexical wiring)
MATCH (:__Chunk__)-[r:__CHUNK_TO_DOCUMENT__]->(:__Document__)
WITH count(r) AS chunk_to_document
MATCH (:__Chunk__)-[n:__NEXT_CHUNK__]->(:__Chunk__)
WITH chunk_to_document, count(n) AS next_chunk
MATCH (:__Entity__)-[t:__NODE_TO_CHUNK__]->(:__Chunk__)
RETURN chunk_to_document, next_chunk, count(t) AS node_to_chunk;

// 1c. One row per imported document with its path + how much it produced.
//     Use this to eyeball that all 4 SYNTHETIC sample docs landed.
MATCH (doc:__Document__)
OPTIONAL MATCH (doc)<-[:__CHUNK_TO_DOCUMENT__]-(c:__Chunk__)
OPTIONAL MATCH (c)<-[:__NODE_TO_CHUNK__]-(e:__Entity__)
RETURN doc.path                       AS document_path,
       count(DISTINCT c)              AS chunks,
       count(DISTINCT e)              AS entities
ORDER BY document_path;


// ------------------------------------------------------------
//  2. Domain label counts
//     How many entities of each clinical domain label were extracted.
//     The pilot model (MODEL.md) targets six labels: Biomarker, LabResult,
//     Condition, Medication, Provider, ClinicalEvent.
//     (Adjust the list if you renamed/added labels in the DI model editor.)
// ------------------------------------------------------------
// 2a. Generic: every label carried by extracted entities, with counts.
//     This works no matter what you named the labels in the model.
MATCH (e:__Entity__)
UNWIND labels(e) AS lbl
WITH lbl, count(*) AS n
WHERE lbl <> '__Entity__'
RETURN lbl AS domain_label, n AS entity_count
ORDER BY entity_count DESC, domain_label;

// 2b. Explicit per-domain counts for the pilot's six target labels.
//     0 for a label simply means the model didn't extract that type
//     from these 4 docs — not an error.
RETURN
  size([(n:Biomarker)     | n]) AS Biomarker,
  size([(n:LabResult)     | n]) AS LabResult,
  size([(n:Condition)     | n]) AS Condition,
  size([(n:Medication)    | n]) AS Medication,
  size([(n:Provider)      | n]) AS Provider,
  size([(n:ClinicalEvent) | n]) AS ClinicalEvent;


// ------------------------------------------------------------
//  3. How many extracted clinical entities linked to a :Day
//     link_clinical_to_days.cypher creates (clinical)-[:ON_DAY]->(:Day)
//     wherever a document states a date that matches an existing Day.
//     "linked_ratio" tells you the temporal-join coverage of the pilot.
// ------------------------------------------------------------
MATCH (e:__Entity__)
WITH count(e) AS total_entities,
     count(e) - count { (e)-[:ON_DAY]->(:Day) } AS unlinked
WITH total_entities, total_entities - unlinked AS linked
RETURN total_entities,
       linked                                        AS linked_to_day,
       total_entities - linked                       AS not_linked,
       CASE WHEN total_entities = 0 THEN 0.0
            ELSE round(100.0 * linked / total_entities, 1)
       END                                           AS linked_pct;

// 3b. Which Days received clinical links, and how many entities each got.
MATCH (e:__Entity__)-[:ON_DAY]->(d:Day)
RETURN d.date AS day, count(e) AS clinical_entities,
       collect(DISTINCT [l IN labels(e) WHERE l <> '__Entity__'][0]) AS kinds
ORDER BY day;


// ------------------------------------------------------------
//  4. Sample provenance traversal:
//     extracted entity -> __Chunk__ -> __Document__ path.
//     This is the "where did this clinical value come from?" trace
//     the Aura Agent is instructed to cite. Every clinical value the
//     agent reports must be groundable back to a __Document__.path here.
// ------------------------------------------------------------
MATCH (e:__Entity__)-[:__NODE_TO_CHUNK__]->(c:__Chunk__)-[:__CHUNK_TO_DOCUMENT__]->(doc:__Document__)
RETURN
  [l IN labels(e) WHERE l <> '__Entity__'][0]       AS entity_label,
  coalesce(e.name, e.key, e.id, elementId(e))       AS entity,
  e.key                                             AS dedup_key,
  doc.path                                          AS source_document,
  left(coalesce(c.text, ''), 160)                   AS chunk_excerpt
ORDER BY source_document, entity_label
LIMIT 25;


// ------------------------------------------------------------
//  5. HYBRID query — the payoff of the pilot.
//     Join a clinical finding to that same day's structured
//     DailySummary metrics, with the source document for grounding.
//     This is the kind of question the structured-only graph could
//     NOT answer before DI (issue #10: "weeks with elevated RHR AND
//     a clinical note mentioning illness").
// ------------------------------------------------------------
// 5a. Every clinical finding next to its day's RHR / HRV / sleep,
//     plus the source document path for citation.
MATCH (e:__Entity__)-[:ON_DAY]->(d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
OPTIONAL MATCH (e)-[:__NODE_TO_CHUNK__]->(:__Chunk__)-[:__CHUNK_TO_DOCUMENT__]->(doc:__Document__)
RETURN d.date                                       AS day,
       [l IN labels(e) WHERE l <> '__Entity__'][0]  AS finding_type,
       coalesce(e.name, e.key)                      AS finding,
       coalesce(e.value, e.result, e.status)        AS value,
       round(s.resting_heart_rate)                  AS RHR,
       round(s.hrv_mean * 10) / 10.0                AS HRV,
       round(s.sleep_hours * 10) / 10.0             AS sleep_h,
       doc.path                                     AS source_document
ORDER BY day;

// 5b. Hybrid signal example: clinical findings landing on (or within 2
//     days of) a structurally "off" day — RHR above 65 OR HRV below 30.
//     Demonstrates correlating a document-derived finding with the
//     wearable time-series around the same date.
MATCH (e:__Entity__)-[:ON_DAY]->(cd:Day)
MATCH (s:DailySummary)
WHERE s.date >= cd.date - duration({days: 2})
  AND s.date <= cd.date + duration({days: 2})
  AND s.resting_heart_rate IS NOT NULL
  AND (s.resting_heart_rate > 65 OR s.hrv_mean < 30)
OPTIONAL MATCH (e)-[:__NODE_TO_CHUNK__]->(:__Chunk__)-[:__CHUNK_TO_DOCUMENT__]->(doc:__Document__)
RETURN cd.date                                      AS clinical_day,
       [l IN labels(e) WHERE l <> '__Entity__'][0]  AS finding_type,
       coalesce(e.name, e.key)                      AS finding,
       s.date                                       AS metric_day,
       round(s.resting_heart_rate)                  AS RHR,
       round(s.hrv_mean * 10) / 10.0                AS HRV,
       doc.path                                     AS source_document
ORDER BY clinical_day, metric_day;
