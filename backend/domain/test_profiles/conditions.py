"""Applied test-condition values.

These are not ModuleProfile datasheet specifications. They reuse Unit, finite-number
parsing, and Provenance from the ModuleProfile package without using
EngineeringValue.specification_type (typical / rating / maximum_rating).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from domain.module_profiles.engineering import FiniteNumber, Provenance, _reject_non_finite_number
from domain.module_profiles.enums import Unit


class TestConditionValue(BaseModel):
    """A numeric test condition with an explicit unit.

    `value` is the applied or target condition. Ranges use min_value/max_value.
    """

    model_config = ConfigDict(extra="forbid")

    value: Optional[FiniteNumber] = None
    min_value: Optional[FiniteNumber] = None
    max_value: Optional[FiniteNumber] = None
    unit: Unit
    provenance: Optional[Provenance] = None

    @field_validator("value", "min_value", "max_value", mode="before")
    @classmethod
    def _finite_optional(cls, value: object) -> object:
        if value is None:
            return value
        return _reject_non_finite_number(value)

    @model_validator(mode="after")
    def _magnitudes_consistent(self) -> TestConditionValue:
        if self.value is None and self.min_value is None and self.max_value is None:
            raise ValueError("a test condition must include value and/or min_value/max_value")
        if self.min_value is not None and self.max_value is not None and self.min_value > self.max_value:
            raise ValueError("min_value must not exceed max_value")
        return self
