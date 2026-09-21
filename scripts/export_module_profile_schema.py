"""Write committed JSON Schema files from canonical Pydantic models."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from domain.module_profiles.schema import module_profile_json_schema  # noqa: E402
from domain.module_profiles.validation import SCHEMA_PATH as MODULE_SCHEMA_PATH  # noqa: E402
from domain.telemetry.schema import telemetry_json_schema  # noqa: E402
from domain.telemetry.validation import SCHEMA_PATH as TELEMETRY_SCHEMA_PATH  # noqa: E402
from domain.test_profiles.schema import test_profile_json_schema  # noqa: E402
from domain.test_profiles.validation import SCHEMA_PATH as TEST_SCHEMA_PATH  # noqa: E402


def _write(path: Path, schema: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path}")


def main() -> None:
    _write(MODULE_SCHEMA_PATH, module_profile_json_schema())
    _write(TEST_SCHEMA_PATH, test_profile_json_schema())
    _write(TELEMETRY_SCHEMA_PATH, telemetry_json_schema())


if __name__ == "__main__":
    main()
