# Cypher + GraphQL files

| File | Purpose |
| --- | --- |
| [`graphql_schema.graphql`](graphql_schema.graphql) | **The thing to paste** into Aura Console → GraphQL Data APIs → *Create → Define my own*. Defines the read schema (Day, Workout, etc.) and three `@cypher` MERGE mutations (`ingestDay`, `ingestWorkout`, `ingestSleep`) the iOS app calls. |
| [`longevity_queries.cypher`](longevity_queries.cypher) | 20 hand-curated Cypher queries powering the longevity analysis. Used directly by the NeoDash dashboard. |
| [`health_analytics.cypher`](health_analytics.cypher) | Extra analytics queries beyond the longevity set. |
| [`health_gds_recipes.cypher`](health_gds_recipes.cypher) | Graph Data Science recipes — community detection on similar-day clusters, PageRank-style metric importance. |
| [`whoop_queries.cypher`](whoop_queries.cypher) | Cypher patterns specific to the Whoop data overlay. |
| [`load_csv_import.cypher`](load_csv_import.cypher) | Pure Cypher fallback for users who prefer `LOAD CSV` over the Python ETL. |

## Deploying the GraphQL schema to Aura

The full setup is documented in [`../docs/AUTH_SETUP.md`](../docs/AUTH_SETUP.md).
TL;DR:

1. Aura Console → your instance → **GraphQL Data APIs** sidebar item.
2. **Create** → **Define my own** → paste the contents of `graphql_schema.graphql`.
3. Give the API a name (e.g. *HealthGraph*) and copy the endpoint URL it produces.
4. Add a JWKS auth provider pointing at your Auth0 tenant's
   `https://YOUR_TENANT.us.auth0.com/.well-known/jwks.json`.

## Validating the mutations *before* you deploy

Before pasting into Aura, you can sanity-check the `@cypher` bodies against
your existing Aura instance via Bolt — they're the same Cypher that will run
once the GraphQL Data API parses them:

```sh
archive/backend-legacy/.venv/bin/python scripts/test_aura_mutations.py
```

Expected: ✅ all three mutations succeed, idempotency verified, cleanup
leaves baseline counts unchanged. See
[`../docs/IOS_PLAN.md`](../docs/IOS_PLAN.md) §1.1.
