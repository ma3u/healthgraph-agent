"""
load_to_neo4j.py — Batch load transformed health data into Neo4j (Import Method 1)

Supports BOTH:
  - Neo4j Desktop (bolt://localhost:7687)
  - Neo4j Aura   (neo4j+s://xxxxx.databases.neo4j.io)

Uses MERGE operations throughout so the pipeline is idempotent (safe to re-run).
Batches writes in chunks of 500 for performance.
"""

import os
import sys
import logging
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase
from tqdm import tqdm

from parse_health_xml import HealthExport, parse_health_export
from transform import transform, TransformedData, DailySummary

load_dotenv()
log = logging.getLogger(__name__)

BATCH_SIZE = 500

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_driver():
    """Connect to Neo4j — auto-detects Desktop (bolt://) vs Aura (neo4j+s://)."""
    uri = os.environ.get("NEO4J_URI")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")

    if not uri or not password:
        print("Error: Set NEO4J_URI and NEO4J_PASSWORD in .env")
        print("")
        print("  Neo4j Desktop:  NEO4J_URI=bolt://localhost:7687")
        print("  Neo4j Aura:     NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io")
        sys.exit(1)

    if uri.startswith("bolt://"):
        log.info(f"Connecting to Neo4j Desktop at {uri}")
    elif "neo4j+s://" in uri or "neo4j+ssc://" in uri:
        log.info(f"Connecting to Neo4j Aura at {uri}")
    else:
        log.info(f"Connecting to Neo4j at {uri}")

    return GraphDatabase.driver(uri, auth=(user, password))


# ---------------------------------------------------------------------------
# Schema: constraints + indexes
# ---------------------------------------------------------------------------

SCHEMA_STATEMENTS = [
    # Uniqueness constraints
    "CREATE CONSTRAINT person_name IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE",
    "CREATE CONSTRAINT device_name IF NOT EXISTS FOR (d:Device) REQUIRE d.name IS UNIQUE",
    "CREATE CONSTRAINT metric_type_id IF NOT EXISTS FOR (m:MetricType) REQUIRE m.identifier IS UNIQUE",
    "CREATE CONSTRAINT day_date IF NOT EXISTS FOR (d:Day) REQUIRE d.date IS UNIQUE",
    "CREATE CONSTRAINT week_iso IF NOT EXISTS FOR (w:Week) REQUIRE w.iso IS UNIQUE",
    "CREATE CONSTRAINT daily_summary_date IF NOT EXISTS FOR (s:DailySummary) REQUIRE s.date IS UNIQUE",
    "CREATE CONSTRAINT workout_id IF NOT EXISTS FOR (w:Workout) REQUIRE w.uid IS UNIQUE",
    "CREATE CONSTRAINT sleep_session_date IF NOT EXISTS FOR (s:SleepSession) REQUIRE s.date IS UNIQUE",

    # Indexes for common lookups
    "CREATE INDEX day_day_of_week IF NOT EXISTS FOR (d:Day) ON (d.day_of_week)",
    "CREATE INDEX workout_type IF NOT EXISTS FOR (w:Workout) ON (w.activity_type)",
    "CREATE INDEX metric_display IF NOT EXISTS FOR (m:MetricType) ON (m.display_name)",
]


def create_schema(driver):
    log.info("Creating schema constraints and indexes...")
    with driver.session() as session:
        for stmt in SCHEMA_STATEMENTS:
            try:
                session.run(stmt)
            except Exception as e:
                # Some constraints may already exist
                if "already exists" not in str(e).lower():
                    log.warning(f"Schema statement failed: {e}")
    log.info("Schema ready")


# ---------------------------------------------------------------------------
# Batch helpers
# ---------------------------------------------------------------------------

def _batch(items, size=BATCH_SIZE):
    """Yield successive chunks from a list."""
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _run_batch(session, query, params_list, desc=""):
    """Run a batched UNWIND query."""
    for chunk in _batch(params_list):
        session.run(query, {"batch": chunk})


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_person(driver, export: HealthExport):
    log.info("Loading Person node...")
    with driver.session() as session:
        session.run(
            """
            MERGE (p:Person {name: $name})
            SET p.date_of_birth = $dob,
                p.biological_sex = $sex
            """,
            {
                "name": "Me",
                "dob": export.person.date_of_birth,
                "sex": export.person.biological_sex,
            },
        )


