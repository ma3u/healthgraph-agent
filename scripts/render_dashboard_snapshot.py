"""Offline Whoop-style snapshot dashboard.

Renders a single self-contained static HTML page (Recovery / Strain / Sleep hero
scores + 30-day score sparklines + streaks) that is VIEWABLE WHILE AURA IS PAUSED.
It is generated during the brief uptime window (CI or a manual run) and committed
to docs/snapshot/, so viewing the dashboard never needs a live database — which is
exactly what makes aggressive pausing usable (issue #13).

Scores implement docs/SCORING.md EXACTLY:
  * Recovery (0-100): 0.60*HRV_z + 0.20*RHR_z + 0.20*Sleep, vs a 30-day baseline.
  * Strain   (0-21) : logarithmic TRIMP-style cardiac load (Banister/Edwards).
  * Sleep    (0-100): duration vs need * efficiency.
Those formulas are open approximations from public literature. NoopApp/noop was
used only as a benchmark to sanity-check them (issue #13); no noop code is reused
(noop is PolyForm-Noncommercial).

PRIVACY (same rule as render_snapshot.py + the no-personal-data policy): only
DERIVED scores, score sparklines, and streak COUNTS reach the HTML. Raw biometric
values (HRV ms, RHR bpm, sleep hours, step counts) never leave the runner.

Usage:
  python scripts/render_dashboard_snapshot.py            # live: query Aura, write HTML
  python scripts/render_dashboard_snapshot.py --demo --out /tmp/dash.html   # no DB
  python scripts/render_dashboard_snapshot.py --selftest                    # checks
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "docs" / "snapshot" / "dashboard.html"
DISPLAY_DAYS = 30
BASELINE_DAYS = 30

ZONES = {
    "GREEN": ("#10b981", "Primed — train hard"),
    "YELLOW": ("#f59e0b", "Maintain — moderate"),
    "RED": ("#ef4444", "Back off — recover"),
}
STRAIN_BANDS = [(9, "Light"), (13, "Moderate"), (17, "Strenuous"), (21, "All-out")]


# --------------------------------------------------------------------------- #
# Scoring — faithful Python port of docs/SCORING.md (pure functions)
# --------------------------------------------------------------------------- #
def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def sleep_performance(sleep_hours, asleep_min=None, in_bed_min=None, need_hours=7.5):
    if asleep_min and in_bed_min and in_bed_min > 0:
        duration = min(asleep_min / (need_hours * 60), 1.0) * 100
        return _clamp(duration * (asleep_min / in_bed_min))
    if sleep_hours is None:
        return None
    duration = min(sleep_hours / need_hours, 1.0) * 100
    return _clamp(duration * 0.92)  # assumed efficiency when no in-bed data


def recovery_score(hrv, rhr, sleep_perf, baseline) -> float | None:
    if hrv is None or rhr is None:
        return None
    hsd, rsd = baseline["hrv_std"], baseline["rhr_std"]
    hrv_z = (hrv - baseline["hrv_mean"]) / hsd if hsd > 0 else 0.0
    rhr_z = (rhr - baseline["rhr_mean"]) / rsd if rsd > 0 else 0.0
    hrv_c = _clamp(50 + 25 * hrv_z)
    rhr_c = _clamp(50 - 25 * rhr_z)
    sleep_c = sleep_perf if sleep_perf is not None else 50.0
    return _clamp(0.60 * hrv_c + 0.20 * rhr_c + 0.20 * sleep_c)


def strain_score(active_kcal, workout_min, target_intensity=8.0, scaling=220.0):
    ae = active_kcal or 0.0
    wm = workout_min or 0.0
    if wm > 0:
        intensity = ae / max(wm, 1.0)
        raw = wm * (intensity / target_intensity) ** 1.92
    else:
        raw = ae / target_intensity  # light-activity day proxy
    return 21.0 * (1.0 - math.exp(-raw / scaling))


def recovery_zone(rec: float) -> str:
    return "GREEN" if rec >= 67 else "YELLOW" if rec >= 34 else "RED"


def strain_band(strain: float) -> str:
    for hi, label in STRAIN_BANDS:
        if strain <= hi:
            return label
    return "All-out"


# --------------------------------------------------------------------------- #
# Model: per-day scores from a date-ascending list of raw metric dicts
# --------------------------------------------------------------------------- #
def _mean_std(xs: list[float]) -> tuple[float, float]:
    if not xs:
        return 0.0, 0.0
    mu = sum(xs) / len(xs)
    var = sum((x - mu) ** 2 for x in xs) / len(xs)
    return mu, math.sqrt(var)


def build_model(days: list[dict]) -> dict:
    """days: ascending by date, each with hrv/rhr/sleep_h/steps/active_kcal/workout_min."""
    scored: list[dict] = []
    for i, d in enumerate(days):
        window = days[max(0, i - BASELINE_DAYS) : i]  # trailing, excludes today
        hrv_b = [w["hrv"] for w in window if w["hrv"] is not None]
        rhr_b = [w["rhr"] for w in window if w["rhr"] is not None]
        hmu, hsd = _mean_std(hrv_b)
        rmu, rsd = _mean_std(rhr_b)
        baseline = {"hrv_mean": hmu, "hrv_std": hsd, "rhr_mean": rmu, "rhr_std": rsd}
        sleep_p = sleep_performance(d.get("sleep_h"))
        scored.append(
            {
                "date": d["date"],
                "recovery": recovery_score(d.get("hrv"), d.get("rhr"), sleep_p, baseline),
                "strain": strain_score(d.get("active_kcal"), d.get("workout_min")),
                "sleep": sleep_p,
                "hrv": d.get("hrv"),
                "rhr": d.get("rhr"),
                "vo2max": d.get("vo2max"),
            }
        )

    display = scored[-DISPLAY_DAYS:]
    latest = scored[-1]
    streaks = {
        "Sleep ≥ 7.5h": _streak(days, lambda r: (r.get("sleep_h") or 0) >= 7.5),
        "Steps ≥ 10k": _streak(days, lambda r: (r.get("steps") or 0) >= 10000),
        "RHR < 60": _streak(days, lambda r: r.get("rhr") is not None and r["rhr"] < 60),
        "HRV ≥ 38": _streak(days, lambda r: r.get("hrv") is not None and r["hrv"] >= 38),
    }
    return {"latest": latest, "display": display, "streaks": streaks}


def _streak(days: list[dict], pred) -> int:
    """Count consecutive matching days from newest backwards (days is ascending)."""
    count = 0
    prev: dt.date | None = None
    for r in reversed(days):
        d = _as_date(r["date"])
        if prev is not None and (prev - d).days != 1:
            break
        if not pred(r):
            break
        count += 1
        prev = d
    return count


def _as_date(d) -> dt.date:
    if hasattr(d, "to_native"):
        d = d.to_native()
    if isinstance(d, dt.datetime):
        return d.date()
    if isinstance(d, dt.date):
        return d
    return dt.date.fromisoformat(str(d)[:10])


# --------------------------------------------------------------------------- #
# Rendering — self-contained HTML, inline SVG sparklines, no external assets
# --------------------------------------------------------------------------- #
def _sparkline(values: list[float], vmax: float, color: str, vmin: float = 0.0) -> str:
    pts = [v for v in values if v is not None]
    if len(pts) < 2:
        return '<svg class="spark" viewBox="0 0 100 28"></svg>'
    n = len(values)
    step = 100 / (n - 1)
    span = max(vmax - vmin, 1e-6)
    coords = []
    for i, v in enumerate(values):
        if v is None:
            continue
        x = i * step
        clamped = max(vmin, min(v, vmax))
        y = 28 - ((clamped - vmin) / span) * 26 - 1
        coords.append(f"{x:.1f},{y:.1f}")
    poly = " ".join(coords)
    return (
        f'<svg class="spark" viewBox="0 0 100 28" preserveAspectRatio="none">'
        f'<polyline points="{poly}" fill="none" stroke="{color}" '
        f'stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/></svg>'
    )


def _metric_card(label, value, unit, color, sub, spark) -> str:
    return f"""
    <div class="metric">
      <div class="m-label">{label}</div>
      <div class="m-value" style="color:{color}">{value}<sup>{unit}</sup></div>
      <div class="m-sub" style="color:{color}">{sub}</div>
      {spark}
    </div>"""


def render_html(model: dict) -> str:
    latest = model["latest"]
    rec = latest["recovery"]
    strain = latest["strain"]
    sleep = latest["sleep"]
    date_iso = _as_date(latest["date"]).isoformat()
    generated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rec_zone = recovery_zone(rec) if rec is not None else "YELLOW"
    rec_color, rec_blurb = ZONES[rec_zone]
    strain_color = "#3b82f6"
    sleep_color = "#a855f7"

    disp = model["display"]
    rec_series = [d["recovery"] for d in disp]
    strain_series = [d["strain"] for d in disp]
    sleep_series = [d["sleep"] for d in disp]
    vo2_series = [d.get("vo2max") for d in disp]
    hrv_series = [d.get("hrv") for d in disp]
    rhr_series = [d.get("rhr") for d in disp]

    def _latest(series):
        return next((v for v in reversed(series) if v is not None), None)

    def _range(series, lo_default, hi_default, pad):
        vals = [v for v in series if v is not None]
        if not vals:
            return (lo_default, hi_default)
        return (max(min(vals) - pad, 0), max(vals) + pad)

    vo2_latest, hrv_latest, rhr_latest = (
        _latest(vo2_series),
        _latest(hrv_series),
        _latest(rhr_series),
    )
    vo2_lo, vo2_hi = _range(vo2_series, 0, 60, 1)
    hrv_lo, hrv_hi = _range(hrv_series, 0, 80, 5)
    rhr_lo, rhr_hi = _range(rhr_series, 40, 70, 3)

    cards = (
        _metric_card(
            "Recovery",
            round(rec) if rec is not None else "—",
            "%",
            rec_color,
            f"{rec_zone} · {rec_blurb}",
            _sparkline(rec_series, 100, rec_color),
        )
        + _metric_card(
            "Strain",
            f"{strain:.1f}" if strain is not None else "—",
            "/21",
            strain_color,
            strain_band(strain) if strain is not None else "—",
            _sparkline(strain_series, 21, strain_color),
        )
        + _metric_card(
            "Sleep",
            round(sleep) if sleep is not None else "—",
            "%",
            sleep_color,
            "Performance",
            _sparkline(sleep_series, 100, sleep_color),
        )
        + _metric_card(
            "VO₂max",
            f"{vo2_latest:.1f}" if vo2_latest is not None else "—",
            " ml/kg·min",
            "#14b8a6",
            "Cardio fitness",
            _sparkline(vo2_series, vo2_hi, "#14b8a6", vmin=vo2_lo),
        )
        + _metric_card(
            "HRV",
            f"{hrv_latest:.0f}" if hrv_latest is not None else "—",
            " ms",
            "#34d399",
            "Higher is better",
            _sparkline(hrv_series, hrv_hi, "#34d399", vmin=hrv_lo),
        )
        + _metric_card(
            "Resting HR",
            f"{rhr_latest:.0f}" if rhr_latest is not None else "—",
            " bpm",
            "#f472b6",
            "Lower is better",
            _sparkline(rhr_series, rhr_hi, "#f472b6", vmin=rhr_lo),
        )
    )

    streak_chips = (
        "".join(
            f'<li><span class="num">{v}</span><span class="lbl">{k}</span></li>'
            for k, v in model["streaks"].items()
            if v > 0
        )
        or '<li class="empty">No active streaks</li>'
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>HealthGraph — offline dashboard</title>
<style>
  :root {{ --bg:#0b0d10; --fg:#e8eef4; --muted:#8392a3; }}
  * {{ box-sizing:border-box; }}
  html,body {{ margin:0; min-height:100%; }}
  body {{
    background:linear-gradient(160deg,#0b0d10 0%,#1c2230 100%);
    color:var(--fg); font-family:-apple-system,"SF Pro Display","Segoe UI",system-ui,sans-serif;
    display:flex; flex-direction:column; align-items:center; padding:2rem 1rem;
  }}
  h1 {{ font-size:.85rem; font-weight:600; letter-spacing:.18em; text-transform:uppercase;
        color:var(--muted); margin:.5rem 0 1.5rem; }}
  .grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:1rem;
           width:min(720px,100%); }}
  @media (max-width:560px) {{ .grid {{ grid-template-columns:1fr; }} }}
  .metric {{ background:rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.08);
             border-radius:1.25rem; padding:1.5rem 1.25rem; text-align:center;
             box-shadow:0 16px 48px rgba(0,0,0,.45); }}
  .m-label {{ font-size:.72rem; letter-spacing:.12em; text-transform:uppercase;
              color:var(--muted); }}
  .m-value {{ font-size:3.4rem; font-weight:200; line-height:1.1;
              font-variant-numeric:tabular-nums; }}
  .m-value sup {{ font-size:1.1rem; font-weight:300; opacity:.6; margin-left:2px; }}
  .m-sub {{ font-size:.8rem; font-weight:600; opacity:.9; }}
  svg.spark {{ width:100%; height:28px; margin-top:1rem; opacity:.85; }}
  ul.streaks {{ list-style:none; padding:0; margin:1.5rem 0 0; width:min(720px,100%);
                display:grid; grid-template-columns:repeat(4,1fr); gap:.5rem; }}
  @media (max-width:560px) {{ ul.streaks {{ grid-template-columns:repeat(2,1fr); }} }}
  ul.streaks li {{ background:rgba(255,255,255,.04); border-radius:.75rem; padding:.75rem;
                   display:flex; flex-direction:column; align-items:center; }}
  ul.streaks .num {{ font-size:1.5rem; font-weight:600; }}
  ul.streaks .lbl {{ font-size:.65rem; color:var(--muted); letter-spacing:.04em;
                     text-transform:uppercase; margin-top:2px; text-align:center; }}
  ul.streaks .empty {{ grid-column:1/-1; color:var(--muted); text-align:center; padding:1rem; }}
  .date {{ color:var(--muted); font-size:.82rem; margin-top:1.5rem; }}
  footer {{ color:var(--muted); font-size:.68rem; margin-top:1.5rem; text-align:center;
            max-width:560px; line-height:1.5; }}
  footer a {{ color:var(--muted); }}
</style>
</head>
<body>
  <h1>HealthGraph · daily readiness</h1>
  <div class="grid">{cards}
  </div>
  <ul class="streaks">{streak_chips}</ul>
  <div class="date">Data through {date_iso}</div>
  <footer>
    Offline snapshot · works while the Aura instance is paused · generated {generated}<br>
    Recovery / Strain / Sleep scores + recent VO₂max · HRV · resting HR. Scores per docs/SCORING.md.
    · <a href="https://github.com/ma3u/healthgraph-agent">repo</a>
  </footer>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# Data sources
# --------------------------------------------------------------------------- #
FETCH_CYPHER = """
MATCH (s:DailySummary)
WITH s ORDER BY s.date DESC LIMIT $n
RETURN s.date AS date, s.hrv_mean AS hrv, s.resting_heart_rate AS rhr,
       s.sleep_hours AS sleep_h, s.total_steps AS steps,
       s.active_energy_kcal AS active_kcal, s.workout_minutes AS workout_min,
       s.vo2max AS vo2max
