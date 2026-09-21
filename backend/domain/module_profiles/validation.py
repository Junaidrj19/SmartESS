"""Deterministic structural and domain validation for ModuleProfile.

No physical-failure diagnosis, ML scoring, or LLM reasoning.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from domain.module_profiles.engineering import EngineeringValue
from domain.module_profiles.enums import SpecificationType, Unit
from domain.module_profiles.models import ModuleProfile, ThermalSpecifications

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "sic-module-profile.schema.json"

POSITIVE_ELECTRICAL_FIELDS = (
    "blocking_voltage",
    "continuous_current",
    "peak_current",
    "rds_on",
    "switching_frequency",
)

EXPECTED_UNITS: dict[str, frozenset[Unit]] = {
    "blocking_voltage": frozenset({Unit.V}),
    "continuous_current": frozenset({Unit.A}),
    "peak_current": frozenset({Unit.A}),
    "rds_on": frozenset({Unit.MOHM, Unit.OHM}),
    "vgs_maximum": frozenset({Unit.V}),
    "vgs_on": frozenset({Unit.V}),
    "vgs_off": frozenset({Unit.V}),
    "vth": frozenset({Unit.V}),
    "igss": frozenset({Unit.UA, Unit.A}),
    "idss": frozenset({Unit.UA, Unit.A}),
    "switching_frequency": frozenset({Unit.HZ}),
    "recommended_positive_gate_voltage": frozenset({Unit.V}),
    "recommended_negative_gate_voltage": frozenset({Unit.V}),
    "gate_resistance": frozenset({Unit.OHM, Unit.MOHM}),
    "total_gate_charge": frozenset({Unit.NC}),
    "tj_maximum": frozenset({Unit.C}),
    "tj_minimum": frozenset({Unit.C}),
    "tc_maximum": frozenset({Unit.C}),
    "ambient_temperature_range": frozenset({Unit.C}),
    "rth_j_c": frozenset({Unit.C_PER_W}),
    "thermal_impedance": frozenset({Unit.C_PER_W}),
}


def _magnitudes(spec: EngineeringValue) -> list[float]:
    return [item for item in (spec.value, spec.min_value, spec.max_value) if item is not None]


def _check_unit(field_name: str, spec: EngineeringValue) -> None:
    allowed = EXPECTED_UNITS.get(field_name)
    if allowed is not None and spec.unit not in allowed:
        allowed_text = ", ".join(sorted(unit.value for unit in allowed))
        raise ValueError(f"{field_name} unit must be one of: {allowed_text}")


def _check_positive(field_name: str, spec: EngineeringValue) -> None:
    for magnitude in _magnitudes(spec):
        if magnitude <= 0:
            raise ValueError(f"{field_name} must be positive")


def _iter_named_specs(container: object, field_names: tuple[str, ...]) -> list[tuple[str, EngineeringValue]]:
    found: list[tuple[str, EngineeringValue]] = []
    for name in field_names:
        raw = getattr(container, name, None)
        if raw is None:
            continue
        if isinstance(raw, EngineeringValue):
            found.append((name, raw))
        else:
            for item in raw:
                found.append((name, item))
    return found


def apply_module_profile_rules(profile: ModuleProfile) -> None:
    electrical_fields = (
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
    )
    for name, spec in _iter_named_specs(profile.electrical, electrical_fields):
        _check_unit(name, spec)
        if name in POSITIVE_ELECTRICAL_FIELDS:
            _check_positive(name, spec)

    if profile.gate_drive is not None:
        gate_fields = (
            "recommended_positive_gate_voltage",
            "recommended_negative_gate_voltage",
            "gate_resistance",
            "total_gate_charge",
        )
        for name, spec in _iter_named_specs(profile.gate_drive, gate_fields):
            _check_unit(name, spec)
            if name in {"gate_resistance", "total_gate_charge"}:
                _check_positive(name, spec)

    if profile.thermal is not None:
        _validate_thermal(profile.thermal)


def _validate_thermal(thermal: ThermalSpecifications) -> None:
    single_fields = ("tj_maximum", "tj_minimum", "tc_maximum", "ambient_temperature_range")
    list_fields = ("rth_j_c", "thermal_impedance")
    for name, spec in _iter_named_specs(thermal, single_fields + list_fields):
        _check_unit(name, spec)
        if name in {"rth_j_c", "thermal_impedance"}:
            _check_positive(name, spec)

    if thermal.ambient_temperature_range is not None:
        if thermal.ambient_temperature_range.specification_type is not SpecificationType.OPERATING_RANGE:
            raise ValueError("ambient_temperature_range must use specification_type operating_range")

    if thermal.tj_maximum is not None and thermal.tj_minimum is not None:
        tmax = thermal.tj_maximum.value
        tmin = thermal.tj_minimum.value
        if tmax is not None and tmin is not None and tmax <= tmin:
            raise ValueError("Tj maximum must be greater than Tj minimum")


def parse_module_profile(data: Mapping[str, Any]) -> ModuleProfile:
    """Validate a mapping and return a ModuleProfile."""
    return ModuleProfile.model_validate(data)


def load_json_schema() -> dict[str, Any]:
    import json

    with SCHEMA_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_against_json_schema(data: Mapping[str, Any]) -> None:
    from jsonschema import Draft202012Validator

    schema = load_json_schema()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(data)
