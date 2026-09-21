"""JSON Schema export for TelemetryRecord. Pydantic is canonical."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from domain.telemetry.models import TelemetryRecord

SCHEMA_ID = "https://smartess.dev/schemas/telemetry.schema.json"
SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def telemetry_json_schema() -> dict[str, Any]:
    schema = deepcopy(TelemetryRecord.model_json_schema())
    schema["$schema"] = SCHEMA_DRAFT
    schema["$id"] = SCHEMA_ID
    schema["title"] = "SmartESS TelemetryRecord"
    schema["description"] = (
        "One timestamped observation during a reliability test. Identifies the "
        "module and test by id only. This object is not a ModuleProfile, TestProfile, "
        "ML output, or investigation record. Canonical timestamps are timezone-aware UTC."
    )
    return schema
