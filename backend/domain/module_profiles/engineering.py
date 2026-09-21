"""Reusable engineering-value structures for ModuleProfile.

Numeric specifications are never stored as bare numbers. Unknown values stay
absent (None / omitted), never 0, empty string, or guessed defaults.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from domain.module_profiles.enums import SourceType, SpecificationType, Unit


def _reject_non_finite_number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("engineering numbers must be finite JSON numbers, not strings or booleans")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("engineering numbers must be finite")
    return number


FiniteNumber = Annotated[float, Field(strict=False)]


class OperatingConditions(BaseModel):
    """Reference conditions for a specification value.

    Intentionally small. Later ingestion may extend this object without
    requiring a generic condition language.
    """

    model_config = ConfigDict(extra="forbid")

    temperature_C: Optional[FiniteNumber] = None
    voltage_V: Optional[FiniteNumber] = None
    current_A: Optional[FiniteNumber] = None
    gate_voltage_V: Optional[FiniteNumber] = None
    case_temperature_C: Optional[FiniteNumber] = None
    junction_temperature_C: Optional[FiniteNumber] = None

    @field_validator(
        "temperature_C",
        "voltage_V",
        "current_A",
        "gate_voltage_V",
        "case_temperature_C",
        "junction_temperature_C",
        mode="before",
    )
    @classmethod
    def _finite_optional(cls, value: object) -> object:
        if value is None:
            return value
        return _reject_non_finite_number(value)


class Provenance(BaseModel):
    """Source and verification metadata for a profile or a single specification."""

    model_config = ConfigDict(extra="forbid")

    source_type: SourceType
    source_document: Optional[str] = Field(default=None, min_length=1)
    source_revision: Optional[str] = Field(default=None, min_length=1)
    source_url: Optional[str] = Field(default=None, min_length=1)
    extraction_method: Optional[str] = Field(default=None, min_length=1)
    verified_by_engineer: bool = False
    verified_at: Optional[datetime] = None
    page_or_section: Optional[str] = Field(default=None, min_length=1)
    notes: Optional[str] = Field(default=None, min_length=1)

    @field_validator("verified_by_engineer", mode="before")
    @classmethod
    def _bool_not_coerced_from_number(cls, value: object) -> object:
        if isinstance(value, bool):
            return value
        raise ValueError("verified_by_engineer must be a boolean")


class EngineeringValue(BaseModel):
    """A single datasheet/engineering specification with unit, type, and conditions.

    `typical` is not a limit. `maximum_rating` is not a recommended operating condition.
    """

    model_config = ConfigDict(extra="forbid")

    value: Optional[FiniteNumber] = None
    min_value: Optional[FiniteNumber] = None
    max_value: Optional[FiniteNumber] = None
    unit: Unit
    specification_type: SpecificationType
    conditions: Optional[OperatingConditions] = None
    provenance: Optional[Provenance] = None

    @field_validator("value", "min_value", "max_value", mode="before")
    @classmethod
    def _finite_optional(cls, value: object) -> object:
        if value is None:
            return value
        return _reject_non_finite_number(value)

    @model_validator(mode="after")
    def _magnitudes_consistent(self) -> EngineeringValue:
        if self.value is None and self.min_value is None and self.max_value is None:
            raise ValueError("an engineering value must include value and/or min_value/max_value")

        if self.specification_type is SpecificationType.OPERATING_RANGE:
            if self.min_value is None or self.max_value is None:
                raise ValueError("operating_range requires both min_value and max_value")
            if self.min_value >= self.max_value:
                raise ValueError("operating_range min_value must be less than max_value")
        elif self.value is None:
            raise ValueError(
                f"{self.specification_type.value} specifications require a point 'value'"
            )

        if self.min_value is not None and self.max_value is not None and self.min_value > self.max_value:
            raise ValueError("min_value must not exceed max_value")
        return self
