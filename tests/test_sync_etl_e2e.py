"""End-to-end test of the "Sync" pipeline against an ISOLATED Neo4j database.

This exercises the real ETL chain exactly as the batch loader runs it:

    generate_test_data.generate()  -> a synthetic Apple Health export.xml
    parse_health_xml.parse_health_export() -> HealthExport
    transform.transform()                  -> TransformedData
    load_to_neo4j.load_all()               -> writes the graph

Everything is written to the isolated enterprise database provided by the
``e2e_db`` fixture (never the developer's real ``neo4j`` database). We point the
production loader at that database by setting NEO4J_URI/USER/PASSWORD/DATABASE
from the fixture, then importing ``load_to_neo4j`` fresh so its module-level
``DATABASE = os.environ.get("NEO4J_DATABASE")`` picks up the isolated db.

Assertions cover the graph shape the iPhone sync relies on:
  - DailySummary nodes ~= number of days generated
  - (Day)-[:HAS_SUMMARY]->(DailySummary)
  - (Day)-[:NEXT_DAY]->(Day) chain
  - Workout nodes loaded and linked to days
And finally that re-running the load is idempotent (MERGE => counts unchanged).
"""

from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ETL_DIR = REPO_ROOT / "etl"

# The ETL modules import each other by bare name (``from transform import ...``),
# so the etl/ directory must be importable.
if str(ETL_DIR) not in sys.path:
    sys.path.insert(0, str(ETL_DIR))

DAYS = 40
PERSONA = "default"
SEED = 1234  # reproducible export so counts are stable across runs

pytestmark = pytest.mark.e2e


def _point_etl_at_isolated_db(e2e_db, monkeypatch):
    """Set the env so production ETL targets the isolated database, then
    (re)import load_to_neo4j so its module-level DATABASE picks up the value."""
    for key, value in e2e_db.env.items():
        monkeypatch.setenv(key, value)

    # parse/transform have no DB coupling; load_to_neo4j caches NEO4J_DATABASE at
    # import time, so import it AFTER the env is set (and reload if already imported).
    import load_to_neo4j as loader  # noqa: WPS433 (local import is intentional)

    loader = importlib.reload(loader)
    assert loader.DATABASE == e2e_db.name, (
        f"loader is pointed at {loader.DATABASE!r}, expected isolated db " f"{e2e_db.name!r}"
    )
    return loader


@pytest.fixture(scope="module")
def synthetic_export(tmp_path_factory):
    """Generate a small synthetic Apple Health export.xml once for this module."""
    import generate_test_data

    out = tmp_path_factory.mktemp("health_export") / "export.xml"
    # Quiet down generate()'s prints — they go to stdout; pytest captures anyway.
    generate_test_data.generate(days=DAYS, output=str(out), persona=PERSONA, seed=SEED)
    assert out.exists() and out.stat().st_size > 0, "export.xml was not generated"
    return out


@pytest.fixture(scope="module")
def parsed_and_transformed(synthetic_export):
    """Run the real parse + transform stages on the synthetic export."""
    import parse_health_xml
    import transform as transform_mod

    # Keep the parser quiet (no tqdm bar / info spam in test output).
    logging.getLogger("parse_health_xml").setLevel(logging.ERROR)

    export = parse_health_xml.parse_health_export(str(synthetic_export), progress=False)
    data = transform_mod.transform(export)
    return export, data


def _load(loader, export, data):
    driver = loader.get_driver()
    try:
        loader.load_all(driver, export, data)
    finally:
        driver.close()


def _counts(e2e_db) -> dict:
    """Snapshot the graph counts we care about, from the isolated database."""
    recs = e2e_db.execute_query(
        """
        RETURN
          count { (s:DailySummary) }                       AS daily_summaries,
          count { (d:Day) }                                AS days,
          count { (:Day)-[:HAS_SUMMARY]->(:DailySummary) } AS has_summary,
          count { (:Day)-[:NEXT_DAY]->(:Day) }             AS next_day,
          count { (w:Workout) }                            AS workouts,
          count { (:Workout)-[:ON_DAY]->(:Day) }           AS workout_on_day,
          count { (:Week) }                                AS weeks
        """
    )
    return dict(recs[0])


