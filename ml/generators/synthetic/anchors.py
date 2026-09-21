"""Extract type-level simulation anchors from ModuleProfile and TestProfile.

Missing required fields fail explicitly. Values from the illustrative profiles
are configuration anchors, not manufacturer facts.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.module_profiles.enums import SpecificationType, Technology, Topology, Unit
from domain.module_profiles.models import ModuleProfile
from domain.test_profiles.conditions import TestConditionValue
from domain.test_profiles.enums import TestType
from domain.test_profiles.models import TestProfile


@dataclass(frozen=True)
class TypeAnchors:
    module_profile_id: str
    test_id: str
    rds_ref_mohm: float
    rds_hot_mohm: float
    t_ref_C: float
    t_hot_C: float
    vth_ref_V: float
    igss_base_uA: float
    idss_base_uA: float
    rth_jc_C_per_W: float
    vds_V: float
    id_A: float
    vgs_on_V: float
    tj_min_C: float
    tj_max_C: float
    delta_tj_C: float
    tc_min_C: float | None
    tc_max_C: float | None
    ta_C: float
    target_cycles: int
    cycle_duration_s: float
    heating_duration_s: float
    cooling_duration_s: float
    switching_frequency_Hz: float | None


def _point(value: TestConditionValue, name: str) -> float:
    if value.value is None:
        raise ValueError(f"TestProfile {name} must include a point value for generation")
    return float(value.value)


def _typical_rds(profile: ModuleProfile, tj_C: float) -> float:
    if not profile.electrical.rds_on:
        raise ValueError("ModuleProfile electrical.rds_on is required to generate RDS(on)")
    matches = []
    for item in profile.electrical.rds_on:
        if item.specification_type is not SpecificationType.TYPICAL:
            continue
        if item.unit is not Unit.MOHM:
            raise ValueError("generator v1 requires RDS(on) in mOhm")
        tj = None if item.conditions is None else item.conditions.junction_temperature_C
        if tj is not None and abs(float(tj) - tj_C) < 1e-6 and item.value is not None:
            matches.append(float(item.value))
    if not matches:
        raise ValueError(f"ModuleProfile has no typical RDS(on) at Tj={tj_C} C")
    return matches[0]


def _typical_vth(profile: ModuleProfile) -> float:
    if not profile.electrical.vth:
        raise ValueError("ModuleProfile electrical.vth is required")
    for item in profile.electrical.vth:
        if item.specification_type is SpecificationType.TYPICAL and item.value is not None:
            if item.unit is not Unit.V:
                raise ValueError("VTH must be in V")
            return float(item.value)
    raise ValueError("ModuleProfile has no typical VTH")


def _first_maximum(values, *, unit, name: str) -> float:
    if not values:
        raise ValueError(f"ModuleProfile {name} is required")
    for item in values:
        if item.specification_type in {SpecificationType.MAXIMUM, SpecificationType.MAXIMUM_RATING} and item.value is not None:
            if item.unit is not unit:
                raise ValueError(f"{name} unit must be {unit.value}")
            return float(item.value)
    raise ValueError(f"ModuleProfile has no maximum {name}")


def _typical_rth(profile: ModuleProfile) -> float:
    thermal = profile.thermal
    if thermal is None or not thermal.rth_j_c:
        raise ValueError("ModuleProfile thermal.rth_j_c is required")
    for item in thermal.rth_j_c:
        if item.specification_type is SpecificationType.TYPICAL and item.value is not None:
            if item.unit is not Unit.C_PER_W:
                raise ValueError("Rth(j-c) must be C_per_W")
            return float(item.value)
    raise ValueError("ModuleProfile has no typical Rth(j-c)")


def extract_anchors(
    module_profile: ModuleProfile,
    test_profile: TestProfile,
    *,
    t_ref_C: float,
    t_hot_C: float = 150.0,
) -> TypeAnchors:
    if module_profile.identity.technology is not Technology.SIC_MOSFET:
        raise ValueError("generator v1 supports SiC MOSFET ModuleProfiles only")
    if module_profile.device.topology is not Topology.HALF_BRIDGE:
        raise ValueError("generator v1 supports half_bridge topology only")
    if test_profile.test_type is not TestType.POWER_CYCLING:
        raise ValueError("generator v1 supports power_cycling TestProfiles only")
    if test_profile.module_profile_id != module_profile.identity.module_id:
        raise ValueError(
            "TestProfile.module_profile_id must match ModuleProfile.identity.module_id "
            f"({test_profile.module_profile_id!r} vs {module_profile.identity.module_id!r})"
        )

    electrical = test_profile.electrical_stress
    thermal = test_profile.thermal_stress
    cycle = test_profile.cycle_profile
    if electrical is None or thermal is None or cycle is None:
        raise ValueError("power-cycling TestProfile must include electrical_stress, thermal_stress, and cycle_profile")
    if electrical.vds is None or electrical.id is None:
        raise ValueError("TestProfile electrical_stress must include vds and id")
    if thermal.tj_minimum is None or thermal.tj_maximum is None:
        raise ValueError("TestProfile thermal_stress must include tj_minimum and tj_maximum")

    vgs = electrical.vgs_on if electrical.vgs_on is not None else electrical.vgs
    if vgs is None:
        raise ValueError("TestProfile electrical_stress must include vgs_on or vgs")

    delta_tj = thermal.delta_tj
    tj_min = _point(thermal.tj_minimum, "tj_minimum")
    tj_max = _point(thermal.tj_maximum, "tj_maximum")
    if delta_tj is not None and delta_tj.value is not None:
        delta = float(delta_tj.value)
    else:
        delta = tj_max - tj_min

    cycle_duration = cycle.cycle_duration_s
    if cycle_duration is None:
        extra = float(cycle.dwell_time_s or 0.0)
        cycle_duration = float(cycle.heating_duration_s) + float(cycle.cooling_duration_s) + extra
    if cycle_duration <= 0:
        raise ValueError("cycle duration must be positive")

    ta = 25.0
    if test_profile.environmental_conditions and test_profile.environmental_conditions.ambient_temperature:
        ta = _point(test_profile.environmental_conditions.ambient_temperature, "ambient_temperature")

    igss_max = _first_maximum(module_profile.electrical.igss, unit=Unit.UA, name="IGSS")
    idss_max = _first_maximum(module_profile.electrical.idss, unit=Unit.UA, name="IDSS")

    freq = None
    if electrical.switching_frequency is not None and electrical.switching_frequency.value is not None:
        freq = float(electrical.switching_frequency.value)

    tc_min = None if thermal.tc_minimum is None else _point(thermal.tc_minimum, "tc_minimum")
    tc_max = None if thermal.tc_maximum is None else _point(thermal.tc_maximum, "tc_maximum")

    return TypeAnchors(
        module_profile_id=module_profile.identity.module_id,
        test_id=test_profile.test_id,
        rds_ref_mohm=_typical_rds(module_profile, t_ref_C),
        rds_hot_mohm=_typical_rds(module_profile, t_hot_C),
        t_ref_C=t_ref_C,
        t_hot_C=t_hot_C,
        vth_ref_V=_typical_vth(module_profile),
        igss_base_uA=max(igss_max * 0.16, 1e-4),
        idss_base_uA=max(idss_max * 0.20, 1e-3),
        rth_jc_C_per_W=_typical_rth(module_profile),
        vds_V=_point(electrical.vds, "vds"),
        id_A=_point(electrical.id, "id"),
        vgs_on_V=_point(vgs, "vgs_on"),
        tj_min_C=tj_min,
        tj_max_C=tj_max,
        delta_tj_C=delta,
        tc_min_C=tc_min,
        tc_max_C=tc_max,
        ta_C=ta,
        target_cycles=int(cycle.target_cycles),
        cycle_duration_s=float(cycle_duration),
        heating_duration_s=float(cycle.heating_duration_s),
        cooling_duration_s=float(cycle.cooling_duration_s),
        switching_frequency_Hz=freq,
    )