def load_devices(driver, devices: list[str]):
    log.info(f"Loading {len(devices)} Device nodes...")
    with driver.session() as session:
        for dev in devices:
            session.run(
                """
                MERGE (d:Device {name: $name})
                MERGE (p:Person {name: 'Me'})
                MERGE (p)-[:USES]->(d)
                """,
                {"name": dev},
            )


def load_metric_types(driver, metric_types: dict):
    log.info(f"Loading {len(metric_types)} MetricType nodes...")
    params = [
        {
            "identifier": v["identifier"],
            "display_name": v["display_name"],
            "unit": v["unit"],
            "category": v["category"],
        }
        for v in metric_types.values()
    ]

    query = """
    UNWIND $batch AS row
    MERGE (m:MetricType {identifier: row.identifier})
    SET m.display_name = row.display_name,
        m.unit = row.unit,
        m.category = row.category
    """

    with driver.session() as session:
        _run_batch(session, query, params)


def load_days_and_weeks(driver, data: TransformedData):
    log.info(f"Loading {len(data.daily_summaries)} Day nodes and {len(data.weeks)} Week nodes...")

    # Weeks first
    week_params = [
        {
            "iso": iso,
            "year": w["year"],
            "week_number": w["week_number"],
            "start_date": w["start_date"],
        }
        for iso, w in data.weeks.items()
    ]

    week_query = """
    UNWIND $batch AS row
    MERGE (w:Week {iso: row.iso})
    SET w.year = row.year,
        w.week_number = row.week_number,
        w.start_date = date(row.start_date)
    """

    with driver.session() as session:
        _run_batch(session, week_query, week_params)

    # Days
    day_params = [
        {
            "date": s.date,
            "day_of_week": s.day_of_week,
            "week_iso": s.week_iso,
        }
        for s in data.daily_summaries.values()
    ]

    day_query = """
    UNWIND $batch AS row
    MERGE (d:Day {date: date(row.date)})
    SET d.day_of_week = row.day_of_week
    WITH d, row
    MATCH (w:Week {iso: row.week_iso})
    MERGE (d)-[:PART_OF]->(w)
    """

    with driver.session() as session:
        _run_batch(session, day_query, day_params)


def load_daily_summaries(driver, data: TransformedData):
    summaries = list(data.daily_summaries.values())
    log.info(f"Loading {len(summaries)} DailySummary nodes...")

    params = []
    for s in summaries:
        params.append({
            "date": s.date,
            "avg_heart_rate": s.avg_heart_rate,
            "min_heart_rate": s.min_heart_rate,
            "max_heart_rate": s.max_heart_rate,
            "resting_heart_rate": s.resting_heart_rate,
            "hrv_mean": s.hrv_mean,
            "total_steps": s.total_steps,
            "total_distance_km": s.total_distance_km,
            "active_energy_kcal": s.active_energy_kcal,
            "basal_energy_kcal": s.basal_energy_kcal,
            "flights_climbed": s.flights_climbed,
            "exercise_minutes": s.exercise_minutes,
            "stand_hours": s.stand_hours,
            "avg_blood_oxygen": s.avg_blood_oxygen,
            "avg_respiratory_rate": s.avg_respiratory_rate,
            "body_mass_kg": s.body_mass_kg,
            "vo2max": s.vo2max,
            "sleep_hours": s.sleep_hours,
            "workout_count": s.workout_count,
            "workout_minutes": s.workout_minutes,
            "description": s.description,
        })

    query = """
    UNWIND $batch AS row
    MERGE (s:DailySummary {date: date(row.date)})
    SET s.avg_heart_rate = row.avg_heart_rate,
        s.min_heart_rate = row.min_heart_rate,
        s.max_heart_rate = row.max_heart_rate,
        s.resting_heart_rate = row.resting_heart_rate,
        s.hrv_mean = row.hrv_mean,
        s.total_steps = row.total_steps,
        s.total_distance_km = row.total_distance_km,
        s.active_energy_kcal = row.active_energy_kcal,
        s.basal_energy_kcal = row.basal_energy_kcal,
        s.flights_climbed = row.flights_climbed,
        s.exercise_minutes = row.exercise_minutes,
        s.stand_hours = row.stand_hours,
        s.avg_blood_oxygen = row.avg_blood_oxygen,
        s.avg_respiratory_rate = row.avg_respiratory_rate,
        s.body_mass_kg = row.body_mass_kg,
        s.vo2max = row.vo2max,
        s.sleep_hours = row.sleep_hours,
        s.workout_count = row.workout_count,
        s.workout_minutes = row.workout_minutes,
        s.description = row.description
    WITH s, row
    MATCH (d:Day {date: date(row.date)})
    MERGE (d)-[:HAS_SUMMARY]->(s)
    """

    with driver.session() as session:
        _run_batch(session, query, params)


