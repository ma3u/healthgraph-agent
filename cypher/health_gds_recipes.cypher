// ============================================================
//  Graph Data Science recipes for HealthGraph (5 analytics).
//
//  Run these from an Aura Graph Analytics SESSION (not the main
//  Aura instance — sessions are billed per-minute).
//
//  Workflow per recipe:
//    1. Project an in-memory graph with gds.graph.project.cypher
//       (or gds.graph.project) from your :DailySummary / :Workout nodes
//    2. Run the algorithm
//    3. Stream results back, or write to the live graph
//    4. Drop the projection: CALL gds.graph.drop(...)
//
//  Replace `myGraph` per recipe — projections are session-scoped.
// ============================================================


// =====================================================
//  Q11: Personal training zones — GDS K-Means
//  Cluster each workout on (duration, intensity, avg_HR) → discover
//  your natural 4-5 training zones (Z2/Z3/Z4/HIIT-style).
// =====================================================

// Step 1 — project a workout-node graph (no relationships needed for K-Means).
CALL gds.graph.project.cypher(
  'workouts',
  'MATCH (w:Workout)-[:ON_DAY]->(d:Day)-[:HAS_SUMMARY]->(s:DailySummary)
   WHERE w.duration_min IS NOT NULL
     AND s.avg_heart_rate IS NOT NULL
     AND s.active_energy_kcal IS NOT NULL
     AND s.workout_minutes IS NOT NULL AND s.workout_minutes > 0
   RETURN id(w) AS id,
          [w.duration_min,
           s.avg_heart_rate,
           s.active_energy_kcal / s.workout_minutes] AS features',
  'MATCH (w:Workout)-[:ON_DAY]->(d)
   RETURN id(w) AS source, id(w) AS target  // dummy self-loop, K-Means needs no edges'
);

// Step 2 — run K-Means with k=5.
CALL gds.kmeans.stream('workouts', {nodeProperty: 'features', k: 5})
YIELD nodeId, communityId, distanceFromCentroid
MATCH (w) WHERE id(w) = nodeId
RETURN communityId AS zone,
       w.activity_type AS activity,
       count(*) AS workouts,
       round(avg(w.duration_min)) AS `Avg duration (min)`,
       round(avg(distanceFromCentroid)*100)/100.0 AS `Avg distance`
ORDER BY zone, workouts DESC;

CALL gds.graph.drop('workouts');


// =====================================================
//  Q12: Day-similarity via K-NN
//  Embed each day on (HRV, RHR, sleep, steps, energy), find the 5
//  most similar past days. Useful as "Given today's stress profile,
//  what days felt like this — and how did they end?"
// =====================================================

CALL gds.graph.project.cypher(
  'days',
  'MATCH (s:DailySummary)
   WHERE s.hrv_mean IS NOT NULL AND s.resting_heart_rate IS NOT NULL
     AND s.sleep_hours IS NOT NULL AND s.total_steps IS NOT NULL
     AND s.active_energy_kcal IS NOT NULL
   RETURN id(s) AS id,
          [s.hrv_mean, s.resting_heart_rate, s.sleep_hours,
           s.total_steps*1.0, s.active_energy_kcal] AS features',
  'MATCH (s:DailySummary)
   RETURN id(s) AS source, id(s) AS target  // dummy self-loop'
);

CALL gds.knn.stream('days', {
  nodeProperties: ['features'],
  topK: 5,
  similarityCutoff: 0.7,
  sampleRate: 1.0
})
YIELD node1, node2, similarity
MATCH (a:DailySummary) WHERE id(a) = node1
MATCH (b:DailySummary) WHERE id(b) = node2
RETURN a.date AS day, b.date AS similar_day,
       round(similarity*1000)/1000.0 AS similarity
ORDER BY day DESC, similarity DESC
LIMIT 50;

CALL gds.graph.drop('days');


// =====================================================
//  Q13: Recovery regime clusters — Louvain on day-similarity
//  First create KNN edges between days, then run Louvain on that graph.
//  Communities = "regimes" — e.g. Build / Peak / Sick / Recovery — discovered
//  from your actual data without you labeling anything.
// =====================================================

// Step 1: project days with metric vector
CALL gds.graph.project.cypher(
  'daysForRegimes',
  'MATCH (s:DailySummary)
   WHERE s.hrv_mean IS NOT NULL AND s.resting_heart_rate IS NOT NULL
     AND s.sleep_hours IS NOT NULL
   RETURN id(s) AS id,
          [s.hrv_mean, s.resting_heart_rate, s.sleep_hours] AS feats',
  'MATCH (s:DailySummary) RETURN id(s) AS source, id(s) AS target'
);

// Step 2: write KNN edges to the projection
CALL gds.knn.write('daysForRegimes', {
  nodeProperties: ['feats'],
  topK: 8,
  writeRelationshipType: 'SIMILAR_DAY',
  writeProperty: 'similarity'
});

