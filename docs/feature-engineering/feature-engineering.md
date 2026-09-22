# Feature Engineering (M6)

**Status:** COMPLETE  
**Feature Version:** v1  
**Milestone:** M6 — Versioned Feature Engineering

The authoritative feature registry is `ml/features/definitions.py`. Feature counts, Parquet schemas, metadata, and validator expectations are derived from that registry. They are not maintained independently.

---

## 1. Feature Architecture

The pipeline converts validated longitudinal telemetry into ML-ready features while preserving temporal structure and preventing leakage.

### 1.1 Core Principles

1. **Raw telemetry remains immutable** — source dataset files are never modified
2. **Ground truth is never used as input** — `ground-truth.parquet` is never loaded
3. **Module/lot identity for grouping only** — identifiers are not predictive features
4. **Features from telemetry + declared context only** — TestProfile `target_cycles` and ModuleProfile RDS(on) typicals
5. **Preserve cycle ordering** — all computations respect `module_id`, then `cycle_number`
6. **Explicit temperature confounding handling** — RDS_on is normalized with the M4 type curve
7. **Deterministic, versioned definitions** — schema is independent of incidental missingness
8. **Preserve missingness** — missing stays NaN; never silently zero-filled or imputed
9. **No future leakage** — observation features use current and past observations only
10. **Independence from the M4 generator runtime** — any validated telemetry with declared context can be transformed

### 1.2 Feature Levels

- **Observation-level features**: one row per telemetry observation; **causal**
- **Module-level aggregate features**: one row per module over the **complete trajectory**; **retrospective**

These representations are never mixed. M7 must not use full-trajectory module aggregates to detect an anomaly at an earlier cycle.

---

## 2. Feature Version: v1

M6 defines `feature_version = v1` only. Changing any of the following requires a new feature version:

- feature definitions or formulas
- baseline rules
- rolling windows
- trend rules
- temperature normalization
- signal sets
- missingness behavior
- feature expansion rules

Do not introduce v2 in M6. The validator rejects metadata whose `feature_version` is not `v1`.

---

## 3. Authoritative v1 Signal Sets

Encoded in `ml/features/definitions.py`. The schema does **not** depend on whether a signal is all-NaN in a given dataset.

### 3.1 Electrical passthrough (10)

`RDS_on`, `VTH`, `IGSS`, `IDSS`, `VDS_on`, `VF`, `VDS`, `VGS`, `ID`, `electrical_power`

### 3.2 Thermal passthrough and derived (6)

`Tj`, `Tc`, `Ta`, `delta_Tj`, `Tj_minus_Tc`, `temperature_normalized_RDS_on`

### 3.3 Baseline and rolling signals (8)

`RDS_on`, `VTH`, `IGSS`, `IDSS`, `VDS_on`, `electrical_power`, `Tj`, `Tc`

**VF is not part of the v1 baseline or rolling set.** VF is retained only as a raw electrical passthrough. If VF is missing, all-NaN, or populated, the v1 column set is unchanged. v1 does not implement “if VF is all NaN, exclude VF”.

### 3.4 Trend signals (5)

`RDS_on`, `VTH`, `IGSS`, `IDSS`, `Tj`

---

## 4. Observation-Level Features

**7 identifier columns + 153 feature columns = 160 Parquet columns.**

Identifiers: `module_id`, `test_id`, `lot_id`, `dataset_id`, `timestamp`, `cycle_number`, `observation_index_within_module`.

`cycle_number` is an identifier, not counted in the 153 features.

| Family | Count | Arithmetic |
| --- | --- | --- |
| Temporal | 4 | `normalized_cycle_position`, `elapsed_time`, `observation_index`, `cycle_delta` |
| Electrical | 10 | raw passthrough of the electrical set, including VF |
| Thermal | 6 | 3 raw + `delta_Tj` + `Tj_minus_Tc` + `temperature_normalized_RDS_on` |
| Baseline-relative | 32 | 8 signals × 4 statistics |
| Rolling | 96 | 8 signals × 4 statistics × 3 windows |
| Trend | 5 | 5 signals × 1 trailing slope |
| **Total features** | **153** | 4 + 10 + 6 + 32 + 96 + 5 |

