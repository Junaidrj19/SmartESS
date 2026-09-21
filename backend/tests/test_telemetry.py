from __future__ import annotations

import copy
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from domain.module_profiles.enums import HealthParameter, Unit
from domain.module_profiles.validation import (
    SCHEMA_PATH as MODULE_SCHEMA_PATH,
    parse_module_profile,
    validate_against_json_schema as validate_module_schema,
)
from domain.telemetry.enums import DataOrigin, MeasurementOrigin, MeasurementStatus, TelemetryParameter
from domain.telemetry.models import SCHEMA_VERSION, TelemetryRecord
from domain.telemetry.schema import SCHEMA_DRAFT, telemetry_json_schema
from domain.telemetry.validation import (
    SCHEMA_PATH,
    parse_telemetry_payload,
    parse_telemetry_record,
    validate_against_json_schema,
)
from domain.test_profiles.validation import (
    SCHEMA_PATH as TEST_SCHEMA_PATH,
    parse_test_profile,
    validate_against_json_schema as validate_test_schema,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_PATH = REPO_ROOT / "examples" / "telemetry" / "power-cycling-reference.json"
MODULE_REFERENCE_PATH = REPO_ROOT / "examples" / "module-profiles" / "sic-reference-module.json"
TEST_REFERENCE_PATH = REPO_ROOT / "examples" / "test-profiles" / "power-cycling-reference.json"


def load_reference() -> list[dict]:
    with REFERENCE_PATH.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    assert isinstance(payload, list)
    return payload


def utc_stamp() -> str:
    return "2024-06-01T00:00:00Z"


def valid_measurement(**overrides: object) -> dict:
    payload: dict = {
        "parameter": "Tj",
        "status": "valid",
        "origin": "measured",
        "value": 80.0,
        "unit": "C",
    }
    payload.update(overrides)
    return payload


def valid_record(**overrides: object) -> dict:
    payload: dict = {
        "schema_version": SCHEMA_VERSION,
        "telemetry_id": "tel-001",
        "module_id": "sic-ref-half-bridge-illustrative",
        "test_id": "pc-sic-ref-illustrative-001",
        "timestamp": utc_stamp(),
        "measurements": [valid_measurement()],
        "provenance": {
            "data_origin": "synthetic",
            "source_type": "illustrative_reference",
            "notes": "unit-test fixture",
        },
    }
    payload.update(overrides)
    return payload


class TestValidTelemetry:
    def test_valid_record_accepted(self) -> None:
        record = parse_telemetry_record(valid_record())
        assert record.telemetry_id == "tel-001"
        assert record.module_id == "sic-ref-half-bridge-illustrative"
        assert record.test_id == "pc-sic-ref-illustrative-001"

    def test_valid_multiple_measurements_accepted(self) -> None:
        payload = valid_record(
            measurements=[
                valid_measurement(parameter="RDS_on", value=17.4, unit="mOhm"),
                valid_measurement(parameter="Tj", value=90.0, unit="C"),
                valid_measurement(parameter="VDS", value=400.0, unit="V"),
                valid_measurement(parameter="ID", value=300.0, unit="A"),
            ]
        )
        record = parse_telemetry_record(payload)
        assert [item.parameter.value for item in record.measurements] == ["RDS_on", "Tj", "VDS", "ID"]

    def test_valid_utc_timestamp_accepted(self) -> None:
        record = parse_telemetry_record(valid_record(timestamp="2024-01-15T12:00:00+00:00"))
        assert record.timestamp.tzinfo is not None
        assert record.timestamp.utcoffset().total_seconds() == 0

    def test_naive_timestamp_rejected(self) -> None:
        with pytest.raises(ValidationError, match="timezone-aware UTC"):
            parse_telemetry_record(valid_record(timestamp="2024-01-15T12:00:00"))

    def test_non_utc_offset_rejected(self) -> None:
        with pytest.raises(ValidationError, match="must be UTC"):
            parse_telemetry_record(valid_record(timestamp="2024-01-15T12:00:00+05:30"))


class TestIdentity:
    def test_invalid_telemetry_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            parse_telemetry_record(valid_record(telemetry_id=""))

    def test_invalid_module_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            parse_telemetry_record(valid_record(module_id=""))

    def test_invalid_test_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            parse_telemetry_record(valid_record(test_id=""))

    def test_empty_dataset_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            parse_telemetry_record(valid_record(dataset_id=""))


class TestCycle:
    def test_cycle_zero_accepted(self) -> None:
        record = parse_telemetry_record(valid_record(cycle_number=0, cycle_phase="heating"))
        assert record.cycle_number == 0

    def test_negative_cycle_number_rejected(self) -> None:
        with pytest.raises(ValidationError):
            parse_telemetry_record(valid_record(cycle_number=-1))

    def test_cycle_number_optional(self) -> None:
        record = parse_telemetry_record(valid_record())
        assert record.cycle_number is None


class TestMeasurements:
    def test_invalid_parameter_rejected(self) -> None:
        payload = valid_record(measurements=[valid_measurement(parameter="Rds_on_measured")])
        with pytest.raises(ValidationError):
            parse_telemetry_record(payload)

    def test_invalid_unit_rejected(self) -> None:
        payload = valid_record(measurements=[valid_measurement(unit="kelvin")])
        with pytest.raises(ValidationError):
            parse_telemetry_record(payload)

    def test_parameter_unit_mismatch_rejected(self) -> None:
        payload = valid_record(measurements=[valid_measurement(parameter="RDS_on", value=17.4, unit="V")])
        with pytest.raises(ValidationError, match="RDS_on unit"):
            parse_telemetry_record(payload)

    def test_tj_with_ampere_rejected(self) -> None:
        payload = valid_record(measurements=[valid_measurement(parameter="Tj", value=80.0, unit="A")])
        with pytest.raises(ValidationError, match="Tj unit"):
            parse_telemetry_record(payload)

    def test_duplicate_parameter_rejected(self) -> None:
        payload = valid_record(
            measurements=[
                valid_measurement(parameter="Tj", value=80.0, unit="C"),
                valid_measurement(parameter="Tj", value=81.0, unit="C"),
            ]
        )
        with pytest.raises(ValidationError, match="duplicate parameter"):
            parse_telemetry_record(payload)

    def test_non_finite_measurement_rejected(self) -> None:
        payload = valid_record(measurements=[valid_measurement(value=math.inf)])
        with pytest.raises(ValidationError, match="finite"):
            parse_telemetry_record(payload)

    def test_boolean_measurement_rejected(self) -> None:
        payload = valid_record(measurements=[valid_measurement(value=True)])
        with pytest.raises(ValidationError, match="not strings or booleans"):
            parse_telemetry_record(payload)

    def test_missing_measurement_represented_correctly(self) -> None:
        payload = valid_record(
            measurements=[
                valid_measurement(),
                {
                    "parameter": "Tc",
                    "status": "missing",
                    "origin": "measured",
                },
            ]
        )
        record = parse_telemetry_record(payload)
        missing = next(item for item in record.measurements if item.parameter is TelemetryParameter.TC)
        assert missing.status is MeasurementStatus.MISSING
        assert missing.value is None

    def test_missing_must_not_masquerade_as_valid_zero(self) -> None:
        payload = valid_record(
            measurements=[
                {
                    "parameter": "Tc",
                    "status": "missing",
                    "origin": "measured",
                    "value": 0.0,
                    "unit": "C",
                }
            ]
        )
        with pytest.raises(ValidationError, match="must not include a numeric value"):
            parse_telemetry_record(payload)

    def test_invalid_measurement_status_rejected(self) -> None:
        payload = valid_record(measurements=[valid_measurement(status="ok")])
        with pytest.raises(ValidationError):
            parse_telemetry_record(payload)

    def test_negative_uncertainty_rejected(self) -> None:
        payload = valid_record(measurements=[valid_measurement(uncertainty=-0.1)])
        with pytest.raises(ValidationError, match="uncertainty must not be negative"):
            parse_telemetry_record(payload)

    def test_valid_zero_is_allowed_when_measured(self) -> None:
        record = parse_telemetry_record(
            valid_record(measurements=[valid_measurement(parameter="ID", value=0.0, unit="A")])
        )
        assert record.measurements[0].value == 0.0
        assert record.measurements[0].status is MeasurementStatus.VALID


class TestProvenanceAndMetadata:
    def test_synthetic_data_origin_accepted(self) -> None:
        record = parse_telemetry_record(valid_record())
        assert record.provenance.data_origin is DataOrigin.SYNTHETIC

    def test_invalid_data_origin_rejected(self) -> None:
        payload = valid_record()
        payload["provenance"]["data_origin"] = "production"
        with pytest.raises(ValidationError):
            parse_telemetry_record(payload)

    def test_provenance_preserved(self) -> None:
        payload = valid_record()
        payload["provenance"] = {
            "data_origin": "synthetic",
            "source_type": "json",
            "source_file": "lab/run.json",
            "source_dataset": "ds-1",
            "acquisition_system": "bench-a",
            "imported_at": "2024-06-01T01:00:00Z",
            "import_version": "import-1",
            "notes": "preserved",
        }
        record = parse_telemetry_record(payload)
        assert record.provenance.source_file == "lab/run.json"
        assert record.provenance.source_dataset == "ds-1"
        assert record.provenance.import_version == "import-1"
        assert record.provenance.notes == "preserved"

    def test_sensor_channel_metadata_preserved(self) -> None:
        payload = valid_record(
            measurements=[
                valid_measurement(
                    sensor_id="s-1",
                    channel_id="ch-tj",
                    instrument_id="scope-1",
                    acquisition_system="daq-x",
                )
            ]
        )
        measurement = parse_telemetry_record(payload).measurements[0]
        assert measurement.sensor_id == "s-1"
        assert measurement.channel_id == "ch-tj"
        assert measurement.instrument_id == "scope-1"
        assert measurement.acquisition_system == "daq-x"

    def test_raw_vs_derived_distinction_preserved(self) -> None:
        payload = valid_record(
            measurements=[
                valid_measurement(parameter="VDS", value=400.0, unit="V", origin="measured"),
                {
                    "parameter": "electrical_power",
                    "status": "derived",
                    "origin": "derived",
                    "value": 120000.0,
                    "unit": "W",
                    "derivation": {
                        "method": "illustrative P = VDS * ID",
                        "input_parameters": ["VDS", "ID"],
                    },
                },
            ]
        )
        record = parse_telemetry_record(payload)
        by_name = {item.parameter: item for item in record.measurements}
        assert by_name[TelemetryParameter.VDS].origin is MeasurementOrigin.MEASURED
        derived = by_name[TelemetryParameter.ELECTRICAL_POWER]
        assert derived.origin is MeasurementOrigin.DERIVED
        assert derived.derivation is not None
        assert derived.derivation.method.startswith("illustrative")

    def test_derived_measurement_provenance_can_be_represented(self) -> None:
        payload = valid_record(
            measurements=[
                {
                    "parameter": "RDS_on",
                    "status": "derived",
                    "origin": "derived",
                    "value": 17.4,
                    "unit": "mOhm",
                    "derivation": {
                        "method": "VDS_on / ID",
                        "input_parameters": ["VDS", "ID"],
                        "notes": "no calculation performed in M3",
                    },
                }
            ]
        )
        derived = parse_telemetry_record(payload).measurements[0]
        assert derived.derivation is not None
        assert derived.derivation.input_parameters == [TelemetryParameter.VDS, TelemetryParameter.ID]


class TestAnalyticalBoundary:
    @pytest.mark.parametrize(
        "field",
        [
            "anomaly_score",
            "prediction",
            "predicted_failure",
            "failure_probability",
            "failure_mechanism",
            "hypothesis",
            "investigation_result",
        ],
    )
    def test_ml_and_investigation_fields_rejected(self, field: str) -> None:
        payload = valid_record()
        payload[field] = 1
        with pytest.raises(ValidationError):
            parse_telemetry_record(payload)

    def test_embedded_profiles_rejected(self) -> None:
        payload = valid_record()
        payload["module_profile"] = {"identity": {"module_id": "x"}}
        with pytest.raises(ValidationError):
            parse_telemetry_record(payload)


class TestSharedTerminology:
    def test_health_parameter_names_are_reused(self) -> None:
        telemetry_values = {item.value for item in TelemetryParameter}
        health_values = {item.value for item in HealthParameter}
        assert health_values <= telemetry_values
        assert Unit.W.value == "W"

    def test_reference_ids_match_module_and_test_profiles(self) -> None:
        module = parse_module_profile(json.loads(MODULE_REFERENCE_PATH.read_text(encoding="utf-8")))
        test = parse_test_profile(json.loads(TEST_REFERENCE_PATH.read_text(encoding="utf-8")))
        records = parse_telemetry_payload(load_reference())
        assert all(item.module_id == module.identity.module_id for item in records)
        assert all(item.test_id == test.test_id for item in records)
        assert all(item.provenance.data_origin is DataOrigin.SYNTHETIC for item in records)


class TestSchemaConsistency:
    def test_committed_schema_matches_pydantic_export(self) -> None:
        generated = telemetry_json_schema()
        committed = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        assert committed["$schema"] == SCHEMA_DRAFT
        assert committed == generated

    def test_reference_telemetry_validates_against_json_schema(self) -> None:
        for record in load_reference():
            parse_telemetry_record(record)
            validate_against_json_schema(record)

    def test_module_and_test_references_still_validate(self) -> None:
        module = json.loads(MODULE_REFERENCE_PATH.read_text(encoding="utf-8"))
        test = json.loads(TEST_REFERENCE_PATH.read_text(encoding="utf-8"))
        parse_module_profile(module)
        validate_module_schema(module)
        parse_test_profile(test)
        validate_test_schema(test)
        assert MODULE_SCHEMA_PATH.exists()
        assert TEST_SCHEMA_PATH.exists()

    def test_json_schema_rejects_invalid_data_origin(self) -> None:
        from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

        payload = copy.deepcopy(valid_record())
        payload["provenance"]["data_origin"] = "not-an-origin"
        with pytest.raises(JsonSchemaValidationError):
            validate_against_json_schema(payload)

    def test_round_trip(self) -> None:
        original = load_reference()[0]
        record = TelemetryRecord.model_validate(original)
        again = parse_telemetry_record(json.loads(record.model_dump_json()))
        assert again.telemetry_id == record.telemetry_id
        assert again.timestamp == record.timestamp
        assert datetime.fromisoformat(original["timestamp"].replace("Z", "+00:00")).tzinfo is timezone.utc
