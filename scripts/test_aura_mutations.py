#!/usr/bin/env python3
"""Smoke-test the @cypher mutation bodies from cypher/graphql_schema.graphql
against the real Aura instance, using .env credentials.

This proves the mutations are correct *before* you finish the Auth0 + Aura
GraphQL Data API setup. When the GraphQL Data API is eventually wired up,
it will run the same Cypher with the same parameters — so a green run here
is a strong signal that the iOS path will work end-to-end.

Uses a test date (2099-01-01) and synthetic source names so nothing
collides with real data, then cleans up everything it created.

Run from repo root:
  backend/.venv/bin/python scripts/test_aura_mutations.py
"""

from __future__ import annotations

import os
import sys
import logging
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("test_aura_mutations")

TEST_DAY = "2099-01-01"
TEST_WORKOUT_UID = "HealthGraphSync-Test-Workout-2099"
TEST_SOURCE = "HealthGraphSync-Test"


# These Cypher bodies are copy-pasted from cypher/graphql_schema.graphql
# (the @cypher directives on ingestDay / ingestWorkout / ingestSleep). When
# the Aura GraphQL Data API parses the SDL, it runs exactly these statements
# with $input bound to the GraphQL mutation argument.

INGEST_DAY_CYPHER = """
MERGE (d:Day {date: date($input.date)})
  ON CREATE SET d.day_of_week = $input.dayOfWeek
MERGE (s:DailySummary {date: date($input.date)})
SET s.avg_heart_rate     = $input.avgHeartRate,
    s.min_heart_rate     = $input.minHeartRate,
    s.max_heart_rate     = $input.maxHeartRate,
    s.resting_heart_rate = $input.restingHeartRate,
    s.hrv_mean           = $input.hrvMean,
    s.total_steps        = $input.totalSteps,
    s.total_distance_km  = $input.totalDistanceKm,
    s.active_energy_kcal = $input.activeEnergyKcal,
    s.basal_energy_kcal  = $input.basalEnergyKcal,
    s.flights_climbed    = $input.flightsClimbed,
    s.avg_blood_oxygen   = $input.avgBloodOxygen,
    s.avg_respiratory_rate = $input.avgRespiratoryRate,
    s.body_mass_kg       = $input.bodyMassKg,
    s.vo2max             = $input.vo2max,
    s.sleep_hours        = $input.sleepHours,
    s.workout_count      = $input.workoutCount,
    s.workout_minutes    = $input.workoutMinutes,
    s.description        = $input.description
MERGE (d)-[:HAS_SUMMARY]->(s)
FOREACH (_ IN CASE WHEN $input.weekIso IS NULL THEN [] ELSE [1] END |
  MERGE (w:Week {iso: $input.weekIso})
  MERGE (d)-[:PART_OF]->(w)
)
RETURN toString(d.date) AS date
"""

INGEST_WORKOUT_CYPHER = """
MERGE (w:Workout {uid: $input.uid})
SET w.activity_type = $input.activityType,
    w.start_date    = datetime($input.startDate),
    w.end_date      = datetime($input.endDate),
    w.duration_min  = $input.durationMin,
    w.device        = $input.device,
    w.source_name   = $input.sourceName
WITH w, date(datetime($input.startDate)) AS dayDate
MERGE (d:Day {date: dayDate})
MERGE (w)-[:ON_DAY]->(d)
RETURN w.uid AS uid
"""

INGEST_SLEEP_CYPHER = """
MERGE (s:SleepSession {date: date($input.date)})
SET s.asleep_minutes = $input.asleepMinutes,
    s.in_bed_minutes = $input.inBedMinutes,
    s.source_name    = $input.sourceName
MERGE (d:Day {date: date($input.date)})
MERGE (s)-[:ON_DAY]->(d)
RETURN toString(s.date) AS date
"""


def driver_from_env():
    uri = os.environ.get("NEO4J_URI")
    user = os.environ.get("NEO4J_USER", "neo4j")
    pw = os.environ.get("NEO4J_PASSWORD")
    if not uri or not pw:
        log.error("NEO4J_URI / NEO4J_PASSWORD not set in .env")
        sys.exit(1)
    return GraphDatabase.driver(uri, auth=(user, pw))


def baseline_counts(s) -> dict[str, int]:
    return {
        "Day": s.run("MATCH (n:Day) RETURN count(n) AS c").single()["c"],
        "DailySummary": s.run("MATCH (n:DailySummary) RETURN count(n) AS c").single()["c"],
        "Workout": s.run("MATCH (n:Workout) RETURN count(n) AS c").single()["c"],
        "SleepSession": s.run("MATCH (n:SleepSession) RETURN count(n) AS c").single()["c"],
        "Week": s.run("MATCH (n:Week) RETURN count(n) AS c").single()["c"],
    }


