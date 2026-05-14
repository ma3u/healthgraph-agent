"""Render a public-safe daily-recovery snapshot HTML page.

Reads .env / env vars for Neo4j connection, queries the live Aura instance,
computes the Whoop-equivalent Recovery score and current streaks for the
latest day of data, then writes a single self-contained HTML file to
docs/snapshot/index.html (no external assets, no JavaScript that calls
back to Aura, no API keys, no raw biometric values).

Only the following fields make it onto the page (per user approval, see
docs/STATUS.md §1 and the memory rule on personal data):

  * Recovery percentage (integer 0-100)
  * Recovery zone (GREEN / YELLOW / RED)
  * Date of the data snapshot (date the export was generated)
  * Current streaks (consecutive days of: 10k+ steps, RHR<60, sleep >= 7.5h,
                     HRV above 38ms). Streak counts only, no underlying values.

If the Aura instance is paused, the script optionally resumes it via the
public API when AURA_CLIENT_ID/AURA_CLIENT_SECRET are present, then waits
up to 5 min for status=running before querying.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parent.parent
DOCS_OUT = ROOT / "docs" / "snapshot" / "index.html"

ZONE_CSS = {
    "GREEN": ("#10b981", "Recover & train"),
    "YELLOW": ("#f59e0b", "Maintain"),
    "RED": ("#ef4444", "Back off"),
}


def load_env() -> dict[str, str]:
    """Read .env (if present) plus actual env vars; env vars win."""
    env: dict[str, str] = {}
    env_path = ROOT / ".env"
    if env_path.exists():
        for raw in env_path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    env.update({k: v for k, v in os.environ.items()
                if k.startswith(("NEO4J_", "AURA_"))})
    if "NEO4J_URI" not in env or "NEO4J_PASSWORD" not in env:
        sys.exit("Set NEO4J_URI and NEO4J_PASSWORD via .env or env vars.")
    env.setdefault("NEO4J_USER", "neo4j")
    return env


# ----- Aura instance auto-resume (best effort) -----

def aura_status(env: dict[str, str]) -> str | None:
    cid = env.get("AURA_CLIENT_ID")
    csec = env.get("AURA_CLIENT_SECRET")
    iid = env.get("AURA_INSTANCEID")
    if not all([cid, csec, iid]):
        return None  # no creds, skip the resume dance
    token = _aura_token(cid, csec)
    info = _aura_api(token, f"https://api.neo4j.io/v1/instances/{iid}", "GET")
    return info["data"]["status"]


def aura_resume_and_wait(env: dict[str, str], timeout_s: int = 300) -> None:
    cid, csec, iid = env["AURA_CLIENT_ID"], env["AURA_CLIENT_SECRET"], env["AURA_INSTANCEID"]
    token = _aura_token(cid, csec)
    print(f"[aura] resuming {iid}…")
    _aura_api(token, f"https://api.neo4j.io/v1/instances/{iid}/resume", "POST")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        info = _aura_api(token, f"https://api.neo4j.io/v1/instances/{iid}", "GET")
        st = info["data"]["status"]
        if st == "running":
            print(f"[aura] running after {int(time.time() - deadline + timeout_s)}s")
            return
        print(f"[aura] status={st}, sleeping 10s…")
        time.sleep(10)
    sys.exit("Aura did not reach running status in time")


def _aura_token(client_id: str, client_secret: str) -> str:
    body = "grant_type=client_credentials".encode()
    creds_b64 = _basic_auth(client_id, client_secret)
    req = urllib.request.Request(
        "https://api.neo4j.io/oauth/token",
        data=body,
        headers={
            "Authorization": f"Basic {creds_b64}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["access_token"]


def _basic_auth(user: str, pw: str) -> str:
    import base64
    return base64.b64encode(f"{user}:{pw}".encode()).decode()


def _aura_api(token: str, url: str, method: str):
    req = urllib.request.Request(
        url,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"Aura API {method} {url} -> {e.code}: {e.read().decode()}")


# ----- Recovery score query (anchored to latest data) -----

RECOVERY_CYPHER = """
MATCH (m:DailySummary) WITH max(m.date) AS anchor
MATCH (s:DailySummary)
WHERE s.date = anchor AND s.hrv_mean IS NOT NULL AND s.resting_heart_rate IS NOT NULL
MATCH (b:DailySummary)
WHERE b.date >= s.date - duration({days: 30}) AND b.date < s.date
  AND b.hrv_mean IS NOT NULL AND b.resting_heart_rate IS NOT NULL
