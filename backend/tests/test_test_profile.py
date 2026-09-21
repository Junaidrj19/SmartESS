from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from domain.module_profiles.validation import (
    SCHEMA_PATH as MODULE_SCHEMA_PATH,
    parse_module_profile,
    validate_against_json_schema as validate_module_schema,
)
from domain.test_profiles.models import SCHEMA_VERSION, TestProfile
from domain.test_profiles.schema import SCHEMA_DRAFT
from domain.test_profiles.schema import test_profile_json_schema as export_test_profile_schema
from domain.test_profiles.validation import (
    SCHEMA_PATH,
    parse_test_profile,
    validate_against_json_schema,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_PATH = REPO_ROOT / "examples" / "test-profiles" / "power-cycling-reference.json"
MODULE_REFERENCE_PATH = REPO_ROOT / "examples" / "module-profiles" / "sic-reference-module.json"


def load_reference() -> dict:
    with REFERENCE_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def base_identity(**overrides: object) -> dict:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "test_id": "test-001",
        "module_profile_id": "sic-ref-half-bridge-illustrative",
        "test_type": "custom",
        "provenance": {
            "source_type": "illustrative_reference",
            "notes": "unit-test fixture",
        },
    }
    payload.update(overrides)
    return payload


def power_cycling_payload() -> dict:
    return copy.deepcopy(load_reference())


def htol_payload() -> dict:
    return base_identity(
        test_id="htol-001",
        test_type="HTOL",
        htol_configuration={
            "temperature": {"value": 175, "unit": "C"},
            "duration_s": 1000 * 3600,
            "vds": {"value": 800, "unit": "V"},
            "id": {"value": 20, "unit": "A"},
        },
    )


def htrb_payload() -> dict:
    return base_identity(
        test_id="htrb-001",
        test_type="HTRB",
        htrb_configuration={
            "temperature": {"value": 150, "unit": "C"},
            "duration_s": 168 * 3600,
            "reverse_voltage": {"value": 960, "unit": "V"},
            "bias_condition": "drain-source reverse bias, gate off (illustrative)",
        },
    )


def htgb_payload() -> dict:
    return base_identity(
        test_id="htgb-001",
        test_type="HTGB",
        htgb_configuration={
            "temperature": {"value": 150, "unit": "C"},
            "duration_s": 168 * 3600,
            "gate_bias": {"value": 20, "unit": "V"},
            "drain_source_condition": "source and drain shorted (illustrative)",
        },
    )


class TestValidProfiles:
    def test_power_cycling_reference_accepted(self) -> None:
        profile = parse_test_profile(load_reference())
        assert profile.test_type.value == "power_cycling"
        assert profile.module_profile_id == "sic-ref-half-bridge-illustrative"
        assert not hasattr(profile, "module_profile") or not isinstance(
            getattr(profile, "module_profile", None), dict
        )
        assert profile.model_dump().get("module_profile") is None

    def test_htol_accepted(self) -> None:
        profile = parse_test_profile(htol_payload())
        assert profile.htol_configuration is not None
        assert profile.htol_configuration.temperature.value == 175

    def test_htrb_accepted(self) -> None:
        profile = parse_test_profile(htrb_payload())
        assert profile.htrb_configuration is not None
        assert profile.htrb_configuration.reverse_voltage.value == 960

    def test_htgb_accepted(self) -> None:
        profile = parse_test_profile(htgb_payload())
        assert profile.htgb_configuration is not None
        assert profile.htgb_configuration.gate_bias.value == 20

    def test_custom_accepted(self) -> None:
        profile = parse_test_profile(base_identity())
        assert profile.test_type.value == "custom"
        assert profile.cycle_profile is None


class TestIdentityAndEnums:
    def test_invalid_test_type_rejected(self) -> None:
        payload = base_identity(test_type="HTFB")
        with pytest.raises(ValidationError):
            parse_test_profile(payload)

    def test_missing_module_profile_id_rejected(self) -> None:
        payload = base_identity()
        del payload["module_profile_id"]
        with pytest.raises(ValidationError):
            parse_test_profile(payload)

    def test_empty_test_id_rejected(self) -> None:
        payload = base_identity(test_id="")
        with pytest.raises(ValidationError):
            parse_test_profile(payload)

    def test_embedded_module_profile_rejected(self) -> None:
        payload = base_identity()
        payload["module_profile"] = {"identity": {"module_id": "x"}}
        with pytest.raises(ValidationError):
            parse_test_profile(payload)

    def test_relationship_is_id_only(self) -> None:
        dumped = parse_test_profile(load_reference()).model_dump()
        assert dumped["module_profile_id"] == "sic-ref-half-bridge-illustrative"
        assert "identity" not in dumped
        assert "device" not in dumped


