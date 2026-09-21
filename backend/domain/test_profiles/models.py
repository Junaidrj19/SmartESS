"""Canonical TestProfile domain model.

TestProfile describes HOW THE MODULE IS STRESSED. It references a ModuleProfile
by id and must not carry telemetry, ML outputs, diagnoses, or an embedded profile.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from domain.module_profiles.engineering import FiniteNumber, _reject_non_finite_number
from domain.module_profiles.enums import HealthParameter, SourceType, Unit
from domain.test_profiles.conditions import TestConditionValue
from domain.test_profiles.enums import TestType


SCHEMA_VERSION = "1.0.0"

FORBIDDEN_TEST_PROFILE_FIELDS = frozenset(
    {
        "timestamp",
        "cycle_number",
        "lot_id",
        "telemetry",
        "measurements",
        "anomaly_score",
        "anomaly_scores",
        "degradation_state",
        "degradation_label",
        "prediction",
        "predictions",
        "investigation",
        "investigation_id",
        "test_run",
        "dataset",
        "ground_truth",
        "predicted_failure",
        "failure_probability",
        "model_prediction",
        "module_profile",
        "failure_diagnosis",
    }
)


class ElectricalStress(BaseModel):
    """Applied electrical test conditions, not device ratings."""

    model_config = ConfigDict(extra="forbid")

    vds: Optional[TestConditionValue] = None
    id: Optional[TestConditionValue] = None
    vgs: Optional[TestConditionValue] = None
    vgs_on: Optional[TestConditionValue] = None
    vgs_off: Optional[TestConditionValue] = None
    switching_frequency: Optional[TestConditionValue] = None
    duty_cycle_percent: Optional[FiniteNumber] = None
    gate_resistance: Optional[TestConditionValue] = None
    electrical_power_W: Optional[FiniteNumber] = None

    @field_validator("duty_cycle_percent", "electrical_power_W", mode="before")
    @classmethod
    def _finite_optional(cls, value: object) -> object:
        if value is None:
            return value
        return _reject_non_finite_number(value)


class ThermalStress(BaseModel):
    """Applied thermal excursion / control setpoints."""

    model_config = ConfigDict(extra="forbid")

    tj_minimum: Optional[TestConditionValue] = None
    tj_maximum: Optional[TestConditionValue] = None
    delta_tj: Optional[TestConditionValue] = None
    tc_minimum: Optional[TestConditionValue] = None
    tc_maximum: Optional[TestConditionValue] = None
    ambient_temperature_minimum: Optional[TestConditionValue] = None
    ambient_temperature_maximum: Optional[TestConditionValue] = None
    thermal_control_method: Optional[str] = Field(default=None, min_length=1)
    cooling_method: Optional[str] = Field(default=None, min_length=1)


class EnvironmentalConditions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ambient_temperature: Optional[TestConditionValue] = None
    humidity_percent: Optional[FiniteNumber] = None
    pressure_value: Optional[FiniteNumber] = None
    pressure_unit: Optional[str] = Field(default=None, min_length=1)
    atmosphere: Optional[str] = Field(default=None, min_length=1)
    cooling_method: Optional[str] = Field(default=None, min_length=1)

    @field_validator("humidity_percent", "pressure_value", mode="before")
    @classmethod
    def _finite_optional(cls, value: object) -> object:
        if value is None:
            return value
        return _reject_non_finite_number(value)


class CycleProfile(BaseModel):
    """Timing for cyclic tests such as power cycling."""

    model_config = ConfigDict(extra="forbid")

    target_cycles: int = Field(ge=1)
    heating_duration_s: FiniteNumber
    cooling_duration_s: FiniteNumber
    dwell_time_s: Optional[FiniteNumber] = None
    cycle_duration_s: Optional[FiniteNumber] = None
    cycle_frequency_Hz: Optional[FiniteNumber] = None

    @field_validator(
        "heating_duration_s",
        "cooling_duration_s",
        "dwell_time_s",
        "cycle_duration_s",
        "cycle_frequency_Hz",
        mode="before",
    )
    @classmethod
    def _finite_optional(cls, value: object) -> object:
        if value is None:
            return value
        return _reject_non_finite_number(value)


class HtolConfiguration(BaseModel):
    """Minimum HTOL description: temperature, duration, optional electrical bias."""

    model_config = ConfigDict(extra="forbid")

    temperature: TestConditionValue
    duration_s: FiniteNumber
    vds: Optional[TestConditionValue] = None
    id: Optional[TestConditionValue] = None
    vgs: Optional[TestConditionValue] = None

    @field_validator("duration_s", mode="before")
    @classmethod
    def _finite_duration(cls, value: object) -> float:
        return _reject_non_finite_number(value)


class HtrbConfiguration(BaseModel):
    """Minimum HTRB description: temperature, reverse voltage, duration."""

    model_config = ConfigDict(extra="forbid")

    temperature: TestConditionValue
    duration_s: FiniteNumber
    reverse_voltage: TestConditionValue
    bias_condition: Optional[str] = Field(default=None, min_length=1)

    @field_validator("duration_s", mode="before")
    @classmethod
    def _finite_duration(cls, value: object) -> float:
        return _reject_non_finite_number(value)


class HtgbConfiguration(BaseModel):
    """Minimum HTGB description: temperature, gate bias, duration."""

    model_config = ConfigDict(extra="forbid")

    temperature: TestConditionValue
    duration_s: FiniteNumber
    gate_bias: TestConditionValue
    drain_source_condition: Optional[str] = Field(default=None, min_length=1)

    @field_validator("duration_s", mode="before")
    @classmethod
    def _finite_duration(cls, value: object) -> float:
        return _reject_non_finite_number(value)


class MeasurementChannel(BaseModel):
    """Declares a telemetry channel to collect. Stores no samples."""

    model_config = ConfigDict(extra="forbid")

    parameter: HealthParameter
    unit: Optional[Unit] = None
    method_or_instrument: Optional[str] = Field(default=None, min_length=1)


class MeasurementConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channels: list[MeasurementChannel] = Field(min_length=1)
    sampling_interval_s: Optional[FiniteNumber] = None
    sampling_frequency_Hz: Optional[FiniteNumber] = None

    @field_validator("sampling_interval_s", "sampling_frequency_Hz", mode="before")
    @classmethod
    def _finite_optional(cls, value: object) -> object:
        if value is None:
            return value
        return _reject_non_finite_number(value)

    @model_validator(mode="after")
    def _unique_parameters(self) -> MeasurementConfiguration:
        names = [channel.parameter for channel in self.channels]
        if len(names) != len(set(names)):
            raise ValueError("measurement parameters must be unique")
        return self


class AcceptanceCriteriaReference(BaseModel):
    """Which ModuleProfile acceptance criteria apply to this test. Not a duplicate of the limits."""

    model_config = ConfigDict(extra="forbid")

    parameters: list[HealthParameter] = Field(min_length=1)
    notes: Optional[str] = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> AcceptanceCriteriaReference:
        if len(self.parameters) != len(set(self.parameters)):
            raise ValueError("acceptance criteria parameter references must be unique")
        return self


class TestProfileProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: SourceType
    source_document: Optional[str] = Field(default=None, min_length=1)
    source_revision: Optional[str] = Field(default=None, min_length=1)
    source_url: Optional[str] = Field(default=None, min_length=1)
    created_by: Optional[str] = Field(default=None, min_length=1)
    created_at: Optional[datetime] = None
    configuration_version: Optional[str] = Field(default=None, min_length=1)
    notes: Optional[str] = Field(default=None, min_length=1)


class TestProfile(BaseModel):
    """How a module is stressed. `__test__` disables pytest class collection."""

    __test__: ClassVar[bool] = False
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.0\.0$")
    test_id: str = Field(min_length=1)
    module_profile_id: str = Field(min_length=1)
    test_type: TestType
    objective: Optional[str] = Field(default=None, min_length=1)
    electrical_stress: Optional[ElectricalStress] = None
    thermal_stress: Optional[ThermalStress] = None
    environmental_conditions: Optional[EnvironmentalConditions] = None
    cycle_profile: Optional[CycleProfile] = None
    htol_configuration: Optional[HtolConfiguration] = None
    htrb_configuration: Optional[HtrbConfiguration] = None
    htgb_configuration: Optional[HtgbConfiguration] = None
    measurement_configuration: Optional[MeasurementConfiguration] = None
    acceptance_criteria_reference: Optional[AcceptanceCriteriaReference] = None
    provenance: TestProfileProvenance

    @model_validator(mode="before")
    @classmethod
    def _reject_telemetry_and_embedded_profile(cls, data: object) -> object:
        if isinstance(data, dict):
            illegal = FORBIDDEN_TEST_PROFILE_FIELDS.intersection(data)
            if illegal:
                names = ", ".join(sorted(illegal))
                raise ValueError(
                    f"TestProfile must not contain telemetry, ML, investigation, or embedded ModuleProfile fields: {names}"
                )
        return data

    @model_validator(mode="after")
    def _domain_rules(self) -> TestProfile:
        from domain.test_profiles.validation import apply_test_profile_rules

        apply_test_profile_rules(self)
        return self
