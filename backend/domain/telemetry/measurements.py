"""Structured measurement observations.

These are telemetry *observations*, not ModuleProfile EngineeringValue
specifications and not TestProfile applied conditions.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from domain.module_profiles.engineering import FiniteNumber, OperatingConditions, _reject_non_finite_number
from domain.module_profiles.enums import Unit
from domain.telemetry.enums import MeasurementOrigin, MeasurementStatus, TelemetryParameter


class DerivationProvenance(BaseModel):
    """How a derived value was obtained. Not a calculation engine."""

    model_config = ConfigDict(extra="forbid")

    method: str = Field(min_length=1)
    input_parameters: Optional[list[TelemetryParameter]] = None
    notes: Optional[str] = Field(default=None, min_length=1)


class Measurement(BaseModel):
    """One parameter observation at a telemetry timestamp."""

    model_config = ConfigDict(extra="forbid")

    parameter: TelemetryParameter
    status: MeasurementStatus
    origin: MeasurementOrigin
    value: Optional[FiniteNumber] = None
    unit: Optional[Unit] = None
    uncertainty: Optional[FiniteNumber] = None
    sensor_id: Optional[str] = Field(default=None, min_length=1)
    channel_id: Optional[str] = Field(default=None, min_length=1)
    instrument_id: Optional[str] = Field(default=None, min_length=1)
    acquisition_system: Optional[str] = Field(default=None, min_length=1)
    conditions: Optional[OperatingConditions] = None
    derivation: Optional[DerivationProvenance] = None

    @field_validator("value", "uncertainty", mode="before")
    @classmethod
    def _finite_optional(cls, value: object) -> object:
        if value is None:
            return value
        return _reject_non_finite_number(value)

    @model_validator(mode="after")
    def _status_and_origin_consistent(self) -> Measurement:
        if self.uncertainty is not None and self.uncertainty < 0:
            raise ValueError("uncertainty must not be negative")
        if self.uncertainty is not None and self.status is MeasurementStatus.MISSING:
            raise ValueError("missing measurements must not include uncertainty")

        if self.status is MeasurementStatus.MISSING:
            if self.value is not None:
                raise ValueError("missing measurements must not include a numeric value")
        elif self.status in {MeasurementStatus.VALID, MeasurementStatus.ESTIMATED, MeasurementStatus.DERIVED}:
            if self.value is None:
                raise ValueError(f"{self.status.value} measurements require a numeric value")
            if self.unit is None:
                raise ValueError(f"{self.status.value} measurements require an explicit unit")
        elif self.status is MeasurementStatus.INVALID:
            if self.value is not None and self.unit is None:
                raise ValueError("invalid measurements that include a value require an explicit unit")

        if self.status is MeasurementStatus.DERIVED and self.origin is not MeasurementOrigin.DERIVED:
            raise ValueError("status derived requires origin derived")
        if self.origin is MeasurementOrigin.MEASURED and self.derivation is not None:
            raise ValueError("measured observations must not include derivation provenance")
        if self.origin is MeasurementOrigin.DERIVED and self.status is MeasurementStatus.MISSING:
            raise ValueError("derived observations must not use status missing")
        return self
