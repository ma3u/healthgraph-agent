#!/usr/bin/env python3
"""Reconcile the Aura Agent defined in agents/healthgraph-coach.json with the
live tenant. Uses the v2beta1 Aura platform API (per Ed Sandoval's tip — see
issue #6 and https://neo4j.com/docs/aura/platform/api/specification/?urls.primaryName=Aura%20v2beta1).

Requires .env values: AURA_CLIENT_ID, AURA_CLIENT_SECRET.

Modes (default = report-only, no mutations):

  python scripts/create_aura_agent.py                  # status: live vs file
  python scripts/create_aura_agent.py --pull           # live → file
  python scripts/create_aura_agent.py --push           # file → live (PUT or POST)

Always appends AURA_AGENT_URL / AURA_AGENT_TOKEN_URL / AURA_AGENT_CLIENT_ID /
AURA_AGENT_CLIENT_SECRET to .env if the agent exists, so scripts/build_ios.sh
can patch the iOS app's "Ask your graph" panel.

Run:
  /tmp/aura-venv/bin/python scripts/create_aura_agent.py
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent
load_dotenv(REPO / ".env")

AGENT_FILE = REPO / "agents" / "healthgraph-coach.json"
API_ROOT = "https://api.neo4j.io/v2beta1"
TOKEN_URL = "https://api.neo4j.io/oauth/token"
ALLOWED_FIELDS = {
    "name", "description", "system_prompt", "dbid",
    "is_private", "is_mcp_enabled", "tools", "enabled",
}


def get_token() -> str:
    cid = os.environ["AURA_CLIENT_ID"]
    csec = os.environ["AURA_CLIENT_SECRET"]
    creds = base64.b64encode(f"{cid}:{csec}".encode()).decode()
    req = Request(
        TOKEN_URL,
        data=b"grant_type=client_credentials",
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    return json.loads(urlopen(req).read())["access_token"]


def api(method: str, path: str, token: str, body: dict | None = None) -> tuple[int, dict | list | str]:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = Request(f"{API_ROOT}{path}", method=method, headers=headers, data=data)
    try:
        with urlopen(req) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else {}
    except HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw


def discover_scope(token: str) -> tuple[str, str]:
    code, orgs = api("GET", "/organizations", token)
    if code != 200 or not isinstance(orgs, dict):
        sys.exit(f"GET /organizations → {code} {orgs}")
    org_list = orgs.get("data", [])
    if not org_list:
        sys.exit("No organizations on this account.")
    org_id = org_list[0]["id"]

    code, projs = api("GET", f"/organizations/{org_id}/projects", token)
    if code != 200 or not isinstance(projs, dict):
        sys.exit(f"GET projects → {code} {projs}")
    proj_list = projs.get("data", [])
    if not proj_list:
        sys.exit("No projects in the organization.")
    return org_id, proj_list[0]["id"]


def find_agent(token: str, org: str, proj: str, name: str) -> dict | None:
    code, body = api("GET", f"/organizations/{org}/projects/{proj}/agents", token)
    if code != 200:
        sys.exit(f"GET agents → {code} {body}")
    if isinstance(body, list):
        agents = body
    elif isinstance(body, dict):
        agents = body.get("data", [])
    else:
        sys.exit(f"Unexpected agents response: {body!r}")
    for a in agents:
        if a.get("name") == name:
            return a
    return None


def strip_server_fields(agent: dict) -> dict:
    return {k: v for k, v in agent.items() if k in ALLOWED_FIELDS}


def append_env(endpoint: str) -> None:
    env_path = REPO / ".env"
    text = env_path.read_text() if env_path.exists() else ""
    if "AURA_AGENT_URL=" in text:
        print("  (.env already has AURA_AGENT_URL — not overwriting; edit by hand if it's wrong)")
        return
    with env_path.open("a") as f:
        f.write("\n# Aura Agent (created by scripts/create_aura_agent.py)\n")
        f.write(f"AURA_AGENT_URL={endpoint}\n")
        f.write(f"AURA_AGENT_TOKEN_URL={TOKEN_URL}\n")
        f.write(f"AURA_AGENT_CLIENT_ID={os.environ['AURA_CLIENT_ID']}\n")
        f.write(f"AURA_AGENT_CLIENT_SECRET={os.environ['AURA_CLIENT_SECRET']}\n")
    print(f"  appended AURA_AGENT_* to {env_path}")


def load_local() -> dict:
    if not AGENT_FILE.exists():
        sys.exit(f"Agent JSON not found at {AGENT_FILE}")
    return json.loads(AGENT_FILE.read_text())


def cmd_status(token: str, org: str, proj: str, local: dict) -> int:
    agent = find_agent(token, org, proj, local["name"])
    if not agent:
        print(f"NOT FOUND on live: agent named '{local['name']}'")
        print("Run with --push to create it from agents/healthgraph-coach.json.")
        return 1
    print(f"FOUND on live: id={agent['id']}  name={agent['name']!r}  enabled={agent.get('enabled')}")
    print(f"  endpoint: {agent.get('endpoint_link')}")
    live = strip_server_fields(agent)
    # Re-fetch full agent (list endpoint may return summaries without tool config)
    code, full = api(
        "GET", f"/organizations/{org}/projects/{proj}/agents/{agent['id']}", token
    )
    if code == 200 and isinstance(full, dict):
        live = strip_server_fields(full)
    diff = {k for k in ALLOWED_FIELDS if local.get(k) != live.get(k)}
    if diff:
        print(f"  DIFFERS from {AGENT_FILE.name} in: {sorted(diff)}")
        print("  Run --push to overwrite live with file, or --pull to overwrite file with live.")
    else:
        print(f"  IN SYNC with {AGENT_FILE.name}")
    append_env(agent["endpoint_link"])
    return 0


def cmd_pull(token: str, org: str, proj: str, local: dict) -> int:
    agent = find_agent(token, org, proj, local["name"])
    if not agent:
        sys.exit(f"No live agent named '{local['name']}' to pull from.")
    code, full = api(
        "GET", f"/organizations/{org}/projects/{proj}/agents/{agent['id']}", token
    )
    if code != 200 or not isinstance(full, dict):
        sys.exit(f"GET agent → {code} {full}")
    clean = strip_server_fields(full)
    AGENT_FILE.write_text(json.dumps(clean, indent=2, sort_keys=True) + "\n")
    print(f"Wrote live agent to {AGENT_FILE}")
    return 0


def cmd_push(token: str, org: str, proj: str, local: dict) -> int:
    missing = [f for f in ("name", "description", "dbid", "is_private", "tools") if f not in local]
    if missing:
        sys.exit(f"Agent JSON missing required fields: {missing}")

    agent = find_agent(token, org, proj, local["name"])
    if agent is None:
        print(f"Creating agent '{local['name']}'…")
        code, resp = api(
            "POST", f"/organizations/{org}/projects/{proj}/agents", token, body=local
        )
        if code != 201 or not isinstance(resp, dict):
            sys.exit(f"POST agent → {code} {json.dumps(resp, indent=2)}")
        print(f"  created: id={resp['id']}")
        print(f"  endpoint: {resp.get('endpoint_link')}")
        append_env(resp["endpoint_link"])
        return 0

    print(f"Updating agent {agent['id']} (PUT)…")
    code, resp = api(
        "PUT",
        f"/organizations/{org}/projects/{proj}/agents/{agent['id']}",
        token,
        body=local,
    )
    if code != 200 or not isinstance(resp, dict):
        sys.exit(f"PUT agent → {code} {json.dumps(resp, indent=2)}")
    print(f"  endpoint: {resp.get('endpoint_link')}")
    append_env(resp["endpoint_link"])
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--pull", action="store_true", help="Overwrite local JSON with live agent")
    g.add_argument("--push", action="store_true", help="POST/PUT local JSON to live")
    args = p.parse_args()

    local = load_local()
    token = get_token()
    org, proj = discover_scope(token)
    print(f"org={org}  project={proj}")

    if args.pull:
        return cmd_pull(token, org, proj, local)
    if args.push:
        return cmd_push(token, org, proj, local)
    return cmd_status(token, org, proj, local)


if __name__ == "__main__":
    sys.exit(main())
