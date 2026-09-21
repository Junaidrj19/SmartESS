# Telemetry

## Purpose

`TelemetryRecord` describes **what was measured** at one point during a test: a timestamped observation for a physical module under a TestProfile, with structured measurements, data-quality status, and provenance.

It is the third data-foundation contract, after `ModuleProfile` and `TestProfile`. Dataset generation, ingestion, feature engineering, and ML are later milestones.

## Scope

Belongs in telemetry:

- observation identity (`telemetry_id`)
- identifiers only: `module_id`, `test_id`, optional `lot_id` / `dataset_id` / `batch_id`
- timezone-aware UTC `timestamp`
- optional `cycle_number` and `cycle_phase`
- structured measurements (parameter, value, unit, status, origin)
- optional uncertainty, sensor/channel metadata, measurement conditions
- provenance including explicit `data_origin` (real / synthetic / simulated / unknown)

Does **not** belong in telemetry:

- ModuleProfile datasheet specifications or an embedded ModuleProfile
- TestProfile stress configuration or an embedded TestProfile
- ML outputs (`anomaly_score`, `prediction`, `predicted_failure`, `failure_probability`)
- investigation fields (`failure_mechanism`, `hypothesis`, `investigation_result`)
- ground-truth simulator labels

The Python model rejects those extra fields (`extra="forbid"` plus an explicit analytical-field blocklist).

## Semantic separation

| Object | Meaning |
| --- | --- |
| **ModuleProfile** | what the component *is* (identity, ratings, specified health parameters) |
| **TestProfile** | how the component *is stressed* (applied conditions, cycle plan, channels to collect) |
| **Telemetry** | what *happened* (measured or derived observations) |
| ML output (later) | what the analytical system *inferred* |
| Investigation (later) | possible engineering *explanations* |

These concepts must not be mixed.

Relationship (identifiers only; no embedded objects, no database foreign keys in this milestone):

```text
ModuleProfile
      ↑
module_id
      │
Telemetry ─── test_id ───→ TestProfile
```

`module_id` identifies the physical module (`ModuleProfile.identity.module_id`).  
`test_id` identifies the TestProfile / test-execution context.

Telemetry may include the same channel names declared in `TestProfile.measurement_configuration`. This milestone does **not** cross-check a record against a TestProfile file.

## Observation model

Canonical implementation: `backend/domain/telemetry/models.py`.  
JSON Schema: `schemas/telemetry.schema.json` (Draft 2020-12, generated from Pydantic).

The unit of exchange is **one** `TelemetryRecord` (one timestamped observation). A time series is a sequence of records. The reference fixture is a JSON array of records for schema tests only.

| Field | Role |
| --- | --- |
| `schema_version` | Contract version (`1.0.0`) |
| `telemetry_id` | Observation identity |
| `module_id` / `test_id` | Links to module and test configuration |
| `timestamp` | When the observation occurred (UTC) |
| `cycle_number` / `cycle_phase` | Cycle context when the test uses cycles |
| `measurements` | One or more structured channel observations |
| `lot_id` / `dataset_id` / `batch_id` | Optional grouping identifiers |
| `provenance` | Origin and import metadata |

Full dataset metadata (validation status, feature versions, simulation seeds) is **not** this object.

## Timestamp semantics

Canonical telemetry timestamps are **timezone-aware UTC**.

- Naive timestamps are rejected.
- Non-UTC offsets are rejected. This milestone does not convert timezones.
- JSON examples use `Z` or `+00:00`.

`imported_at`, when present, follows the same UTC rule.

## Cycle semantics

`cycle_number` is an optional integer `>= 0`. Cycle `0` is allowed. It is not required for every test type (for example HTOL may omit it). Power cycling typically supplies it because degradation is expected to evolve over cycles.

`cycle_phase` is optional: `heating`, `cooling`, `dwell`, `unknown`.

## Measurements

Each `Measurement` is a structured object, not an unvalidated JSON dictionary:

- `parameter` — observation channel
- `value` — finite JSON number, or omitted when missing
- `unit` — explicit unit from the shared `Unit` enum
- `status` — data-quality label for this sample
- `origin` — `measured` or `derived`
- optional `uncertainty`, sensor/channel/instrument ids, `conditions`, `derivation`

**ModuleProfile `EngineeringValue`** is specification semantics.  
**Telemetry `Measurement`** is observation semantics. They may share a physical unit and must not be treated as the same type.

### Parameters

Health-parameter names are exactly the ModuleProfile `HealthParameter` values: `RDS_on`, `VTH`, `IGSS`, `IDSS`, `VDS_on`, `VF`, `Tj`, `Tc`, `Ta`, `Rth`, `VDS`, `VGS`, `ID`.

