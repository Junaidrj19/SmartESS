"""JSON Schema export for TestProfile. Pydantic is canonical."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from domain.test_profiles.models import TestProfile

SCHEMA_ID = "https://smartess.dev/schemas/test-profile.schema.json"
SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def test_profile_json_schema() -> dict[str, Any]:
    schema = deepcopy(TestProfile.model_json_schema())
    schema["$schema"] = SCHEMA_DRAFT
    schema["$id"] = SCHEMA_ID
    schema["title"] = "SiC TestProfile"
    schema["description"] = (
        "How a SiC module is stressed during a reliability test. References a "
        "ModuleProfile by module_profile_id. This object is not telemetry."
    )
    return schema
