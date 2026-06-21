"""Pure-Python unit tests for the Dashboard scoring functions.

These tests exercise the scoring math in
``scripts/render_dashboard_snapshot.py`` directly — no database, no subprocess,
no I/O. They pin known inputs to expected outputs so any change to the formulas
(or an accidental regression) is caught immediately.

The scoring contract under test (see the module docstring + docs/SCORING.md):
  * recovery_score: 0.60*HRV_z + 0.20*RHR_z + 0.20*Sleep vs a baseline, clamped [0,100].
  * strain_score: logarithmic 0..21 cardiac load; higher for hard work, ~0 at rest.
  * sleep_performance: duration/need * efficiency; 0.92 assumed efficiency fallback.
  * recovery_zone: GREEN>=67, YELLOW>=34, else RED.
  * strain_band: Light<=9, Moderate<=13, Strenuous<=17, else All-out.
  * build_model: per-day scores using a TRAILING baseline that EXCLUDES today.
"""

from __future__ import annotations

import datetime as dt
import math
import sys
from pathlib import Path

import pytest

# Make scripts/ importable regardless of pytest's invocation cwd.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import render_dashboard_snapshot as rds  # noqa: E402


# --------------------------------------------------------------------------- #
# sleep_performance
# --------------------------------------------------------------------------- #
def test_sleep_fallback_uses_092_efficiency_at_full_need():
    # No in-bed data: duration capped at 100 (>= need), times the 0.92 fallback.
    assert rds.sleep_performance(7.5) == pytest.approx(92.0)


def test_sleep_fallback_scales_with_duration():
    # Half the 7.5h need -> 50% duration * 0.92 efficiency = 46.0.
    assert rds.sleep_performance(3.75) == pytest.approx(46.0)


def test_sleep_fallback_caps_duration_at_full_need():
    # Oversleeping does not exceed 100% duration; result stays 92.0.
    assert rds.sleep_performance(10.0) == pytest.approx(92.0)


def test_sleep_none_returns_none():
    assert rds.sleep_performance(None) is None


def test_sleep_with_inbed_uses_measured_efficiency():
    # asleep 450 of 480 in-bed -> efficiency 0.9375; duration 450/(7.5*60)=1.0 -> 100.
    # 100 * 0.9375 = 93.75 (no longer the 0.92 fallback).
    assert rds.sleep_performance(None, asleep_min=450, in_bed_min=480) == pytest.approx(93.75)


# --------------------------------------------------------------------------- #
# recovery_score — z-score math + clamping
# --------------------------------------------------------------------------- #
_BASE = {"hrv_mean": 50.0, "hrv_std": 10.0, "rhr_mean": 60.0, "rhr_std": 5.0}


def test_recovery_at_baseline_mean_is_midpoint():
    # hrv & rhr at the mean -> z=0 -> both centered at 50; sleep 50 -> overall 50.
    assert rds.recovery_score(50.0, 60.0, 50.0, _BASE) == pytest.approx(50.0)


def test_recovery_hrv_one_std_above():
    # hrv +1 std -> hrv_c=75; rhr at mean -> 50; sleep 50.
    # 0.60*75 + 0.20*50 + 0.20*50 = 65.
    assert rds.recovery_score(60.0, 60.0, 50.0, _BASE) == pytest.approx(65.0)


def test_recovery_rhr_one_std_above_lowers_score():
    # Higher RHR is WORSE: rhr +1 std -> rhr_c=25; hrv at mean -> 50; sleep 50.
    # 0.60*50 + 0.20*25 + 0.20*50 = 45.
    assert rds.recovery_score(50.0, 65.0, 50.0, _BASE) == pytest.approx(45.0)


def test_recovery_clamps_each_component_to_0_100():
    # Extreme HRV would push hrv_c past 100 but it clamps to 100.
    # 0.60*100 + 0.20*50 + 0.20*100 = 90.
    assert rds.recovery_score(1000.0, 60.0, 100.0, _BASE) == pytest.approx(90.0)