def test_sync_etl_loads_expected_graph(e2e_db, monkeypatch, parsed_and_transformed):
    """Full ETL load produces the expected node/relationship shape."""
    export, data = parsed_and_transformed
    loader = _point_etl_at_isolated_db(e2e_db, monkeypatch)

    # The generator logs sleep for the *previous* night on each day, so the
    # transform yields ~DAYS summaries (one leading sleep-only day is expected).
    n_summaries = len(data.daily_summaries)
    assert (
        n_summaries >= DAYS
    ), f"transform produced {n_summaries} daily summaries, expected >= {DAYS}"
    assert len(export.workouts) > 0, "synthetic export should contain workouts"

    _load(loader, export, data)

    c = _counts(e2e_db)

    # DailySummary count > 0 and matches what transform produced.
    assert c["daily_summaries"] > 0
    assert (
        c["daily_summaries"] == n_summaries
    ), f"expected {n_summaries} DailySummary nodes, got {c['daily_summaries']}"

    # One Day per summary, each with exactly one HAS_SUMMARY edge.
    assert c["days"] == n_summaries
    assert (
        c["has_summary"] == n_summaries
    ), "every Day should have one HAS_SUMMARY edge to its DailySummary"

    # NEXT_DAY chain: a fully linked chain of N days has N-1 edges.
    assert (
        c["next_day"] == c["days"] - 1
    ), f"expected a NEXT_DAY chain of {c['days'] - 1} edges, got {c['next_day']}"

    # Workouts loaded and linked to their day.
    assert c["workouts"] > 0, "no Workout nodes loaded"
    assert (
        c["workout_on_day"] == c["workouts"]
    ), "every Workout should be linked to a Day via ON_DAY"

    # Weeks exist and days are bucketed into them.
    assert c["weeks"] > 0


def test_sync_etl_is_idempotent_on_rerun(e2e_db, monkeypatch, parsed_and_transformed):
    """Re-running the load must not duplicate anything (MERGE semantics)."""
    export, data = parsed_and_transformed
    loader = _point_etl_at_isolated_db(e2e_db, monkeypatch)

    # Ensure data is present (this test may run before or after the shape test;
    # loading once here guarantees a baseline regardless of ordering).
    _load(loader, export, data)
    before = _counts(e2e_db)

    # Second identical load — counts must be unchanged.
    _load(loader, export, data)
    after = _counts(e2e_db)

    assert after == before, (
        "re-running the ETL changed the graph; MERGE is not idempotent.\n"
        f"before={before}\nafter={after}"
    )


def test_sync_etl_did_not_touch_default_neo4j_db(e2e_db, monkeypatch, parsed_and_transformed):
    """Belt-and-braces: the ETL writes ONLY to the isolated db, never 'neo4j'.

    We mark our isolated DailySummary nodes by checking that the default
    'neo4j' database has no DailySummary with a date in our synthetic range.
    We only READ from 'neo4j' here — never write.
    """
    export, data = parsed_and_transformed
    loader = _point_etl_at_isolated_db(e2e_db, monkeypatch)
    _load(loader, export, data)

    # The synthetic dates we just loaded.
    sample_date = next(iter(data.daily_summaries.keys()))

    # READ-ONLY against the default 'neo4j' database.
    records, _, _ = e2e_db.driver.execute_query(
        "MATCH (s:DailySummary {date: date($d)}) RETURN count(s) AS c",
        d=sample_date,
        database_="neo4j",
    )
    assert records[0]["c"] == 0, "ETL leaked a DailySummary into the default 'neo4j' database"

    # And it IS present in the isolated db.
    iso = e2e_db.execute_query(
        "MATCH (s:DailySummary {date: date($d)}) RETURN count(s) AS c", d=sample_date
    )
    assert iso[0]["c"] == 1
