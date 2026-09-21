"""Bounded enumerations for TestProfile.

Test type is the stress protocol. It is not a failure diagnosis.
"""

from enum import Enum


class TestType(str, Enum):
    POWER_CYCLING = "power_cycling"
    HTOL = "HTOL"
    HTRB = "HTRB"
    HTGB = "HTGB"
    CUSTOM = "custom"
