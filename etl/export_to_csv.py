"""
export_to_csv.py — Export parsed Apple Health data to CSV files for LOAD CSV import

Import Method 2: For users who prefer loading via Neo4j Browser / cypher-shell
without running the full Python ETL pipeline against a live database.

Workflow:
  1. Parse export.xml with parse_health_xml.py
  2. Transform with transform.py
  3. Export to CSV with this script
  4. Run cypher/load_csv_import.cypher in Neo4j Browser

Works with both Neo4j Desktop (file:/// paths) and Aura (upload CSVs).
"""

import csv
import logging
import sys
from dataclasses import asdict
from pathlib import Path

from parse_health_xml import HealthExport, parse_health_export
from transform import transform, TransformedData

log = logging.getLogger(__name__)


def export_to_csv(export: HealthExport, data: TransformedData, output_dir: str) -> None:
    """Export all graph-ready data to CSV files."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 1. Person
    _write_csv(out / "person.csv", ["name", "date_of_birth", "biological_sex"], [
        {"name": "Me", "date_of_birth": export.person.date_of_birth or "",
         "biological_sex": export.person.biological_sex or ""},
    ])

    # 2. Devices
    _write_csv(out / "devices.csv", ["name"], [
        {"name": d} for d in data.devices
    ])

    # 3. Metric types
    _write_csv(out / "metric_types.csv",
               ["identifier", "display_name", "unit", "category"],
               list(data.metric_types.values()))

    # 4. Weeks
    week_rows = [
        {"iso": iso, "year": w["year"], "week_number": w["week_number"],
         "start_date": w["start_date"]}
        for iso, w in data.weeks.items()
    ]
    _write_csv(out / "weeks.csv", ["iso", "year", "week_number", "start_date"], week_rows)

    # 5. Daily summaries (also serves as Day nodes)
    summary_fields = [
        "date", "day_of_week", "week_iso",
        "avg_heart_rate", "min_heart_rate", "max_heart_rate",
        "resting_heart_rate", "hrv_mean",
        "total_steps", "total_distance_km",
        "active_energy_kcal", "basal_energy_kcal",
        "flights_climbed", "exercise_minutes", "stand_hours",
        "avg_blood_oxygen", "avg_respiratory_rate",
        "body_mass_kg", "vo2max",
        "sleep_hours", "workout_count", "workout_minutes",
        "description",
    ]
    summary_rows = []
    for s in data.daily_summaries.values():
        row = {}
        for f in summary_fields:
            val = getattr(s, f, None)
            row[f] = val if val is not None else ""
        summary_rows.append(row)
    _write_csv(out / "daily_summaries.csv", summary_fields, summary_rows)

    # 6. Workouts
    workout_fields = [
        "uid", "activity_type", "source_name", "duration_min",
        "total_distance", "total_distance_unit",
        "total_energy_burned", "total_energy_burned_unit",
        "start_date", "end_date", "device", "date",
    ]
    workout_rows = []
    for w in export.workouts:
        uid = f"{w.display_type}_{w.start_date}"
        workout_rows.append({
            "uid": uid,
            "activity_type": w.display_type,
            "source_name": w.source_name,
            "duration_min": w.duration or "",
            "total_distance": w.total_distance or "",
            "total_distance_unit": w.total_distance_unit or "",
            "total_energy_burned": w.total_energy_burned or "",
            "total_energy_burned_unit": w.total_energy_burned_unit or "",
            "start_date": w.start_date or "",
            "end_date": w.end_date or "",
            "device": w.device or "",
            "date": w.date or "",
        })
    _write_csv(out / "workouts.csv", workout_fields, workout_rows)

    # 7. Sleep sessions
    sleep_fields = ["date", "in_bed_start", "in_bed_end", "asleep_minutes",
                    "in_bed_minutes", "source_name"]
    sleep_rows = []
    for s in data.sleep_sessions:
        sleep_rows.append({
            "date": s.date,
            "in_bed_start": s.in_bed_start or "",
            "in_bed_end": s.in_bed_end or "",
            "asleep_minutes": s.asleep_minutes,
            "in_bed_minutes": s.in_bed_minutes,
            "source_name": s.source_name,
        })
    _write_csv(out / "sleep_sessions.csv", sleep_fields, sleep_rows)

    # 8. Temporal relationships
    rel_fields = ["from_type", "from_id", "to_type", "to_id", "rel_type", "hours_between"]
    rel_rows = []
    for r in data.temporal_rels:
        rel_rows.append({
            "from_type": r.from_type,
            "from_id": r.from_id,
            "to_type": r.to_type,
            "to_id": r.to_id,
            "rel_type": r.rel_type,
            "hours_between": r.hours_between if r.hours_between is not None else "",
        })
    _write_csv(out / "temporal_rels.csv", rel_fields, rel_rows)

    # 9. Activity summaries (ring data)
    if export.activity_summaries:
        ring_fields = [
            "date", "active_energy_burned", "active_energy_burned_goal",
            "apple_exercise_time", "apple_exercise_time_goal",
            "apple_stand_hours", "apple_stand_hours_goal",
        ]
        ring_rows = []
        for a in export.activity_summaries:
            if a.date:
                ring_rows.append({
                    "date": a.date,
                    "active_energy_burned": a.active_energy_burned or "",
                    "active_energy_burned_goal": a.active_energy_burned_goal or "",
                    "apple_exercise_time": a.apple_exercise_time or "",
                    "apple_exercise_time_goal": a.apple_exercise_time_goal or "",
                    "apple_stand_hours": a.apple_stand_hours or "",
                    "apple_stand_hours_goal": a.apple_stand_hours_goal or "",
                })
        _write_csv(out / "activity_summaries.csv", ring_fields, ring_rows)

    log.info(f"Exported {len(summary_rows)} days of data to {out}/")
    print(f"\nCSV files written to: {out}/")
    print(f"  person.csv            ({1} row)")
    print(f"  devices.csv           ({len(data.devices)} rows)")
    print(f"  metric_types.csv      ({len(data.metric_types)} rows)")
    print(f"  weeks.csv             ({len(week_rows)} rows)")
    print(f"  daily_summaries.csv   ({len(summary_rows)} rows)")
    print(f"  workouts.csv          ({len(workout_rows)} rows)")
    print(f"  sleep_sessions.csv    ({len(sleep_rows)} rows)")
    print(f"  temporal_rels.csv     ({len(rel_rows)} rows)")
    if export.activity_summaries:
        print(f"  activity_summaries.csv ({len(export.activity_summaries)} rows)")
    print(f"\nNext: Run cypher/load_csv_import.cypher in Neo4j Browser")


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Export Apple Health data to CSV for LOAD CSV import"
    )
    parser.add_argument("input", help="Path to export.xml")
    parser.add_argument(
        "--output", "-o", default="data/csv",
        help="Output directory for CSV files (default: data/csv)",
    )
    parser.add_argument(
        "--max-records", "-n", type=int,
        help="Limit number of records to parse (for testing)",
    )

    args = parser.parse_args()

    log.info("Step 1/3: Parsing XML...")
    export = parse_health_export(args.input, max_records=args.max_records)

    log.info("Step 2/3: Transforming data...")
    data = transform(export)

    log.info("Step 3/3: Exporting to CSV...")
    export_to_csv(export, data, args.output)


if __name__ == "__main__":
    main()
