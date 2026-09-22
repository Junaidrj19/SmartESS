"""Constants and M3-aligned column contracts for M5.

M3 TelemetryRecord remains the semantic authority. This module only names the
wide parquet layout produced by M4 so the validator can inspect files.
"""

from __future__ import annotations

from domain.telemetry.enums import MeasurementOrigin, MeasurementStatus, TelemetryParameter
from domain.telemetry.models import FORBIDDEN_TELEMETRY_FIELDS
from domain.telemetry.validation import PARAMETER_UNITS
from ml.generators.synthetic.config import DegradationStage, HealthState, Mechanism, Scenario

VALIDATOR_VERSION = "1.0.0"

REQUIRED_ARTIFACTS = (
    "metadata/dataset.json",
    "metadata/generation-config.json",
    "metadata/assumptions.json",
    "telemetry/telemetry.parquet",
    "ground_truth/ground-truth.parquet",
    "provenance/provenance.json",
)

CORE_TELEMETRY_COLUMNS = (
    "schema_version",
    "telemetry_id",
    "module_id",
    "test_id",
    "lot_id",
    "dataset_id",
    "timestamp",
    "cycle_number",
    "cycle_phase",
    "data_origin",
    "source_type",
    "source_dataset",
    "provenance_notes",
)

GROUND_TRUTH_REQUIRED_COLUMNS = (
    "module_id",
    "lot_id",
    "module_profile_id",
    "test_id",
    "health_state",
    "degradation_mechanism",
    "degradation_stage",
    "onset_cycle",
    "cycle_early",
    "cycle_measurable",
    "cycle_advanced",
    "cycle_terminal",
    "terminal_cycle",
    "degradation_severity",
    "rate_scale",
    "simulation_seed",
    "generator_version",
    "mechanism_model",
    "dataset_id",
    "scenario",
    "data_origin",
)

DISTRIBUTION_SIGNALS = (
    "RDS_on",
    "VTH",
    "IGSS",
    "IDSS",
    "Tj",
    "Tc",
    "Rth",
    "VDS",
    "VGS",
    "ID",
    "electrical_power",
    "delta_Tj",
)

NON_NEGATIVE_CHANNELS = frozenset(
    {
        TelemetryParameter.RDS_ON.value,
        TelemetryParameter.RTH.value,
        TelemetryParameter.ELECTRICAL_POWER.value,
    }
)

ABSOLUTE_ZERO_C = -273.15

VALID_VALUE_STATUSES = frozenset(
    {
        MeasurementStatus.VALID.value,
        MeasurementStatus.ESTIMATED.value,
        MeasurementStatus.DERIVED.value,
    }
)
ALL_STATUSES = frozenset(item.value for item in MeasurementStatus)
ALL_ORIGINS = frozenset(item.value for item in MeasurementOrigin)
ALL_MECHANISMS = frozenset(item.value for item in Mechanism)
ALL_STAGES = frozenset(item.value for item in DegradationStage)
ALL_HEALTH = frozenset(item.value for item in HealthState)
ALL_SCENARIOS = frozenset(item.value for item in Scenario)

STAGE_ORDER = {
    DegradationStage.HEALTHY.value: 0,
    DegradationStage.EARLY.value: 1,
    DegradationStage.MEASURABLE.value: 2,
    DegradationStage.ADVANCED.value: 3,
    DegradationStage.TERMINAL.value: 4,
}

FORBIDDEN_TELEMETRY_COLUMNS = FORBIDDEN_TELEMETRY_FIELDS | {
    "degradation_mechanism",
    "health_state",
    "onset_cycle",
    "terminal_cycle",
    "degradation_stage",
    "rate_scale",
    "mechanism_model",
    "degradation_severity",
    "damage_index_end",
    "cycle_early",
    "cycle_measurable",
    "cycle_advanced",
    "cycle_terminal",
    "severity",
}

LEAKAGE_NAME_FRAGMENTS = (
    "degradation_mechanism",
    "health_state",
    "onset_cycle",
    "terminal_cycle",
    "rate_scale",
    "mechanism_model",
    "ground_truth",
    "anomaly_score",
    "failure_mechanism",
)

PARAMETER_UNIT_VALUES = {
    parameter.value: frozenset(unit.value for unit in units)
    for parameter, units in PARAMETER_UNITS.items()
}

DERIVED_CHANNELS = frozenset({"RDS_on", "VDS_on", "delta_Tj", "electrical_power", "Rth"})

LIMITATIONS = [
    "M5 validates the integrity and analytical suitability of the synthetic dataset within its declared simulation assumptions. Passing M5 does not establish experimental validity or real-world physical accuracy.",
    "Distribution and correlation checks are simulation diagnostics, not experimental validation or proof of physical realism.",
    "Mechanism diagnostics are not a classifier and do not declare mechanism-identification success.",
    "No real-world industry thresholds or literature citations are applied unless already recorded in the dataset contracts.",
]