WITH s,
     collect(b.hrv_mean) AS hb,
     collect(b.resting_heart_rate) AS rb
WITH s, hb, rb,
     reduce(t = 0.0, x IN hb | t + x) / size(hb) AS hmu,
     reduce(t = 0.0, x IN rb | t + x) / size(rb) AS rmu
WITH s, hb, rb, hmu, rmu,
     sqrt(reduce(t = 0.0, x IN hb | t + (x - hmu) * (x - hmu)) / size(hb)) AS hsd,
     sqrt(reduce(t = 0.0, x IN rb | t + (x - rmu) * (x - rmu)) / size(rb)) AS rsd
WITH s,
     CASE WHEN hsd > 0 THEN (s.hrv_mean - hmu) / hsd ELSE 0 END AS hz,
     CASE WHEN rsd > 0 THEN (s.resting_heart_rate - rmu) / rsd ELSE 0 END AS rz
WITH s,
     CASE WHEN 50 + 25 * hz > 100 THEN 100
          WHEN 50 + 25 * hz < 0 THEN 0
          ELSE 50 + 25 * hz END AS hrv_c,
     CASE WHEN 50 - 25 * rz > 100 THEN 100
          WHEN 50 - 25 * rz < 0 THEN 0
          ELSE 50 - 25 * rz END AS rhr_c,
     CASE WHEN s.sleep_hours IS NULL THEN 50
          WHEN s.sleep_hours >= 7.5 THEN 92
          ELSE (s.sleep_hours / 7.5) * 92 END AS sleep_c
RETURN s.date AS date,
       toInteger(round(0.60 * hrv_c + 0.20 * rhr_c + 0.20 * sleep_c)) AS recovery
"""

LAST_60_DAYS = """
MATCH (s:DailySummary)
WITH s ORDER BY s.date DESC LIMIT 60
RETURN s.date AS date,
       s.hrv_mean AS hrv,
       s.resting_heart_rate AS rhr,
       s.sleep_hours AS sleep_h,
       s.total_steps AS steps