// Step 3: run Louvain on SIMILAR_DAY relationships
CALL gds.louvain.stream('daysForRegimes', {
  relationshipTypes: ['SIMILAR_DAY'],
  relationshipWeightProperty: 'similarity'
})
YIELD nodeId, communityId
MATCH (s:DailySummary) WHERE id(s) = nodeId
WITH communityId, collect(s) AS days
WHERE size(days) >= 10
RETURN communityId AS regime,
       size(days) AS days,
       round(avg([d IN days | d.hrv_mean])*10)/10.0 AS `Avg HRV`,
       round(avg([d IN days | d.resting_heart_rate])*10)/10.0 AS `Avg RHR`,
       round(avg([d IN days | d.sleep_hours])*10)/10.0 AS `Avg sleep`
ORDER BY regime;

CALL gds.graph.drop('daysForRegimes');


// =====================================================
//  Q14: Activity-type centrality — PageRank
//  Build a graph of Activity → Day → Activity (workouts on the same day).
//  PageRank reveals which activity types are most structurally central
//  to your training graph.
// =====================================================

CALL gds.graph.project.cypher(
  'activityNet',
  'MATCH (w:Workout) RETURN DISTINCT w.activity_type AS id',
  'MATCH (w1:Workout)-[:ON_DAY]->(d:Day)<-[:ON_DAY]-(w2:Workout)
   WHERE w1.activity_type <> w2.activity_type
   RETURN w1.activity_type AS source, w2.activity_type AS target, count(*) AS weight'
);

CALL gds.pageRank.stream('activityNet', {
  relationshipWeightProperty: 'weight',
  maxIterations: 20
})
YIELD nodeId, score
RETURN gds.util.asNode(nodeId) AS activity,
       round(score*1000)/1000.0 AS pageRank
ORDER BY pageRank DESC;

CALL gds.graph.drop('activityNet');


// =====================================================
//  Q15: Bridge events — Betweenness centrality
//  After Q13 generates regime clusters, betweenness on the day-graph
//  identifies the specific days that lie on shortest paths between
//  regimes — i.e. events that tipped you from "good" to "bad" or vice versa.
// =====================================================

// (Run after Q13 has tagged days with their community)
CALL gds.graph.project.cypher(
  'dayChain',
  'MATCH (s:DailySummary) RETURN id(s) AS id',
  'MATCH (a:DailySummary), (b:DailySummary)
   WHERE b.date = a.date + duration({days:1})
   RETURN id(a) AS source, id(b) AS target'
);

CALL gds.betweenness.stream('dayChain')
YIELD nodeId, score
MATCH (s:DailySummary) WHERE id(s) = nodeId
RETURN s.date AS date,
       round(score*100)/100.0 AS betweenness,
       round(s.hrv_mean*10)/10.0 AS `HRV`,
       round(s.resting_heart_rate) AS `RHR`
ORDER BY betweenness DESC LIMIT 20;

CALL gds.graph.drop('dayChain');


// =====================================================
//  Q20: Predict tomorrow's recovery — Node Regression
//  Train a logistic-regression model on historical days to predict
//  the next day's recovery zone (Green/Yellow/Red).
//  Features: HRV, RHR, sleep, prev day's strain.
// =====================================================

// Step 1: tag each day with its computed Recovery % (from Whoop scoring)
//   In practice: write a property `recovery` onto each :DailySummary via
//   cypher/whoop_queries.cypher → Q-RECOVERY-TREND result.
//   Then bucket into 1/2/3 (Green/Yellow/Red) for classification.

// Step 2: project graph
CALL gds.graph.project(
  'recoveryGraph',
  'DailySummary',
  '*',
  {nodeProperties: ['hrv_mean', 'resting_heart_rate', 'sleep_hours', 'recovery_class']}
);

// Step 3: create the pipeline
CALL gds.beta.pipeline.nodeClassification.create('recoveryPipeline');
CALL gds.beta.pipeline.nodeClassification.addNodeProperty('recoveryPipeline', 'scaleProperties', {
  nodeProperties: ['hrv_mean', 'resting_heart_rate', 'sleep_hours'],
  scaler: 'L1NORM', mutateProperty: 'scaled'
});
CALL gds.beta.pipeline.nodeClassification.selectFeatures('recoveryPipeline', ['scaled']);
CALL gds.beta.pipeline.nodeClassification.configureSplit('recoveryPipeline', {
  testFraction: 0.2, validationFolds: 5
});
CALL gds.beta.pipeline.nodeClassification.addLogisticRegression('recoveryPipeline');

// Step 4: train
CALL gds.beta.pipeline.nodeClassification.train('recoveryGraph', {
  pipeline: 'recoveryPipeline',
  modelName: 'recoveryModel',
  targetProperty: 'recovery_class',
  metrics: ['F1_WEIGHTED']
}) YIELD modelInfo
RETURN modelInfo.metrics AS metrics;

// Step 5: predict on all days
CALL gds.beta.pipeline.nodeClassification.predict.stream('recoveryGraph', {
  modelName: 'recoveryModel'
}) YIELD nodeId, predictedClass, predictedProbabilities
MATCH (s:DailySummary) WHERE id(s) = nodeId
RETURN s.date AS date,
       predictedClass AS predicted_zone,
       predictedProbabilities AS probabilities
ORDER BY date DESC LIMIT 30;

CALL gds.graph.drop('recoveryGraph');
CALL gds.beta.pipeline.drop('recoveryPipeline');
CALL gds.beta.model.drop('recoveryModel');
