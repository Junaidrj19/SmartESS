# Data Validation Engine (M5)

M5 independently inspects a generated SmartESS dataset and answers:

> Is this dataset structurally valid, internally consistent, temporally coherent, statistically reasonable **within its declared synthetic assumptions**, and safe for downstream ML?

It does **not** train models, engineer features, detect anomalies, or split train/test data.

**M5 validates the integrity and analytical suitability of the synthetic dataset within its declared simulation assumptions. Passing M5 does not establish experimental validity or real-world physical accuracy.**

M4 generator validation asks whether the generator emitted what it was programmed to emit. M5 inspects the **resulting artifacts** as a downstream consumer. M5 does not treat a successful M4 `validate_generated_dataset` call as sufficient.

## CLI

```text
python3 scripts/validate_synthetic_dataset.py ml/datasets/synthetic/syn-sic-pc-dev-001
python3 -m ml.validators.synthetic ml/datasets/synthetic/syn-smoke
```

Python:

```python
from ml.validators.synthetic import validate_dataset

report = validate_dataset("ml/datasets/synthetic/syn-sic-pc-dev-001")
```

Reports are written next to the dataset (source parquet/JSON is not overwritten):

```text
<dataset>/validation/validation-report.json
<dataset>/validation/validation-report.md
```

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | `PASS` |
| 1 | `WARNING` |
| 2 | `BLOCKED` |

Stdout prints dataset id, overall status, each check, and a short summary.

## PASS / WARNING / BLOCKED

Each check has:

- `status`: `PASS` | `WARNING` | `BLOCKED` — outcome
- `severity`: `blocking` | `warning` | `info` — how a failure must be classified

A **warning-severity** failure becomes `WARNING`, never `BLOCKED`.  
A **blocking-severity** failure becomes `BLOCKED`, never `WARNING`.  
Passing checks are always `PASS`.

Overall status (deterministic):

1. `BLOCKED` if any check has status `BLOCKED` (cannot be downgraded)
2. else `WARNING` if any check has status `WARNING`
3. else `PASS`

`WARNING` is not a failure of the overall pipeline by itself. `BLOCKED` datasets must not enter training (later milestones).

## Dataset discovery

The validator accepts a dataset directory such as `ml/datasets/synthetic/syn-sic-pc-dev-001/` and requires:

- `metadata/dataset.json`
- `metadata/generation-config.json`
- `metadata/assumptions.json`
- `telemetry/telemetry.parquet`
- `ground_truth/ground-truth.parquet`
- `provenance/provenance.json`

Missing or unreadable required artifacts are `BLOCKED`. Files are not silently skipped.

## Validation categories

| Category | Intent |
| --- | --- |
| Artifacts | Required files present and readable |
| Metadata | Identity, scenario, seed, versions, `data_origin=synthetic`, provenance, assumptions |
| Telemetry | Schema, identifiers, dtypes, NaN/Inf, M3 missingness, units/origin, sampled M3 reconstruct |
| Ground truth | Required fields, unique modules, supported mechanisms, onset/stage order, finite severity/rate |
| Consistency | `dataset_id`, seed, generator version, scenario, module counts, mechanism mix, population membership |
| Temporal | Cycle validity, scenario-aware monotonicity, stride, UTC timestamps |
| Numerical | Finite values; non-negative resistance/power/current/Rth; Celsius not below absolute zero; lumped Tj–Tc consistency |
| Missingness | Clean vs `data_quality_stress`; missing is never numeric zero |
| Identity | Duplicate ids / module-cycle / rows; lot ids |
| Size | Module, lot, row, and GT counts vs configuration (dropout-tolerant in quality scenario) |
| Distribution | Non-degenerate variation, outlier rates, group collapse (simulation diagnostics) |
| Correlation | Declared relationships present; suspiciously perfect links flagged |
| Temperature confounding | Healthy RDS(on) vs Tj; labels not trivially `high Tj = degraded` |
| Degradation | Onset in trajectory, progression, not a one-cycle jump, rate heterogeneity |
| Mechanism | Group means / standardized differences; not a classifier |
| Leakage | Ground-truth and ML fields absent from telemetry columns and notes |

## Scenario-aware behavior

| Scenario | Missingness / duplicates / time |
| --- | --- |
| `clean_healthy`, `degradation_benchmark` | Unexpected missing/invalid statuses, duplicate module/cycle, non-strict cycles, non-strict timestamps → typically `BLOCKED` |
| `data_quality_stress` | Controlled missingness, duplicate module/cycle rows, jitter, and time jumps are **expected**. They are measured against configuration. Absence of configured missingness on a large file is `BLOCKED`. Duplicate `telemetry_id` remains `BLOCKED` (identity must stay unique; the generator uses a `-dup` suffix). |

Empty `source_references` is **not** an error (M4 has not ingested verified external sources).

Synthetic data labelled `data_origin=real` is `BLOCKED`.

Missing provenance is `BLOCKED`.

Mechanism composition is checked with the same largest-remainder / per-lot allocation as the generator. Metadata is not repaired.

## Report format

JSON is a `ValidationReport`:

- `dataset_id`, `validator_version`, `validation_timestamp`, `overall_status`
- `checks[]` with `check_id`, `category`, `severity`, `status`, `message`, `metrics`, `affected_records`, `affected_modules`
- `summary` (counts, missingness, duplicates, key metrics, runtime)
- `limitations`

Markdown restates overall status, size, PASS/WARNING/BLOCKED lists, key metrics, and limitations.

## Numerical and statistical policy

Only deterministic limits justified by M3 or the declared simulation are enforced (example: resistance not negative; Celsius not below −273.15 °C). M5 does **not** invent datasheet or “industry typical” windows.

Distribution, correlation, temperature-confounding, and mechanism checks are **simulation diagnostics**. They can `WARNING` or `BLOCKED` when the file is degenerate or unusable as a benchmark. Passing them does **not** prove physical realism or mechanism-identification performance. No ML classifier is trained.

## Limitations

- Passing M5 is not experimental validation and not a reliability qualification.
- Sampled M3 pydantic reconstruction (not every row) is used for speed on ~375k-row files; vectorized column checks cover the full table.
- Correlation coefficients have no “correct” target value.
- `data_quality_stress` bounds on missingness rates are loose statistical checks, not a proof of the defect RNG.
- Validator version `1.0.0`.
