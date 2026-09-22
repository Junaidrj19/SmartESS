"""Temperature normalization for feature engineering.

Uses the M4 declared RDS(on) type curve: linear interpolation between
ModuleProfile typicals at T_ref and T_hot.

RDS_on_normalized = RDS_on_measured / (R_type(Tj) / R_type(T_ref))
R_type(Tj) = R_ref + (R_hot - R_ref) * (Tj - T_ref) / (T_hot - T_ref)
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

from domain.module_profiles.enums import SpecificationType, Unit
from domain.module_profiles.models import ModuleProfile
from domain.module_profiles.validation import parse_module_profile


class TemperatureNormalizer:
    """Normalize RDS_on to T_ref using the M4 linear type curve."""

    def __init__(
        self,
        rds_on_ref_mohm: float,
        rds_on_hot_mohm: float,
        t_ref_C: float,
        t_hot_C: float,
    ):
        if t_hot_C <= t_ref_C:
            raise ValueError("t_hot_C must be greater than t_ref_C")
        if rds_on_ref_mohm <= 0 or rds_on_hot_mohm <= 0:
            raise ValueError("RDS_on typicals must be positive")
        self.rds_on_ref_mohm = float(rds_on_ref_mohm)
        self.rds_on_hot_mohm = float(rds_on_hot_mohm)
        self.t_ref_C = float(t_ref_C)
        self.t_hot_C = float(t_hot_C)
        self.reference_temperature = self.t_ref_C
        self.temp_coeff_fractional = (self.rds_on_hot_mohm / self.rds_on_ref_mohm - 1.0) / (
            self.t_hot_C - self.t_ref_C
        )

    @classmethod
    def from_module_profile(
        cls,
        profile: ModuleProfile,
        *,
        t_ref_C: float,
        t_hot_C: float = 150.0,
    ) -> "TemperatureNormalizer":
        return cls(
            rds_on_ref_mohm=_typical_rds_mohm(profile, t_ref_C),
            rds_on_hot_mohm=_typical_rds_mohm(profile, t_hot_C),
            t_ref_C=t_ref_C,
            t_hot_C=t_hot_C,
        )

    @classmethod
    def from_module_profile_path(
        cls,
        path: Union[str, Path],
        *,
        t_ref_C: float,
        t_hot_C: float = 150.0,
    ) -> "TemperatureNormalizer":
        import json

        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_module_profile(parse_module_profile(payload), t_ref_C=t_ref_C, t_hot_C=t_hot_C)

    def r_type_ratio(self, tj: Union[float, pd.Series, np.ndarray]) -> Union[float, pd.Series, np.ndarray]:
        """R_type(Tj) / R_type(T_ref), matching M4 rds_type_ratio."""
        slope = (self.rds_on_hot_mohm - self.rds_on_ref_mohm) / (self.t_hot_C - self.t_ref_C)
        r_type = self.rds_on_ref_mohm + slope * (tj - self.t_ref_C)
        return r_type / self.rds_on_ref_mohm

    def _normalization_factor(self, tj: Union[float, pd.Series]) -> Union[float, pd.Series]:
        return self.r_type_ratio(tj)

    def normalize(
        self,
        rds_on: Union[float, pd.Series],
        tj: Union[float, pd.Series],
    ) -> Union[float, pd.Series]:
        if isinstance(rds_on, pd.Series) or isinstance(tj, pd.Series):
            rds_series = rds_on if isinstance(rds_on, pd.Series) else pd.Series(rds_on, dtype=float)
            tj_series = tj if isinstance(tj, pd.Series) else pd.Series(tj, index=rds_series.index, dtype=float)
            result = pd.Series(np.nan, index=rds_series.index, dtype=float)
            mask = rds_series.notna() & tj_series.notna()
            if mask.any():
                result.loc[mask] = rds_series.loc[mask] / self.r_type_ratio(tj_series.loc[mask])
            return result
        if pd.isna(rds_on) or pd.isna(tj):
            return np.nan
        return float(rds_on) / float(self.r_type_ratio(tj))

    def denormalize(
        self,
        rds_on_normalized: Union[float, pd.Series],
        tj: Union[float, pd.Series],
    ) -> Union[float, pd.Series]:
        if isinstance(rds_on_normalized, pd.Series) or isinstance(tj, pd.Series):
            rds_series = (
                rds_on_normalized
                if isinstance(rds_on_normalized, pd.Series)
                else pd.Series(rds_on_normalized, dtype=float)
            )
            tj_series = tj if isinstance(tj, pd.Series) else pd.Series(tj, index=rds_series.index, dtype=float)
            result = pd.Series(np.nan, index=rds_series.index, dtype=float)
            mask = rds_series.notna() & tj_series.notna()
            if mask.any():
                result.loc[mask] = rds_series.loc[mask] * self.r_type_ratio(tj_series.loc[mask])
            return result
        if pd.isna(rds_on_normalized) or pd.isna(tj):
            return np.nan
        return float(rds_on_normalized) * float(self.r_type_ratio(tj))

    def get_normalization_info(self) -> dict:
        return {
            "normalization_equation": (
                "RDS_on_normalized = RDS_on_measured / (R_type(Tj) / R_type(T_ref)); "
                "R_type(Tj) = R_ref + (R_hot - R_ref) * (Tj - T_ref) / (T_hot - T_ref)"
            ),
            "reference_temperature_C": self.reference_temperature,
            "t_ref_C": self.t_ref_C,
            "t_hot_C": self.t_hot_C,
            "rds_on_ref_mohm": self.rds_on_ref_mohm,
            "rds_on_hot_mohm": self.rds_on_hot_mohm,
            "temperature_coefficient_fractional_per_C": self.temp_coeff_fractional,
            "required_inputs": ["RDS_on", "Tj"],
            "source": "Declared ModuleProfile typicals at T_ref and T_hot (M4 type curve)",
            "assumptions": [
                "Linear temperature dependence of RDS_on between T_ref and T_hot",
                "ModuleProfile typicals at T_ref and T_hot define the type curve",
                "No second-order temperature effects",
            ],
            "behavior_when_Tj_missing": "Returns NaN (missingness preserved)",
            "behavior_when_RDS_on_missing": "Returns NaN (missingness preserved)",
        }


def _typical_rds_mohm(profile: ModuleProfile, tj_C: float) -> float:
    if not profile.electrical.rds_on:
        raise ValueError("ModuleProfile electrical.rds_on is required for temperature normalization")
    matches = []
    for item in profile.electrical.rds_on:
        if item.specification_type is not SpecificationType.TYPICAL:
            continue
        if item.unit is not Unit.MOHM:
            raise ValueError("v1 temperature normalization requires RDS(on) typicals in mOhm")
        tj = None if item.conditions is None else item.conditions.junction_temperature_C
        if tj is not None and abs(float(tj) - float(tj_C)) < 1e-6 and item.value is not None:
            matches.append(float(item.value))
    if not matches:
        raise ValueError(f"ModuleProfile has no typical RDS(on) at Tj={tj_C} C")
    return matches[0]
