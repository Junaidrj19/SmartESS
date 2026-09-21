"""GenerationConfig for the M4 synthetic dataset generator.

Numeric defaults are simulation/benchmark parameters, not measured fab statistics
and not real-world failure prevalence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from domain.module_profiles.engineering import _reject_non_finite_number
from domain.telemetry.enums import CyclePhase, TelemetryParameter


GENERATOR_VERSION = "1.0.0"

DEFAULT_CHANNELS: tuple[str, ...] = (
    TelemetryParameter.RDS_ON.value,
    TelemetryParameter.VTH.value,
    TelemetryParameter.IGSS.value,
    TelemetryParameter.IDSS.value,
    TelemetryParameter.VDS_ON.value,
    TelemetryParameter.TJ.value,
    TelemetryParameter.TC.value,
    TelemetryParameter.TA.value,
    TelemetryParameter.RTH.value,
    TelemetryParameter.VDS.value,
    TelemetryParameter.VGS.value,
    TelemetryParameter.ID.value,
    TelemetryParameter.DELTA_TJ.value,
    TelemetryParameter.ELECTRICAL_POWER.value,
)

_CHANNEL_VALUES = {item.value for item in TelemetryParameter}


class Scenario(str, Enum):
    CLEAN_HEALTHY = "clean_healthy"
    DEGRADATION_BENCHMARK = "degradation_benchmark"
    DATA_QUALITY_STRESS = "data_quality_stress"


class Mechanism(str, Enum):
    HEALTHY = "healthy"
    BOND_WIRE_INTERCONNECT = "bond_wire_interconnect"
    DIE_ATTACH_THERMAL_PATH = "die_attach_thermal_path"
    GATE_RELATED = "gate_related"


class DegradationStage(str, Enum):
    HEALTHY = "healthy"
    EARLY = "early"
    MEASURABLE = "measurable"
    ADVANCED = "advanced"
    TERMINAL = "terminal"


class HealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADING = "degrading"
    TERMINAL = "terminal"


def _finite_ge_zero(value: object, *, name: str) -> float:
    number = _reject_non_finite_number(value)
    if number < 0:
        raise ValueError(f"{name} must be >= 0")
    return number


class PopulationMix(BaseModel):
    """Benchmark class fractions. Not field prevalence."""

    model_config = ConfigDict(extra="forbid")

    healthy: float = 0.70
    bond_wire_interconnect: float = 0.10
    die_attach_thermal_path: float = 0.10
    gate_related: float = 0.10

    @field_validator(
        "healthy",
        "bond_wire_interconnect",
        "die_attach_thermal_path",
        "gate_related",
        mode="before",
    )
    @classmethod
    def _finite_fraction(cls, value: object) -> float:
        number = _reject_non_finite_number(value)
        if number < 0 or number > 1:
            raise ValueError("mix fractions must be in [0, 1]")
        return number

    @model_validator(mode="after")
    def _sums_to_one(self) -> PopulationMix:
        total = (
            self.healthy
            + self.bond_wire_interconnect
            + self.die_attach_thermal_path
            + self.gate_related
        )
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"population_mix fractions must sum to 1.0, got {total}")
        return self

    def as_mechanism_map(self) -> dict[Mechanism, float]:
        return {
            Mechanism.HEALTHY: self.healthy,
            Mechanism.BOND_WIRE_INTERCONNECT: self.bond_wire_interconnect,
            Mechanism.DIE_ATTACH_THERMAL_PATH: self.die_attach_thermal_path,
            Mechanism.GATE_RELATED: self.gate_related,
        }


class ManufacturingVariationConfig(BaseModel):
    """Lot and within-lot Gaussian σ. Simulation convenience, not Cpk data."""

    model_config = ConfigDict(extra="forbid")

    lot_sigma_rds_mohm: float = 0.08
    module_sigma_rds_mohm: float = 0.05
    lot_sigma_vth_V: float = 0.08
    module_sigma_vth_V: float = 0.05
    lot_sigma_rth_C_per_W: float = 0.004
    module_sigma_rth_C_per_W: float = 0.003
    lot_sigma_igss_uA: float = 0.02
    module_sigma_igss_uA: float = 0.02
    lot_sigma_idss_uA: float = 5.0
    module_sigma_idss_uA: float = 5.0
    module_sigma_k_th: float = 0.02

    @field_validator(
        "lot_sigma_rds_mohm",
        "module_sigma_rds_mohm",
        "lot_sigma_vth_V",
        "module_sigma_vth_V",
        "lot_sigma_rth_C_per_W",
        "module_sigma_rth_C_per_W",
        "lot_sigma_igss_uA",
        "module_sigma_igss_uA",
        "lot_sigma_idss_uA",
        "module_sigma_idss_uA",
        "module_sigma_k_th",
        mode="before",
    )
    @classmethod
    def _sigmas(cls, value: object) -> float:
        return _finite_ge_zero(value, name="manufacturing sigma")


class StressVariationConfig(BaseModel):
    """Scatter around TestProfile setpoints. Does not replace TestProfile."""

    model_config = ConfigDict(extra="forbid")

    id_rel_sigma: float = 0.01
    delta_tj_sigma_C: float = 1.5
    vds_sigma_V: float = 0.5
    tj_tracking_sigma_C: float = 0.8
    cycle_id_rel_sigma: float = 0.003
    cycle_delta_tj_sigma_C: float = 0.4
    cycle_tj_sigma_C: float = 0.3

    @field_validator(
        "id_rel_sigma",
        "delta_tj_sigma_C",
        "vds_sigma_V",
        "tj_tracking_sigma_C",
        "cycle_id_rel_sigma",
        "cycle_delta_tj_sigma_C",
        "cycle_tj_sigma_C",
        mode="before",
    )
    @classmethod
    def _sigmas(cls, value: object) -> float:
        return _finite_ge_zero(value, name="stress sigma")


class HealthyJitterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rds_sigma_mohm: float = 0.02
    vth_sigma_V: float = 0.002
    tj_wander_sigma_C: float = 4.0
    ar1_rho: float = 0.3

    @field_validator("rds_sigma_mohm", "vth_sigma_V", "tj_wander_sigma_C", mode="before")
    @classmethod
    def _sigmas(cls, value: object) -> float:
        return _finite_ge_zero(value, name="healthy jitter sigma")

    @field_validator("ar1_rho", mode="before")
    @classmethod
    def _rho(cls, value: object) -> float:
        number = _reject_non_finite_number(value)
        if not 0 <= number < 1:
            raise ValueError("ar1_rho must be in [0, 1)")
        return number


class TemperatureModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    t_ref_C: float = 25.0
    alpha_vth_V_per_C: float = -0.002
    p_switching_W: float = 80.0
    rth_ca_C_per_W: float = 0.04
    die_attach_tj_overshoot_max_C: float = 8.0

    @field_validator("p_switching_W", "rth_ca_C_per_W", "die_attach_tj_overshoot_max_C", mode="before")
    @classmethod
    def _nonneg(cls, value: object) -> float:
        return _finite_ge_zero(value, name="temperature model parameter")

    @field_validator("t_ref_C", "alpha_vth_V_per_C", mode="before")
    @classmethod
    def _finite(cls, value: object) -> float:
        return _reject_non_finite_number(value)


class BondWireModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str = "bond_wire_v1"
    delta_rds_max_rel: float = 0.20

    @field_validator("delta_rds_max_rel", mode="before")
    @classmethod
    def _rel(cls, value: object) -> float:
        number = _finite_ge_zero(value, name="delta_rds_max_rel")
        if number > 2:
            raise ValueError("delta_rds_max_rel is unreasonably large for v1")
        return number


class DieAttachModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str = "die_attach_v1"
    gamma_rth: float = 0.30
    secondary_rds_ref_rel: float = 0.0

    @field_validator("gamma_rth", "secondary_rds_ref_rel", mode="before")
    @classmethod
    def _nonneg(cls, value: object) -> float:
        return _finite_ge_zero(value, name="die-attach parameter")


class GateModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str = "gate_related_v1"
    delta_vth_max_V: float = 0.35
    igss_delta_uA: float = 0.40
    idss_delta_uA: float = 30.0
    idss_coupling: float = 0.35
    rds_per_vth_mohm: float = 0.02

    @field_validator(
        "delta_vth_max_V",
        "igss_delta_uA",
        "idss_delta_uA",
        "idss_coupling",
        "rds_per_vth_mohm",
        mode="before",
    )
    @classmethod
    def _nonneg(cls, value: object) -> float:
        number = _finite_ge_zero(value, name="gate model parameter")
        if number > 1000:
            raise ValueError("gate model parameter is unreasonably large")
        return number


class StageThresholds(BaseModel):
    """Latent severity thresholds. Simulation knobs for lead-time labels."""

    model_config = ConfigDict(extra="forbid")

    measurable: float = 0.03
    advanced: float = 0.10
    terminal: float = 0.18

    @field_validator("measurable", "advanced", "terminal", mode="before")
    @classmethod
    def _pos(cls, value: object) -> float:
        number = _reject_non_finite_number(value)
        if number <= 0:
            raise ValueError("stage thresholds must be > 0")
        return number

    @model_validator(mode="after")
    def _ordered(self) -> StageThresholds:
        if not (self.measurable < self.advanced < self.terminal):
            raise ValueError("stage thresholds must satisfy measurable < advanced < terminal")
        return self


class DegradationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    onset_min_cycle: int = Field(default=5000, ge=0)
    onset_max_cycle: int = Field(default=70000, ge=0)
    cycle_span: int = Field(default=40000, ge=1)
    progression_exponent_p: float = 1.4
    rate_scale_lognormal_sigma: float = 0.25
    damage_process_sigma: float = 0.0
    stage_thresholds: StageThresholds = Field(default_factory=StageThresholds)
    bond_wire: BondWireModelConfig = Field(default_factory=BondWireModelConfig)
    die_attach: DieAttachModelConfig = Field(default_factory=DieAttachModelConfig)
    gate: GateModelConfig = Field(default_factory=GateModelConfig)

    @field_validator("progression_exponent_p", "rate_scale_lognormal_sigma", "damage_process_sigma", mode="before")
    @classmethod
    def _nonneg(cls, value: object) -> float:
        return _finite_ge_zero(value, name="degradation parameter")

    @model_validator(mode="after")
    def _onset_window(self) -> DegradationConfig:
        if self.onset_min_cycle > self.onset_max_cycle:
            raise ValueError("onset_min_cycle must be <= onset_max_cycle")
        if self.progression_exponent_p <= 0:
            raise ValueError("progression_exponent_p must be > 0")
        return self


class SensorNoiseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    RDS_on: float = 0.02
    VTH: float = 0.005
    IGSS: float = 0.02
    IDSS: float = 2.0
    VDS_on: float = 0.02
    Tj: float = 0.3
    Tc: float = 0.3
    Ta: float = 0.3
    Rth: float = 0.002
    VDS: float = 0.5
    VGS: float = 0.05
    ID: float = 0.5
    delta_Tj: float = 0.3
    electrical_power: float = 5.0

    @model_validator(mode="after")
    def _nonneg(self) -> SensorNoiseConfig:
        for name, value in self.model_dump().items():
            _finite_ge_zero(value, name=f"sensor noise {name}")
        return self

    def sigma_map(self) -> dict[str, float]:
        return self.model_dump()


class SensorBiasConfig(BaseModel):
    """Per-channel bias σ used to draw a constant per-module offset."""

    model_config = ConfigDict(extra="forbid")

    RDS_on: float = 0.005
    VTH: float = 0.002
    IGSS: float = 0.005
    IDSS: float = 0.5
    VDS_on: float = 0.005
    Tj: float = 0.15
    Tc: float = 0.15
    Ta: float = 0.1
    Rth: float = 0.001
    VDS: float = 0.2
    VGS: float = 0.02
    ID: float = 0.15
    delta_Tj: float = 0.1
    electrical_power: float = 2.0

    @model_validator(mode="after")
    def _nonneg(self) -> SensorBiasConfig:
        for name, value in self.model_dump().items():
            _finite_ge_zero(value, name=f"sensor bias {name}")
        return self

    def sigma_map(self) -> dict[str, float]:
        return self.model_dump()


class SensorDriftConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    rds_mohm_over_test: float = 0.0
    vth_V_over_test: float = 0.0

    @field_validator("rds_mohm_over_test", "vth_V_over_test", mode="before")
    @classmethod
    def _finite(cls, value: object) -> float:
        return _reject_non_finite_number(value)


class QuantizationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    temperature_C: float = 0.1
    rds_mohm: float = 0.01

    @field_validator("temperature_C", "rds_mohm", mode="before")
    @classmethod
    def _step(cls, value: object) -> float:
        number = _reject_non_finite_number(value)
        if number <= 0:
            raise ValueError("quantization steps must be > 0")
        return number


class QualityDefectConfig(BaseModel):
    """Applied only when scenario is data_quality_stress."""

    model_config = ConfigDict(extra="forbid")

    p_missing: float = 0.02
    p_duplicate_record: float = 0.005
    p_invalid: float = 0.002
    p_spike: float = 0.003
    spike_sigma_mult: float = 25.0
    p_dropout: float = 0.002
    dropout_run_length: int = Field(default=3, ge=1)
    p_time_jump: float = 0.004
    time_jump_seconds: float = 30.0
    timestamp_jitter_s: float = 0.15

    @field_validator(
        "p_missing",
        "p_duplicate_record",
        "p_invalid",
        "p_spike",
        "p_dropout",
        "p_time_jump",
        mode="before",
    )
    @classmethod
    def _prob(cls, value: object) -> float:
        number = _reject_non_finite_number(value)
        if not 0 <= number <= 1:
            raise ValueError("quality probabilities must be in [0, 1]")
        return number

    @field_validator("spike_sigma_mult", "time_jump_seconds", "timestamp_jitter_s", mode="before")
    @classmethod
    def _nonneg(cls, value: object) -> float:
        return _finite_ge_zero(value, name="quality parameter")


class GenerationConfig(BaseModel):
    """Controls synthetic population generation. Does not duplicate TestProfile stress tables."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(default="syn-sic-pc-dev-001", min_length=1)
    scenario: Scenario = Scenario.DEGRADATION_BENCHMARK
    seed: int = Field(default=20260921)
    generator_version: str = GENERATOR_VERSION

    n_modules: int = Field(default=750, ge=1)
    n_lots: int = Field(default=5, ge=1)
    modules_per_lot: int = Field(default=150, ge=1)
    stratify_mix_by_lot: bool = True
    population_mix: PopulationMix = Field(default_factory=PopulationMix)

    target_cycles: Optional[int] = Field(default=None, ge=1)
    observation_stride_cycles: int = Field(default=200, ge=1)
    cycle_phase: CyclePhase = CyclePhase.HEATING
    t0: datetime = datetime(2024, 1, 15, tzinfo=timezone.utc)

    include_channels: list[str] = Field(default_factory=lambda: list(DEFAULT_CHANNELS))

    manufacturing: ManufacturingVariationConfig = Field(default_factory=ManufacturingVariationConfig)
    stress_variation: StressVariationConfig = Field(default_factory=StressVariationConfig)
    healthy_jitter: HealthyJitterConfig = Field(default_factory=HealthyJitterConfig)
    temperature_model: TemperatureModelConfig = Field(default_factory=TemperatureModelConfig)
    degradation: DegradationConfig = Field(default_factory=DegradationConfig)
    sensor_noise: SensorNoiseConfig = Field(default_factory=SensorNoiseConfig)
    sensor_bias: SensorBiasConfig = Field(default_factory=SensorBiasConfig)
    sensor_drift: SensorDriftConfig = Field(default_factory=SensorDriftConfig)
    quantization: QuantizationConfig = Field(default_factory=QuantizationConfig)
    quality: QualityDefectConfig = Field(default_factory=QualityDefectConfig)

    module_profile_path: Optional[str] = None
    test_profile_path: Optional[str] = None
    notes: str = (
        "Synthetic development/benchmark dataset. Not measured production telemetry. "
        "Population mix is a simulation choice, not failure prevalence."
    )

    @field_validator("t0")
    @classmethod
    def _t0_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("t0 must be timezone-aware UTC")
        if value.utcoffset().total_seconds() != 0:
            raise ValueError("t0 must be UTC")
        return value.astimezone(timezone.utc)

    @field_validator("include_channels")
    @classmethod
    def _channels(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("include_channels must not be empty")
        unknown = [item for item in value if item not in _CHANNEL_VALUES]
        if unknown:
            raise ValueError(f"unknown telemetry channels: {unknown}")
        if len(set(value)) != len(value):
            raise ValueError("include_channels must be unique")
        required = {TelemetryParameter.RDS_ON.value, TelemetryParameter.TJ.value}
        missing = required - set(value)
        if missing:
            raise ValueError(f"include_channels must include {sorted(missing)} so temperature conditioning is possible")
        return value

    @field_validator("generator_version")
    @classmethod
    def _version(cls, value: str) -> str:
        if value != GENERATOR_VERSION:
            raise ValueError(f"generator_version must be {GENERATOR_VERSION} for this code")
        return value

    @model_validator(mode="after")
    def _population_counts(self) -> GenerationConfig:
        expected = self.n_lots * self.modules_per_lot
        if expected != self.n_modules:
            raise ValueError(
                f"n_modules ({self.n_modules}) must equal n_lots * modules_per_lot "
                f"({self.n_lots} * {self.modules_per_lot} = {expected})"
            )
        return self

    def effective_mix(self) -> PopulationMix:
        if self.scenario is Scenario.CLEAN_HEALTHY:
            return PopulationMix(
                healthy=1.0,
                bond_wire_interconnect=0.0,
                die_attach_thermal_path=0.0,
                gate_related=0.0,
            )
        return self.population_mix

    def quality_enabled(self) -> bool:
        return self.scenario is Scenario.DATA_QUALITY_STRESS