class TestNumericAndThermal:
    def test_negative_cycle_count_rejected(self) -> None:
        payload = power_cycling_payload()
        payload["cycle_profile"]["target_cycles"] = -1
        with pytest.raises(ValidationError):
            parse_test_profile(payload)

    def test_negative_heating_duration_rejected(self) -> None:
        payload = power_cycling_payload()
        payload["cycle_profile"]["heating_duration_s"] = -2
        with pytest.raises(ValidationError, match="heating_duration_s"):
            parse_test_profile(payload)

    def test_invalid_thermal_range_rejected(self) -> None:
        payload = power_cycling_payload()
        payload["thermal_stress"]["tj_minimum"]["value"] = 150
        payload["thermal_stress"]["tj_maximum"]["value"] = 40
        del payload["thermal_stress"]["delta_tj"]
        with pytest.raises(ValidationError, match="Tj maximum must be greater than Tj minimum"):
            parse_test_profile(payload)

    def test_inconsistent_delta_tj_rejected(self) -> None:
        payload = power_cycling_payload()
        payload["thermal_stress"]["delta_tj"]["value"] = 50
        with pytest.raises(ValidationError, match="delta_Tj must equal"):
            parse_test_profile(payload)

    def test_non_finite_rejected(self) -> None:
        payload = power_cycling_payload()
        payload["electrical_stress"]["id"]["value"] = math.inf
        with pytest.raises(ValidationError, match="finite"):
            parse_test_profile(payload)

    def test_boolean_not_accepted_as_number(self) -> None:
        payload = power_cycling_payload()
        payload["electrical_stress"]["vds"]["value"] = True
        with pytest.raises(ValidationError, match="not strings or booleans"):
            parse_test_profile(payload)


class TestMeasurement:
    def test_duplicate_measurement_parameters_rejected(self) -> None:
        payload = power_cycling_payload()
        payload["measurement_configuration"]["channels"].append(
            {"parameter": "RDS_on", "unit": "mOhm"}
        )
        with pytest.raises(ValidationError, match="unique"):
            parse_test_profile(payload)

    def test_invalid_measurement_parameter_rejected(self) -> None:
        payload = power_cycling_payload()
        payload["measurement_configuration"]["channels"][0]["parameter"] = "Rds_on_measured"
        with pytest.raises(ValidationError):
            parse_test_profile(payload)

    def test_invalid_sampling_interval_rejected(self) -> None:
        payload = power_cycling_payload()
        payload["measurement_configuration"]["sampling_interval_s"] = 0
        with pytest.raises(ValidationError, match="sampling_interval_s must be positive"):
            parse_test_profile(payload)


class TestTelemetryBoundary:
    @pytest.mark.parametrize(
        "field",
        [
            "timestamp",
            "cycle_number",
            "anomaly_score",
            "test_run",
            "degradation_state",
            "predicted_failure",
            "ground_truth",
            "investigation",
        ],
    )
    def test_telemetry_and_ml_fields_rejected(self, field: str) -> None:
        payload = base_identity()
        payload[field] = 1
        with pytest.raises(ValidationError):
            parse_test_profile(payload)


class TestSchemaConsistency:
    def test_committed_schema_matches_pydantic_export(self) -> None:
        generated = export_test_profile_schema()
        committed = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        assert committed["$schema"] == SCHEMA_DRAFT
        assert committed == generated

    def test_reference_validates_against_json_schema(self) -> None:
        validate_against_json_schema(load_reference())

    def test_module_profile_reference_still_validates(self) -> None:
        data = json.loads(MODULE_REFERENCE_PATH.read_text(encoding="utf-8"))
        parse_module_profile(data)
        validate_module_schema(data)
        assert MODULE_SCHEMA_PATH.exists()

    def test_json_schema_rejects_invalid_test_type(self) -> None:
        from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

        payload = copy.deepcopy(load_reference())
        payload["test_type"] = "not_a_test"
        with pytest.raises(JsonSchemaValidationError):
            validate_against_json_schema(payload)

    def test_round_trip(self) -> None:
        profile = TestProfile.model_validate(load_reference())
        again = parse_test_profile(json.loads(profile.model_dump_json()))
        assert again.test_id == profile.test_id
        assert again.module_profile_id == profile.module_profile_id
