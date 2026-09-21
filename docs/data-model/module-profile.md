# Module Profile

## Purpose

`ModuleProfile` describes **what a SiC MOSFET power module is**: identity, electrical and thermal specifications, which health parameters matter, conventional acceptance limits, reliability-test metadata, and provenance.

It is the central configuration object for later Test Profile, telemetry validation, feature engineering, ML, investigation, and reporting. Those systems are not implemented in this milestone.

## Scope

Belongs in a ModuleProfile:

- component identity (`module_id`, optional manufacturer/part number, technology, status)
- device construction (topology, switch count, package, dimensions)
- datasheet-style electrical, gate-drive, and thermal specifications
- the **names** of primary and secondary health parameters
- conventional acceptance criteria
- supported reliability test types and candidate failure-mechanism **references**
- source and verification metadata

Does **not** belong in a ModuleProfile:

- telemetry measurements (`timestamp`, `cycle_number`, time-series values)
- ML outputs (`anomaly_score`, `predicted_failure`, `model_prediction`)
- degradation state or investigation results
- Test Profile / test-run conditions

The Python model rejects those extra fields (`extra="forbid"` plus an explicit telemetry-field blocklist).

## Structure

Canonical implementation: `backend/domain/module_profiles/models.py`.

Interoperable schema: `schemas/sic-module-profile.schema.json` (Draft 2020-12, generated from Pydantic).

| Section | Role |
| --- | --- |
| `schema_version` | Profile contract version (`1.0.0`) |
| `identity` | Who/what the module is |
| `device` | Topology, switch count, package, dimensions |
| `electrical` | Blocking voltage, currents, RDS(on), VGS/VTH, leakages, optional switching frequency |
| `gate_drive` | Recommended VGS+, VGS−, Rg, Qg (all optional) |
| `thermal` | Tj/Tc limits, Ta range, Rth(j-c), thermal impedance, cooling method |
| `health_parameters` | Which parameters are primary vs secondary monitors |
| `acceptance_criteria` | Conventional pass/fail limits per health parameter |
| `reliability` | Supported tests and mechanism **references** (not diagnoses) |
| `provenance` | How the profile was obtained and whether an engineer verified it |

Identity requires `module_id`, `technology` (`SiC MOSFET`), and `status` (`draft` / `candidate` / `verified` / `deprecated`). Manufacturer and part number are optional.

Device requires `topology` (`single_switch`, `half_bridge`, `full_bridge`, `other`) and `switch_count` ≥ 1.

## Engineering Values

Numeric specifications are **not** bare numbers. Each `EngineeringValue` can carry:

- `value` — point specification
- `min_value` / `max_value` — range bounds (`operating_range` requires both, with min < max)
- `unit` — one of `V`, `A`, `mOhm`, `Ohm`, `uA`, `nC`, `C`, `C_per_W`, `W`, `mm`, `Hz` (`W` was added in M3 for telemetry electrical power; ModuleProfile specification fields do not use it)
- `specification_type` — `typical`, `maximum`, `minimum`, `guaranteed`, `rating`, `maximum_rating`, `operating_range`
- `conditions` — optional reference conditions (`temperature_C`, `voltage_V`, `current_A`, `gate_voltage_V`, `case_temperature_C`, `junction_temperature_C`)
- `provenance` — optional source metadata for that single value

`typical` is not a limit. `maximum_rating` is not a recommended operating condition. RDS(on) may appear multiple times (e.g. typical at 25 °C and typical at 150 °C).

Domain temperatures in this model use Celsius (`C`). This milestone does not convert units.

## Specification vs Measurement

**ModuleProfile:** “What is specified about the component?”  
**Telemetry (later):** “What was measured during a test?”

A specified RDS(on) of 4.5 mΩ typical at 25 °C is configuration. A measured RDS(on) at cycle 10 000 is telemetry and must not be stored on this object.

## Acceptance Criteria vs Anomaly Detection

Acceptance criteria are conventional engineering pass/fail limits (absolute max, min/max window, allowed relative change, allowed shift).

They are **not** ML or statistical anomaly thresholds.

A module may remain inside a datasheet/acceptance limit while exhibiting abnormal behavioral drift. Later anomaly detection must keep that distinction.

## Unknown Values

Unknown engineering data stays omitted or `null`. The model does not substitute `0`, empty strings, or guessed defaults.

Empty specification lists are rejected; omit the field instead. Optional sections (`gate_drive`, `thermal`, most electrical parameters) may be absent on a draft profile.

## Provenance

Profile-level and value-level `Provenance` can record:

- `source_type`: `manufacturer_datasheet`, `technical_document`, `standard`, `manually_entered`, `automated_extraction`, `illustrative_reference`
- `source_document`, `source_revision`, `source_url`, `page_or_section`
- `extraction_method`
- `verified_by_engineer`, `verified_at`
- `notes`

Extracted or example values remain unverified until an engineer confirms them. The committed reference example is explicitly `illustrative_reference` and is not a verified production specification.

Reliability `relevant_failure_mechanisms` are investigation configuration only. They do not assert that a module has failed.

## Validation

Validation is deterministic (Pydantic + `backend/domain/module_profiles/validation.py`). No LLM and no failure diagnosis.

Implemented rules include:

- required identity/device/provenance structure
- bounded enums for technology, topology, units, specification types, health parameters, tests, mechanism references
- finite JSON numbers only (not strings, booleans, NaN, or infinity)
- blocking voltage, currents, RDS(on), switching frequency, Rg, Qg, Rth > 0 when present
- field-specific units (e.g. blocking voltage must be `V`)
- dimensions positive and in `mm`; `switch_count` ≥ 1
- Tj maximum > Tj minimum when both point values exist
- ambient temperature range must be `operating_range` with min < max
- acceptance min ≤ max; relative-change limit must not be negative
- health parameters cannot be both primary and secondary
- extra properties and telemetry/ML fields rejected

## Example

Reference profile for schema and validation testing (placeholder values, not manufacturer facts):

[`examples/module-profiles/sic-reference-module.json`](../../examples/module-profiles/sic-reference-module.json)

Load and validate in Python:

```python
import json
from pathlib import Path
from domain.module_profiles.validation import parse_module_profile, validate_against_json_schema

data = json.loads(Path("examples/module-profiles/sic-reference-module.json").read_text())
profile = parse_module_profile(data)
validate_against_json_schema(data)
```
