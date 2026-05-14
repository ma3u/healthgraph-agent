"""Render a richer multi-card health dashboard backed by the Aura GraphQL Data API.

Replaces the Bolt-based scripts/render_snapshot.py for the iOS app's
Dashboard tab and the public GitHub Pages site. Same output path
(docs/snapshot/index.html), same noindex/nofollow header, but multiple
cards: Recovery, Latest day stats, Last-7-days summary, Workouts this week,
Streaks.

All queries go through the Aura GraphQL Data API with `x-api-key`. No Bolt
driver, no per-sample data — just derived/aggregated metrics, matching the
privacy posture of the original snapshot.

Required env:
  AURA_GRAPHQL_URL      e.g. https://....data.neo4j.io/graphql
  AURA_GRAPHQL_API_KEY  the API-key auth provider's key

Optional env (for paused-instance auto-resume):
  AURA_INSTANCEID, AURA_CLIENT_ID, AURA_CLIENT_SECRET
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "snapshot" / "index.html"

ZONE_CSS = {
    "GREEN": ("#10b981", "Recover & train"),
    "YELLOW": ("#f59e0b", "Maintain"),
    "RED": ("#ef4444", "Rest day"),
}


# ---------------------------------------------------------------------------
# Optional: auto-resume Aura if paused
# ---------------------------------------------------------------------------

def _aura_token(client_id: str, client_secret: str) -> str:
    body = "grant_type=client_credentials".encode()
    creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req = urllib.request.Request(
        "https://api.neo4j.io/oauth/token",
        data=body,
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["access_token"]


def maybe_resume_instance() -> None:
    iid = os.environ.get("AURA_INSTANCEID")
    cid = os.environ.get("AURA_CLIENT_ID")
    csec = os.environ.get("AURA_CLIENT_SECRET")
    if not (iid and cid and csec):
        return  # no management creds — fine, just try the GraphQL endpoint directly
    try:
        token = _aura_token(cid, csec)
        req = urllib.request.Request(
            f"https://api.neo4j.io/v1/instances/{iid}",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req) as r:
            status = json.loads(r.read())["data"]["status"]
        if status == "paused":
            print(f"[aura] instance paused — resuming…")
            urllib.request.urlopen(
                urllib.request.Request(
                    f"https://api.neo4j.io/v1/instances/{iid}/resume",
                    method="POST",
                    headers={"Authorization": f"Bearer {token}"},
                )
            )
            # Wait up to 5 min for status=running
            for _ in range(60):
                with urllib.request.urlopen(
                    urllib.request.Request(
                        f"https://api.neo4j.io/v1/instances/{iid}",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                ) as r:
                    st = json.loads(r.read())["data"]["status"]
                if st == "running":
                    print("[aura] running")
                    return
                time.sleep(5)
            sys.exit("Aura did not reach running status in time")
    except urllib.error.HTTPError as e:
        print(f"[aura] resume check failed (HTTP {e.code}) — trying the GraphQL endpoint anyway")


# ---------------------------------------------------------------------------
# GraphQL helpers
# ---------------------------------------------------------------------------

def gql(query: str, variables: dict | None = None) -> dict:
    url = os.environ["AURA_GRAPHQL_URL"]
    key = os.environ["AURA_GRAPHQL_API_KEY"]
    body = {"query": query, "variables": variables or {}}
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Content-Type": "application/json", "x-api-key": key},
    )
    with urllib.request.urlopen(req) as r:
        payload = json.loads(r.read())
    if payload.get("errors"):
        sys.exit(f"GraphQL errors: {payload['errors']}")
    return payload["data"]


LAST_60_QUERY = """
{
  dailySummaries(sort: [{ date: DESC }], limit: 60) {
    date
    hrvMean
    restingHeartRate
    sleepHours
    totalSteps
    activeEnergyKcal
    workoutCount
    workoutMinutes
  }
}
"""

RECENT_WORKOUTS_QUERY = """
{
  workouts(sort: [{ startDate: DESC }], limit: 30) {
    activityType
    durationMin
    startDate
  }
}
"""


# ---------------------------------------------------------------------------
# Derived metrics (client-side; matches the old Cypher recovery formula)
# ---------------------------------------------------------------------------

def recovery_score(latest: dict, baseline: list[dict]) -> int | None:
    """30-day z-score recovery, same formula as the Cypher version."""
    if latest.get("hrvMean") is None or latest.get("restingHeartRate") is None:
        return None
    hb = [b["hrvMean"] for b in baseline if b.get("hrvMean") is not None]
    rb = [b["restingHeartRate"] for b in baseline if b.get("restingHeartRate") is not None]
    if not hb or not rb:
        return None
    hmu, rmu = statistics.fmean(hb), statistics.fmean(rb)
    hsd = statistics.pstdev(hb) if len(hb) > 1 else 0
    rsd = statistics.pstdev(rb) if len(rb) > 1 else 0
    hz = (latest["hrvMean"] - hmu) / hsd if hsd > 0 else 0
    rz = (latest["restingHeartRate"] - rmu) / rsd if rsd > 0 else 0
    hrv_c = max(0, min(100, 50 + 25 * hz))
    rhr_c = max(0, min(100, 50 - 25 * rz))
    if latest.get("sleepHours") is None:
        sleep_c = 50
    elif latest["sleepHours"] >= 7.5:
        sleep_c = 92
    else:
        sleep_c = (latest["sleepHours"] / 7.5) * 92
    return round(0.60 * hrv_c + 0.20 * rhr_c + 0.20 * sleep_c)


def streak_count(rows: list[dict], predicate) -> int:
    """Walk newest -> oldest; count consecutive matching rows. Stop on gap or miss."""
    count = 0
    prev: dt.date | None = None
    for r in rows:
        try:
            d = dt.date.fromisoformat(r["date"])
        except (TypeError, ValueError):
            break
        if prev is not None and (prev - d).days != 1:
            break
        if not predicate(r):
            break
        count += 1
        prev = d
    return count


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

def render(
    latest_date: str,
    recovery: int | None,
    seven_day: dict,
    workouts_this_week: dict,
    streaks: dict[str, int],
) -> str:
    if recovery is None:
        zone, color, blurb = "—", "#8392a3", "Insufficient data"
    elif recovery >= 67:
        zone, color, blurb = "GREEN", *ZONE_CSS["GREEN"]
    elif recovery >= 34:
        zone, color, blurb = "YELLOW", *ZONE_CSS["YELLOW"]
    else:
        zone, color, blurb = "RED", *ZONE_CSS["RED"]

    streak_chips = "".join(
        f'<li><span class="num">{v}</span><span class="lbl">{k}</span></li>'
        for k, v in streaks.items()
        if v > 0
    ) or '<li class="empty">No active streaks today</li>'

    generated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def fmt(value, suffix: str = "", precision: int = 0) -> str:
        if value is None:
            return "—"
        if precision == 0:
            return f"{round(value)}{suffix}"
        return f"{value:.{precision}f}{suffix}"

    workout_types = ", ".join(
        f"{c}× {t}" for t, c in workouts_this_week["by_type"].items()
    ) or "none"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>HealthGraph dashboard</title>
<style>
  :root {{
    --accent: {color};
    --bg: #0b0d10;
    --fg: #e8eef4;
    --muted: #8392a3;
    --card-bg: rgba(255,255,255,0.03);
    --card-border: rgba(255,255,255,0.08);
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; min-height: 100%; }}
  body {{
    background: linear-gradient(160deg, #0b0d10 0%, #1c2230 100%);
    color: var(--fg);
    font-family: -apple-system, "SF Pro Display", "Segoe UI", system-ui, sans-serif;
    padding: 2rem 1rem 4rem;
  }}
  main {{
    max-width: 540px; margin: 0 auto;
    display: flex; flex-direction: column; gap: 1rem;
  }}
  h1 {{
    font-size: 0.85rem; font-weight: 600; letter-spacing: 0.18em;
    text-transform: uppercase; color: var(--muted);
    margin: 0 0 0.5rem;
  }}
  h2 {{ font-size: 0.7rem; letter-spacing: 0.12em;
        text-transform: uppercase; color: var(--muted);
        margin: 0 0 0.75rem; font-weight: 600; }}
  .card {{
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 1.25rem;
    padding: 1.5rem;
  }}
  .recovery {{ text-align: center; padding: 2rem 1.5rem; }}
  .score {{ font-size: 5rem; font-weight: 200; line-height: 1; color: var(--accent);
            font-variant-numeric: tabular-nums; }}
  .score sup {{ font-size: 1.5rem; font-weight: 300; opacity: 0.7; margin-left: 4px; }}
  .zone {{ display: inline-block; margin-top: 0.5rem; padding: 0.35rem 0.9rem;
           border-radius: 999px; background: var(--accent); color: #0b0d10;
           font-weight: 600; letter-spacing: 0.05em; font-size: 0.8rem; }}
  .blurb {{ color: var(--muted); margin-top: 0.5rem; font-size: 0.95rem; }}
  .stat-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }}
  .stat {{ text-align: center; }}
  .stat .num {{ font-size: 1.6rem; font-weight: 600; color: var(--fg);
                font-variant-numeric: tabular-nums; }}
  .stat .lbl {{ font-size: 0.7rem; color: var(--muted);
                letter-spacing: 0.05em; text-transform: uppercase; margin-top: 2px; }}
  ul.streaks {{ list-style: none; padding: 0; margin: 0;
                display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; }}
  ul.streaks li {{ background: rgba(255,255,255,0.04); border-radius: 0.75rem;
                   padding: 0.75rem; display: flex; flex-direction: column; align-items: center; }}
  ul.streaks .num {{ font-size: 1.4rem; font-weight: 600; }}
  ul.streaks .lbl {{ font-size: 0.65rem; color: var(--muted);
                     letter-spacing: 0.04em; text-transform: uppercase; margin-top: 2px; }}
  ul.streaks .empty {{ grid-column: span 2; color: var(--muted);
                       text-align: center; padding: 0.75rem; font-size: 0.85rem; }}
  .date {{ color: var(--muted); font-size: 0.8rem; text-align: center; }}
  footer {{ color: var(--muted); font-size: 0.7rem;
            text-align: center; margin-top: 2rem; max-width: 480px;
            margin-left: auto; margin-right: auto; }}
  footer a {{ color: var(--muted); }}
</style>
</head>
<body>
  <main>
    <h1>HealthGraph</h1>

    <div class="card recovery">
      <div class="score">{fmt(recovery)}<sup>%</sup></div>
      <span class="zone">{zone}</span>
      <div class="blurb">{blurb}</div>
      <div class="date" style="margin-top: 1rem">Data through {latest_date}</div>
    </div>

    <div class="card">
      <h2>Last 7 days · averages</h2>
      <div class="stat-grid">
        <div class="stat"><div class="num">{fmt(seven_day["avg_rhr"], precision=0)}</div><div class="lbl">RHR (bpm)</div></div>
        <div class="stat"><div class="num">{fmt(seven_day["avg_hrv"], precision=0)}</div><div class="lbl">HRV (ms)</div></div>
        <div class="stat"><div class="num">{fmt(seven_day["avg_sleep"], precision=1)}</div><div class="lbl">Sleep (h)</div></div>
        <div class="stat"><div class="num">{fmt(seven_day["avg_steps"], precision=0)}</div><div class="lbl">Steps</div></div>
      </div>
    </div>

    <div class="card">
      <h2>This week · workouts</h2>
      <div class="stat-grid" style="margin-bottom: 0.75rem">
        <div class="stat"><div class="num">{workouts_this_week["count"]}</div><div class="lbl">Sessions</div></div>
        <div class="stat"><div class="num">{round(workouts_this_week["total_minutes"])}</div><div class="lbl">Minutes</div></div>
      </div>
      <div class="date">{workout_types}</div>
    </div>

    <div class="card">
      <h2>Active streaks</h2>
      <ul class="streaks">{streak_chips}</ul>
    </div>

    <footer>
      Generated {generated} · queried via <a href="https://github.com/ma3u/healthgraph-agent/blob/main/cypher/graphql_schema.graphql">Aura GraphQL Data API</a> ·
      <a href="https://github.com/ma3u/healthgraph-agent">repo</a>
    </footer>
  </main>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if not os.environ.get("AURA_GRAPHQL_URL") or not os.environ.get("AURA_GRAPHQL_API_KEY"):
        sys.exit("AURA_GRAPHQL_URL / AURA_GRAPHQL_API_KEY missing from env")

    maybe_resume_instance()

    print("[gql] fetching last 60 daily summaries…")
    data = gql(LAST_60_QUERY)
    rows = data["dailySummaries"]
    if not rows:
        sys.exit("No DailySummary rows returned.")

    latest = rows[0]
    # For recovery we need HRV+RHR on the anchor day. The most-recent days
    # may have come from a partial iOS sync (HK perms gotcha) and lack those.
    # Walk forward until we find a day that has both, falling back to "—" if
    # nothing qualifies in the last 60.
    anchor_idx = next(
        (i for i, r in enumerate(rows)
         if r.get("hrvMean") is not None and r.get("restingHeartRate") is not None),
        None,
    )
    if anchor_idx is None:
        recovery = None
        anchor = latest
    else:
        anchor = rows[anchor_idx]
        baseline = rows[anchor_idx + 1: anchor_idx + 31]
        recovery = recovery_score(anchor, baseline)
    print(f"  latest={latest['date']}, recovery_anchor={anchor['date']}, recovery={recovery}")

    # Last 7 days averages
    seven = [r for r in rows[:7] if r["date"]]
    def avg(field: str) -> float | None:
        vs = [r[field] for r in seven if r.get(field) is not None]
        return statistics.fmean(vs) if vs else None

    seven_day = {
        "avg_rhr": avg("restingHeartRate"),
        "avg_hrv": avg("hrvMean"),
        "avg_sleep": avg("sleepHours"),
        "avg_steps": avg("totalSteps"),
    }

    # Workouts this week (last 7 days)
    print("[gql] fetching recent workouts…")
    workouts = gql(RECENT_WORKOUTS_QUERY)["workouts"]
    week_cutoff = dt.date.fromisoformat(latest["date"]) - dt.timedelta(days=7)
    weekly = []
    for w in workouts:
        # startDate comes back as DateTime ISO string; date-only prefix
        try:
            wdate = dt.date.fromisoformat(w["startDate"][:10])
        except (TypeError, ValueError):
            continue
        if wdate >= week_cutoff:
            weekly.append(w)
    by_type: dict[str, int] = {}
    total_min = 0.0
    for w in weekly:
        t = w.get("activityType") or "Other"
        by_type[t] = by_type.get(t, 0) + 1
        total_min += w.get("durationMin") or 0
    workouts_this_week = {
        "count": len(weekly),
        "total_minutes": total_min,
        "by_type": by_type,
    }

    # Streaks (same formula as old snapshot)
    streaks = {
        "Sleep ≥ 7.5h": streak_count(rows, lambda r: (r.get("sleepHours") or 0) >= 7.5),
        "Steps ≥ 10k": streak_count(rows, lambda r: (r.get("totalSteps") or 0) >= 10000),
        "RHR < 60": streak_count(rows, lambda r: r.get("restingHeartRate") is not None and r["restingHeartRate"] < 60),
        "HRV ≥ 38": streak_count(rows, lambda r: r.get("hrvMean") is not None and r["hrvMean"] >= 38),
    }
    print(f"  streaks: {streaks}")

    html = render(anchor["date"], recovery, seven_day, workouts_this_week, streaks)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
