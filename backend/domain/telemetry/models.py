"""Canonical telemetry observation model.

Telemetry describes WHAT WAS MEASURED during a test. It references a module and
a test by identifier only and must not carry ML outputs or investigation fields.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from domain.telemetry.enums import CyclePhase, DataOrigin, TelemetrySourceType
from domain.telemetry.measurements import Measurement


SCHEMA_VERSION = "1.0.0"

FORBIDDEN_TELEMETRY_FIELDS = frozenset(
    {
        "anomaly_score",
        "anomaly_scores",
        "prediction",
        "predictions",
        "predicted_failure",
        "failure_probability",
        "failure_mechanism",
        "hypothesis",
        "investigation_result",
        "investigation",
        "investigation_id",
        "degradation_state",
        "ground_truth",
        "model_prediction",
        "module_profile",
        "test_profile",
    }
)


def require_utc_datetime(value: object, *, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{field_name} must be timezone-aware UTC; naive timestamps are not valid canonical telemetry")
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} canonical representation must be UTC (offset +00:00)")
    return value.astimezone(timezone.utc)


class TelemetryProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_origin: DataOrigin
    source_type: Optional[TelemetrySourceType] = None
    source_file: Optional[str] = Field(default=None, min_length=1)
    source_dataset: Optional[str] = Field(default=None, min_length=1)
    acquisition_system: Optional[str] = Field(default=None, min_length=1)
    imported_at: Optional[datetime] = None
    import_version: Optional[str] = Field(default=None, min_length=1)
    notes: Optional[str] = Field(default=None, min_length=1)

    @field_validator("imported_at", mode="after")
    @classmethod
    def _imported_at_utc(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is None:
            return value
        return require_utc_datetime(value, field_name="imported_at")


class TelemetryRecord(BaseModel):
    """One timestamped observation during a test."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.0\.0$")
    telemetry_id: str = Field(min_length=1)
    module_id: str = Field(min_length=1)
    test_id: str = Field(min_length=1)
    timestamp: datetime
    measurements: list[Measurement] = Field(min_length=1)
    provenance: TelemetryProvenance
    lot_id: Optional[str] = Field(default=None, min_length=1)
    dataset_id: Optional[str] = Field(default=None, min_length=1)
    batch_id: Optional[str] = Field(default=None, min_length=1)
    cycle_number: Optional[int] = Field(default=None, ge=0)
    cycle_phase: Optional[CyclePhase] = None

    @model_validator(mode="before")
    @classmethod
    def _reject_analytical_fields(cls, data: object) -> object:
        if isinstance(data, dict):
            illegal = FORBIDDEN_TELEMETRY_FIELDS.intersection(data)
            if illegal:
                names = ", ".join(sorted(illegal))
                raise ValueError(
                    f"Telemetry must not contain ML or investigation fields: {names}"
                )
        return data

    @field_validator("timestamp", mode="after")
    @classmethod
    def _timestamp_utc(cls, value: datetime) -> datetime:
        return require_utc_datetime(value, field_name="timestamp")

    @model_validator(mode="after")
    def _domain_rules(self) -> TelemetryRecord:
        from domain.telemetry.validation import apply_telemetry_rules

        apply_telemetry_rules(self)
        return self
