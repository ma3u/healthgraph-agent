"""Offline-render tests for the Dashboard snapshot.

These tests drive ``scripts/render_dashboard_snapshot.py`` as a SUBPROCESS so
they exercise exactly what CI / a manual run does — no database required:

  * ``--selftest`` runs the built-in scoring/render assertions and must exit 0.
  * ``--demo --out <tmp>`` renders synthetic data to a self-contained HTML file.

The rendered page must be:
  * valid-ish HTML (starts with ``<!doctype html>``),
  * a real dashboard (mentions Recovery / Strain / Sleep, has inline sparklines),
  * PRIVACY-CLEAN — no raw-biometric markers leak into the page, and
  * SELF-CONTAINED — no scripts, and no external URLs except the github.com/ma3u
    repo link (so it renders offline while Aura is paused).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "render_dashboard_snapshot.py"


def _run(*args):
    """Run the dashboard script as a subprocess; return the CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


# --------------------------------------------------------------------------- #
# --selftest
# --------------------------------------------------------------------------- #
def test_selftest_exits_zero():
    proc = _run("--selftest")
    assert proc.returncode == 0, (
        f"--selftest failed (rc={proc.returncode})\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )


# --------------------------------------------------------------------------- #
# --demo render -> HTML on disk
# --------------------------------------------------------------------------- #
def _render_demo(tmp_path) -> tuple[Path, str]:
    out = tmp_path / "dashboard.html"
    proc = _run("--demo", "--out", str(out))
    assert proc.returncode == 0, (
        f"--demo render failed (rc={proc.returncode})\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert out.exists(), "expected the dashboard HTML file to be written"
    return out, out.read_text(encoding="utf-8")


def test_demo_writes_file(tmp_path):
    out, html = _render_demo(tmp_path)
    assert out.is_file()
    assert len(html) > 0


def test_demo_is_valid_ish_html(tmp_path):
    _, html = _render_demo(tmp_path)
    assert html.lstrip().lower().startswith("<!doctype html>")
    # Balanced top-level structure, just enough to call it HTML.
    assert "<html" in html and "</html>" in html
    assert "<head>" in html and "<body>" in html


def test_demo_mentions_the_three_hero_scores(tmp_path):
    _, html = _render_demo(tmp_path)
    for term in ("Recovery", "Strain", "Sleep"):
        assert term in html, f"dashboard missing hero score label {term!r}"


def test_demo_has_inline_sparklines(tmp_path):
    _, html = _render_demo(tmp_path)
    assert '<svg class="spark"' in html
    # One sparkline per hero card.
    assert html.count('<svg class="spark"') >= 3


def test_demo_has_no_raw_biometric_markers(tmp_path):
    """Privacy: only derived scores may appear — never raw biometric values/units."""
    _, html = _render_demo(tmp_path)
    for forbidden in (" bpm", " ms", "hrv_mean", "resting_heart_rate", "sleep_hours"):
        assert forbidden not in html, f"raw-biometric marker leaked into HTML: {forbidden!r}"


def test_demo_is_self_contained(tmp_path):
    """No scripts and no external URLs except the github.com/ma3u repo link."""
    _, html = _render_demo(tmp_path)

    # No client-side scripting at all.
    assert "<script" not in html.lower(), "dashboard must not embed any <script>"

    # Every absolute http(s) URL must point at the allowed repo.
    urls = re.findall(r"https?://[^\s\"'<>)]+", html)
    for url in urls:
        assert url.startswith(
            "https://github.com/ma3u"
        ), f"unexpected external URL (must render offline): {url!r}"


def test_demo_is_deterministic(tmp_path):
    """Synthetic data has no randomness — two renders match except the UTC stamp."""
    _, html_a = _render_demo(tmp_path)
    out_b = tmp_path / "dashboard_b.html"
    proc = _run("--demo", "--out", str(out_b))
    assert proc.returncode == 0
    html_b = out_b.read_text(encoding="utf-8")

    # Strip the "generated <timestamp> UTC" line which is the only volatile part.
    def strip(h):
        return re.sub(r"generated [0-9:\- ]+UTC", "generated UTC", h)

    assert strip(html_a) == strip(html_b)
