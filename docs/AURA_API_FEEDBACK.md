# Feedback for Neo4j Aura Platform team

Filed as part of building the [Apple HealthGraph Agent](../README.md) for the Aura Agent Hackathon. The data layer (instance management, ETL) was a smooth API-first experience. The two new managed surfaces — **Dashboards** and **Agents** — are not.

## File these

### 1. GitHub issue — `neo4j/aura-cli`

**Where to file:** https://github.com/neo4j/aura-cli/issues/new

**Title:** *Add `dashboard` and `agent` subcommands so we can automate Aura's new managed tools*

**Body:**

```markdown
## Context

I built a hackathon entry (Apple HealthGraph Agent) and wanted my whole
pipeline reproducible from `bash scripts/run.sh`:

1. Create AuraDB instance         → `aura-cli instance create`     ✅
2. Snapshot / restore             → `aura-cli instance snapshot`   ✅
3. Manage tenant / data API       → `aura-cli tenant/dataapi`      ✅
4. Create dashboard from JSON     → ?
5. Create agent + attach tools    → ?

Steps 4 and 5 have no CLI or public-API path today. The CLI's
`subcommands/` tree (verified at HEAD) is:

    agent  config  credential  customermanagedkey  dataapi
    deployment  graphanalytics  import  instance  tenant  utils

`agent` exists but only for managing one of the older agent concepts (per
the README example), not the new in-console **Aura Agents** with tools
and chat. There is no `dashboard` subcommand at all.

The public REST API (`api.neo4j.io/v1/*`) returns 403 for every
dashboard- or agent-related path I could think of. Only `/v1/instances`
and `/v1/tenants` are routed.

Meanwhile the Console UI talks to its own undocumented internal API at
`https://console.neo4j.io/api/shared-storage/v1/dashboards/dashboards`
which **does** support the full CRUD I'd want (POST dashboard, POST
pages, POST widgets, PATCH, DELETE). That API only trusts user-session
OIDC tokens from `login.neo4j.com` — service-account tokens from
`api.neo4j.io/oauth/token` are rejected with `"token-invalid"` even
though both have `aud=https://console.neo4j.io`.

## Why this matters

Hackathon participants and anyone shipping a reproducible Aura demo need
to bootstrap the same dashboard / agent setup on every fresh tenant.
Right now we either:

- Click through the UI on every demo (not reproducible)
- Reverse-engineer the console JS bundle to call the undocumented API
  with a browser-grabbed bearer token that rotates every 15 min
  (what I ended up doing — see [my upload script](https://github.com/ma3u/healthgraph-agent/blob/main/scripts/upload_aura_dashboard.py))
- Skip the new tools and fall back to legacy NeoDash (we did this too —
  it has the public `_Neodash_Dashboard` node-label storage that works
  fine from `cypher-shell`)

## Asks

1. **Dashboard CRUD via Aura API or aura-cli** — accept the same JSON
   that `Tools → Dashboards → Export` produces, plus support the
   convert-from-NeoDash flow that the UI already implements.
2. **Agent CRUD via Aura API or aura-cli** — at minimum: create agent,
   attach Text2Cypher / Similarity / custom tools, set system prompt.
3. **Document the schema** for either route (Aura's dashboard JSON
   format is not in the public docs — I had to reverse-engineer it from
   `neo4j-product-examples/sample-applications/.../*.dashboard.json`
   to know that `widgets` replaces NeoDash's `reports` etc.).

Happy to share my conversion script and the reverse-engineered request
shapes if useful.
```

### 2. LinkedIn comment for Ari Waller

**Original post:** Ari's hackathon update — https://www.linkedin.com/posts/ari-waller... (the post that listed Apple HealthGraph Agent among submissions)

**Reply draft (≤ 1200 chars to keep it readable on mobile):**

```
Hey Ari — glad HealthGraph made the list! Quick piece of feedback from
building it:

The data-layer Aura API and `aura-cli` were great — `aura-cli instance
create` to dataapi setup, all reproducible.

What blocked me from making my hackathon entry fully one-command-deploy
was the lack of a public API or CLI for the *new* console tools:

• Dashboards — no `aura dashboard *` command and no `/v1/dashboards`
  on api.neo4j.io. Ended up scripting against the undocumented
  /api/shared-storage endpoint with a browser-grabbed user token that
  rotates every 15 min. Works but isn't something I can ship in a
  hackathon README.

• Aura Agents — same gap. The Text2Cypher setup has to be done in the
  Console UI for every new tenant; can't be checked into git.

If service-account access to those endpoints landed in the public Aura
API (or `aura-cli`), hackathon entries — and prod deployments of
graph-powered apps — get fully reproducible. Right now we have to
choose between “use the shiny new tools and click-through every demo”
or “stay on legacy NeoDash for reproducibility.” Both are wins for
Neo4j as a platform, neither for the dev experience.

Filed a more detailed ask at github.com/neo4j/aura-cli/issues. Happy
to demo the reverse-engineered workflow if helpful.
```

---

## Why this is filed in our repo

Keeping the feedback artifact in this repo so:
- It's traceable to the actual reproducer (the Whoop dashboard upload script)
- If/when Neo4j responds, we can mark resolved and update DASHBOARD.md Path B
- Other hackathon participants who hit the same wall can fork the upload script + the prose