def load_workouts(driver, export: HealthExport):
    log.info(f"Loading {len(export.workouts)} Workout nodes...")

    params = []
    for w in export.workouts:
        uid = f"{w.display_type}_{w.start_date}"
        params.append({
            "uid": uid,
            "activity_type": w.display_type,
            "raw_type": w.activity_type,
            "source_name": w.source_name,
            "duration_min": w.duration,
            "total_distance": w.total_distance,
            "total_distance_unit": w.total_distance_unit,
            "total_energy_burned": w.total_energy_burned,
            "total_energy_burned_unit": w.total_energy_burned_unit,
            "start_date": w.start_date,
            "end_date": w.end_date,
            "device": w.device,
            "date": w.date,
        })

    query = """
    UNWIND $batch AS row
    MERGE (w:Workout {uid: row.uid})
    SET w.activity_type = row.activity_type,
        w.raw_type = row.raw_type,
        w.source_name = row.source_name,
        w.duration_min = row.duration_min,
        w.total_distance = row.total_distance,
        w.total_distance_unit = row.total_distance_unit,
        w.total_energy_burned = row.total_energy_burned,
        w.total_energy_burned_unit = row.total_energy_burned_unit,
        w.start_date = datetime(row.start_date),
        w.end_date = datetime(row.end_date),
        w.device = row.device
    WITH w, row
    WHERE row.date IS NOT NULL
    MATCH (d:Day {date: date(row.date)})
    MERGE (w)-[:ON_DAY]->(d)
    """

    with driver.session() as session:
        _run_batch(session, query, params)

    # Link workouts to devices
    device_query = """
    UNWIND $batch AS row
    WITH row WHERE row.device IS NOT NULL
    MATCH (w:Workout {uid: row.uid})
    MATCH (dev:Device {name: row.device})
    MERGE (dev)-[:RECORDED]->(w)
    """

    with driver.session() as session:
        _run_batch(session, device_query, params)


def load_sleep_sessions(driver, data: TransformedData):
    log.info(f"Loading {len(data.sleep_sessions)} SleepSession nodes...")

    params = [
        {
            "date": s.date,
            "in_bed_start": s.in_bed_start,
            "in_bed_end": s.in_bed_end,
            "asleep_minutes": s.asleep_minutes,
            "in_bed_minutes": s.in_bed_minutes,
            "source_name": s.source_name,
        }
        for s in data.sleep_sessions
    ]

    query = """
    UNWIND $batch AS row
    MERGE (s:SleepSession {date: date(row.date)})
    SET s.asleep_minutes = row.asleep_minutes,
        s.in_bed_minutes = row.in_bed_minutes,
        s.source_name = row.source_name
    WITH s, row
    MATCH (d:Day {date: date(row.date)})
    MERGE (s)-[:ON_DAY]->(d)
    """

    with driver.session() as session:
        _run_batch(session, query, params)


