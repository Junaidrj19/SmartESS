"""Structured M5 validation results.

Status (PASS / WARNING / BLOCKED) is the outcome of a check.
Severity (blocking / warning / info) is how a failing outcome must be treated.
They are not interchangeable: a warning-severity check never produces BLOCKED,
and a blocking-severity failure never becomes WARNING.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

VALIDATOR_VERSION = "1.0.0"


class CheckStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    BLOCKED = "BLOCKED"


class CheckSeverity(str, Enum):
    BLOCKING = "blocking"
    WARNING = "warning"
    INFO = "info"


class CheckCategory(str, Enum):
    ARTIFACTS = "artifacts"
    METADATA = "metadata"
    TELEMETRY = "telemetry"
    GROUND_TRUTH = "ground_truth"
    CONSISTENCY = "consistency"
    TEMPORAL = "temporal"
    NUMERICAL = "numerical"
    MISSINGNESS = "missingness"
    DISTRIBUTION = "distribution"
    CORRELATION = "correlation"
    TEMPERATURE_CONFOUNDING = "temperature_confounding"
    DEGRADATION = "degradation"
    MECHANISM = "mechanism"
    LEAKAGE = "leakage"
    IDENTITY = "identity"
    SIZE = "size"


class CheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str = Field(min_length=1)
    category: CheckCategory
    severity: CheckSeverity
    status: CheckStatus
    message: str = Field(min_length=1)
    metrics: dict[str, Any] = Field(default_factory=dict)
    affected_records: list[str] = Field(default_factory=list)
    affected_modules: list[str] = Field(default_factory=list)


class ValidationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    n_checks: int
    n_pass: int
    n_warning: int
    n_blocked: int
    n_modules: Optional[int] = None
    n_lots: Optional[int] = None
    n_telemetry_rows: Optional[int] = None
    n_ground_truth_rows: Optional[int] = None
    mechanism_counts: dict[str, int] = Field(default_factory=dict)
    missingness: dict[str, Any] = Field(default_factory=dict)
    duplicate_counts: dict[str, Any] = Field(default_factory=dict)
    key_metrics: dict[str, Any] = Field(default_factory=dict)
    elapsed_s: float = 0.0
    scenario: Optional[str] = None
    data_origin: Optional[str] = None


class ValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    validator_version: str = VALIDATOR_VERSION
    validation_timestamp: str
    overall_status: CheckStatus
    checks: list[CheckResult]
    summary: ValidationSummary
    limitations: list[str]

    def checks_by_status(self, status: CheckStatus) -> list[CheckResult]:
        return [item for item in self.checks if item.status is status]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def outcome_for(severity: CheckSeverity, *, failed: bool) -> CheckStatus:
    """Map (severity, failed) to status. Passing checks are always PASS."""

    if not failed:
        return CheckStatus.PASS
    if severity is CheckSeverity.BLOCKING:
        return CheckStatus.BLOCKED
    if severity is CheckSeverity.WARNING:
        return CheckStatus.WARNING
    return CheckStatus.WARNING


def aggregate_status(checks: list[CheckResult]) -> CheckStatus:
    """Deterministic overall status. BLOCKED cannot be downgraded."""

    if any(item.status is CheckStatus.BLOCKED for item in checks):
        return CheckStatus.BLOCKED
    if any(item.status is CheckStatus.WARNING for item in checks):
        return CheckStatus.WARNING
    return CheckStatus.PASS


def make_check(
    check_id: str,
    category: CheckCategory,
    severity: CheckSeverity,
    *,
    failed: bool,
    pass_message: str,
    fail_message: str,
    metrics: Optional[dict[str, Any]] = None,
    affected_records: Optional[list[str]] = None,
    affected_modules: Optional[list[str]] = None,
) -> CheckResult:
    status = outcome_for(severity, failed=failed)
    return CheckResult(
        check_id=check_id,
        category=category,
        severity=severity,
        status=status,
        message=fail_message if failed else pass_message,
        metrics=metrics or {},
        affected_records=(affected_records or [])[:25],
        affected_modules=(affected_modules or [])[:25],
    )
