# ReviewGraph AI integration

**ReviewGraph AI** (Aura-powered code review graph — companion hackathon project) can **review this repository** using a code intelligence graph + hosted **Aura Agent**.

## What ReviewGraph adds

| Layer | HealthGraph Agent | ReviewGraph AI |
| --- | --- | --- |
| Data | Apple Health → Neo4j (`Day`, `Workout`, …) | GitHub PRs → review graph (`PullRequest`, `File`, …) |
| Ask | Aura Coach (longevity Text2Cypher) | Aura Agent (PR risk, reviewers, architecture) |
| UI | iOS HealthGraphSync + NeoDash | React app — Assessment + Ask the Graph |

Same Neo4j Aura instance can hold **both** graphs (different node labels).

## Try it on this repo

1. Clone ReviewGraph AI and configure `.env`:

   ```env
   GITHUB_REPO=ma3u/healthgraph-agent
   GITHUB_TOKEN=ghp_...          # optional for public read; required to open PRs
   NEO4J_URI=neo4j+s://...
   NEO4J_USER=...
   NEO4J_PASSWORD=...
   AURA_CLIENT_ID=...
   AURA_CLIENT_SECRET=...
   AURA_AGENT_INVOKE_URL=...
   ```

2. `npm run dev` → sidebar lists pull requests from this repo.

3. Select a PR → **Ask the Graph** → e.g. *Why is this PR risky?*

4. Rules for this repo: `.reviewgraph.json` (sensitive paths: `ios/`, `etl/`).

## Windows ETL note

Synthetic `export.xml` from `generate_test_data.py` may include a DTD and `device="<<HKDevice…"` attributes that break `lxml` on Windows. Use:

```bash
python scripts/prepare_export_windows.py data/export.xml data/export.clean.xml
python etl/load_to_neo4j.py data/export.clean.xml
```

## Demo PR (this branch)

Adds:

- `.reviewgraph.json` — ReviewGraph architecture hints
- `scripts/prepare_export_windows.py` — Windows-friendly XML prep before ETL load
- This document

Open a PR from branch `feature/reviewgraph-ai-demo` to see ReviewGraph ingest the change set.
