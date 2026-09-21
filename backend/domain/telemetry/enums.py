"""Bounded enumerations for telemetry observations.

Health-parameter names reuse ModuleProfile.HealthParameter values.
delta_Tj and electrical_power are telemetry-only observation channels.
"""

from __future__ import annotations

from enum import Enum

from domain.module_profiles.enums import HealthParameter


class TelemetryParameter(str, Enum):
    """Observation channels. Health-parameter members keep ModuleProfile names."""

    RDS_ON = HealthParameter.RDS_ON.value
    VTH = HealthParameter.VTH.value
    IGSS = HealthParameter.IGSS.value
    IDSS = HealthParameter.IDSS.value
    VDS_ON = HealthParameter.VDS_ON.value
    VF = HealthParameter.VF.value
    TJ = HealthParameter.TJ.value
    TC = HealthParameter.TC.value
    TA = HealthParameter.TA.value
    RTH = HealthParameter.RTH.value
    VDS = HealthParameter.VDS.value
    VGS = HealthParameter.VGS.value
    ID = HealthParameter.ID.value
    DELTA_TJ = "delta_Tj"
    ELECTRICAL_POWER = "electrical_power"


class MeasurementStatus(str, Enum):
    VALID = "valid"
    MISSING = "missing"
    INVALID = "invalid"
    ESTIMATED = "estimated"
    DERIVED = "derived"


class MeasurementOrigin(str, Enum):
    """Whether the value was acquired or computed. Independent of quality status."""

    MEASURED = "measured"
    DERIVED = "derived"


class DataOrigin(str, Enum):
    REAL = "real"
    SYNTHETIC = "synthetic"
    SIMULATED = "simulated"
    UNKNOWN = "unknown"


class TelemetrySourceType(str, Enum):
    CSV = "csv"
    JSON = "json"
    PARQUET = "parquet"
    DATABASE_EXPORT = "database_export"
    LABORATORY = "laboratory"
    ILLUSTRATIVE_REFERENCE = "illustrative_reference"
    UNKNOWN = "unknown"


class CyclePhase(str, Enum):
    HEATING = "heating"
    COOLING = "cooling"
    DWELL = "dwell"
    UNKNOWN = "unknown"


HEALTH_PARAMETER_VALUES = frozenset(item.value for item in HealthParameter)
TELEMETRY_ONLY_PARAMETERS = frozenset(
    {TelemetryParameter.DELTA_TJ, TelemetryParameter.ELECTRICAL_POWER}
)
