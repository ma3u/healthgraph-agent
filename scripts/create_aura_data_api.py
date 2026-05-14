#!/usr/bin/env python3
"""Create a GraphQL Data API on the Aura instance using the curated SDL.

Uses the v1beta5 Aura Management REST API. The aura-cli v1.8.0 does NOT yet
expose data-api commands (only the deprecated Python aura-cli mentions them,
and even there they don't work) — so we hit the REST endpoint directly.

Requires .env values: AURA_CLIENT_ID, AURA_CLIENT_SECRET, AURA_INSTANCEID,
NEO4J_PASSWORD.

Idempotent-ish: lists existing Data APIs first; if one named "HealthGraph"
already exists, prints its URL and exits without re-creating.

Output: appends AURA_GRAPHQL_DATA_API_ID, AURA_GRAPHQL_URL, and
AURA_GRAPHQL_API_KEY to .env. The API key is shown ONCE — save it now or
generate a new one via the console.

Run:
  /tmp/aura-venv/bin/python scripts/create_aura_data_api.py
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent
load_dotenv(REPO / ".env")

INSTANCE_ID = os.environ.get("AURA_INSTANCEID") or sys.exit("AURA_INSTANCEID not set")
API_BASE = f"https://api.neo4j.io/v1beta5/instances/{INSTANCE_ID}/data-apis/graphql"
SDL_PATH = REPO / "cypher" / "graphql_schema.graphql"
DATA_API_NAME = "HealthGraph"
MEMORY = "512MB"


def get_token() -> str:
    cid = os.environ["AURA_CLIENT_ID"]
    csec = os.environ["AURA_CLIENT_SECRET"]
    creds = base64.b64encode(f"{cid}:{csec}".encode()).decode()
    req = Request(
        "https://api.neo4j.io/oauth/token",
        data=b"grant_type=client_credentials",
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    return json.loads(urlopen(req).read())["access_token"]


def api_request(method: str, url: str, token: str, body: dict | None = None) -> tuple[int, dict]:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = Request(url, method=method, headers=headers, data=data)
    try:
        with urlopen(req) as r:
            return r.status, json.loads(r.read())
    except HTTPError as e:
        return e.code, json.loads(e.read())


def find_existing(token: str) -> dict | None:
    code, body = api_request("GET", API_BASE, token)
    if code != 200:
        sys.exit(f"GET {API_BASE} → {code} {body}")
    for api in body.get("data", []):
        if api.get("name") == DATA_API_NAME:
            return api
    return None


def create(token: str) -> dict:
    sdl_b64 = base64.b64encode(SDL_PATH.read_bytes()).decode()
    body = {
        "name": DATA_API_NAME,
        "type_definitions": sdl_b64,
        "security": {
            "authentication_providers": [
                {"name": "API key", "type": "api-key", "enabled": True}
            ]
        },
        "aura_instance": {
            "username": "neo4j",
            "password": os.environ["NEO4J_PASSWORD"],
        },
        "memory": MEMORY,
    }
    code, resp = api_request("POST", API_BASE, token, body)
    if code != 202:
        sys.exit(f"POST {API_BASE} → {code} {json.dumps(resp, indent=2)}")
    return resp["data"]


def poll_ready(token: str, api_id: str, max_wait_secs: int = 240) -> dict:
    url = f"{API_BASE}/{api_id}"
    for _ in range(max_wait_secs // 5):
        code, resp = api_request("GET", url, token)
        status = resp.get("data", {}).get("status")
        print(f"  status={status}")
        if status == "ready":
            return resp["data"]
        time.sleep(5)
    sys.exit("Data API did not reach ready in time")


def append_to_env(api: dict) -> None:
    env_path = REPO / ".env"
    existing = env_path.read_text()
    if "AURA_GRAPHQL_DATA_API_ID" in existing:
        print("  (.env already has AURA_GRAPHQL_* — not overwriting)")
        return
    api_key = ""
    for p in api.get("authentication_providers", []):
        if p.get("type") == "api-key":
            api_key = p.get("key", "")
            break
    with env_path.open("a") as f:
        f.write("\n# Aura GraphQL Data API (created by scripts/create_aura_data_api.py)\n")
        f.write(f"AURA_GRAPHQL_DATA_API_ID={api['id']}\n")
        f.write(f"AURA_GRAPHQL_URL={api['url']}\n")
        if api_key:
            f.write(f"AURA_GRAPHQL_API_KEY={api_key}\n")
    print(f"  appended to {env_path}")


def main() -> int:
    if not SDL_PATH.exists():
        sys.exit(f"SDL not found at {SDL_PATH}")
    print(f"Instance: {INSTANCE_ID}")

    token = get_token()
    existing = find_existing(token)
    if existing:
        print(f"Already exists — id={existing['id']}, url={existing['url']}")
        print("To create a fresh one, delete the existing API in the console first.")
        return 0

    print(f"Creating Data API '{DATA_API_NAME}'…")
    created = create(token)
    print(f"  id={created['id']}  status={created['status']}")
    api_key_provider = next(
        (p for p in created["authentication_providers"] if p["type"] == "api-key"),
        None,
    )
    if api_key_provider:
        print(f"  API key (save now, shown once): {api_key_provider['key']}")

    print("\nPolling for ready…")
    ready = poll_ready(token, created["id"])
    print(f"\nReady. URL: {ready['url']}")

    # Re-fetch the key — it's only on the creation response, so use that
    ready["authentication_providers"] = created["authentication_providers"]
    append_to_env(ready)

    print("\nSmoke test:")
    print(f"  curl -X POST '{ready['url']}' \\")
    print(f"    -H 'Content-Type: application/json' \\")
    if api_key_provider:
        print(f"    -H 'x-api-key: {api_key_provider['key']}' \\")
    print("    -d '{\"query\": \"{ days(sort:[{date:DESC}], limit:1) { date } }\"}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
