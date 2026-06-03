# ReviewGraph demo — intentionally risky PR

This branch exists **only** to demonstrate [ReviewGraph AI](https://github.com/ma3u/healthgraph-agent) risk assessment. **Do not merge to `main`.**

## What ReviewGraph should flag

| Signal | File(s) |
| --- | --- |
| Security-sensitive paths | `etl/load_to_neo4j.py`, `agents/unsafe_auth_demo.py` |
| Hardcoded secrets / weak auth | `agents/unsafe_auth_demo.py` |
| Architecture violation (ETL → iOS) | `etl/quick_ios_bridge.py` + `docs/reviewgraph-config.json` |
| AI-assisted change | PR title/body mentions Copilot / AI-generated |

## After opening the PR

1. In ReviewGraph AI `.env`: `GITHUB_REPO=ma3u/healthgraph-agent`
2. `POST http://127.0.0.1:4000/api/reload` or restart `npm run dev`
3. Select the new PR → **Risk Assessment** → **Ask the Graph** (*Why is this PR risky?*)

Delete this branch after the demo.
