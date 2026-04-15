"""
transform.py — Transform parsed Apple Health data into graph-ready structures

Takes the raw parsed data from parse_health_xml.py and produces:
  - DailySummary nodes (aggregated metrics per day)
  - Temporal relationships (FOLLOWED_BY between workouts and sleep)
  - Day → Week → Month hierarchy
  - Correlation edges between daily metric dimensions
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, timedelta
from typing import Optional

from parse_health_xml import (
    HealthExport,
    HealthRecord,
    WorkoutRecord,
    safe_float,
    parse_timestamp,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Metric categories — which record types map to which summary dimensions
# ---------------------------------------------------------------------------

HEART_RATE_TYPES = {"HeartRate"}
RESTING_HR_TYPES = {"RestingHeartRate"}
HRV_TYPES = {"HeartRateVariabilitySDNN"}
STEP_TYPES = {"StepCount"}
DISTANCE_TYPES = {"DistanceWalkingRunning"}
ACTIVE_ENERGY_TYPES = {"ActiveEnergyBurned"}
BASAL_ENERGY_TYPES = {"BasalEnergyBurned"}
FLIGHTS_TYPES = {"FlightsClimbed"}
BLOOD_OXYGEN_TYPES = {"OxygenSaturation"}
RESPIRATORY_TYPES = {"RespiratoryRate"}
BODY_MASS_TYPES = {"BodyMass"}
SLEEP_TYPES = {"SleepAnalysis"}
STAND_TYPES = {"AppleStandHour"}
EXERCISE_TIME_TYPES = {"AppleExerciseTime"}
VO2MAX_TYPES = {"VO2Max"}

# All numeric record types we want to aggregate
NUMERIC_TYPES = (
    HEART_RATE_TYPES
    | RESTING_HR_TYPES
    | HRV_TYPES
    | STEP_TYPES
    | DISTANCE_TYPES
    | ACTIVE_ENERGY_TYPES
    | BASAL_ENERGY_TYPES
    | FLIGHTS_TYPES
    | BLOOD_OXYGEN_TYPES
    | RESPIRATORY_TYPES
    | BODY_MASS_TYPES
    | VO2MAX_TYPES
)


# ---------------------------------------------------------------------------
# Data classes for graph-ready structures
# ---------------------------------------------------------------------------

@dataclass
class DailySummary:
    date: str  # YYYY-MM-DD
    day_of_week: str  # Monday, Tuesday, etc.
    week_iso: str  # e.g. "2024-W03"

    # Heart
    avg_heart_rate: Optional[float] = None
    min_heart_rate: Optional[float] = None
    max_heart_rate: Optional[float] = None
    resting_heart_rate: Optional[float] = None
    hrv_mean: Optional[float] = None

    # Activity
    total_steps: Optional[float] = None
    total_distance_km: Optional[float] = None
    active_energy_kcal: Optional[float] = None
    basal_energy_kcal: Optional[float] = None
    flights_climbed: Optional[float] = None
    exercise_minutes: Optional[float] = None
    stand_hours: Optional[float] = None

    # Vitals
    avg_blood_oxygen: Optional[float] = None
    avg_respiratory_rate: Optional[float] = None
    body_mass_kg: Optional[float] = None
    vo2max: Optional[float] = None

    # Sleep (computed from SleepAnalysis records)
    sleep_hours: Optional[float] = None
    sleep_start: Optional[str] = None
    sleep_end: Optional[str] = None

    # Workout count for the day
    workout_count: int = 0
    workout_minutes: float = 0.0

    # Text description for similarity search embedding
    description: str = ""


@dataclass
class SleepSession:
    """A consolidated sleep session (multiple SleepAnalysis records merged)."""
    date: str
    in_bed_start: Optional[str] = None
    in_bed_end: Optional[str] = None
    asleep_minutes: float = 0.0
    in_bed_minutes: float = 0.0
    source_name: str = ""


@dataclass
class TemporalRelationship:
    """Workout → Sleep or Day → Day relationship."""
    from_type: str  # "Workout" or "Day"
    from_id: str
    to_type: str  # "SleepSession" or "Day"
    to_id: str
    rel_type: str  # "FOLLOWED_BY" or "NEXT_DAY"
    hours_between: Optional[float] = None


@dataclass
class TransformedData:
    """All graph-ready structures."""
    daily_summaries: dict = field(default_factory=dict)  # date → DailySummary
    sleep_sessions: list = field(default_factory=list)
    temporal_rels: list = field(default_factory=list)
    weeks: dict = field(default_factory=dict)  # "2024-W03" → {start_date, end_date}
    devices: list = field(default_factory=list)
    metric_types: dict = field(default_factory=dict)  # display_type → {unit, category}


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def _aggregate_numeric(values: list[float], mode: str = "sum") -> Optional[float]:
    """Aggregate a list of float values."""
    if not values:
        return None
    if mode == "sum":
        return sum(values)
    elif mode == "mean":
        return sum(values) / len(values)
    elif mode == "min":
        return min(values)
    elif mode == "max":
        return max(values)
    elif mode == "last":
        return values[-1]
    return None


def _compute_sleep_hours(sleep_records: list[HealthRecord]) -> tuple[Optional[float], Optional[str], Optional[str]]:
    """Compute total sleep from SleepAnalysis records for a day.

    Sleep records have value = "Asleep", "InBed", "Awake", "AsleepCore",
    "AsleepDeep", "AsleepREM", "AsleepUnspecified".

    Returns (total_asleep_hours, earliest_start, latest_end)
    """
    asleep_minutes = 0.0
    earliest_start = None
    latest_end = None

    asleep_values = {"Asleep", "AsleepCore", "AsleepDeep", "AsleepREM", "AsleepUnspecified"}

    for r in sleep_records:
        cat = r.category_value or r.value
        if cat not in asleep_values:
            continue

        start = parse_timestamp(r.start_date) if r.start_date else None
        end = parse_timestamp(r.end_date) if r.end_date else None

        if start and end:
            delta = (end - start).total_seconds() / 60.0
            if 0 < delta < 1440:  # sanity: max 24 hours
                asleep_minutes += delta

            if earliest_start is None or start < earliest_start:
                earliest_start = start
            if latest_end is None or end > latest_end:
                latest_end = end

    hours = asleep_minutes / 60.0 if asleep_minutes > 0 else None
    start_str = earliest_start.isoformat() if earliest_start else None
    end_str = latest_end.isoformat() if latest_end else None
    return hours, start_str, end_str


# ---------------------------------------------------------------------------
# Main transform
# ---------------------------------------------------------------------------

def transform(export: HealthExport) -> TransformedData:
    """Transform raw parsed data into graph-ready structures."""

    result = TransformedData()

    # -----------------------------------------------------------------------
    # 1. Index records by date and type
    # -----------------------------------------------------------------------
    log.info("Indexing records by date...")

    records_by_date: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))

    for r in export.records:
        if r.date:
            records_by_date[r.date][r.display_type].append(r)

    # -----------------------------------------------------------------------
    # 2. Index workouts by date
    # -----------------------------------------------------------------------
    workouts_by_date: dict[str, list] = defaultdict(list)
    for w in export.workouts:
        if w.date:
            workouts_by_date[w.date].append(w)

    # -----------------------------------------------------------------------
    # 3. Collect unique metric types
    # -----------------------------------------------------------------------
    for r in export.records:
        if r.display_type not in result.metric_types:
            category = "quantity"
            if r.record_type.startswith("HKCategoryType"):
                category = "category"
            elif r.record_type.startswith("HKCorrelationType"):
                category = "correlation"
            result.metric_types[r.display_type] = {
                "identifier": r.record_type,
                "display_name": r.display_type,
                "unit": r.unit,
                "category": category,
            }

    # -----------------------------------------------------------------------
    # 4. Collect devices
    # -----------------------------------------------------------------------
    result.devices = sorted(export.device_names)

    # -----------------------------------------------------------------------
    # 5. Build daily summaries
    # -----------------------------------------------------------------------
    log.info(f"Building daily summaries for {len(records_by_date)} days...")

    all_dates = sorted(records_by_date.keys())

    for day_str in all_dates:
        day_records = records_by_date[day_str]
        day_obj = date.fromisoformat(day_str)
        iso_cal = day_obj.isocalendar()
        week_key = f"{iso_cal.year}-W{iso_cal.week:02d}"

        summary = DailySummary(
            date=day_str,
            day_of_week=day_obj.strftime("%A"),
            week_iso=week_key,
        )

        # Heart rate
        hr_vals = [safe_float(r.value) for r in day_records.get("HeartRate", [])
                   if safe_float(r.value)]
        if hr_vals:
            summary.avg_heart_rate = round(sum(hr_vals) / len(hr_vals), 1)
            summary.min_heart_rate = round(min(hr_vals), 1)
            summary.max_heart_rate = round(max(hr_vals), 1)

        # Resting heart rate
        rhr_vals = [safe_float(r.value) for r in day_records.get("RestingHeartRate", [])
                    if safe_float(r.value)]
        if rhr_vals:
            summary.resting_heart_rate = round(sum(rhr_vals) / len(rhr_vals), 1)

        # HRV
        hrv_vals = [safe_float(r.value) for r in day_records.get("HeartRateVariabilitySDNN", [])
                    if safe_float(r.value)]
        if hrv_vals:
            summary.hrv_mean = round(sum(hrv_vals) / len(hrv_vals), 1)

        # Steps
        step_vals = [safe_float(r.value) for r in day_records.get("StepCount", [])
                     if safe_float(r.value)]
        if step_vals:
            summary.total_steps = round(sum(step_vals))

        # Distance
        dist_vals = [safe_float(r.value) for r in day_records.get("DistanceWalkingRunning", [])
                     if safe_float(r.value)]
        if dist_vals:
            summary.total_distance_km = round(sum(dist_vals), 2)

        # Energy
        active_e = [safe_float(r.value) for r in day_records.get("ActiveEnergyBurned", [])
                    if safe_float(r.value)]
        if active_e:
            summary.active_energy_kcal = round(sum(active_e), 1)

        basal_e = [safe_float(r.value) for r in day_records.get("BasalEnergyBurned", [])
                   if safe_float(r.value)]
        if basal_e:
            summary.basal_energy_kcal = round(sum(basal_e), 1)

        # Flights
        flights = [safe_float(r.value) for r in day_records.get("FlightsClimbed", [])
                   if safe_float(r.value)]
        if flights:
            summary.flights_climbed = round(sum(flights))

        # Blood oxygen
        spo2 = [safe_float(r.value) for r in day_records.get("OxygenSaturation", [])
                if safe_float(r.value)]
        if spo2:
            # SpO2 is stored as decimal (0.98) in some exports, percentage in others
            vals = [v * 100 if v <= 1.0 else v for v in spo2]
            summary.avg_blood_oxygen = round(sum(vals) / len(vals), 1)

        # Respiratory rate
        resp = [safe_float(r.value) for r in day_records.get("RespiratoryRate", [])
                if safe_float(r.value)]
        if resp:
            summary.avg_respiratory_rate = round(sum(resp) / len(resp), 1)

        # Body mass
        mass = [safe_float(r.value) for r in day_records.get("BodyMass", [])
                if safe_float(r.value)]
        if mass:
            summary.body_mass_kg = round(mass[-1], 1)  # latest reading

        # VO2 Max
        vo2 = [safe_float(r.value) for r in day_records.get("VO2Max", [])
               if safe_float(r.value)]
        if vo2:
            summary.vo2max = round(vo2[-1], 1)

        # Sleep
        sleep_recs = day_records.get("SleepAnalysis", [])
        if sleep_recs:
            hours, s_start, s_end = _compute_sleep_hours(sleep_recs)
            summary.sleep_hours = round(hours, 1) if hours else None
            summary.sleep_start = s_start
            summary.sleep_end = s_end

        # Workouts for this day
        day_workouts = workouts_by_date.get(day_str, [])
        summary.workout_count = len(day_workouts)
        summary.workout_minutes = round(
            sum(w.duration or 0 for w in day_workouts), 1
        )

        # Build text description for similarity search embedding
        summary.description = _build_description(summary)

        result.daily_summaries[day_str] = summary

        # Track week
        if week_key not in result.weeks:
            # Compute week start (Monday)
            week_start = day_obj - timedelta(days=day_obj.weekday())
            result.weeks[week_key] = {
                "year": iso_cal.year,
                "week_number": iso_cal.week,
                "start_date": week_start.isoformat(),
            }

    # -----------------------------------------------------------------------
    # 6. Build sleep sessions
    # -----------------------------------------------------------------------
    log.info("Building sleep sessions...")
    sleep_by_date: dict[str, list] = defaultdict(list)
    for r in export.records:
        if r.display_type == "SleepAnalysis" and r.date:
            sleep_by_date[r.date].append(r)

    for day_str, recs in sleep_by_date.items():
        hours, start, end = _compute_sleep_hours(recs)
        if hours and hours > 0:
            # Compute in-bed time from InBed records
            in_bed_minutes = 0.0
            for r in recs:
                cat = r.category_value or r.value
                if cat == "InBed":
                    s = parse_timestamp(r.start_date) if r.start_date else None
                    e = parse_timestamp(r.end_date) if r.end_date else None
                    if s and e:
                        in_bed_minutes += (e - s).total_seconds() / 60.0

            session = SleepSession(
                date=day_str,
                in_bed_start=start,
                in_bed_end=end,
                asleep_minutes=hours * 60,
                in_bed_minutes=in_bed_minutes if in_bed_minutes > 0 else hours * 60,
                source_name=recs[0].source_name if recs else "",
            )
            result.sleep_sessions.append(session)

    # -----------------------------------------------------------------------
    # 7. Build temporal relationships
    # -----------------------------------------------------------------------
    log.info("Building temporal relationships...")

    # NEXT_DAY chains
    for i in range(len(all_dates) - 1):
        result.temporal_rels.append(TemporalRelationship(
            from_type="Day",
            from_id=all_dates[i],
            to_type="Day",
            to_id=all_dates[i + 1],
            rel_type="NEXT_DAY",
        ))

    # Workout → SleepSession (FOLLOWED_BY)
    sleep_sessions_by_date = {s.date: s for s in result.sleep_sessions}
    for w in export.workouts:
        if not w.date or not w.end_date:
            continue
        # Look for sleep on same day or next day
        workout_date = date.fromisoformat(w.date)
        for offset in [0, 1]:
            check_date = (workout_date + timedelta(days=offset)).isoformat()
            if check_date in sleep_sessions_by_date:
                sleep = sleep_sessions_by_date[check_date]
                # Compute hours between workout end and sleep start
                w_end = parse_timestamp(w.end_date)
                s_start = parse_timestamp(sleep.in_bed_start) if sleep.in_bed_start else None
                hours_between = None
                if w_end and s_start:
                    delta = (s_start - w_end).total_seconds() / 3600.0
                    if 0 < delta < 24:
                        hours_between = round(delta, 1)

                result.temporal_rels.append(TemporalRelationship(
                    from_type="Workout",
                    from_id=f"{w.display_type}_{w.start_date}",
                    to_type="SleepSession",
                    to_id=check_date,
                    rel_type="FOLLOWED_BY",
                    hours_between=hours_between,
                ))
                break  # Take first matching sleep

    log.info(
        f"Transform complete: {len(result.daily_summaries)} daily summaries, "
        f"{len(result.sleep_sessions)} sleep sessions, "
        f"{len(result.temporal_rels)} temporal relationships, "
        f"{len(result.weeks)} weeks"
    )

    return result


# ---------------------------------------------------------------------------
# Description builder for embeddings
# ---------------------------------------------------------------------------

def _build_description(s: DailySummary) -> str:
    """Build a natural-language description of a day for similarity search embedding."""
    parts = [f"{s.day_of_week}, {s.date}."]

    if s.total_steps:
        parts.append(f"{int(s.total_steps):,} steps.")
    if s.avg_heart_rate:
        parts.append(f"Average HR {s.avg_heart_rate} bpm.")
    if s.resting_heart_rate:
        parts.append(f"Resting HR {s.resting_heart_rate} bpm.")
    if s.hrv_mean:
        parts.append(f"HRV {s.hrv_mean} ms.")
    if s.sleep_hours:
        parts.append(f"Slept {s.sleep_hours} hours.")
    if s.active_energy_kcal:
        parts.append(f"Burned {int(s.active_energy_kcal)} active kcal.")
    if s.workout_count > 0:
        parts.append(f"{s.workout_count} workout(s), {int(s.workout_minutes)} minutes total.")
    if s.avg_blood_oxygen:
        parts.append(f"SpO2 {s.avg_blood_oxygen}%.")
    if s.vo2max:
        parts.append(f"VO2max {s.vo2max}.")

    return " ".join(parts)
