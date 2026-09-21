from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from domain.module_profiles.models import SCHEMA_VERSION, ModuleProfile
from domain.module_profiles.schema import SCHEMA_DRAFT, module_profile_json_schema
from domain.module_profiles.validation import (
    SCHEMA_PATH,
    parse_module_profile,
    validate_against_json_schema,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_PROFILE_PATH = REPO_ROOT / "examples" / "module-profiles" / "sic-reference-module.json"


def load_reference() -> dict:
    with REFERENCE_PROFILE_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def minimal_profile() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "identity": {
            "module_id": "min-001",
            "technology": "SiC MOSFET",
            "status": "draft",
        },
        "device": {
            "topology": "single_switch",
            "switch_count": 1,
        },
        "provenance": {
            "source_type": "illustrative_reference",
            "verified_by_engineer": False,
        },
    }


class TestValidProfile:
    def test_reference_profile_parses(self) -> None:
        profile = parse_module_profile(load_reference())
        assert profile.identity.technology.value == "SiC MOSFET"
        assert profile.identity.status.value == "draft"
        assert profile.device.topology.value == "half_bridge"
        assert profile.device.switch_count == 2

    def test_minimal_profile_allows_unknown_optional_engineering_values(self) -> None:
        profile = parse_module_profile(minimal_profile())
        assert profile.electrical.rds_on is None
        assert profile.electrical.blocking_voltage is None
        assert profile.gate_drive is None
        assert profile.thermal is None
        dumped = profile.model_dump()
        assert dumped["electrical"]["rds_on"] is None
        assert 0 not in (dumped["electrical"].values())


class TestRequiredFields:
    def test_missing_module_id_rejected(self) -> None:
        payload = minimal_profile()
        del payload["identity"]["module_id"]
        with pytest.raises(ValidationError):
            parse_module_profile(payload)

    def test_missing_technology_rejected(self) -> None:
        payload = minimal_profile()
        del payload["identity"]["technology"]
        with pytest.raises(ValidationError):
            parse_module_profile(payload)

    def test_missing_identity_rejected(self) -> None:
        payload = minimal_profile()
        del payload["identity"]
        with pytest.raises(ValidationError):
            parse_module_profile(payload)


class TestEnumerations:
    def test_invalid_topology_rejected(self) -> None:
        payload = minimal_profile()
        payload["device"]["topology"] = "three_level"
        with pytest.raises(ValidationError):
            parse_module_profile(payload)

    def test_invalid_technology_rejected(self) -> None:
        payload = minimal_profile()
        payload["identity"]["technology"] = "silicon IGBT"
        with pytest.raises(ValidationError):
            parse_module_profile(payload)

    def test_invalid_specification_type_rejected(self) -> None:
        payload = minimal_profile()
        payload["electrical"] = {
            "blocking_voltage": [
                {"value": 1200, "unit": "V", "specification_type": "nominal"}
            ]
        }
        with pytest.raises(ValidationError):
            parse_module_profile(payload)


class TestUnits:
    def test_unknown_unit_rejected(self) -> None:
        payload = minimal_profile()
        payload["electrical"] = {
            "blocking_voltage": [
                {"value": 1200, "unit": "kV", "specification_type": "maximum_rating"}
            ]
        }
        with pytest.raises(ValidationError):
            parse_module_profile(payload)

    def test_wrong_unit_for_blocking_voltage_rejected(self) -> None:
        payload = minimal_profile()
        payload["electrical"] = {
            "blocking_voltage": [
                {"value": 1200, "unit": "A", "specification_type": "maximum_rating"}
            ]
        }
        with pytest.raises(ValidationError, match="blocking_voltage unit"):
            parse_module_profile(payload)


class TestNumericValidation:
    def test_negative_blocking_voltage_rejected(self) -> None:
        payload = minimal_profile()
        payload["electrical"] = {
            "blocking_voltage": [
                {"value": -1200, "unit": "V", "specification_type": "maximum_rating"}
            ]
        }
        with pytest.raises(ValidationError, match="blocking_voltage must be positive"):
            parse_module_profile(payload)

    def test_negative_rds_on_rejected(self) -> None:
        payload = minimal_profile()
        payload["electrical"] = {
            "rds_on": [{"value": -4.5, "unit": "mOhm", "specification_type": "typical"}]
        }
        with pytest.raises(ValidationError, match="rds_on must be positive"):
            parse_module_profile(payload)

    def test_non_finite_value_rejected(self) -> None:
        payload = minimal_profile()
        payload["electrical"] = {
            "continuous_current": [
                {"value": math.inf, "unit": "A", "specification_type": "rating"}
            ]
        }
        with pytest.raises(ValidationError, match="finite"):
            parse_module_profile(payload)

    def test_boolean_not_accepted_as_engineering_number(self) -> None:
        payload = minimal_profile()
        payload["electrical"] = {
            "continuous_current": [
                {"value": True, "unit": "A", "specification_type": "rating"}
            ]
        }
        with pytest.raises(ValidationError, match="not strings or booleans"):
            parse_module_profile(payload)

    def test_negative_gate_voltage_off_is_allowed(self) -> None:
        payload = minimal_profile()
        payload["electrical"] = {
            "vgs_off": [{"value": -5, "unit": "V", "specification_type": "typical"}]
        }
        profile = parse_module_profile(payload)
        assert profile.electrical.vgs_off is not None
        assert profile.electrical.vgs_off[0].value == -5


