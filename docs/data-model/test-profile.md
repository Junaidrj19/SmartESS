# Test Profile

## Purpose

`TestProfile` describes **how a SiC MOSFET power module is stressed** during a reliability test: electrical and thermal conditions, cycle timing, what will be measured, which ModuleProfile acceptance criteria apply, and provenance.

It is the second data-foundation contract, after `ModuleProfile`. Dataset generation, telemetry ingestion, and ML are later milestones.

## Scope

Belongs in a TestProfile:

- `test_id` and `test_type`
- `module_profile_id` (reference only)
- applied electrical and thermal **test conditions**
- environmental setpoints
- cycle timing (power cycling)
- HTOL / HTRB / HTGB configuration sections
- measurement **channels** (names and units, not samples)
- references to ModuleProfile acceptance parameters
- provenance of the test configuration

Does **not** belong in a TestProfile:

- device ratings or datasheet typicals (those live on ModuleProfile)
- timestamped telemetry or `cycle_number` observations
- anomaly scores, ML predictions, degradation labels, ground truth
- investigation results or failure diagnoses
- an embedded ModuleProfile object

## Relationship to ModuleProfile and Telemetry

**ModuleProfile** = what the component *is* (identity, ratings, specified health parameters, conventional limits).

**TestProfile** = how it is *stressed* (applied VDS/ID, Tj excursion, cycle count, duration).

**Telemetry** = what *happened* (measured time series). See `docs/data-model/telemetry.md`.

A ModuleProfile `blocking_voltage` of 1200 V is a device rating. A TestProfile `electrical_stress.vds` of 400 V is the voltage applied during the test. They must not be collapsed.

The link is `module_profile_id` → `ModuleProfile.identity.module_id`. There is no database foreign key in this milestone.

## Supported test types

Machine-readable `test_type` values:

- `power_cycling`
- `HTOL`
- `HTRB`
- `HTGB`
- `custom`

One common `TestProfile` model; type-specific fields live in optional sections (`cycle_profile`, `htol_configuration`, `htrb_configuration`, `htgb_configuration`). Different tests are not assumed to target the same failure mechanism.

## Structure

Canonical implementation: `backend/domain/test_profiles/models.py`.  
JSON Schema: `schemas/test-profile.schema.json` (Draft 2020-12, generated from Pydantic).

| Section | Role |
| --- | --- |
| `schema_version` | Contract version (`1.0.0`) |
| `test_id` | Test-configuration identity |
| `module_profile_id` | ModuleProfile being tested |
| `test_type` | Stress protocol |
| `objective` | Optional engineering intent |
| `electrical_stress` | Applied VDS, ID, VGS, frequency, duty, Rg, power |
| `thermal_stress` | Tj/Tc/Ta setpoints, ΔTj, cooling/control method |
| `environmental_conditions` | Ambient T, humidity, pressure, atmosphere |
| `cycle_profile` | Cycle count and heating/cooling/dwell timing |
| `htol_configuration` / `htrb_configuration` / `htgb_configuration` | Minimum protocol description |
| `measurement_configuration` | Channels to record later as telemetry |
| `acceptance_criteria_reference` | Which ModuleProfile criteria apply |
| `provenance` | How the configuration was obtained |

## Electrical stress

Test conditions use `TestConditionValue` (`value` / range, `unit`, optional provenance). That type reuses ModuleProfile `Unit` and finite-number rules but **does not** use datasheet `specification_type` (`typical`, `maximum_rating`, …).

`electrical_power_W` and `duty_cycle_percent` are explicit numeric fields because watt and percent are not in the ModuleProfile unit enum (left unchanged).

## Thermal stress

Power cycling records `tj_minimum`, `tj_maximum`, and optional `delta_tj` in Celsius. If all three point values are present, `delta_tj` must equal `Tj_max - Tj_min`. Inconsistent values are **rejected**, not rewritten.

## Power cycling

A `power_cycling` profile must include:

- `cycle_profile` with `target_cycles` ≥ 1 and non-negative heating/cooling durations
- `thermal_stress.tj_minimum` and `tj_maximum` with `Tj_max > Tj_min`
- `electrical_stress` with applied `vds` and/or `id`

HTOL requires `htol_configuration` (temperature + duration). HTRB requires temperature, duration, and reverse voltage. HTGB requires temperature, duration, and gate bias. `custom` has no extra protocol section.

## Measurement configuration

Lists intended channels using the same `HealthParameter` names as ModuleProfile (`RDS_on`, `VTH`, `Tj`, …). Sampling interval/frequency, if present, must be positive. Duplicate channel names are rejected. **No samples are stored here.**

## Provenance

`source_type` reuses the ModuleProfile source enumeration (`manually_entered`, `standard`, `manufacturer_datasheet`, `illustrative_reference`, …). Additional fields: `created_by`, `created_at`, `configuration_version`, `notes`. Demo configurations must be labeled `illustrative_reference` and must not be presented as a verified standard or manufacturer procedure.

## Validation

Deterministic rules in `backend/domain/test_profiles/validation.py`:

- non-empty `test_id` and `module_profile_id`; valid `test_type`
- finite JSON numbers only (not bool/string/NaN/Inf)
- positive cycle count; non-negative durations; positive frequencies and sampling intervals
- field-specific units (V, A, Hz, C, Ohm/mOhm)
- Tj/Tc/Ta ranges ordered; ΔTj consistency
- unique measurement parameters from the closed HealthParameter set
- extra properties and telemetry/ML fields rejected
- no embedded ModuleProfile

## Example

Illustrative power-cycling configuration (placeholders, not a verified test plan):

[`examples/test-profiles/power-cycling-reference.json`](../../examples/test-profiles/power-cycling-reference.json)

It references `module_profile_id`: `sic-ref-half-bridge-illustrative`.