def test_recovery_overall_result_stays_in_0_100():
    # Worst-case inputs still land inside the clamp window.
    val = rds.recovery_score(-1000.0, 1000.0, 0.0, _BASE)
    assert 0.0 <= val <= 100.0


def test_recovery_zero_std_yields_zscore_zero():
    base0 = {"hrv_mean": 50.0, "hrv_std": 0.0, "rhr_mean": 60.0, "rhr_std": 0.0}
    # std==0 -> z forced to 0 -> hrv_c=rhr_c=50; with sleep 50 -> 50.
    assert rds.recovery_score(99.0, 99.0, 50.0, base0) == pytest.approx(50.0)


def test_recovery_missing_inputs_return_none():
    assert rds.recovery_score(None, 60.0, 50.0, _BASE) is None
    assert rds.recovery_score(50.0, None, 50.0, _BASE) is None


def test_recovery_missing_sleep_defaults_to_50():
    # sleep_perf None -> treated as 50; with hrv/rhr at mean -> overall 50.
    assert rds.recovery_score(50.0, 60.0, None, _BASE) == pytest.approx(50.0)


# --------------------------------------------------------------------------- #
# strain_score — 0..21 range, ordering, rest ~0
# --------------------------------------------------------------------------- #
def test_strain_zero_with_no_activity():
    assert rds.strain_score(0, 0) == pytest.approx(0.0, abs=1e-9)
    assert rds.strain_score(None, None) == pytest.approx(0.0, abs=1e-9)


def test_strain_within_0_to_21_range():
    for kcal, mins in [(0, 0), (300, 0), (800, 60), (5000, 120), (20000, 300)]:
        s = rds.strain_score(kcal, mins)
        assert 0.0 <= s <= 21.0, f"strain {s} out of range for {(kcal, mins)}"


def test_strain_hard_workout_exceeds_rest_day():
    rest = rds.strain_score(0, 0)
    hard = rds.strain_score(800, 60)
    assert hard > rest
    assert hard > 0.0


def test_strain_monotonic_with_load():
    # More work -> more strain.
    assert rds.strain_score(1200, 90) > rds.strain_score(800, 60) > rds.strain_score(300, 30)


def test_strain_saturates_below_ceiling():
    # A very high load approaches but does not exceed the 21 ceiling.
    s = rds.strain_score(5000, 120)
    assert 20.5 < s < 21.0
    # And an extreme load saturates AT the ceiling without overshooting it.
    assert rds.strain_score(50000, 600) <= 21.0


# --------------------------------------------------------------------------- #
# recovery_zone thresholds (67 / 34)
# --------------------------------------------------------------------------- #
def test_recovery_zone_thresholds():
    assert rds.recovery_zone(100) == "GREEN"
    assert rds.recovery_zone(67) == "GREEN"  # boundary inclusive
    assert rds.recovery_zone(66.999) == "YELLOW"
    assert rds.recovery_zone(34) == "YELLOW"  # boundary inclusive
    assert rds.recovery_zone(33.999) == "RED"
    assert rds.recovery_zone(0) == "RED"


# --------------------------------------------------------------------------- #
# strain_band thresholds (9 / 13 / 17)
# --------------------------------------------------------------------------- #
def test_strain_band_thresholds():
    assert rds.strain_band(0) == "Light"
    assert rds.strain_band(9) == "Light"  # boundary inclusive
    assert rds.strain_band(9.001) == "Moderate"
    assert rds.strain_band(13) == "Moderate"  # boundary inclusive
    assert rds.strain_band(13.001) == "Strenuous"
    assert rds.strain_band(17) == "Strenuous"  # boundary inclusive
    assert rds.strain_band(17.001) == "All-out"
    assert rds.strain_band(21) == "All-out"


