"""M5 synthetic dataset validation engine.

Inspects generated artifacts for analytical suitability. Does not train models,
engineer features, or claim experimental physical validity.
"""

from ml.validators.synthetic.engine import validate_dataset
from ml.validators.synthetic.models import (
    VALIDATOR_VERSION,
    CheckResult,
    CheckStatus,
    ValidationReport,
    aggregate_status,
)

__all__ = [
    "VALIDATOR_VERSION",
    "CheckResult",
    "CheckStatus",
    "ValidationReport",
    "aggregate_status",
    "validate_dataset",
]
