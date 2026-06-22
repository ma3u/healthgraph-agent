"""Tests for the Cronometer silo connector.

Two layers:

* **Parser unit tests** (no database) — drive the pure parsing functions in
  ``etl/load_cronometer.py`` against the synthetic sample CSVs shipped in
  ``docs/connectors/cronometer/sample/``. These assert the tricky real-world
  cases: ``"2,154.5"`` thousands separators, the ``µg`` micro sign, blank cells
  skipped (not zeroed), header-name parsing, and repeating same-day biometrics.

* **E2E load test** (``e2e_db``) — loads the parsed Observations into an isolated
  enterprise database via the reusable spine (``observation_model``) and asserts
  the graph shape + idempotency, exactly as ``python etl/load_cronometer.py``
  would. Skips cleanly if no local Neo4j Enterprise is available.
"""

from __future__ import annotations

import importlib
import sys
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ETL_DIR = REPO_ROOT / "etl"

# The ETL modules import each other by bare name, so etl/ must be importable.
if str(ETL_DIR) not in sys.path:
    sys.path.insert(0, str(ETL_DIR))

import load_cronometer as crono  # noqa: E402 (after sys.path tweak)

SAMPLE_DIR = REPO_ROOT / "docs" / "connectors" / "cronometer" / "sample"
NUTRITION_CSV = SAMPLE_DIR / "daily-nutrition.csv"
BIOMETRICS_CSV = SAMPLE_DIR / "biometrics.csv"


# --------------------------------------------------------------------------- #
# Cell-level parsing
# --------------------------------------------------------------------------- #
def test_parse_header_splits_name_and_unit():
    assert crono.parse_header("Energy (kcal)") == ("Energy", "kcal")
    assert crono.parse_header("Net Carbs (g)") == ("Net Carbs", "g")
    # Nested parens: take the LAST parenthetical as the unit.
    assert crono.parse_header("B12 (Cobalamin) (µg)") == ("B12 (Cobalamin)", "µg")
    # No unit -> empty unit string.
    assert crono.parse_header("Completed") == ("Completed", "")


def test_parse_number_handles_thousands_and_blanks():
    assert crono.parse_number("2,154.5") == 2154.5  # US: comma thousands
    assert crono.parse_number("71.9") == 71.9
    assert crono.parse_number("92") == 92.0
    assert crono.parse_number("2,154") == 2154.0  # lone comma + 3 digits = thousands
    assert crono.parse_number("1,234,567") == 1234567.0
    assert crono.parse_number("") is None
    assert crono.parse_number("   ") is None
    assert crono.parse_number(None) is None
    assert crono.parse_number("n/a") is None


def test_parse_number_european_locale():
    """German/EU exports use a decimal comma — must not 10x the value."""
    assert crono.parse_number("78,4") == 78.4  # decimal comma, NOT 784
    assert crono.parse_number("18,25") == 18.25
    assert crono.parse_number("2.154,5") == 2154.5  # dot thousands, comma decimal
    assert crono.parse_number("1.234.567,8") == 1234567.8


def test_parse_date_accepts_iso_slash_and_datetime():
    assert crono.parse_date("2026-06-01") == date(2026, 6, 1)
    assert crono.parse_date("06/15/2026") == date(2026, 6, 15)  # US m/d/Y
    assert crono.parse_date("2026-06-01T08:05:00") == date(2026, 6, 1)  # ISO datetime
    with pytest.raises(ValueError):
        crono.parse_date("not a date")


# --------------------------------------------------------------------------- #
# Daily Nutrition file
# --------------------------------------------------------------------------- #
def test_parse_daily_nutrition_counts_and_skips_blanks():
    obs = crono.parse_daily_nutrition(NUTRITION_CSV)
    # 5 rows x 11 nutrient cols, minus 4 blanks on 2026-06-03 = 51.
    assert len(obs) == 51
    # Date / Completed are never emitted as observations.
    assert all(o.type not in ("Date", "Completed") for o in obs)
    assert all(o.category == "nutrition" for o in obs)
    # The blank row keeps only its 7 non-empty nutrients.
    june3 = [o for o in obs if o.date == "2026-06-03"]
    assert len(june3) == 7


def test_parse_daily_nutrition_values_units_and_thousands():
    obs = crono.parse_daily_nutrition(NUTRITION_CSV)
    energy = next(o for o in obs if o.date == "2026-06-01" and o.type == "Energy")
    assert energy.value == 2154.5  # parsed from "2,154.5"
    assert energy.unit == "kcal"
    # Micro sign survives the UTF-8 round trip.
    b12 = next(o for o in obs if o.date == "2026-06-01" and o.type.startswith("B12"))
    assert b12.unit == "µg"
    # day_of_week is set (so any Day this creates matches the Apple-Health ETL).
    assert energy.day_of_week == "Monday"  # 2026-06-01 is a Monday


def test_nutrition_keys_are_unique_per_day_type():
    obs = crono.parse_daily_nutrition(NUTRITION_CSV)
    keys = [o.key for o in obs]
    assert len(keys) == len(set(keys)), "nutrition observation keys must be unique"
    # No seq segment for once-a-day values.
    assert all(o.seq is None for o in obs)


