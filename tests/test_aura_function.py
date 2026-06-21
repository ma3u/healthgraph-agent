"""Tests for the "Aura function" — the GraphQL Data API ingest mutations.

The Aura GraphQL Data API exposes custom ``ingestDay`` / ``ingestWorkout`` /
``ingestSleep`` mutations whose behavior is defined entirely by the ``@cypher``
statements in ``cypher/graphql_schema.graphql``. Those statements are the real
"function" the iPhone app calls to upsert one day / workout / sleep session.

This test extracts those exact MERGE statements from the SDL and runs them
against the ISOLATED database (via the ``e2e_db`` fixture), passing ``$input``
as a parameter map — the same shape the GraphQL layer binds. We assert the
nodes/relationships are created and that re-running is idempotent.

An OPTIONAL live test (marked ``live``) POSTs a real ingestDay mutation to the
deployed Aura GraphQL Data API. It is skipped unless AURA_GRAPHQL_URL and
AURA_GRAPHQL_API_KEY are set AND RUN_LIVE=1, so the default test run never hits
the network or the user's real Aura instance.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "cypher" / "graphql_schema.graphql"

pytestmark = pytest.mark.e2e


# --------------------------------------------------------------------------- #
# Extract the @cypher MERGE statements from the GraphQL SDL.
# --------------------------------------------------------------------------- #
def _extract_cypher_statements(sdl: str) -> dict[str, str]:
    """Map mutation name -> the Cypher body inside its @cypher(statement: \"\"\"...\"\"\").

    The SDL declares each custom mutation as::

        ingestDay(input: ...): String!
          @cypher(statement: \"\"\"
            ...cypher...
          \"\"\", columnName: "date")

    We find each ``<name>(`` declaration, then the first triple-quoted block that
    follows it, which is the @cypher statement body.
    """
    statements: dict[str, str] = {}
    for name in ("ingestDay", "ingestWorkout", "ingestSleep"):
        # Locate the mutation declaration, then the next triple-quoted block.
        decl = re.search(rf"\b{name}\s*\(", sdl)
        assert decl, f"mutation {name} not found in SDL"
        body_match = re.search(r'"""(.*?)"""', sdl[decl.end() :], re.DOTALL)
        assert body_match, f"@cypher statement block not found for {name}"
        statements[name] = body_match.group(1).strip()
    return statements


@pytest.fixture(scope="module")
def cypher_statements() -> dict[str, str]:
    assert SCHEMA_PATH.exists(), f"schema not found: {SCHEMA_PATH}"
    sdl = SCHEMA_PATH.read_text()
    stmts = _extract_cypher_statements(sdl)
    # Sanity: each extracted body should be a MERGE upsert that returns something.
    for name, body in stmts.items():
        assert "MERGE" in body, f"{name} body is not a MERGE upsert:\n{body}"
        assert "$input" in body, f"{name} body does not reference $input:\n{body}"
        assert "RETURN" in body, f"{name} body has no RETURN:\n{body}"
    return stmts


# Sample params matching the GraphQL *UpsertInput shapes (camelCase keys, as the
# @cypher statements reference $input.avgHeartRate etc.).
DAY_INPUT = {
    "date": "2026-03-01",
    "dayOfWeek": "Sunday",
    "weekIso": "2026-W09",
    "avgHeartRate": 62.0,
    "minHeartRate": 48.0,
    "maxHeartRate": 142.0,
    "restingHeartRate": 55.0,
    "hrvMean": 48.0,
    "totalSteps": 9000.0,
    "totalDistanceKm": 6.5,
    "activeEnergyKcal": 520.0,
    "basalEnergyKcal": 1650.0,
    "flightsClimbed": 8.0,
    "avgBloodOxygen": 97.0,
    "avgRespiratoryRate": 15.0,
    "bodyMassKg": 77.5,
    "vo2max": 39.0,
    "sleepHours": 7.4,
    "workoutCount": 1,
    "workoutMinutes": 35.0,
    "description": "A solid Sunday.",
}

WORKOUT_INPUT = {
    "uid": "Running_2026-03-01 07:15:00",
    "activityType": "Running",
    "startDate": "2026-03-01T07:15:00",
    "endDate": "2026-03-01T07:50:00",
    "durationMin": 35.0,
    "device": "Apple Watch",
    "sourceName": "Apple Watch",
}

SLEEP_INPUT = {
    "date": "2026-03-01",
    "asleepMinutes": 444.0,
    "inBedMinutes": 470.0,
    "sourceName": "Apple Watch",
}


def test_ingest_day_creates_day_and_summary(e2e_db, cypher_statements):
    """ingestDay MERGEs a Day + DailySummary and links them; idempotent on re-run."""
    stmt = cypher_statements["ingestDay"]

    # First run.
    recs = e2e_db.execute_query(stmt, input=DAY_INPUT)
    assert recs[0]["date"] == DAY_INPUT["date"]

    counts = e2e_db.execute_query(
        """
        RETURN
          count { (d:Day {date: date($d)}) }                       AS days,
          count { (s:DailySummary {date: date($d)}) }              AS summaries,
          count { (:Day {date: date($d)})-[:HAS_SUMMARY]->
                  (:DailySummary {date: date($d)}) }               AS has_summary,
          count { (:Day {date: date($d)})-[:PART_OF]->(:Week) }    AS part_of_week
        """,
        d=DAY_INPUT["date"],
    )[0]
    assert counts["days"] == 1
    assert counts["summaries"] == 1
    assert counts["has_summary"] == 1
    assert counts["part_of_week"] == 1, "weekIso should create a PART_OF edge"

    # Verify a couple of properties round-tripped through the alias mapping.
    props = e2e_db.execute_query(
        "MATCH (s:DailySummary {date: date($d)}) "
        "RETURN s.avg_heart_rate AS hr, s.total_steps AS steps, s.description AS desc",
        d=DAY_INPUT["date"],
    )[0]
    assert props["hr"] == DAY_INPUT["avgHeartRate"]
    assert props["steps"] == DAY_INPUT["totalSteps"]
    assert props["desc"] == DAY_INPUT["description"]

    # Idempotent re-run: counts unchanged.
    e2e_db.execute_query(stmt, input=DAY_INPUT)
    after = e2e_db.execute_query(
        """
        RETURN count { (d:Day {date: date($d)}) }          AS days,
               count { (s:DailySummary {date: date($d)}) }  AS summaries
        """,
        d=DAY_INPUT["date"],
    )[0]
    assert after["days"] == 1
    assert after["summaries"] == 1


def test_ingest_workout_creates_workout_on_day(e2e_db, cypher_statements):
    """ingestWorkout MERGEs a Workout, derives its Day, and links ON_DAY."""
    stmt = cypher_statements["ingestWorkout"]

    recs = e2e_db.execute_query(stmt, input=WORKOUT_INPUT)
    assert recs[0]["uid"] == WORKOUT_INPUT["uid"]

    counts = e2e_db.execute_query(
        """
        RETURN
          count { (w:Workout {uid: $uid}) }                  AS workouts,
          count { (:Workout {uid: $uid})-[:ON_DAY]->
                  (:Day {date: date($d)}) }                  AS on_day
        """,
        uid=WORKOUT_INPUT["uid"],
        d="2026-03-01",  # derived from startDate
    )[0]
    assert counts["workouts"] == 1
    assert counts["on_day"] == 1, "Workout should be linked to the day of its startDate"

    props = e2e_db.execute_query(
        "MATCH (w:Workout {uid: $uid}) " "RETURN w.activity_type AS at, w.duration_min AS dur",
        uid=WORKOUT_INPUT["uid"],
    )[0]
    assert props["at"] == WORKOUT_INPUT["activityType"]
    assert props["dur"] == WORKOUT_INPUT["durationMin"]

    # Idempotent.
    e2e_db.execute_query(stmt, input=WORKOUT_INPUT)
    again = e2e_db.execute_query(
        "RETURN count { (w:Workout {uid: $uid}) } AS workouts, "
        "count { (:Workout {uid: $uid})-[:ON_DAY]->(:Day) } AS on_day",
        uid=WORKOUT_INPUT["uid"],
    )[0]
    assert again["workouts"] == 1
    assert again["on_day"] == 1


def test_ingest_sleep_creates_session_on_day(e2e_db, cypher_statements):
    """ingestSleep MERGEs a SleepSession keyed by date and links ON_DAY."""
    stmt = cypher_statements["ingestSleep"]

    recs = e2e_db.execute_query(stmt, input=SLEEP_INPUT)
    assert recs[0]["date"] == SLEEP_INPUT["date"]

    counts = e2e_db.execute_query(
        """
        RETURN
          count { (s:SleepSession {date: date($d)}) }   AS sessions,
          count { (:SleepSession {date: date($d)})-[:ON_DAY]->
                  (:Day {date: date($d)}) }             AS on_day
        """,
        d=SLEEP_INPUT["date"],
    )[0]
    assert counts["sessions"] == 1
    assert counts["on_day"] == 1

    props = e2e_db.execute_query(
        "MATCH (s:SleepSession {date: date($d)}) "
        "RETURN s.asleep_minutes AS am, s.in_bed_minutes AS ibm",
        d=SLEEP_INPUT["date"],
    )[0]
    assert props["am"] == SLEEP_INPUT["asleepMinutes"]
    assert props["ibm"] == SLEEP_INPUT["inBedMinutes"]

    # Idempotent.
    e2e_db.execute_query(stmt, input=SLEEP_INPUT)
    again = e2e_db.execute_query(
        "RETURN count { (s:SleepSession {date: date($d)}) } AS sessions",
        d=SLEEP_INPUT["date"],
    )[0]
    assert again["sessions"] == 1


# --------------------------------------------------------------------------- #
# OPTIONAL live test — hits the real Aura GraphQL Data API.
# --------------------------------------------------------------------------- #
_LIVE_URL = os.environ.get("AURA_GRAPHQL_URL")
_LIVE_KEY = os.environ.get("AURA_GRAPHQL_API_KEY")
_RUN_LIVE = os.environ.get("RUN_LIVE") == "1"

_live_skip_reason = (
    "live Aura test disabled — set RUN_LIVE=1 AND AURA_GRAPHQL_URL AND "
    "AURA_GRAPHQL_API_KEY to enable"
)


@pytest.mark.live
@pytest.mark.skipif(not (_RUN_LIVE and _LIVE_URL and _LIVE_KEY), reason=_live_skip_reason)
def test_live_ingest_day_against_real_aura():
    """POST a real ingestDay mutation to the deployed Aura GraphQL Data API.

    Opt-in only. Writes a clearly-marked probe day far in the future so it is
    obvious it came from a test if it ever lands in a real instance.
    """
    mutation = "mutation ($input: DailySummaryUpsertInput!) " "{ ingestDay(input: $input) }"
    probe = {
        "date": "2099-12-31",
        "dayOfWeek": "Thursday",
        "avgHeartRate": 60.0,
        "totalSteps": 1.0,
        "description": "E2E live probe — safe to delete.",
    }
    payload = json.dumps({"query": mutation, "variables": {"input": probe}}).encode()

    req = urllib.request.Request(
        _LIVE_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": _LIVE_KEY,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())

    assert "errors" not in body, f"GraphQL errors: {body.get('errors')}"
    assert body["data"]["ingestDay"] == probe["date"], f"unexpected ingestDay result: {body!r}"