Registry observation definitions: 89 (rolling statistics are one definition each, expanded across windows `[5, 10, 20]`).

### 4.1 Temporal

| Feature | Formula |
| --- | --- |
| `normalized_cycle_position` | `cycle_number / target_cycles` |
| `elapsed_time` | timestamp minus first timestamp **in cycle order** for the module |
| `observation_index` | 0-based index within module after cycle ordering |
| `cycle_delta` | `cycle_number - previous_cycle_number` (NaN on the first observation) |

`target_cycles` comes from declared TestProfile / dataset metadata and is known a priori. If it is missing, generation **fails**. There is no fallback to `max(observed cycle_number)`.

### 4.2 Baseline-relative (causal early-life window)

For each of the 8 baseline/rolling signals:

- `{signal}_baseline_median`
- `{signal}_delta_from_baseline`
- `{signal}_pct_change_from_baseline`
- `{signal}_robust_normalized_deviation` = `(x - median) / (1.4826 * MAD)`

Baseline size:

```text
baseline_size = min(max(baseline_min_cycles, int(n_obs * baseline_window_fraction)), n_obs)
```

Defaults: `baseline_window_fraction = 0.1`, `baseline_min_cycles = 10`. If `n_obs < baseline_min_cycles`, all available observations are used. Ground-truth `onset_cycle` is never used.

### 4.3 Rolling (trailing only)

Windows: `[5, 10, 20]` observations. Never centered.

| Statistic | min_periods |
| --- | --- |
| mean, median | 1 |
| std, MAD | 2 |

Column names: `{signal}_rolling_{stat}_{window}`.

### 4.4 Trend (trailing only)

`{signal}_trend` is the linear-regression slope over the trailing `max(window_sizes)` observations (default 20). `min_periods = 2`. The first observation is NaN. Future points are not used.

---

## 5. Module-Level Features (Retrospective)

**4 identifier columns + 918 aggregate columns + 7 metadata columns = 929 Parquet columns.**

| Component | Count |
| --- | --- |
| Numeric observation features | 153 |
| Aggregates per feature (`mean`, `median`, `std`, `min`, `max`, `range`) | 6 |
| Aggregate columns | 153 × 6 = 918 |
| Metadata | `observation_count`, `first_timestamp`, `last_timestamp`, `time_span_seconds`, `first_cycle`, `last_cycle`, `cycle_span` (7) |
| Identifiers | `module_id`, `test_id`, `lot_id`, `dataset_id` (4) |
| **Total** | **929** |

Metadata records `feature_designation.module_features_is_retrospective = true`.

Suitable for: post-test module analysis, population comparison, retrospective investigation.  
Not suitable for: online/incremental anomaly detection or any model that must decide at an earlier cycle.

---

## 6. Temperature Normalization

M6 uses the M4 RDS(on) type curve loaded from the declared ModuleProfile typicals (not a second hardcoded physics model):

```text
R_type(Tj) = R_ref + (R_hot - R_ref) * (Tj - T_ref) / (T_hot - T_ref)
RDS_on_normalized = RDS_on_measured / (R_type(Tj) / R_type(T_ref))
```

From `examples/module-profiles/sic-reference-module.json` (M4 default context):

| Parameter | Value |
| --- | --- |
| T_ref | 25°C |
| T_hot | 150°C |
| RDS_on typical at T_ref | 4.5 mOhm |
| RDS_on typical at T_hot | 7.2 mOhm |

At 25°C the factor is 1 (identity). At 150°C the factor is 7.2/4.5 = 1.6 (exact inverse of the M4 map). Missing `RDS_on` or `Tj` yields NaN.

The CLI loads T_ref from `generation-config.json` `temperature_model.t_ref_C` when present, and RDS typicals from the declared ModuleProfile path (default: the reference profile above).

---

## 7. Missingness

Missing telemetry remains missing. Insufficient windows produce NaN (std/MAD need 2 points; trend needs 2 finite points; percent change is NaN if the baseline median is 0 or NaN). No imputation.

---

## 8. Leakage Prevention

