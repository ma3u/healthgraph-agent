"""Pydantic schemas for the iOS HealthKit ingest payload.

The iOS app reads HealthKit samples natively, then POSTs them as JSON. The
shape mirrors HealthKit semantics (HKQuantitySample / HKCategorySample /
HKWorkout), and the backend translates these into the existing
HealthRecord/WorkoutRecord dataclasses from etl/parse_health_xml.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class QuantitySample(BaseModel):
    """HKQuantitySample — e.g. HeartRate, StepCount, ActiveEnergyBurned."""
    type: str = Field(..., description="Cleaned type, e.g. 'HeartRate'")
    raw_type: Optional[str] = Field(
        None, description="Original HK identifier, e.g. 'HKQuantityTypeIdentifierHeartRate'"
    )
    value: float
    unit: Optional[str] = None
    start_date: datetime
    end_date: datetime
    source_name: str = "iPhone"
    source_version: Optional[str] = None
    device: Optional[str] = None
    uuid: Optional[str] = None  # HKSample uuid; used for dedup if we ever need it


class CategorySample(BaseModel):
    """HKCategorySample — e.g. SleepAnalysis, AppleStandHour."""
    type: str
    raw_type: Optional[str] = None
    category_value: str = Field(..., description="e.g. 'AsleepCore', 'InBed'")
    raw_category_value: Optional[str] = None
    start_date: datetime
    end_date: datetime
    source_name: str = "iPhone"
    source_version: Optional[str] = None
    device: Optional[str] = None
    uuid: Optional[str] = None


class Workout(BaseModel):
    """HKWorkout."""
    activity_type: str = Field(..., description="Cleaned type, e.g. 'Running'")
    raw_activity_type: Optional[str] = None
    duration_seconds: float
    total_distance_meters: Optional[float] = None
    total_energy_kcal: Optional[float] = None
    start_date: datetime
    end_date: datetime
    source_name: str = "iPhone"
    source_version: Optional[str] = None
    device: Optional[str] = None
    uuid: Optional[str] = None


class PersonInfo(BaseModel):
    date_of_birth: Optional[str] = None  # YYYY-MM-DD
    biological_sex: Optional[str] = None  # "Male" | "Female" | "Other"
    blood_type: Optional[str] = None


class IngestPayload(BaseModel):
    """A single sync batch from the iOS app.

    For initial sync, send everything in one or more large batches.
    For incremental sync, the app uses HKAnchoredObjectQuery to find dates
    touched since last anchor, then re-sends the FULL day of samples for each
    affected date so the backend can rebuild that day's DailySummary correctly.
    """
    person: Optional[PersonInfo] = None
    quantity_samples: list[QuantitySample] = Field(default_factory=list)
    category_samples: list[CategorySample] = Field(default_factory=list)
    workouts: list[Workout] = Field(default_factory=list)
    # Range covered by this batch — backend uses this to know which days to (re)compute summaries for
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    client_anchor: Optional[str] = None  # opaque; client may use this to track its own state


class IngestResponse(BaseModel):
    accepted_samples: int
    accepted_workouts: int
    days_affected: list[str]  # YYYY-MM-DD list
    server_anchor: str  # opaque token the client should send back next time


class SyncState(BaseModel):
    last_anchor: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    total_samples_seen: int = 0


class SyncPreview(BaseModel):
    """Tells the iOS app where Aura currently stops, so the app can locally
    compute the HealthKit delta and present a confirmation dialog before the
    user kicks off the upload.
    """
    latest_day_in_aura: Optional[str] = None  # YYYY-MM-DD, max Day.date
    total_days_in_aura: int = 0
    total_workouts_in_aura: int = 0


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
