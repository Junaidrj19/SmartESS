"""JSON Schema export for ModuleProfile.

Pydantic is the canonical Python definition. The committed schema file is the
interoperable artifact for non-Python consumers.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from domain.module_profiles.models import ModuleProfile

SCHEMA_ID = "https://smartess.dev/schemas/sic-module-profile.schema.json"
SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def module_profile_json_schema() -> dict[str, Any]:
    schema = deepcopy(ModuleProfile.model_json_schema())
    schema["$schema"] = SCHEMA_DRAFT
    schema["$id"] = SCHEMA_ID
    schema["title"] = "SiC ModuleProfile"
    schema["description"] = (
        "Identity, electrical/thermal specifications, health-parameter selection, "
        "acceptance criteria, reliability metadata, and provenance for a configurable "
        "SiC MOSFET power module. This object is not telemetry."
    )
    return schema
