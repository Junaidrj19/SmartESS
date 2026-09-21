"""Bounded enumerations for ModuleProfile.

Only genuinely closed sets are enumerated. Manufacturer, part number, package,
qualification, cooling method, and MOSFET configuration remain free-form.
"""

from enum import Enum


class Technology(str, Enum):
    SIC_MOSFET = "SiC MOSFET"


class ProfileStatus(str, Enum):
    DRAFT = "draft"
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    DEPRECATED = "deprecated"


class Topology(str, Enum):
    SINGLE_SWITCH = "single_switch"
    HALF_BRIDGE = "half_bridge"
    FULL_BRIDGE = "full_bridge"
    OTHER = "other"


class SpecificationType(str, Enum):
    TYPICAL = "typical"
    MAXIMUM = "maximum"
    MINIMUM = "minimum"
    GUARANTEED = "guaranteed"
    RATING = "rating"
    MAXIMUM_RATING = "maximum_rating"
    OPERATING_RANGE = "operating_range"


class Unit(str, Enum):
    V = "V"
    A = "A"
    MOHM = "mOhm"
    OHM = "Ohm"
    UA = "uA"
    NC = "nC"
    C = "C"
    C_PER_W = "C_per_W"
    W = "W"
    MM = "mm"
    HZ = "Hz"


class SourceType(str, Enum):
    MANUFACTURER_DATASHEET = "manufacturer_datasheet"
    TECHNICAL_DOCUMENT = "technical_document"
    STANDARD = "standard"
    MANUALLY_ENTERED = "manually_entered"
    AUTOMATED_EXTRACTION = "automated_extraction"
    ILLUSTRATIVE_REFERENCE = "illustrative_reference"


class HealthParameter(str, Enum):
    RDS_ON = "RDS_on"
    VTH = "VTH"
    IGSS = "IGSS"
    IDSS = "IDSS"
    VDS_ON = "VDS_on"
    VF = "VF"
    TJ = "Tj"
    TC = "Tc"
    TA = "Ta"
    RTH = "Rth"
    VDS = "VDS"
    VGS = "VGS"
    ID = "ID"


class ReliabilityTestType(str, Enum):
    POWER_CYCLING = "power_cycling"
    HTOL = "HTOL"
    HTRB = "HTRB"
    HTGB = "HTGB"


class FailureMechanismRef(str, Enum):
    """Configuration references only — not confirmed diagnoses."""

    BOND_WIRE_DEGRADATION = "bond_wire_degradation"
    DIE_ATTACH_DEGRADATION = "die_attach_degradation"
    GATE_OXIDE_DEGRADATION = "gate_oxide_degradation"
    THERMAL_PATH_DEGRADATION = "thermal_path_degradation"
