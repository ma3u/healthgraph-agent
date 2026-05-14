"""Translate iOS JSON payloads into the existing etl/ data model and MERGE into Aura.

Reuses:
  - etl/parse_health_xml.py — HealthRecord, WorkoutRecord, HealthExport dataclasses
  - etl/transform.py        — transform() to build DailySummary etc.
  - etl/load_to_neo4j.py    — load_all() to MERGE everything

The payload contract is "everything for the days you're sending" — for any date
that appears in the payload, the daily summary is recomputed from the payload's
samples on that date. This works for both initial sync (all dates at once) and
incremental sync (iOS re-sends a full day when any sample on that day changed).
"""

from __future__ import annotations

import os
import sys
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Make etl/ importable
_ETL_DIR = Path(__file__).resolve().parent.parent / "etl"
if str(_ETL_DIR) not in sys.path:
    sys.path.insert(0, str(_ETL_DIR))

from parse_health_xml import (  # type: ignore  noqa: E402
    HealthExport,
    HealthRecord,
    WorkoutRecord,
    PersonInfo as EtlPersonInfo,
)
from transform import transform  # type: ignore  noqa: E402
import load_to_neo4j  # type: ignore  noqa: E402

from .models import IngestPayload  # noqa: E402

log = logging.getLogger(__name__)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _date_key(dt: datetime) -> str:
    return dt.date().isoformat()


def payload_to_export(payload: IngestPayload) -> HealthExport:
    """Convert the API payload into the HealthExport dataclass the etl/ code expects."""
    export = HealthExport()

    if payload.person:
        export.person = EtlPersonInfo(
            date_of_birth=payload.person.date_of_birth,
            biological_sex=payload.person.biological_sex,
            blood_type=payload.person.blood_type,
        )

    type_counts: dict[str, int] = defaultdict(int)
    source_counts: dict[str, int] = defaultdict(int)
    devices: set[str] = set()
    min_date: str | None = None
    max_date: str | None = None

    # Quantity samples
    for s in payload.quantity_samples:
        rec = HealthRecord(
            record_type=s.raw_type or f"HKQuantityTypeIdentifier{s.type}",
            display_type=s.type,
            source_name=s.source_name,
            value=str(s.value),
            unit=s.unit,
            start_date=_iso(s.start_date),
            end_date=_iso(s.end_date),
            creation_date=_iso(s.start_date),
            source_version=s.source_version,
            device=s.device,
            date=_date_key(s.start_date),
        )
        export.records.append(rec)
        type_counts[rec.record_type] += 1
        source_counts[rec.source_name] += 1
        if rec.device:
            devices.add(rec.device)
        if min_date is None or rec.date < min_date:
            min_date = rec.date
        if max_date is None or rec.date > max_date:
            max_date = rec.date

    # Category samples
    for c in payload.category_samples:
        rec = HealthRecord(
            record_type=c.raw_type or f"HKCategoryTypeIdentifier{c.type}",
            display_type=c.type,
            source_name=c.source_name,
            value=c.category_value,
            start_date=_iso(c.start_date),
            end_date=_iso(c.end_date),
            creation_date=_iso(c.start_date),
            source_version=c.source_version,
            device=c.device,
            date=_date_key(c.start_date),
            category_value=c.category_value,
        )
        export.records.append(rec)
        type_counts[rec.record_type] += 1
        source_counts[rec.source_name] += 1
        if rec.device:
            devices.add(rec.device)
        if min_date is None or rec.date < min_date:
            min_date = rec.date
        if max_date is None or rec.date > max_date:
            max_date = rec.date

    # Workouts
    for w in payload.workouts:
        wrec = WorkoutRecord(
            activity_type=w.raw_activity_type or f"HKWorkoutActivityType{w.activity_type}",
            display_type=w.activity_type,
            source_name=w.source_name,
            duration=w.duration_seconds / 60.0 if w.duration_seconds else None,
            duration_unit="min",
            total_distance=(w.total_distance_meters / 1000.0) if w.total_distance_meters else None,
            total_distance_unit="km" if w.total_distance_meters else None,
            total_energy_burned=w.total_energy_kcal,
            total_energy_burned_unit="kcal" if w.total_energy_kcal else None,
            start_date=_iso(w.start_date),
            end_date=_iso(w.end_date),
            creation_date=_iso(w.start_date),
            source_version=w.source_version,
            device=w.device,
            date=_date_key(w.start_date),
        )
        export.workouts.append(wrec)
        if w.device:
            devices.add(w.device)
        if wrec.date and (min_date is None or wrec.date < min_date):
            min_date = wrec.date
        if wrec.date and (max_date is None or wrec.date > max_date):
            max_date = wrec.date

    export.record_type_counts = type_counts
    export.source_counts = source_counts
    export.device_names = devices
    export.date_range = (min_date, max_date)
    export.export_date = datetime.utcnow().isoformat()
    return export


def ingest_to_aura(payload: IngestPayload, dry_run: bool = False) -> dict:
    """Translate the payload, transform it, and MERGE into Aura.

    When dry_run is True, skip the Aura write (used for local smoke tests).
    """
    export = payload_to_export(payload)
    data = transform(export)

    days_affected = sorted({s.date for s in data.daily_summaries.values()})

    if dry_run:
        log.info(
            "DRY RUN — would ingest %d records, %d workouts, %d days",
            len(export.records),
            len(export.workouts),
            len(days_affected),
        )
        return {
            "accepted_samples": len(export.records),
            "accepted_workouts": len(export.workouts),
            "days_affected": days_affected,
        }

    driver = load_to_neo4j.get_driver()
    try:
        load_to_neo4j.load_all(driver, export, data)
    finally:
        driver.close()

    return {
        "accepted_samples": len(export.records),
        "accepted_workouts": len(export.workouts),
        "days_affected": days_affected,
    }