# --------------------------------------------------------------------------- #
# Biometrics file
# --------------------------------------------------------------------------- #
def test_parse_biometrics_basic_mapping():
    obs = crono.parse_biometrics(BIOMETRICS_CSV)
    assert len(obs) == 9
    assert all(o.category == "biometric" for o in obs)
    bodyfat = next(o for o in obs if o.type == "Body Fat")
    assert bodyfat.unit == "%"
    hrv = next(o for o in obs if o.type == "HRV")
    assert hrv.unit == "ms" and hrv.value == 64.0


def test_biometrics_repeated_same_day_metric_stays_distinct():
    obs = crono.parse_biometrics(BIOMETRICS_CSV)
    weights_0601 = [o for o in obs if o.date == "2026-06-01" and o.type == "Weight"]
    assert len(weights_0601) == 2  # two weigh-ins
    assert {o.seq for o in weights_0601} == {0, 1}
    assert len({o.key for o in weights_0601}) == 2  # distinct keys -> both survive
    # All keys across the file are unique (idempotent re-import).
    keys = [o.key for o in obs]
    assert len(keys) == len(set(keys))


def test_biometrics_keys_are_row_order_independent(tmp_path):
    """A re-export with rows in a different order must yield the SAME keys, so a
    re-import stays idempotent even for metrics logged several times a day."""
    original = BIOMETRICS_CSV.read_text(encoding="utf-8").splitlines()
    header, rows = original[0], original[1:]
    shuffled = tmp_path / "biometrics_shuffled.csv"
    shuffled.write_text("\n".join([header, *reversed(rows)]) + "\n", encoding="utf-8")

    keys_a = {o.key for o in crono.parse_biometrics(BIOMETRICS_CSV)}
    keys_b = {o.key for o in crono.parse_biometrics(shuffled)}
    assert keys_a == keys_b


# --------------------------------------------------------------------------- #
# E2E: load into an isolated Neo4j and check the graph + idempotency
# --------------------------------------------------------------------------- #
def _point_connector_at_isolated_db(e2e_db, monkeypatch):
    """Point the spine + connector at the isolated db, reloading so module-level
    DATABASE/NEO4J_* are picked up (same pattern as test_sync_etl_e2e)."""
    for key, value in e2e_db.env.items():
        monkeypatch.setenv(key, value)

    import observation_model

    observation_model = importlib.reload(observation_model)
    assert observation_model.DATABASE == e2e_db.name

    # Reload the connector AFTER the spine, so its `from observation_model import …`
    # rebinds to the reloaded module.
    connector = importlib.reload(crono)
    return observation_model, connector


@pytest.mark.e2e
def test_load_cronometer_into_graph(e2e_db, monkeypatch):
    obs_mod, connector = _point_connector_at_isolated_db(e2e_db, monkeypatch)

    observations = connector.parse_daily_nutrition(NUTRITION_CSV) + connector.parse_biometrics(
        BIOMETRICS_CSV
    )
    assert len(observations) == 60  # 51 nutrition + 9 biometric

    driver = obs_mod.get_driver()
    try:
        written = obs_mod.load_observations(driver, observations, create_days=True)
        assert written == 60

        # The source landed.
        rec = e2e_db.execute_query("MATCH (s:Source {name:'cronometer'}) RETURN count(s) AS n")
        assert rec[0]["n"] == 1

        # Every observation exists and is ON_DAY-linked.
        rec = e2e_db.execute_query("MATCH (o:Observation) RETURN count(o) AS n")
        assert rec[0]["n"] == 60
        rec = e2e_db.execute_query(
            "MATCH (:Observation)-[:ON_DAY]->(d:Day) RETURN count(*) AS links, "
            "count(DISTINCT d) AS days"
        )
        assert rec[0]["links"] == 60
        assert rec[0]["days"] == 5  # 2026-06-01 .. 2026-06-05

        # Day creation set day_of_week (matches the Apple-Health ETL).
        rec = e2e_db.execute_query(
            "MATCH (d:Day {date: date('2026-06-01')}) RETURN d.day_of_week AS dow"
        )
        assert rec[0]["dow"] == "Monday"

        # Both weigh-ins on 2026-06-01 survived.
        rec = e2e_db.execute_query(
            "MATCH (o:Observation {source:'cronometer', type:'Weight'})-[:ON_DAY]->"
            "(:Day {date: date('2026-06-01')}) RETURN count(o) AS n"
        )
        assert rec[0]["n"] == 2

        # The thousands-separated energy made it through as a real number.
        rec = e2e_db.execute_query(
            "MATCH (o:Observation {source:'cronometer', type:'Energy'})-[:ON_DAY]->"
            "(:Day {date: date('2026-06-01')}) RETURN o.value AS kcal"
        )
        assert rec[0]["kcal"] == 2154.5

        # Idempotency: re-loading the same data changes nothing.
        obs_mod.load_observations(driver, observations, create_days=True)
        rec = e2e_db.execute_query("MATCH (o:Observation) RETURN count(o) AS n")
        assert rec[0]["n"] == 60
        rec = e2e_db.execute_query("MATCH (:Observation)-[:ON_DAY]->(:Day) RETURN count(*) AS n")
        assert rec[0]["n"] == 60
    finally:
        driver.close()