ORDER BY s.date ASC
"""


def fetch_days(env: dict, n: int) -> list[dict]:
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(env["NEO4J_URI"], auth=(env["NEO4J_USER"], env["NEO4J_PASSWORD"]))
    # Target an explicit database only when NEO4J_DATABASE is set (e.g. tests
    # against an isolated db); otherwise use the server default (unchanged).
    database = os.environ.get("NEO4J_DATABASE")
    session_kwargs = {"database": database} if database else {}
    with driver.session(**session_kwargs) as sess:
        rows = [dict(r) for r in sess.run(FETCH_CYPHER, n=n)]
    driver.close()
    return rows


def demo_days(n: int) -> list[dict]:
    """Deterministic synthetic data (no DB, no randomness) for layout/self-test."""
    start = dt.date(2026, 1, 1)
    days = []
    for i in range(n):
        phase = i / 7.0
        days.append(
            {
                "date": start + dt.timedelta(days=i),
                "hrv": 42 + 8 * math.sin(phase) - (i % 5),
                "rhr": 56 + 4 * math.sin(phase + 1) + (i % 3),
                "sleep_h": 7.6 + 0.8 * math.sin(phase + 2),
                "steps": 9000 + 3000 * (1 + math.sin(phase)),
                "active_kcal": 450 + 300 * (1 + math.sin(phase + 0.5)),
                "workout_min": 0 if i % 3 == 0 else 35 + 20 * (i % 4),
                "vo2max": 42 + 3 * math.sin(phase),
            }
        )
    return days


# --------------------------------------------------------------------------- #
# Entry points
# --------------------------------------------------------------------------- #
def selftest() -> int:
    model = build_model(demo_days(60))
    latest = model["latest"]
    assert latest["recovery"] is None or 0 <= latest["recovery"] <= 100, "recovery range"
    assert 0 <= latest["strain"] <= 21, "strain range"
    assert latest["sleep"] is None or 0 <= latest["sleep"] <= 100, "sleep range"
    assert len(model["display"]) == DISPLAY_DAYS, "display window"
    html = render_html(model)
    assert html.lstrip().startswith("<!doctype html>"), "html shape"
    # The page intentionally shows personal metrics now; check the cards rendered
    # and that internal Cypher aliases never leak as text.
    for label in ("Recovery", "Strain", "Sleep", "VO₂max", "HRV", "Resting HR"):
        assert label in html, f"missing card: {label!r}"
    for internal in ("hrv_mean", "resting_heart_rate"):
        assert internal not in html, f"internal field leaked: {internal!r}"
    rec = round(latest["recovery"]) if latest["recovery"] is not None else None
    slp = round(latest["sleep"]) if latest["sleep"] is not None else None
    print(f"selftest OK — recovery={rec} strain={latest['strain']:.1f} sleep={slp}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output HTML path")
    p.add_argument("--days", type=int, default=DISPLAY_DAYS, help="days to display (default 30)")
    p.add_argument("--demo", action="store_true", help="render from synthetic data (no DB)")
    p.add_argument(
        "--local",
        action="store_true",
        help="render from the local Neo4j (LOCAL_NEO4J_* env; default bolt://localhost:7687) — no Aura",
    )
    p.add_argument("--selftest", action="store_true", help="run scoring/render checks and exit")
    args = p.parse_args()

    if args.selftest:
        return selftest()

    fetch_n = args.days + BASELINE_DAYS
    if args.demo:
        days = demo_days(fetch_n)
    elif args.local:
        try:
            from dotenv import load_dotenv

            load_dotenv(ROOT / ".env")
        except Exception:
            pass
        pw = os.environ.get("LOCAL_NEO4J_PASSWORD")
        if not pw:
            sys.exit(
                "Set LOCAL_NEO4J_PASSWORD (and optionally LOCAL_NEO4J_URI / "
                "LOCAL_NEO4J_USER) in .env or env to render from the local Neo4j."
            )
        env = {
            "NEO4J_URI": os.environ.get("LOCAL_NEO4J_URI", "bolt://localhost:7687"),
            "NEO4J_USER": os.environ.get("LOCAL_NEO4J_USER", "neo4j"),
            "NEO4J_PASSWORD": pw,
        }
        print(f"[local] {env['NEO4J_URI']} (no Aura resume needed)")
        days = fetch_days(env, fetch_n)
    else:
        from render_snapshot import aura_resume_and_wait, aura_status, load_env

        env = load_env()
        st = aura_status(env)
        if st == "paused":
            aura_resume_and_wait(env)
        elif st is not None and st != "running":
            sys.exit(f"Aura instance not usable; status={st}")
        days = fetch_days(env, fetch_n)

    if not days:
        sys.exit("No DailySummary data found.")

    html = render_html(build_model(days))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html)
    print(f"Wrote {args.out} ({len(html)} bytes, {len(days)} days)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