class TestThermalValidation:
    def test_tj_max_not_greater_than_min_rejected(self) -> None:
        payload = minimal_profile()
        payload["thermal"] = {
            "tj_maximum": {"value": 25, "unit": "C", "specification_type": "maximum_rating"},
            "tj_minimum": {"value": 150, "unit": "C", "specification_type": "minimum"},
        }
        with pytest.raises(ValidationError, match="Tj maximum must be greater than Tj minimum"):
            parse_module_profile(payload)

    def test_ambient_range_requires_operating_range(self) -> None:
        payload = minimal_profile()
        payload["thermal"] = {
            "ambient_temperature_range": {
                "value": 25,
                "unit": "C",
                "specification_type": "typical",
            }
        }
        with pytest.raises(ValidationError):
            parse_module_profile(payload)

    def test_ambient_operating_range_accepted(self) -> None:
        payload = minimal_profile()
        payload["thermal"] = {
            "ambient_temperature_range": {
                "min_value": -40,
                "max_value": 85,
                "unit": "C",
                "specification_type": "operating_range",
            }
        }
        profile = parse_module_profile(payload)
        assert profile.thermal is not None
        assert profile.thermal.ambient_temperature_range is not None
        assert profile.thermal.ambient_temperature_range.specification_type.value == "operating_range"


class TestAcceptanceCriteria:
    def test_min_greater_than_max_rejected(self) -> None:
        payload = minimal_profile()
        payload["acceptance_criteria"] = [
            {
                "parameter": "VTH",
                "minimum_absolute": {
                    "value": 5.0,
                    "unit": "V",
                    "specification_type": "minimum",
                },
                "maximum_absolute": {
                    "value": 1.0,
                    "unit": "V",
                    "specification_type": "maximum",
                },
            }
        ]
        with pytest.raises(ValidationError, match="minimum acceptance threshold"):
            parse_module_profile(payload)

    def test_negative_relative_change_rejected(self) -> None:
        payload = minimal_profile()
        payload["acceptance_criteria"] = [
            {
                "parameter": "RDS_on",
                "maximum_relative_change_percent": -10,
            }
        ]
        with pytest.raises(ValidationError, match="must not be negative"):
            parse_module_profile(payload)


class TestProvenanceAndSpecificationSemantics:
    def test_reference_provenance_is_preserved(self) -> None:
        profile = parse_module_profile(load_reference())
        assert profile.provenance.source_type.value == "illustrative_reference"
        assert profile.provenance.verified_by_engineer is False
        assert "not a verified production specification" in (profile.provenance.notes or "")

    def test_specification_types_remain_distinguishable(self) -> None:
        payload = minimal_profile()
        payload["electrical"] = {
            "rds_on": [
                {"value": 4.5, "unit": "mOhm", "specification_type": "typical"},
                {"value": 6.0, "unit": "mOhm", "specification_type": "maximum"},
                {"value": 6.5, "unit": "mOhm", "specification_type": "guaranteed"},
            ],
            "blocking_voltage": [
                {"value": 1200, "unit": "V", "specification_type": "maximum_rating"}
            ],
            "continuous_current": [
                {"value": 400, "unit": "A", "specification_type": "rating"}
            ],
            "vth": [{"value": 1.8, "unit": "V", "specification_type": "minimum"}],
        }
        profile = parse_module_profile(payload)
        types = [item.specification_type.value for item in profile.electrical.rds_on or []]
        assert types == ["typical", "maximum", "guaranteed"]
        assert profile.electrical.blocking_voltage is not None
        assert profile.electrical.blocking_voltage[0].specification_type.value == "maximum_rating"
        assert profile.electrical.continuous_current is not None
        assert profile.electrical.continuous_current[0].specification_type.value == "rating"
        assert profile.electrical.vth is not None
        assert profile.electrical.vth[0].specification_type.value == "minimum"

    def test_temperature_dependent_rds_on_preserves_conditions(self) -> None:
        profile = parse_module_profile(load_reference())
        assert profile.electrical.rds_on is not None
        temperatures = [
            spec.conditions.junction_temperature_C if spec.conditions else None
            for spec in profile.electrical.rds_on
        ]
        assert 25 in temperatures
        assert 150 in temperatures
        spec_25 = next(
            spec
            for spec in profile.electrical.rds_on
            if spec.conditions and spec.conditions.junction_temperature_C == 25
            and spec.specification_type.value == "typical"
        )
        assert spec_25.value == 4.5
        assert spec_25.conditions is not None
        assert spec_25.conditions.gate_voltage_V == 15


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
        ],
    )
    def test_telemetry_and_ml_fields_rejected(self, field: str) -> None:
        payload = minimal_profile()
        payload[field] = 1
        with pytest.raises(ValidationError):
            parse_module_profile(payload)

    def test_extra_unknown_top_level_field_rejected(self) -> None:
        payload = minimal_profile()
        payload["failure_probability"] = 0.9
        with pytest.raises(ValidationError):
            parse_module_profile(payload)


class TestSchemaConsistency:
    def test_committed_schema_matches_pydantic_export(self) -> None:
        generated = module_profile_json_schema()
        committed = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        assert committed["$schema"] == SCHEMA_DRAFT
        assert committed == generated

    def test_reference_profile_validates_against_json_schema(self) -> None:
        validate_against_json_schema(load_reference())

    def test_reference_round_trips_through_pydantic(self) -> None:
        original = load_reference()
        profile = ModuleProfile.model_validate(original)
        dumped = json.loads(profile.model_dump_json())
        again = parse_module_profile(dumped)
        assert again.identity.module_id == profile.identity.module_id
        assert again.provenance.source_type == profile.provenance.source_type

    def test_json_schema_rejects_invalid_topology(self) -> None:
        from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

        payload = copy.deepcopy(load_reference())
        payload["device"]["topology"] = "not_a_topology"
        with pytest.raises(JsonSchemaValidationError):
            validate_against_json_schema(payload)