ORDER BY s.date DESC
"""


def streak_count(rows: list[dict], pred) -> int:
    """Walk newest -> oldest; return count of consecutive matching rows from the top."""
    count = 0
    prev_date: dt.date | None = None
    for row in rows:
        d = row["date"]
        if hasattr(d, "to_native"):
            d = d.to_native()
        if not isinstance(d, dt.date):
            d = dt.date.fromisoformat(str(d))
        if prev_date is not None and (prev_date - d).days != 1:
            break  # gap in data — streak ends here
        if not pred(row):
            break
        count += 1
        prev_date = d
    return count


def render_html(date_iso: str, recovery: int, streaks: dict[str, int]) -> str:
    if recovery >= 67:
        zone = "GREEN"
    elif recovery >= 34:
        zone = "YELLOW"
    else:
        zone = "RED"
    color, blurb = ZONE_CSS[zone]
    generated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    streak_chips = "".join(
        f'<li><span class="num">{v}</span><span class="lbl">{k}</span></li>'
        for k, v in streaks.items() if v > 0
    ) or '<li class="empty">No active streaks today</li>'

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Recovery — HealthGraph snapshot</title>
<style>
  :root {{
    --accent: {color};
    --bg: #0b0d10;
    --fg: #e8eef4;
    --muted: #8392a3;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; height: 100%; }}
  body {{
    background: linear-gradient(160deg, #0b0d10 0%, #1c2230 100%);
    color: var(--fg);
    font-family: -apple-system, "SF Pro Display", "Segoe UI", system-ui, sans-serif;
    display: flex; flex-direction: column; align-items: center;
    justify-content: center;
    min-height: 100vh; padding: 2rem;
  }}
  h1 {{ font-size: 1rem; font-weight: 600; letter-spacing: 0.18em;
        text-transform: uppercase; color: var(--muted);
        margin: 0 0 1.5rem; }}
  .card {{
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 1.5rem;
    padding: 3rem 2.5rem;
    width: min(420px, 100%);
    text-align: center;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
  }}
  .score {{
    font-size: 7rem; font-weight: 200; line-height: 1;
    color: var(--accent);
    font-variant-numeric: tabular-nums;
  }}
  .score sup {{ font-size: 2rem; font-weight: 300; opacity: 0.7; margin-left: 4px; }}
  .zone {{
    display: inline-block;
    margin-top: 0.75rem; padding: 0.4rem 1rem;
    border-radius: 999px;
    background: var(--accent);
    color: #0b0d10;
    font-weight: 600; letter-spacing: 0.05em;
    font-size: 0.85rem;
  }}
  .blurb {{ color: var(--muted); margin-top: 0.75rem; font-size: 1rem; }}
  .date {{ color: var(--muted); font-size: 0.85rem; margin-top: 2rem; }}
  ul.streaks {{
    list-style: none; padding: 0; margin: 2rem 0 0;
    display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;
  }}
  ul.streaks li {{
    background: rgba(255,255,255,0.04);
    border-radius: 0.75rem;
    padding: 0.75rem;
    display: flex; flex-direction: column; align-items: center;
  }}
  ul.streaks .num {{ font-size: 1.5rem; font-weight: 600; color: var(--fg); }}
  ul.streaks .lbl {{ font-size: 0.7rem; color: var(--muted);
                       letter-spacing: 0.04em; text-transform: uppercase; margin-top: 2px; }}
  ul.streaks .empty {{ grid-column: span 2; color: var(--muted);
                         text-align: center; padding: 1rem; }}
  footer {{ color: var(--muted); font-size: 0.7rem; margin-top: 2rem;
             text-align: center; max-width: 420px; }}
  footer a {{ color: var(--muted); }}
</style>
</head>
<body>
  <h1>Recovery</h1>
  <div class="card">
    <div class="score">{recovery}<sup>%</sup></div>
    <span class="zone">{zone}</span>
    <div class="blurb">{blurb}</div>
    <ul class="streaks">{streak_chips}</ul>
    <div class="date">Data through {date_iso}</div>
  </div>
  <footer>
    HealthGraph daily snapshot · generated {generated} ·
    <a href="https://github.com/ma3u/healthgraph-agent">repo</a>
  </footer>
</body>
</html>
"""


def main() -> None:
    env = load_env()

    # Best-effort auto-resume if Aura is paused
    st = aura_status(env)
    if st == "paused":
        aura_resume_and_wait(env)
    elif st is not None and st != "running":
        sys.exit(f"Aura instance not usable; status={st}")

    driver = GraphDatabase.driver(
        env["NEO4J_URI"], auth=(env["NEO4J_USER"], env["NEO4J_PASSWORD"])
    )
    with driver.session() as sess:
        rec = sess.run(RECOVERY_CYPHER).single()
        if rec is None:
            sys.exit("No recovery score returned (no latest day with HRV+RHR?).")
        latest_date = str(rec["date"])
        recovery = int(rec["recovery"])

        last60 = [dict(r) for r in sess.run(LAST_60_DAYS)]

    driver.close()

    # Streaks — only the names go to the HTML, not the underlying values
    streaks = {
        "Sleep ≥ 7.5h": streak_count(
            last60, lambda r: (r["sleep_h"] or 0) >= 7.5
        ),
        "Steps ≥ 10k": streak_count(
            last60, lambda r: (r["steps"] or 0) >= 10000
        ),
        "RHR < 60": streak_count(
            last60, lambda r: r["rhr"] is not None and r["rhr"] < 60
        ),
        "HRV ≥ 38": streak_count(
            last60, lambda r: r["hrv"] is not None and r["hrv"] >= 38
        ),
    }

    html = render_html(latest_date, recovery, streaks)
    DOCS_OUT.parent.mkdir(parents=True, exist_ok=True)
    DOCS_OUT.write_text(html)
    print(f"Wrote {DOCS_OUT}")
    print(f"  Date: {latest_date}  Recovery: {recovery}  Streaks: {streaks}")


if __name__ == "__main__":
    main()
