"""
parse_health_xml.py — Streaming parser for Apple Health export.xml

Handles:
  - Files up to 2GB+ via lxml.iterparse (constant memory)
  - Apple's broken embedded DTD (skipped entirely)
  - Duplicate attribute bugs in some iOS versions
  - HK type identifier cleaning (HKQuantityTypeIdentifierHeartRate → HeartRate)
  - Timezone-aware timestamp parsing
  - MetadataEntry and HeartRateVariabilityMetadataList extraction

Usage:
  from parse_health_xml import parse_health_export
  data = parse_health_export("path/to/export.xml")
"""

import re
import sys
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Iterator, Optional

from lxml import etree
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type cleaning
# ---------------------------------------------------------------------------

_HK_PREFIX_RE = re.compile(
    r"^HK(?:Quantity|Category|Correlation|Data)TypeIdentifier"
)
_HK_WORKOUT_RE = re.compile(r"^HKWorkoutActivityType")
_HK_CATEGORY_VALUE_RE = re.compile(r"^HKCategoryValue\w+?(?=\p{Lu})" if False else r"^HKCategoryValue")


def clean_type(raw: str) -> str:
    """Strip verbose HealthKit prefixes from type identifiers.

    HKQuantityTypeIdentifierHeartRate          → HeartRate
    HKCategoryTypeIdentifierSleepAnalysis      → SleepAnalysis
    HKWorkoutActivityTypeRunning               → Running
    HKDataTypeIdentifierHeartbeatSeries        → HeartbeatSeries
    """
    cleaned = _HK_PREFIX_RE.sub("", raw)
    cleaned = _HK_WORKOUT_RE.sub("", cleaned)
    return cleaned or raw


def clean_category_value(raw: str) -> str:
    """Clean category values like HKCategoryValueSleepAnalysisAsleep → Asleep."""
    # Remove common prefixes
    for prefix in [
        "HKCategoryValueSleepAnalysis",
        "HKCategoryValueAppleStandHour",
        "HKCategoryValueNotApplicable",
        "HKCategoryValue",
    ]:
        if raw.startswith(prefix) and len(raw) > len(prefix):
            return raw[len(prefix):]
    return raw


# ---------------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------------

def parse_timestamp(ts: str) -> Optional[datetime]:
    """Parse Apple Health timestamps like '2024-01-15 08:30:00 -0500'.

    Returns timezone-aware datetime or None if parsing fails.
    """
    if not ts:
        return None
    try:
        # Apple format: "2024-01-15 08:30:00 -0500"  (space before offset)
        # Python needs:  "2024-01-15 08:30:00-0500"  (no space before offset)
        # or with colon: "2024-01-15 08:30:00-05:00"
        ts = ts.strip()

        # Handle "+0000" / "-0500" style offsets
        match = re.match(r"(.+)\s([+-]\d{4})$", ts)
        if match:
            base, offset = match.groups()
            offset_formatted = f"{offset[:3]}:{offset[3:]}"
            return datetime.fromisoformat(f"{base}{offset_formatted}")

        # Try direct parse
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def ts_to_iso(ts: Optional[str]) -> Optional[str]:
    """Parse and return ISO 8601 string, or None."""
    dt = parse_timestamp(ts) if isinstance(ts, str) else ts
    return dt.isoformat() if dt else None


def ts_to_date(ts: Optional[str]) -> Optional[str]:
    """Parse and return date-only string (YYYY-MM-DD), or None."""
    dt = parse_timestamp(ts) if isinstance(ts, str) else ts
    return dt.date().isoformat() if dt else None


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PersonInfo:
    date_of_birth: Optional[str] = None
    biological_sex: Optional[str] = None
    blood_type: Optional[str] = None
    fitzpatrick_skin_type: Optional[str] = None


@dataclass
class HealthRecord:
    record_type: str
    display_type: str  # cleaned
    source_name: str
    value: Optional[str] = None
    unit: Optional[str] = None
    start_date: Optional[str] = None  # ISO 8601
    end_date: Optional[str] = None
    creation_date: Optional[str] = None
    source_version: Optional[str] = None
    device: Optional[str] = None
    date: Optional[str] = None  # YYYY-MM-DD derived from start_date
    metadata: dict = field(default_factory=dict)
    # For category types, the cleaned value
    category_value: Optional[str] = None


@dataclass
class WorkoutRecord:
    activity_type: str
    display_type: str  # cleaned
    source_name: str
    duration: Optional[float] = None
    duration_unit: Optional[str] = None
    total_distance: Optional[float] = None
    total_distance_unit: Optional[str] = None
    total_energy_burned: Optional[float] = None
    total_energy_burned_unit: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    creation_date: Optional[str] = None
    source_version: Optional[str] = None
    device: Optional[str] = None
    date: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    events: list = field(default_factory=list)
    statistics: list = field(default_factory=list)


