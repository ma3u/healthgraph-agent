#!/usr/bin/env python3
"""Attach an Auth0 JWKS auth provider to the Aura GraphQL Data API.

Hits the v1beta5 Aura Management REST API directly because aura-cli v1.8.0
doesn't yet expose `data-api graphql auth-provider` commands.

Reads from .env:
  AURA_CLIENT_ID, AURA_CLIENT_SECRET   (Aura M2M creds)
  AURA_INSTANCEID                       (your instance, e.g. 7d4ba607)
  AURA_GRAPHQL_DATA_API_ID              (created by create_aura_data_api.py)
  AUTH0_DOMAIN                          (e.g. healthgraph.us.auth0.com)

Run from repo root:
  /tmp/aura-venv/bin/python scripts/add_auth0_jwks_provider.py
"""

from __future__ import annotations

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

INSTANCE_ID = os.environ.get("AURA_INSTANCEID") or sys.exit("AURA_INSTANCEID missing")
DATA_API_ID = os.environ.get("AURA_GRAPHQL_DATA_API_ID") or sys.exit("AURA_GRAPHQL_DATA_API_ID missing")
AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN") or sys.exit(
    "AUTH0_DOMAIN missing — set it in .env (e.g. healthgraph.us.auth0.com)"
)

API_BASE = (
    f"https://api.neo4j.io/v1beta5/instances/{INSTANCE_ID}"
    f"/data-apis/graphql/{DATA_API_ID}/auth-providers"
)
JWKS_URL = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
PROVIDER_NAME = "Auth0"


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


def request(method: str, url: str, token: str, body: dict | None = None) -> tuple[int, dict]:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    try:
        with urlopen(Request(url, method=method, headers=headers, data=data)) as r:
            return r.status, json.loads(r.read())
    except HTTPError as e:
        return e.code, json.loads(e.read())


def find_existing(token: str) -> dict | None:
    code, body = request("GET", API_BASE, token)
    if code != 200:
        sys.exit(f"GET {API_BASE} → {code} {body}")
    for p in body.get("data", []):
        if p.get("name") == PROVIDER_NAME and p.get("type") == "jwks":
            return p
    return None


def main() -> int:
    print(f"Data API: {DATA_API_ID}")
    print(f"JWKS URL: {JWKS_URL}")
    token = get_token()

    existing = find_existing(token)
    if existing:
        print(f"Provider '{PROVIDER_NAME}' already exists (id={existing['id']}).")
        if existing.get("url") != JWKS_URL:
            print(f"  WARNING: existing URL is {existing.get('url')} — different from current AUTH0_DOMAIN")
            print("  Delete it manually in the Aura console if you need to change it.")
        return 0

    print(f"Creating JWKS provider '{PROVIDER_NAME}'…")
    code, resp = request(
        "POST",
        API_BASE,
        token,
        {
            "name": PROVIDER_NAME,
            "type": "jwks",
            "enabled": True,
            "url": JWKS_URL,
        },
    )
    if code != 202:
        sys.exit(f"POST → {code}: {json.dumps(resp, indent=2)}")

    print(f"\n✅ Created: id={resp['data']['id']}")
    print()
    print("Next: rebuild the iOS app so it sends Bearer JWT instead of x-api-key.")
    print("  1. Fill AUTH0_DOMAIN / AUTH0_CLIENT_ID / AUTH0_AUDIENCE in ios/project.yml")
    print("  2. bash scripts/build_ios.sh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