# --------------------------------------------------------------------------- #
# build_model — trailing baseline excludes the current day
# --------------------------------------------------------------------------- #
def _day(i, hrv, rhr, sleep_h=None, steps=0, active_kcal=0, workout_min=0):
    return {
        "date": dt.date(2026, 1, 1) + dt.timedelta(days=i),
        "hrv": hrv,
        "rhr": rhr,
        "sleep_h": sleep_h,
        "steps": steps,
        "active_kcal": active_kcal,
        "workout_min": workout_min,
    }


def test_build_model_baseline_excludes_current_day():
    # Prior 4 days hrv = 30,50,50,70 -> mean=50, std=sqrt(200)=14.142...
    # rhr constant 60 -> rhr_std 0 -> rhr_c=50; sleep None -> sleep_c=50.
    # Today's hrv = mean + 1*std -> z=1 -> hrv_c=75.
    # recovery = 0.60*75 + 0.20*50 + 0.20*50 = 65.0 EXACTLY — only true if the
    # baseline is the trailing window and does NOT include today's value (which
    # would shift mean/std and change the z-score).
    std = math.sqrt(200.0)
    days = [
        _day(0, 30, 60),
        _day(1, 50, 60),
        _day(2, 50, 60),
        _day(3, 70, 60),
        _day(4, 50.0 + std, 60),
    ]
    model = rds.build_model(days)
    assert model["latest"]["recovery"] == pytest.approx(65.0)


def test_build_model_first_day_has_empty_baseline():
    # Day 0 has no trailing window -> mean/std 0 -> z=0 for hrv & rhr -> both 50.
    # sleep None -> sleep_c 50 -> recovery 50.
    days = [_day(0, 999, 999)]
    model = rds.build_model(days)
    assert model["latest"]["recovery"] == pytest.approx(50.0)


def test_build_model_single_prior_day_has_zero_std():
    # With exactly one prior day, baseline std is 0 -> z forced to 0 regardless of
    # how extreme today's value is. Confirms the current day is excluded AND that
    # a degenerate (std=0) baseline neutralizes the z-score.
    days = [_day(0, 50, 60), _day(1, 100, 30)]
    model = rds.build_model(days)
    # hrv_c=rhr_c=50, sleep None -> 50.
    assert model["latest"]["recovery"] == pytest.approx(50.0)


def test_build_model_display_window_is_capped():
    model = rds.build_model(rds.demo_days(60))
    assert len(model["display"]) == rds.DISPLAY_DAYS


def test_build_model_latest_is_last_day():
    days = [_day(i, 40 + i, 60) for i in range(5)]
    model = rds.build_model(days)
    assert rds._as_date(model["latest"]["date"]) == dt.date(2026, 1, 5)


def test_build_model_streaks_count_from_newest_backwards():
    # rhr: 65,55,55,55 (ascending) -> trailing "RHR < 60" streak is 3 (day0=65 breaks).
    days = [
        _day(0, 40, 65, sleep_h=8.0, steps=12000),
        _day(1, 40, 55, sleep_h=8.0, steps=12000),
        _day(2, 40, 55, sleep_h=8.0, steps=12000),
        _day(3, 40, 55, sleep_h=8.0, steps=12000),
    ]
    streaks = rds.build_model(days)["streaks"]
    assert streaks["RHR < 60"] == 3
    assert streaks["Sleep ≥ 7.5h"] == 4
    assert streaks["Steps ≥ 10k"] == 4
    assert streaks["HRV ≥ 38"] == 4


def test_build_model_scores_stay_in_range_on_demo_data():
    model = rds.build_model(rds.demo_days(60))
    for row in model["display"]:
        if row["recovery"] is not None:
            assert 0.0 <= row["recovery"] <= 100.0
        assert 0.0 <= row["strain"] <= 21.0
        if row["sleep"] is not None:
            assert 0.0 <= row["sleep"] <= 100.0
