"""Deterministic structural validation for telemetry observations.

No anomaly detection, physical plausibility checks, or ML scoring.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from domain.module_profiles.enums import Unit
from domain.telemetry.enums import HEALTH_PARAMETER_VALUES, TelemetryParameter
from domain.telemetry.measurements import Measurement
from domain.telemetry.models import TelemetryRecord


SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "telemetry.schema.json"

RESISTANCE_UNITS = frozenset({Unit.MOHM, Unit.OHM})
VOLTAGE_UNITS = frozenset({Unit.V})
CURRENT_UNITS = frozenset({Unit.A, Unit.UA})
TEMPERATURE_UNITS = frozenset({Unit.C})
THERMAL_RESISTANCE_UNITS = frozenset({Unit.C_PER_W})
POWER_UNITS = frozenset({Unit.W})

PARAMETER_UNITS: dict[TelemetryParameter, frozenset[Unit]] = {
    TelemetryParameter.RDS_ON: RESISTANCE_UNITS,
    TelemetryParameter.VTH: VOLTAGE_UNITS,
    TelemetryParameter.IGSS: CURRENT_UNITS,
    TelemetryParameter.IDSS: CURRENT_UNITS,
    TelemetryParameter.VDS_ON: VOLTAGE_UNITS,
    TelemetryParameter.VF: VOLTAGE_UNITS,
    TelemetryParameter.TJ: TEMPERATURE_UNITS,
    TelemetryParameter.TC: TEMPERATURE_UNITS,
    TelemetryParameter.TA: TEMPERATURE_UNITS,
    TelemetryParameter.RTH: THERMAL_RESISTANCE_UNITS,
    TelemetryParameter.VDS: VOLTAGE_UNITS,
    TelemetryParameter.VGS: VOLTAGE_UNITS,
    TelemetryParameter.ID: frozenset({Unit.A}),
    TelemetryParameter.DELTA_TJ: TEMPERATURE_UNITS,
    TelemetryParameter.ELECTRICAL_POWER: POWER_UNITS,
}


def _assert_health_parameter_coverage() -> None:
    telemetry_values = {item.value for item in TelemetryParameter}
    missing = HEALTH_PARAMETER_VALUES - telemetry_values
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"TelemetryParameter is missing HealthParameter names: {names}")


_assert_health_parameter_coverage()


def apply_telemetry_rules(record: TelemetryRecord) -> None:
    names = [item.parameter for item in record.measurements]
    if len(names) != len(set(names)):
        raise ValueError("duplicate parameter measurements in one record are not allowed")
    for measurement in record.measurements:
        _check_parameter_unit(measurement)


def _check_parameter_unit(measurement: Measurement) -> None:
    if measurement.unit is None:
        return
    allowed = PARAMETER_UNITS[measurement.parameter]
    if measurement.unit not in allowed:
        allowed_text = ", ".join(sorted(unit.value for unit in allowed))
        raise ValueError(
            f"{measurement.parameter.value} unit must be one of: {allowed_text}"
        )


def parse_telemetry_record(data: Mapping[str, Any]) -> TelemetryRecord:
    return TelemetryRecord.model_validate(data)


def parse_telemetry_payload(data: Mapping[str, Any] | list[Mapping[str, Any]]) -> list[TelemetryRecord]:
    if isinstance(data, list):
        return [parse_telemetry_record(item) for item in data]
    return [parse_telemetry_record(data)]


def load_json_schema() -> dict[str, Any]:
    import json

    with SCHEMA_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_against_json_schema(data: Mapping[str, Any]) -> None:
    from jsonschema import Draft202012Validator

    schema = load_json_schema()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(data)
