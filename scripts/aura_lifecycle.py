#!/usr/bin/env python3
"""On-demand Aura lifecycle: wake the instance, stamp activity, and auto-pause
after a true idle window — the cost-saving backbone for issue #13.

Why this exists (the trick): an 8 GB AuraDB Professional instance costs ~$520/mo
always-on; paused it bills at ~20%. Keeping it paused and only waking it for the
morning iPhone sync + a few queries brings it to ~$120/mo (~77% off). See the
plan on issue #13.

This module adds what `scripts/aura_pause.sh` lacks: a *real* 30-minute idle
measurement (the bash `pause-if-idle 30` ignores its minutes arg — it only checks
for in-flight transactions). Here, every write/agent query stamps a last-activity
timestamp, and `pause-if-idle` pauses only when now - lastActivityAt >= threshold
(a sliding TTL).

Subcommands
-----------
  status                     Print the instance status (running/paused/...).
  wake [--wait] [--timeout]  Resume if needed; stamp activity; optionally block
                             until running.
  touch                      Stamp (:System {key:'aura'}).lastActivityAt = now.
  pause-if-idle [--minutes N] [--dry-run]
                             Pause iff running AND idle >= N min AND no in-flight
                             non-self transactions. Run this from a scheduler
                             (cloud function / cron) every ~5-10 min.
  serve [--port P]           Minimal HTTP proxy for the iPhone app:
                               GET  /aura/status  -> {"status": "..."}
                               POST /aura/wake    -> resume + stamp (X-Wake-Secret)
                             Reference only — deploy as a serverless function and
                             gate /aura/wake behind the Auth0 JWT (issue #5).
                             NEVER ship AURA_CLIENT_SECRET inside the app binary.

Env required: AURA_CLIENT_ID, AURA_CLIENT_SECRET, AURA_INSTANCEID.
For touch / pause-if-idle / activity reads: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD.
Optional: AURA_WAKE_SECRET (shared secret checked by `serve`).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parent.parent
API_ROOT = "https://api.neo4j.io/v1"
TOKEN_URL = "https://api.neo4j.io/oauth/token"
ACTIVITY_KEY = "aura"

try:  # optional: tiny .env loader so the script works like aura_pause.sh
    from dotenv import load_dotenv

    load_dotenv(REPO / ".env")
except Exception:  # dotenv is optional; env vars may already be set
    pass


# --------------------------------------------------------------------------- #
# Aura platform API (OAuth2 client credentials + v1 instance endpoints)
# --------------------------------------------------------------------------- #
def _require(*names: str) -> None:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        sys.exit(f"Missing required env: {', '.join(missing)} (set in .env or env)")


def get_token() -> str:
    _require("AURA_CLIENT_ID", "AURA_CLIENT_SECRET")
    creds = base64.b64encode(
        f"{os.environ['AURA_CLIENT_ID']}:{os.environ['AURA_CLIENT_SECRET']}".encode()
    ).decode()
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


def _instance_path(suffix: str = "") -> str:
    _require("AURA_INSTANCEID")
    return f"{API_ROOT}/instances/{os.environ['AURA_INSTANCEID']}{suffix}"


def api(method: str, suffix: str, token: str) -> dict:
    req = Request(
        _instance_path(suffix),
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urlopen(req) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except HTTPError as e:
        body = e.read().decode()
        sys.exit(f"{method} {suffix or '/'} -> {e.code}: {body}")


def instance_status(token: str) -> str:
    return api("GET", "", token).get("data", {}).get("status", "unknown")


# --------------------------------------------------------------------------- #
# Activity signal (last-activity timestamp lives in the graph itself)
# --------------------------------------------------------------------------- #
def _driver():
    _require("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD")
    try:
        from neo4j import GraphDatabase
    except ImportError:
        sys.exit("neo4j driver not installed — `pip install -r etl/requirements.txt`")
    return GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
    )


def _db_kwargs() -> dict:
    """database_= for execute_query when NEO4J_DATABASE is set (else default)."""
    db = os.environ.get("NEO4J_DATABASE")
    return {"database_": db} if db else {}


def stamp_activity() -> None:
    """Record 'something happened' — call from every sync / agent query."""
    with _driver() as drv:
        drv.execute_query(
            "MERGE (s:System {key: $k}) SET s.lastActivityAt = datetime()",
            k=ACTIVITY_KEY,
            **_db_kwargs(),
        )


def idle_minutes() -> float | None:
    """Minutes since the last stamped activity, or None if never stamped."""
    with _driver() as drv:
        recs, _, _ = drv.execute_query(
            "MATCH (s:System {key: $k}) RETURN s.lastActivityAt AS t",
            k=ACTIVITY_KEY,
            **_db_kwargs(),
        )
    if not recs or recs[0]["t"] is None:
        return None
    last = recs[0]["t"].to_native()  # tz-aware datetime
    return (datetime.now(timezone.utc) - last).total_seconds() / 60.0


def has_inflight_transactions() -> bool:
    """True if any non-self transaction is currently running (safety check)."""
    with _driver() as drv:
        recs, _, _ = drv.execute_query(
            "SHOW TRANSACTIONS YIELD currentQuery "
            "WHERE NOT currentQuery STARTS WITH 'SHOW TRANSACTIONS' "
            "RETURN count(*) AS active",
            **_db_kwargs(),
        )
    return bool(recs and recs[0]["active"] > 0)


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_status(_args) -> int:
    print(instance_status(get_token()))
    return 0


def cmd_wake(args) -> int:
    token = get_token()
    status = instance_status(token)
    if status != "running":
        print(f"Resuming {os.environ['AURA_INSTANCEID']} (was: {status})...")
        api("POST", "/resume", token)
    else:
        print("Already running.")

    if args.wait:
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            status = instance_status(token)
            if status == "running":
                break
            print(f"  ...{status}; waiting")
            time.sleep(5)
        if status != "running":
            sys.exit(f"Timed out after {args.timeout}s — last status: {status}")
        print("Running.")

    # Start the idle clock so pause-if-idle has a baseline immediately.
    if status == "running":
        try:
            stamp_activity()
        except SystemExit:
            print("  (could not stamp activity — set NEO4J_* to enable idle tracking)")
    return 0


def cmd_touch(_args) -> int:
    stamp_activity()
    print("Stamped lastActivityAt = now.")
    return 0


def cmd_pause_if_idle(args) -> int:
    token = get_token()
    status = instance_status(token)
    if status != "running":
        print(f"Not running ({status}) — nothing to do.")
        return 0

    idle = idle_minutes()
    if idle is None:
        # No activity ever recorded — fall back to the in-flight check so we never
        # pause an instance that is mid-use but hasn't been instrumented yet.
        if has_inflight_transactions():
            print("No activity stamp, but transactions in flight — not pausing.")
            return 0
        print("No activity stamp and no in-flight transactions — treating as idle.")
        idle = float("inf")
    else:
        print(f"Idle for {idle:.1f} min (threshold {args.minutes}).")

    if idle < args.minutes:
        print("Within active window — not pausing.")
        return 0
    if has_inflight_transactions():
        print("Idle by timestamp but a transaction is in flight — not pausing.")
        return 0

    if args.dry_run:
        print("[dry-run] would pause now.")
        return 0
    print("Pausing (idle threshold reached)...")
    api("POST", "/pause", token)
    print("Paused.")
    return 0


def cmd_serve(args) -> int:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    secret = os.environ.get("AURA_WAKE_SECRET")
    if not secret:
        print("WARNING: AURA_WAKE_SECRET unset — /aura/wake is UNAUTHENTICATED.")
    print(f"Reference proxy on :{args.port} — deploy as a serverless fn for real use.")

    class Handler(BaseHTTPRequestHandler):
        def _json(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            if self.path != "/aura/status":
                return self._json(404, {"error": "not found"})
            try:
                self._json(200, {"status": instance_status(get_token())})
            except SystemExit as e:
                self._json(500, {"error": str(e)})

        def do_POST(self):  # noqa: N802
            if self.path != "/aura/wake":
                return self._json(404, {"error": "not found"})
            if secret and self.headers.get("X-Wake-Secret") != secret:
                return self._json(401, {"error": "unauthorized"})
            try:
                token = get_token()
                status = instance_status(token)
                if status != "running":
                    api("POST", "/resume", token)
                    status = "resuming"
                else:
                    try:
                        stamp_activity()  # extend the sliding idle window
                    except SystemExit:
                        pass
                self._json(202, {"status": status})
            except SystemExit as e:
                self._json(500, {"error": str(e)})

        def log_message(self, *_):  # quiet default logging
            pass

    ThreadingHTTPServer(("", args.port), Handler).serve_forever()
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="print instance status")

    w = sub.add_parser("wake", help="resume the instance (optionally wait)")
    w.add_argument("--wait", action="store_true", help="block until running")
    w.add_argument("--timeout", type=int, default=300, help="max seconds to wait (default 300)")

    sub.add_parser("touch", help="stamp lastActivityAt = now")

    pi = sub.add_parser("pause-if-idle", help="pause if idle >= --minutes")
    pi.add_argument("--minutes", type=float, default=30.0, help="idle threshold (default 30)")
    pi.add_argument("--dry-run", action="store_true", help="report the decision, don't pause")

    sv = sub.add_parser("serve", help="reference HTTP proxy for app-triggered wake")
    sv.add_argument("--port", type=int, default=8787)

    args = p.parse_args()
    return {
        "status": cmd_status,
        "wake": cmd_wake,
        "touch": cmd_touch,
        "pause-if-idle": cmd_pause_if_idle,
        "serve": cmd_serve,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