- Observation features are causal by registry (`is_causal = true`)
- Rolling and trend windows are trailing (`center=False`)
- Baseline uses only the early-life prefix of each module
- `normalized_cycle_position` uses declared `target_cycles`
- `elapsed_time` uses the first timestamp in cycle order, not min over a mutated future
- Ground-truth fields are forbidden in outputs
- A regression test mutates telemetry after cycle N and requires every observation feature at cycles ≤ N to be unchanged

---

## 9. M5 Integration

| M5 status | M6 behavior |
| --- | --- |
| PASS | process |
| WARNING | process; record warning in feature metadata |
| BLOCKED | refuse processing |

Feature metadata stores only:

- `validation_status`
- `validator_version`
- `validation_timestamp`
- `source_dataset_id`
- `validation_report_reference`

The full M5 report is not duplicated.

---

## 10. Raw Data Immutability

Feature generation does not modify:

- `telemetry.parquet`
- `ground-truth.parquet`
- `dataset.json`
- `generation-config.json`
- `assumptions.json`
- `provenance.json`

Outputs:

```text
ml/datasets/features/<feature_version>/
├── observation-features.parquet
├── module-features.parquet
└── feature-metadata.json
```

---

## 11. Feature Metadata

`feature-metadata.json` includes feature version, source dataset and schema versions, M5 validation metadata, the full registry records, exact feature counts (must match Parquet), identifier columns, signal sets, window/baseline/temperature configuration, causal/retrospective designation, creation timestamp, and provenance.

---

## 12. Feature Validator

`FeatureValidator` checks the generated frames against the registry:

1. Missing expected feature
2. Unexpected feature
3. Duplicate feature
4. Incorrect feature count
5. Incorrect identifier set
6. Forbidden ground-truth field
7. Invalid feature version
8. Invalid cycle ordering
9. Duplicate module/cycle rows
10. Non-causal behavior (future-modification comparison)
11. Metadata mismatch
12. Retrospective metadata mismatch

---

## 13. CLI

```bash
python3 scripts/build_features.py <validated_dataset_dir> [--output-dir ml/datasets/features] [--feature-version v1]
```

---

## 14. Tests

```text
python3 -m pytest -W error
```

**Result: 210 passed, 0 failed, 0 skipped** (M1–M6). M6 tests include registry arithmetic, VF schema invariance, future-modification causality, ground-truth isolation, M4 temperature inverse at 25/87.5/125/150°C, short-trajectory baseline, missingness preservation, BLOCKED refusal, and validator missing/unexpected column detection.

```text
python3 -m compileall -q backend ml
```

Succeeded.

---

## 15. Generated Outputs (verified)

### syn-smoke

| Metric | Value |
| --- | --- |
| Observation rows | 420 |
| Module rows | 20 |
| Observation columns | 160 (7 identifiers + 153 features) |
| Module columns | 929 |
| Runtime | 0.2208 s |
| Validation status | PASS |

### syn-sic-pc-dev-001 (written to `ml/datasets/features/v1/`)

| Metric | Value |
| --- | --- |
| Observation rows | 375750 |
| Module rows | 750 |
| Observation columns | 160 (7 identifiers + 153 features) |
| Module columns | 929 |
| Runtime | 110.3524 s |
| Validation status | PASS |

Parquet schemas match the registry column lists exactly. Metadata `actual_*` counts match the Parquet files.

---

## 16. M1–M5 Compatibility

No M1–M5 contracts were modified. M6 consumes ModuleProfile typicals, TestProfile `target_cycles`, Telemetry observations, M4 temperature type-curve semantics, and M5 validation status.

---

## 17. M6 Status: COMPLETE

| Deliverable | Path |
| --- | --- |
| Feature package | `ml/features/` |
| Registry | `ml/features/definitions.py` |
| Transformer | `ml/features/transform.py` |
| Validator | `ml/features/validation.py` |
| Pipeline / CLI | `ml/features/pipeline.py`, `scripts/build_features.py` |
| Tests | `backend/tests/test_m6_feature_engineering.py` |
| Documentation | `docs/feature-engineering/feature-engineering.md` |

Next milestone is M7 (baseline anomaly detection). Do not use retrospective module aggregates as observation-time inputs.