def main() -> int:
    driver = driver_from_env()
    failed: list[str] = []

    try:
        with driver.session() as session:
            log.info("Baseline counts:")
            before = baseline_counts(session)
            for k, v in before.items():
                log.info(f"  {k}: {v:,}")

            # ---------- 1) ingestDay ----------
            day_input = {
                "date": TEST_DAY,
                "dayOfWeek": "Thursday",
                "weekIso": "2099-W01",
                "avgHeartRate": 64.0,
                "minHeartRate": 48.0,
                "maxHeartRate": 142.0,
                "restingHeartRate": 52.0,
                "hrvMean": 48.7,
                "totalSteps": 11342.0,
                "totalDistanceKm": 8.4,
                "activeEnergyKcal": 612.0,
                "basalEnergyKcal": 1680.0,
                "flightsClimbed": 12.0,
                "avgBloodOxygen": 97.5,
                "avgRespiratoryRate": 14.2,
                "bodyMassKg": 78.4,
                "vo2max": 42.1,
                "sleepHours": 7.3,
                "workoutCount": 1,
                "workoutMinutes": 31.0,
                "description": "test record from scripts/test_aura_mutations.py",
            }
            try:
                rec = session.run(INGEST_DAY_CYPHER, input=day_input).single()
                log.info(f"ingestDay → returned date={rec['date']}")
                # Verify
                verify = session.run(
                    "MATCH (d:Day {date: date($d)})-[:HAS_SUMMARY]->(s:DailySummary) "
                    "RETURN s.avg_heart_rate AS hr, s.total_steps AS steps",
                    d=TEST_DAY,
                ).single()
                assert verify and verify["hr"] == 64.0 and verify["steps"] == 11342.0, \
                    f"unexpected daily summary state: {dict(verify) if verify else None}"
                log.info("  ✅ verified DailySummary state")
            except Exception as e:
                failed.append(f"ingestDay: {e}")
                log.exception("ingestDay failed")

            # ---------- 2) ingestWorkout ----------
            workout_input = {
                "uid": TEST_WORKOUT_UID,
                "activityType": "Running",
                "startDate": "2099-01-01T18:05:00Z",
                "endDate": "2099-01-01T18:36:00Z",
                "durationMin": 31.0,
                "device": "HealthGraphSync-Test-Device",
                "sourceName": TEST_SOURCE,
            }
            try:
                rec = session.run(INGEST_WORKOUT_CYPHER, input=workout_input).single()
                log.info(f"ingestWorkout → returned uid={rec['uid']}")
                verify = session.run(
                    "MATCH (w:Workout {uid: $uid})-[:ON_DAY]->(d:Day) "
                    "RETURN d.date AS day, w.duration_min AS dur",
                    uid=TEST_WORKOUT_UID,
                ).single()
                assert verify and verify["dur"] == 31.0, \
                    f"unexpected workout state: {dict(verify) if verify else None}"
                log.info("  ✅ verified Workout linked to Day")
            except Exception as e:
                failed.append(f"ingestWorkout: {e}")
                log.exception("ingestWorkout failed")

            # ---------- 3) ingestSleep ----------
            sleep_input = {
                "date": TEST_DAY,
                "asleepMinutes": 438.0,
                "inBedMinutes": 460.0,
                "sourceName": TEST_SOURCE,
            }
            try:
                rec = session.run(INGEST_SLEEP_CYPHER, input=sleep_input).single()
                log.info(f"ingestSleep → returned date={rec['date']}")
                verify = session.run(
                    "MATCH (s:SleepSession {date: date($d)})-[:ON_DAY]->(d:Day) "
                    "RETURN s.asleep_minutes AS m",
                    d=TEST_DAY,
                ).single()
                assert verify and verify["m"] == 438.0, \
                    f"unexpected sleep state: {dict(verify) if verify else None}"
                log.info("  ✅ verified SleepSession linked to Day")
            except Exception as e:
                failed.append(f"ingestSleep: {e}")
                log.exception("ingestSleep failed")

            # ---------- 4) Idempotency: re-run ingestDay with different values ----------
            try:
                day_input["totalSteps"] = 99999.0
                session.run(INGEST_DAY_CYPHER, input=day_input)
                verify = session.run(
                    "MATCH (s:DailySummary {date: date($d)}) RETURN s.total_steps AS steps",
                    d=TEST_DAY,
                ).single()
                assert verify and verify["steps"] == 99999.0, "MERGE didn't overwrite — not idempotent"
                log.info("  ✅ ingestDay is idempotent (MERGE overwrites cleanly)")
            except Exception as e:
                failed.append(f"idempotency: {e}")
                log.exception("idempotency check failed")

            # ---------- Cleanup ----------
            log.info("Cleaning up test nodes…")
            session.run("MATCH (w:Workout {uid: $u}) DETACH DELETE w", u=TEST_WORKOUT_UID)
            session.run("MATCH (s:SleepSession {date: date($d)}) DETACH DELETE s", d=TEST_DAY)
            session.run("MATCH (s:DailySummary {date: date($d)}) DETACH DELETE s", d=TEST_DAY)
            session.run("MATCH (d:Day {date: date($d)}) DETACH DELETE d", d=TEST_DAY)
            session.run("MATCH (w:Week {iso: '2099-W01'}) WHERE NOT (w)<-[:PART_OF]-() DELETE w")
            session.run(
                "MATCH (d:Device) WHERE d.name CONTAINS 'HealthGraphSync-Test' DETACH DELETE d"
            )

            log.info("Post-cleanup counts:")
            after = baseline_counts(session)
            for k, v in after.items():
                delta = v - before[k]
                marker = "" if delta == 0 else f"  ⚠️ delta {delta:+d}"
                log.info(f"  {k}: {v:,}{marker}")
            counts_match = before == after
    finally:
        driver.close()

    print("=" * 60)
    if failed:
        print("FAILURES:")
        for f in failed:
            print(f"  ❌ {f}")
        return 1
    if not counts_match:
        print("⚠️ Mutations ran OK but cleanup left orphan nodes — investigate.")
        return 2
    print("✅ All three @cypher mutations succeeded against real Aura.")
    print("✅ Idempotency (re-run with new values) verified.")
    print("✅ Cleanup left baseline counts unchanged.")
    print()
    print("Next step: complete docs/AUTH_SETUP.md to wire up Auth0 + the JWKS")
    print("provider on the Aura GraphQL Data API. Once that's done, the same")
    print("Cypher will run via GraphQL mutations from the iOS app.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