@dataclass
class ActivitySummaryRecord:
    date: str  # YYYY-MM-DD from dateComponents
    active_energy_burned: Optional[float] = None
    active_energy_burned_goal: Optional[float] = None
    active_energy_burned_unit: Optional[str] = None
    apple_exercise_time: Optional[float] = None
    apple_exercise_time_goal: Optional[float] = None
    apple_stand_hours: Optional[float] = None
    apple_stand_hours_goal: Optional[float] = None
    apple_move_time: Optional[float] = None
    apple_move_time_goal: Optional[float] = None


@dataclass
class HealthExport:
    """Complete parsed Apple Health export."""
    export_date: Optional[str] = None
    locale: Optional[str] = None
    person: PersonInfo = field(default_factory=PersonInfo)
    records: list = field(default_factory=list)
    workouts: list = field(default_factory=list)
    activity_summaries: list = field(default_factory=list)

    # Stats
    record_type_counts: dict = field(default_factory=lambda: defaultdict(int))
    source_counts: dict = field(default_factory=lambda: defaultdict(int))
    device_names: set = field(default_factory=set)
    date_range: tuple = field(default_factory=lambda: (None, None))

    def summary(self) -> str:
        lines = [
            f"Apple Health Export — {self.export_date or 'unknown date'}",
            f"  Locale: {self.locale}",
            f"  Records: {len(self.records):,}",
            f"  Workouts: {len(self.workouts):,}",
            f"  Activity summaries: {len(self.activity_summaries):,}",
            f"  Unique record types: {len(self.record_type_counts):,}",
            f"  Unique sources: {len(self.source_counts):,}",
            f"  Devices: {', '.join(sorted(self.device_names)) or 'unknown'}",
        ]
        if self.date_range[0]:
            lines.append(f"  Date range: {self.date_range[0]} → {self.date_range[1]}")
        lines.append(f"\n  Top record types:")
        for rt, count in sorted(
            self.record_type_counts.items(), key=lambda x: -x[1]
        )[:15]:
            lines.append(f"    {rt}: {count:,}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Safe float parsing
# ---------------------------------------------------------------------------

def safe_float(val: Optional[str]) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Device name extraction
# ---------------------------------------------------------------------------

_DEVICE_NAME_RE = re.compile(r'name:([^,>]+)')

def extract_device_name(device_str: Optional[str]) -> Optional[str]:
    """Extract human-readable device name from Apple's device string.

    Input:  '<<HKDevice: ...>, name:Apple Watch, manufacturer:Apple Inc., ...'
    Output: 'Apple Watch'
    """
    if not device_str:
        return None
    m = _DEVICE_NAME_RE.search(device_str)
    return m.group(1).strip() if m else None


# ---------------------------------------------------------------------------
# Streaming XML parser
# ---------------------------------------------------------------------------

def _estimate_file_records(path: Path) -> int:
    """Quick estimate of record count by sampling the first 10MB."""
    sample_size = 10 * 1024 * 1024  # 10MB
    file_size = path.stat().st_size

    with open(path, "rb") as f:
        sample = f.read(sample_size)

    count = sample.count(b"<Record ")
    count += sample.count(b"<Workout ")
    count += sample.count(b"<ActivitySummary ")

    if len(sample) < file_size:
        ratio = file_size / len(sample)
        count = int(count * ratio)

    return max(count, 100)


def parse_health_export(
    path: str,
    *,
    record_types: Optional[set] = None,
    max_records: Optional[int] = None,
    skip_metadata: bool = False,
    progress: bool = True,
) -> HealthExport:
    """Parse an Apple Health export.xml file using streaming XML.

    Args:
        path: Path to export.xml
        record_types: If set, only include these record types (cleaned names).
                      E.g. {"HeartRate", "StepCount", "SleepAnalysis"}
        max_records: Stop after this many records (for testing)
        skip_metadata: Skip MetadataEntry parsing (faster)
        progress: Show tqdm progress bar

    Returns:
        HealthExport with all parsed data
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    export = HealthExport()

    log.info(f"Parsing {path} ({path.stat().st_size / 1024 / 1024:.1f} MB)")

    # Estimate for progress bar
    estimated = _estimate_file_records(path) if progress else 0
    pbar = tqdm(total=estimated, desc="Parsing", unit=" elements") if progress else None

    count = 0
    min_date = None
    max_date = None

    # Use iterparse with recover=True to handle Apple's broken DTD and
    # duplicate attribute bugs. This is the key to robustness.
    context = etree.iterparse(
        str(path),
        events=("end",),
        tag=("HealthData", "ExportDate", "Me", "Record", "Workout", "ActivitySummary"),
        recover=True,  # Tolerate DTD errors and malformed XML
        huge_tree=True,  # Allow very large files
    )

    for event, elem in context:
        tag = elem.tag

        if tag == "HealthData":
            export.locale = elem.get("locale")

        elif tag == "ExportDate":
            export.export_date = elem.get("value")

        elif tag == "Me":
            export.person = PersonInfo(
                date_of_birth=elem.get("HKCharacteristicTypeIdentifierDateOfBirth"),
                biological_sex=clean_type(
                    elem.get("HKCharacteristicTypeIdentifierBiologicalSex", "")
                ),
                blood_type=clean_type(
                    elem.get("HKCharacteristicTypeIdentifierBloodType", "")
                ),
                fitzpatrick_skin_type=clean_type(
                    elem.get("HKCharacteristicTypeIdentifierFitzpatrickSkinType", "")
                ),
            )

        elif tag == "Record":
            raw_type = elem.get("type", "")
            display = clean_type(raw_type)

            # Filter by type if requested
            if record_types and display not in record_types:
                elem.clear()
                continue

            start = ts_to_iso(elem.get("startDate"))
            date = ts_to_date(elem.get("startDate"))

            # Track date range
            if date:
                if min_date is None or date < min_date:
                    min_date = date
                if max_date is None or date > max_date:
                    max_date = date

            # Parse value — handle category types
            raw_value = elem.get("value", "")
            category_value = None
            if raw_value.startswith("HKCategoryValue"):
                category_value = clean_category_value(raw_value)
                value = category_value
            else:
                value = raw_value

            # Extract metadata
            metadata = {}
            if not skip_metadata:
                for meta in elem.findall("MetadataEntry"):
                    key = meta.get("key", "")
                    val = meta.get("value", "")
                    if key:
                        metadata[key] = val

                # HRV instantaneous BPM values
                for hrv_list in elem.findall("HeartRateVariabilityMetadataList"):
                    bpm_values = []
                    for inst in hrv_list.findall("InstantaneousBeatsPerMinute"):
                        bpm = safe_float(inst.get("bpm"))
                        if bpm is not None:
                            bpm_values.append(bpm)
                    if bpm_values:
                        metadata["_hrv_bpm_values"] = bpm_values

            # Device
            device_str = elem.get("device")
            device_name = extract_device_name(device_str)
            if device_name:
                export.device_names.add(device_name)

            record = HealthRecord(
                record_type=raw_type,
                display_type=display,
                source_name=elem.get("sourceName", ""),
                value=value,
                unit=elem.get("unit"),
                start_date=start,
                end_date=ts_to_iso(elem.get("endDate")),
                creation_date=ts_to_iso(elem.get("creationDate")),
                source_version=elem.get("sourceVersion"),
                device=device_name,
                date=date,
                metadata=metadata,
                category_value=category_value,
            )

            export.records.append(record)
            export.record_type_counts[display] += 1
            export.source_counts[elem.get("sourceName", "")] += 1

            count += 1

        elif tag == "Workout":
            raw_type = elem.get("workoutActivityType", "")
            display = clean_type(raw_type)
            start = ts_to_iso(elem.get("startDate"))
            date = ts_to_date(elem.get("startDate"))

            # Track date range
            if date:
                if min_date is None or date < min_date:
                    min_date = date
                if max_date is None or date > max_date:
                    max_date = date

            # Parse workout events
            events = []
            for we in elem.findall("WorkoutEvent"):
                events.append({
                    "type": we.get("type", ""),
                    "date": ts_to_iso(we.get("date")),
                    "duration": safe_float(we.get("duration")),
                })

            # Parse workout statistics (iOS 16+)
            statistics = []
            for ws in elem.findall("WorkoutStatistics"):
                statistics.append({
                    "type": clean_type(ws.get("type", "")),
                    "start_date": ts_to_iso(ws.get("startDate")),
                    "end_date": ts_to_iso(ws.get("endDate")),
                    "sum": safe_float(ws.get("sum")),
                    "average": safe_float(ws.get("average")),
                    "minimum": safe_float(ws.get("minimum")),
                    "maximum": safe_float(ws.get("maximum")),
                    "unit": ws.get("unit"),
                })

            metadata = {}
            if not skip_metadata:
                for meta in elem.findall("MetadataEntry"):
                    key = meta.get("key", "")
                    val = meta.get("value", "")
                    if key:
                        metadata[key] = val

            device_name = extract_device_name(elem.get("device"))
            if device_name:
                export.device_names.add(device_name)

            workout = WorkoutRecord(
                activity_type=raw_type,
                display_type=display,
                source_name=elem.get("sourceName", ""),
                duration=safe_float(elem.get("duration")),
                duration_unit=elem.get("durationUnit"),
                total_distance=safe_float(elem.get("totalDistance")),
                total_distance_unit=elem.get("totalDistanceUnit"),
                total_energy_burned=safe_float(elem.get("totalEnergyBurned")),
                total_energy_burned_unit=elem.get("totalEnergyBurnedUnit"),
                start_date=start,
                end_date=ts_to_iso(elem.get("endDate")),
                creation_date=ts_to_iso(elem.get("creationDate")),
                source_version=elem.get("sourceVersion"),
                device=device_name,
                date=date,
                metadata=metadata,
                events=events,
                statistics=statistics,
            )

            export.workouts.append(workout)
            export.source_counts[elem.get("sourceName", "")] += 1
            count += 1

        elif tag == "ActivitySummary":
            date_comp = elem.get("dateComponents", "")
            # dateComponents format: "2024-01-15" (just a date)
            date = date_comp if date_comp else None

            if date:
                if min_date is None or date < min_date:
                    min_date = date
                if max_date is None or date > max_date:
                    max_date = date

            summary = ActivitySummaryRecord(
                date=date or "",
                active_energy_burned=safe_float(elem.get("activeEnergyBurned")),
                active_energy_burned_goal=safe_float(elem.get("activeEnergyBurnedGoal")),
                active_energy_burned_unit=elem.get("activeEnergyBurnedUnit"),
                apple_exercise_time=safe_float(elem.get("appleExerciseTime")),
                apple_exercise_time_goal=safe_float(elem.get("appleExerciseTimeGoal")),
                apple_stand_hours=safe_float(elem.get("appleStandHours")),
                apple_stand_hours_goal=safe_float(elem.get("appleStandHoursGoal")),
                apple_move_time=safe_float(elem.get("appleMoveTime")),
                apple_move_time_goal=safe_float(elem.get("appleMoveTimeGoal")),
            )

            export.activity_summaries.append(summary)
            count += 1

        # Free memory — critical for large files
        elem.clear()
        # Also remove previous siblings from parent to keep memory flat
        while elem.getprevious() is not None:
            del elem.getparent()[0]

        if pbar:
            pbar.update(1)

        if max_records and count >= max_records:
            log.info(f"Reached max_records={max_records}, stopping")
            break

    if pbar:
        pbar.close()

    export.date_range = (min_date, max_date)

    log.info(f"Parsed {count:,} elements")
    log.info(export.summary())

    return export


# ---------------------------------------------------------------------------
# Export to JSON (intermediate format for inspection)
# ---------------------------------------------------------------------------

def export_to_json(data: HealthExport, output_path: str) -> None:
    """Write parsed data to a JSON file for inspection."""
    out = {
        "export_date": data.export_date,
        "locale": data.locale,
        "person": asdict(data.person),
        "record_type_counts": dict(data.record_type_counts),
        "source_counts": dict(data.source_counts),
        "devices": sorted(data.device_names),
        "date_range": list(data.date_range),
        "stats": {
            "total_records": len(data.records),
            "total_workouts": len(data.workouts),
            "total_activity_summaries": len(data.activity_summaries),
        },
        # Sample first 100 records for inspection
        "sample_records": [asdict(r) for r in data.records[:100]],
        "sample_workouts": [asdict(w) for w in data.workouts[:20]],
        "sample_activity_summaries": [asdict(a) for a in data.activity_summaries[:30]],
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(out, f, indent=2, default=str)

    log.info(f"Wrote sample JSON to {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Parse Apple Health export.xml"
    )
    parser.add_argument("input", help="Path to export.xml")
    parser.add_argument(
        "--output", "-o",
        default="data/parsed_health_data.json",
        help="Output JSON path (default: data/parsed_health_data.json)",
    )
    parser.add_argument(
        "--types", "-t",
        nargs="+",
        help="Only include these record types (e.g. HeartRate StepCount SleepAnalysis)",
    )
    parser.add_argument(
        "--max-records", "-n",
        type=int,
        help="Stop after N records (for testing)",
    )
    parser.add_argument(
        "--skip-metadata",
        action="store_true",
        help="Skip metadata parsing (faster)",
    )

    args = parser.parse_args()

    record_types = set(args.types) if args.types else None

    data = parse_health_export(
        args.input,
        record_types=record_types,
        max_records=args.max_records,
        skip_metadata=args.skip_metadata,
    )

    export_to_json(data, args.output)
    print(f"\n{data.summary()}")


if __name__ == "__main__":
    main()
