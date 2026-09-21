"""Canonical ModuleProfile domain model.

ModuleProfile describes WHAT THE COMPONENT IS. It must not carry telemetry
measurements, ML outputs, anomalies, degradation states, investigations, or
test-run results.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from domain.module_profiles.engineering import EngineeringValue, FiniteNumber, Provenance, _reject_non_finite_number
from domain.module_profiles.enums import (
    FailureMechanismRef,
    HealthParameter,
    ProfileStatus,
    ReliabilityTestType,
    Technology,
    Topology,
    Unit,
)


SCHEMA_VERSION = "1.0.0"

# Telemetry / investigation fields that must never appear on ModuleProfile.
FORBIDDEN_MODULE_PROFILE_FIELDS = frozenset(
    {
        "timestamp",
        "cycle_number",
        "lot_id",
        "telemetry",
        "measurements",
        "anomaly_score",
        "anomaly_scores",
        "degradation_state",
        "prediction",
        "predictions",
        "investigation",
        "investigation_id",
        "test_run",
        "test_profile",
        "dataset",
        "ground_truth",
        "predicted_failure",
        "failure_probability",
        "model_prediction",
    }
)


class ModuleIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_id: str = Field(min_length=1)
    manufacturer: Optional[str] = Field(default=None, min_length=1)
    part_number: Optional[str] = Field(default=None, min_length=1)
    device_family: Optional[str] = Field(default=None, min_length=1)
    technology: Technology
    qualification: Optional[str] = Field(default=None, min_length=1)
    generation: Optional[str] = Field(default=None, min_length=1)
    status: ProfileStatus


class ModuleDimensions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    length: FiniteNumber
    width: FiniteNumber
    height: FiniteNumber
    unit: Unit

    @field_validator("length", "width", "height", mode="before")
    @classmethod
    def _finite(cls, value: object) -> float:
        return _reject_non_finite_number(value)

    @model_validator(mode="after")
    def _positive_mm(self) -> ModuleDimensions:
        if self.unit is not Unit.MM:
            raise ValueError("module dimensions unit must be mm")
        for name in ("length", "width", "height"):
            magnitude = getattr(self, name)
            if magnitude <= 0:
                raise ValueError(f"dimension {name} must be positive")
        return self


class Device(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topology: Topology
    switch_count: int = Field(ge=1)
    mosfet_configuration: Optional[str] = Field(default=None, min_length=1)
    package: Optional[str] = Field(default=None, min_length=1)
    dimensions: Optional[ModuleDimensions] = None


class ElectricalSpecifications(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blocking_voltage: Optional[list[EngineeringValue]] = None
    continuous_current: Optional[list[EngineeringValue]] = None
    peak_current: Optional[list[EngineeringValue]] = None
    rds_on: Optional[list[EngineeringValue]] = None
    vgs_maximum: Optional[list[EngineeringValue]] = None
    vgs_on: Optional[list[EngineeringValue]] = None
    vgs_off: Optional[list[EngineeringValue]] = None
    vth: Optional[list[EngineeringValue]] = None
    igss: Optional[list[EngineeringValue]] = None
    idss: Optional[list[EngineeringValue]] = None
    switching_frequency: Optional[list[EngineeringValue]] = None

    @field_validator(
        "blocking_voltage",
        "continuous_current",
        "peak_current",
        "rds_on",
        "vgs_maximum",
        "vgs_on",
        "vgs_off",
        "vth",
        "igss",
        "idss",
        "switching_frequency",
        mode="after",
    )
    @classmethod
    def _non_empty_if_present(cls, value: Optional[list[EngineeringValue]]) -> Optional[list[EngineeringValue]]:
        if value is not None and len(value) == 0:
            raise ValueError("specification lists must be omitted when unknown, not empty")
        return value


class GateDrive(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommended_positive_gate_voltage: Optional[list[EngineeringValue]] = None
    recommended_negative_gate_voltage: Optional[list[EngineeringValue]] = None
    gate_resistance: Optional[list[EngineeringValue]] = None
    total_gate_charge: Optional[list[EngineeringValue]] = None


class ThermalSpecifications(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tj_maximum: Optional[EngineeringValue] = None
    tj_minimum: Optional[EngineeringValue] = None
    tc_maximum: Optional[EngineeringValue] = None
    ambient_temperature_range: Optional[EngineeringValue] = None
    rth_j_c: Optional[list[EngineeringValue]] = None
    thermal_impedance: Optional[list[EngineeringValue]] = None
    cooling_method: Optional[str] = Field(default=None, min_length=1)


class HealthParameters(BaseModel):
    """Declares which parameters are relevant. Stores no measurements."""

    model_config = ConfigDict(extra="forbid")

    primary: list[HealthParameter] = Field(default_factory=list)
    secondary: list[HealthParameter] = Field(default_factory=list)

    @model_validator(mode="after")
    def _no_overlap(self) -> HealthParameters:
        overlap = set(self.primary) & set(self.secondary)
        if overlap:
            names = ", ".join(sorted(item.value for item in overlap))
            raise ValueError(f"health parameters cannot be both primary and secondary: {names}")
        if len(self.primary) != len(set(self.primary)):
            raise ValueError("primary health parameters must be unique")
        if len(self.secondary) != len(set(self.secondary)):
            raise ValueError("secondary health parameters must be unique")
        return self


class AcceptanceCriterion(BaseModel):
    """Conventional pass/fail limits. Not ML anomaly thresholds."""

    model_config = ConfigDict(extra="forbid")

    parameter: HealthParameter
    maximum_absolute: Optional[EngineeringValue] = None
    minimum_absolute: Optional[EngineeringValue] = None
    maximum_relative_change_percent: Optional[FiniteNumber] = None
    maximum_allowed_shift: Optional[EngineeringValue] = None
    notes: Optional[str] = Field(default=None, min_length=1)

    @field_validator("maximum_relative_change_percent", mode="before")
    @classmethod
    def _finite_percent(cls, value: object) -> object:
        if value is None:
            return value
        return _reject_non_finite_number(value)

    @model_validator(mode="after")
    def _limits_consistent(self) -> AcceptanceCriterion:
        if (
            self.maximum_absolute is None
            and self.minimum_absolute is None
            and self.maximum_relative_change_percent is None
            and self.maximum_allowed_shift is None
        ):
            raise ValueError("acceptance criterion must define at least one limit")
        if self.maximum_relative_change_percent is not None and self.maximum_relative_change_percent < 0:
            raise ValueError("maximum_relative_change_percent must not be negative")
        if (
            self.minimum_absolute is not None
            and self.maximum_absolute is not None
            and self.minimum_absolute.unit != self.maximum_absolute.unit
        ):
            raise ValueError("minimum and maximum absolute acceptance limits must use the same unit")
        if (
            self.minimum_absolute is not None
            and self.maximum_absolute is not None
            and self.minimum_absolute.value is not None
            and self.maximum_absolute.value is not None
            and self.minimum_absolute.value > self.maximum_absolute.value
        ):
            raise ValueError("minimum acceptance threshold must not exceed maximum threshold")
        return self


class ReliabilityMetadata(BaseModel):
    """Knowledge/configuration references. Not diagnoses."""

    model_config = ConfigDict(extra="forbid")

    supported_tests: list[ReliabilityTestType] = Field(default_factory=list)
    relevant_failure_mechanisms: list[FailureMechanismRef] = Field(default_factory=list)
    notes: Optional[str] = Field(default=None, min_length=1)


class ModuleProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.0\.0$")
    identity: ModuleIdentity
    device: Device
    electrical: ElectricalSpecifications = Field(default_factory=ElectricalSpecifications)
    gate_drive: Optional[GateDrive] = None
    thermal: Optional[ThermalSpecifications] = None
    health_parameters: HealthParameters = Field(default_factory=HealthParameters)
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    reliability: Optional[ReliabilityMetadata] = None
    provenance: Provenance

    @model_validator(mode="before")
    @classmethod
    def _reject_telemetry_shaped_payloads(cls, data: object) -> object:
        if isinstance(data, dict):
            illegal = FORBIDDEN_MODULE_PROFILE_FIELDS.intersection(data)
            if illegal:
                names = ", ".join(sorted(illegal))
                raise ValueError(
                    f"ModuleProfile must not contain telemetry, ML, or investigation fields: {names}"
                )
        return data

    @model_validator(mode="after")
    def _domain_rules(self) -> ModuleProfile:
        from domain.module_profiles.validation import apply_module_profile_rules

        apply_module_profile_rules(self)
        return self
