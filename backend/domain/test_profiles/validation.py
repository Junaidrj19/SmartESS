"""Deterministic structural and domain validation for TestProfile."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping

from domain.module_profiles.enums import Unit
from domain.test_profiles.conditions import TestConditionValue
from domain.test_profiles.enums import TestType
from domain.test_profiles.models import (
    CycleProfile,
    ElectricalStress,
    EnvironmentalConditions,
    TestProfile,
    ThermalStress,
)

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "test-profile.schema.json"

DELTA_TJ_ABS_TOL = 1e-6

POSITIVE_ELECTRICAL = frozenset({"vds", "id", "switching_frequency", "gate_resistance"})
VOLTAGE_FIELDS = frozenset({"vds", "vgs", "vgs_on", "vgs_off", "reverse_voltage", "gate_bias"})
CURRENT_FIELDS = frozenset({"id"})
RESISTANCE_FIELDS = frozenset({"gate_resistance"})
FREQUENCY_FIELDS = frozenset({"switching_frequency"})
TEMPERATURE_FIELDS = frozenset(
    {
        "tj_minimum",
        "tj_maximum",
        "delta_tj",
        "tc_minimum",
        "tc_maximum",
        "ambient_temperature_minimum",
        "ambient_temperature_maximum",
        "ambient_temperature",
        "temperature",
    }
)


def _point(spec: TestConditionValue | None) -> float | None:
    if spec is None:
        return None
    return spec.value


def _check_unit(name: str, spec: TestConditionValue) -> None:
    if name in VOLTAGE_FIELDS and spec.unit is not Unit.V:
        raise ValueError(f"{name} unit must be V")
    if name in CURRENT_FIELDS and spec.unit is not Unit.A:
        raise ValueError(f"{name} unit must be A")
    if name in RESISTANCE_FIELDS and spec.unit not in {Unit.OHM, Unit.MOHM}:
        raise ValueError(f"{name} unit must be Ohm or mOhm")
    if name in FREQUENCY_FIELDS and spec.unit is not Unit.HZ:
        raise ValueError(f"{name} unit must be Hz")
    if name in TEMPERATURE_FIELDS and spec.unit is not Unit.C:
        raise ValueError(f"{name} unit must be C")


def _check_positive_point(name: str, spec: TestConditionValue) -> None:
    magnitudes = [item for item in (spec.value, spec.min_value, spec.max_value) if item is not None]
    for magnitude in magnitudes:
        if magnitude <= 0:
            raise ValueError(f"{name} must be positive")


def apply_test_profile_rules(profile: TestProfile) -> None:
    if profile.electrical_stress is not None:
        _validate_electrical(profile.electrical_stress)
    if profile.thermal_stress is not None:
        _validate_thermal(profile.thermal_stress)
    if profile.environmental_conditions is not None:
        _validate_environment(profile.environmental_conditions)
    if profile.cycle_profile is not None:
        _validate_cycle(profile.cycle_profile)
    if profile.measurement_configuration is not None:
        _validate_measurement(profile)
    _validate_typed_sections(profile)
    _validate_test_type_minimums(profile)


def _validate_electrical(stress: ElectricalStress) -> None:
    named = {
        "vds": stress.vds,
        "id": stress.id,
        "vgs": stress.vgs,
        "vgs_on": stress.vgs_on,
        "vgs_off": stress.vgs_off,
        "switching_frequency": stress.switching_frequency,
        "gate_resistance": stress.gate_resistance,
    }
    for name, spec in named.items():
        if spec is None:
            continue
        _check_unit(name, spec)
        if name in POSITIVE_ELECTRICAL:
            _check_positive_point(name, spec)
    if stress.duty_cycle_percent is not None and not 0 <= stress.duty_cycle_percent <= 100:
        raise ValueError("duty_cycle_percent must be between 0 and 100")
    if stress.electrical_power_W is not None and stress.electrical_power_W < 0:
        raise ValueError("electrical_power_W must not be negative")


def _validate_thermal(thermal: ThermalStress) -> None:
    named = {
        "tj_minimum": thermal.tj_minimum,
        "tj_maximum": thermal.tj_maximum,
        "delta_tj": thermal.delta_tj,
        "tc_minimum": thermal.tc_minimum,
        "tc_maximum": thermal.tc_maximum,
        "ambient_temperature_minimum": thermal.ambient_temperature_minimum,
        "ambient_temperature_maximum": thermal.ambient_temperature_maximum,
    }
    for name, spec in named.items():
        if spec is None:
            continue
        _check_unit(name, spec)
        if name == "delta_tj":
            _check_positive_point(name, spec)

    tmin = _point(thermal.tj_minimum)
    tmax = _point(thermal.tj_maximum)
    delta = _point(thermal.delta_tj)
    if tmin is not None and tmax is not None and tmax <= tmin:
        raise ValueError("Tj maximum must be greater than Tj minimum")
    if tmin is not None and tmax is not None and delta is not None:
        expected = tmax - tmin
        if not math.isclose(expected, delta, rel_tol=0.0, abs_tol=DELTA_TJ_ABS_TOL):
            raise ValueError("delta_Tj must equal Tj_max - Tj_min; inconsistent values are not corrected")

    tc_min = _point(thermal.tc_minimum)
    tc_max = _point(thermal.tc_maximum)
    if tc_min is not None and tc_max is not None and tc_max <= tc_min:
        raise ValueError("Tc maximum must be greater than Tc minimum")

    ta_min = _point(thermal.ambient_temperature_minimum)
    ta_max = _point(thermal.ambient_temperature_maximum)
    if ta_min is not None and ta_max is not None and ta_max <= ta_min:
        raise ValueError("ambient temperature maximum must be greater than minimum")


def _validate_environment(env: EnvironmentalConditions) -> None:
    if env.ambient_temperature is not None:
        _check_unit("ambient_temperature", env.ambient_temperature)
    if env.humidity_percent is not None and not 0 <= env.humidity_percent <= 100:
        raise ValueError("humidity_percent must be between 0 and 100")
    if env.pressure_value is not None and env.pressure_value <= 0:
        raise ValueError("pressure_value must be positive")


def _validate_cycle(cycle: CycleProfile) -> None:
    if cycle.heating_duration_s < 0:
        raise ValueError("heating_duration_s must not be negative")
    if cycle.cooling_duration_s < 0:
        raise ValueError("cooling_duration_s must not be negative")
    if cycle.dwell_time_s is not None and cycle.dwell_time_s < 0:
        raise ValueError("dwell_time_s must not be negative")
    if cycle.cycle_duration_s is not None and cycle.cycle_duration_s <= 0:
        raise ValueError("cycle_duration_s must be positive when supplied")
    if cycle.cycle_frequency_Hz is not None and cycle.cycle_frequency_Hz <= 0:
        raise ValueError("cycle_frequency_Hz must be positive when supplied")


def _validate_measurement(profile: TestProfile) -> None:
    config = profile.measurement_configuration
    if config is None:
        return
    if config.sampling_interval_s is not None and config.sampling_interval_s <= 0:
        raise ValueError("sampling_interval_s must be positive")
    if config.sampling_frequency_Hz is not None and config.sampling_frequency_Hz <= 0:
        raise ValueError("sampling_frequency_Hz must be positive")


def _validate_typed_sections(profile: TestProfile) -> None:
    if profile.htol_configuration is not None:
        _check_unit("temperature", profile.htol_configuration.temperature)
        if profile.htol_configuration.duration_s < 0:
            raise ValueError("HTOL duration_s must not be negative")
        for name, spec in {
            "vds": profile.htol_configuration.vds,
            "id": profile.htol_configuration.id,
            "vgs": profile.htol_configuration.vgs,
        }.items():
            if spec is None:
                continue
            _check_unit(name, spec)
            if name in POSITIVE_ELECTRICAL:
                _check_positive_point(name, spec)

    if profile.htrb_configuration is not None:
        _check_unit("temperature", profile.htrb_configuration.temperature)
        _check_unit("reverse_voltage", profile.htrb_configuration.reverse_voltage)
        _check_positive_point("reverse_voltage", profile.htrb_configuration.reverse_voltage)
        if profile.htrb_configuration.duration_s < 0:
            raise ValueError("HTRB duration_s must not be negative")

    if profile.htgb_configuration is not None:
        _check_unit("temperature", profile.htgb_configuration.temperature)
        _check_unit("gate_bias", profile.htgb_configuration.gate_bias)
        if profile.htgb_configuration.duration_s < 0:
            raise ValueError("HTGB duration_s must not be negative")


def _validate_test_type_minimums(profile: TestProfile) -> None:
    if profile.test_type is TestType.POWER_CYCLING:
        if profile.cycle_profile is None:
            raise ValueError("power_cycling requires cycle_profile")
        if profile.thermal_stress is None:
            raise ValueError("power_cycling requires thermal_stress")
        if profile.thermal_stress.tj_minimum is None or profile.thermal_stress.tj_maximum is None:
            raise ValueError("power_cycling requires tj_minimum and tj_maximum")
        if profile.electrical_stress is None or (
            profile.electrical_stress.vds is None and profile.electrical_stress.id is None
        ):
            raise ValueError("power_cycling requires electrical_stress with VDS and/or ID")
    elif profile.test_type is TestType.HTOL:
        if profile.htol_configuration is None:
            raise ValueError("HTOL requires htol_configuration")
    elif profile.test_type is TestType.HTRB:
        if profile.htrb_configuration is None:
            raise ValueError("HTRB requires htrb_configuration")
    elif profile.test_type is TestType.HTGB:
        if profile.htgb_configuration is None:
            raise ValueError("HTGB requires htgb_configuration")


def parse_test_profile(data: Mapping[str, Any]) -> TestProfile:
    return TestProfile.model_validate(data)


def load_json_schema() -> dict[str, Any]:
    import json

    with SCHEMA_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_against_json_schema(data: Mapping[str, Any]) -> None:
    from jsonschema import Draft202012Validator

    schema = load_json_schema()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(data)