def load_temporal_relationships(driver, data: TransformedData):
    log.info(f"Loading {len(data.temporal_rels)} temporal relationships...")

    # NEXT_DAY
    next_day_params = [
        {"from_date": r.from_id, "to_date": r.to_id}
        for r in data.temporal_rels if r.rel_type == "NEXT_DAY"
    ]

    if next_day_params:
        query = """
        UNWIND $batch AS row
        MATCH (d1:Day {date: date(row.from_date)})
        MATCH (d2:Day {date: date(row.to_date)})
        MERGE (d1)-[:NEXT_DAY]->(d2)
        """
        with driver.session() as session:
            _run_batch(session, query, next_day_params)

    # FOLLOWED_BY (Workout → SleepSession)
    followed_params = [
        {
            "workout_uid": r.from_id,
            "sleep_date": r.to_id,
            "hours_between": r.hours_between,
        }
        for r in data.temporal_rels if r.rel_type == "FOLLOWED_BY"
    ]

    if followed_params:
        query = """
        UNWIND $batch AS row
        MATCH (w:Workout {uid: row.workout_uid})
        MATCH (s:SleepSession {date: date(row.sleep_date)})
        MERGE (w)-[r:FOLLOWED_BY]->(s)
        SET r.hours_between = row.hours_between
        """
        with driver.session() as session:
            _run_batch(session, query, followed_params)


def load_activity_summaries(driver, export: HealthExport):
    """Load Apple's built-in ActivitySummary data (rings data)."""
    if not export.activity_summaries:
        return

    log.info(f"Loading {len(export.activity_summaries)} ActivitySummary records...")

    params = [
        {
            "date": a.date,
            "active_energy_burned": a.active_energy_burned,
            "active_energy_burned_goal": a.active_energy_burned_goal,
            "apple_exercise_time": a.apple_exercise_time,
            "apple_exercise_time_goal": a.apple_exercise_time_goal,
            "apple_stand_hours": a.apple_stand_hours,
            "apple_stand_hours_goal": a.apple_stand_hours_goal,
        }
        for a in export.activity_summaries
        if a.date
    ]

    query = """
    UNWIND $batch AS row
    MATCH (d:Day {date: date(row.date)})
    SET d.ring_move = row.active_energy_burned,
        d.ring_move_goal = row.active_energy_burned_goal,
        d.ring_exercise = row.apple_exercise_time,
        d.ring_exercise_goal = row.apple_exercise_time_goal,
        d.ring_stand = row.apple_stand_hours,
        d.ring_stand_goal = row.apple_stand_hours_goal
    """

    with driver.session() as session:
        _run_batch(session, query, params)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def load_all(driver, export: HealthExport, data: TransformedData):
    """Execute the full load pipeline."""
    create_schema(driver)
    load_person(driver, export)
    load_devices(driver, data.devices)
    load_metric_types(driver, data.metric_types)
    load_days_and_weeks(driver, data)
    load_daily_summaries(driver, data)
    load_workouts(driver, export)
    load_sleep_sessions(driver, data)
    load_temporal_relationships(driver, data)
    load_activity_summaries(driver, export)

    # Print final counts
    with driver.session() as session:
        result = session.run(
            """
            MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count
            ORDER BY count DESC
            """
        )
        log.info("Graph loaded. Node counts:")
        for record in result:
            log.info(f"  {record['label']}: {record['count']:,}")

        rel_result = session.run(
            """
            MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count
            ORDER BY count DESC
            """
        )
        log.info("Relationship counts:")
        for record in rel_result:
            log.info(f"  {record['type']}: {record['count']:,}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="Load Apple Health data into Neo4j")
    parser.add_argument("input", help="Path to export.xml")
    parser.add_argument(
        "--max-records", "-n", type=int,
        help="Limit number of records to parse (for testing)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse and transform only, don't load into Neo4j",
    )

    args = parser.parse_args()

    # Parse
    log.info("Step 1/3: Parsing XML...")
    export = parse_health_export(
        args.input,
        max_records=args.max_records,
    )

    # Transform
    log.info("Step 2/3: Transforming data...")
    data = transform(export)

    if args.dry_run:
        log.info("Dry run complete. Skipping Neo4j load.")
        print(f"\n{export.summary()}")
        print(f"\nDaily summaries: {len(data.daily_summaries)}")
        print(f"Sleep sessions: {len(data.sleep_sessions)}")
        print(f"Temporal relationships: {len(data.temporal_rels)}")
        return

    # Load
    log.info("Step 3/3: Loading into Neo4j...")
    driver = get_driver()
    try:
        load_all(driver, export, data)
        log.info("Pipeline complete!")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