Telemetry also allows two observation channels that are not health-parameter enums:

- `delta_Tj`
- `electrical_power`

`VDS`, `VGS`, and `ID` are electrical measurements that ModuleProfile already listed as configurable channels. They remain observations here, not inferred health conclusions.

`timestamp` and `cycle_number` are record-level fields, not measurement parameters.

### Units

Explicit units are required whenever a numeric value is present. Shared `Unit` members used here include `V`, `A`, `mOhm`, `Ohm`, `uA`, `C`, `W`, `Hz`, and existing `C_per_W` for `Rth`.

Parameter/unit compatibility is deterministic. Examples:

- `RDS_on` → `mOhm` or `Ohm`
- `Tj` / `Tc` / `Ta` / `delta_Tj` → `C`
- `VDS` / `VGS` / `VTH` → `V`
- `ID` → `A`
- `electrical_power` → `W`

`RDS_on` in `V` or `Tj` in `A` is rejected. No silent unit conversion.

### Shared Unit enum change

`Unit.W` (`"W"`) was added to the shared ModuleProfile unit enumeration so electrical power can be expressed without a second unit system. ModuleProfile specification fields still do not use watt; TestProfile continues to store applied power as `electrical_power_W` (a numeric field from M2). Telemetry observations of power use `parameter: electrical_power` with `unit: W`.

## Measured vs derived

`origin` is required:

- `measured` — acquired from a sensor/instrument
- `derived` — computed from other observations or a documented method

Typical raw channels include `VDS`, `ID`, `Tj`, `Tc`. Typical derived channels include `RDS_on`, `delta_Tj`, `electrical_power`, thermal-resistance estimates. The contract does **not** assume a parameter is always derived; the record must say so.

If `origin` is `derived`, optional `derivation` may record `method`, `input_parameters`, and `notes`. This milestone does not implement a calculation engine.

## Measurement status

`status` records data quality for the sample:

- `valid`
- `missing`
- `invalid`
- `estimated`
- `derived`

Invalid samples are retained, not discarded. Status `derived` requires `origin: derived`. Full dataset quality classification (`PASS` / `WARNING` / `BLOCKED`) belongs to a later data-validation engine.

## Missing values

Missingness is explicit: `status: missing` and **no** numeric `value`.

Raw telemetry must not replace missing values with zero, mean, previous value, or interpolation. A measured `0` with `status: valid` is a real zero, not missingness.

## Uncertainty

Optional, finite, and not negative. Many datasets omit it. Uncertainty must not be invented.

## Sensor metadata

Optional per measurement: `sensor_id`, `channel_id`, `instrument_id`, `acquisition_system`. Metadata only; not a hardware integration framework.

## Provenance

`TelemetryProvenance` includes:

- `data_origin` (required): `real`, `synthetic`, `simulated`, `unknown`
- optional `source_type`: `csv`, `json`, `parquet`, `database_export`, `laboratory`, `illustrative_reference`, `unknown`
- optional `source_file`, `source_dataset`, `acquisition_system`, `imported_at`, `import_version`, `notes`

### Real vs synthetic

Synthetic or simulated telemetry must **never** be represented as real production telemetry. The reference fixture is labeled `data_origin: synthetic` and `source_type: illustrative_reference`.

`unknown` is allowed when origin is genuinely unknown; it is not a substitute for labeling synthetic development data as real.

## Raw telemetry immutability

Raw telemetry is **immutable source data**. Later processing should produce derived datasets or features rather than silently rewriting original observations. This is a domain rule. This milestone does not implement storage immutability.

## Validation rules

Deterministic rules in `backend/domain/telemetry/validation.py` and model validators:

- non-empty `telemetry_id`, `module_id`, `test_id`; non-empty `dataset_id` when supplied
- timezone-aware UTC timestamps
- `cycle_number >= 0` when present
- finite JSON numbers only (not bool / string / NaN / Inf)
- valid units; compatible parameter/unit pairs
- duplicate parameters in one record rejected
- `missing` has no value; `valid` / `estimated` / `derived` require value and unit
- uncertainty finite and not negative
- valid `data_origin`; extra ML/investigation fields rejected
- identifiers only (no embedded profiles)

No anomaly detection or physical-range plausibility checks in M3.

## Example

Synthetic/illustrative power-cycling observations (placeholders, not real measurements):

[`examples/telemetry/power-cycling-reference.json`](../../examples/telemetry/power-cycling-reference.json)

The array references `module_id` `sic-ref-half-bridge-illustrative` and `test_id` `pc-sic-ref-illustrative-001`. It includes a few cycles, raw channels (`VDS`, `ID`, `Tj`, `Tc`), derived `RDS_on` / `delta_Tj` / `electrical_power`, and one explicit missing `Tc`.
