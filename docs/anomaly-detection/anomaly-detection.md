# Baseline Anomaly Detection (M7)

**Status:** COMPLETE  
**Detector version:** v1  
**Algorithm:** Isolation Forest (unsupervised) + Statistical Baseline (deterministic)  
**Consumes:** M6 feature version `v1` observation features only

---

## 1. Purpose

M7 learns a **population normality** model from unlabeled observation-level features and scores each observation for behavioral anomaly.

It does **not**:

- classify failure mechanisms
- use ground truth as a training feature or training-set filter
- use retrospective module-level aggregates (929 columns) as observation-time inputs
- certify, reject, or release components
- claim universal accuracy

An anomaly is not a confirmed physical failure. Datasheet compliance is a separate finding from population/trajectory abnormality.

---

## 2. Inputs

| Input | Role |
| --- | --- |
| `ml/datasets/features/v1/observation-features.parquet` | Model matrix (153 v1 observation features + identifiers) |
| `feature-metadata.json` | Feature version, M5 validation status |
| `ground_truth/ground-truth.parquet` | **Evaluation only**, loaded after training |

M5 `BLOCKED` features are refused. `WARNING` and `PASS` may be trained; status is copied into the model record.

---

## 3. Splits

Splits are **lot-level**. Entire modules stay in one side. Telemetry rows are never randomly split.

Default: hold out `test_lot_fraction = 0.4` of lots, seeded.

---

## 4. Training

1. Select observation feature columns from the M6 v1 registry: the complete **153-column** observation model matrix.
2. Fit a median imputer on the **train lots only**. All-NaN columns (for example unused VF) are recorded and filled with 0.0 for the model matrix only. M6 parquet files are not modified.

> **Model matrix is the full 153-column M6 observation contract.** The four temporal-position
> columns of the v1 observation schema — `normalized_cycle_position`, `elapsed_time`,
> `observation_index`, `cycle_delta` — are **retained as model features**. They are not treated
> as identifiers and are not excluded from the Isolation Forest matrix. They are kept because they
> are already part of the frozen, causal M6 observation feature contract (M6 is the source of
> truth and is not modified by M7); they describe within-module temporal position and are
> consumed just like any other model feature. M7 does not introduce a 149-feature contract.
3. Fit `sklearn.ensemble.IsolationForest` with `contamination=0.10`, `n_estimators=100`, `random_state` recorded.
4. Threshold = train-score quantile at `1 - contamination`. Higher `anomaly_score` means more anomalous.

Ground-truth `health_state` / `degradation_mechanism` / `onset_cycle` are not passed to `fit()`.

---

## 5. Scoring

Each observation receives:

- `anomaly_score` — inverted Isolation Forest decision function (higher = more anomalous)
- `is_anomaly` — `anomaly_score >= threshold`
- `statistical_baseline_score` — `max(abs(robust_normalized_deviation))` across 8 core signals
- `statistical_baseline_flag` — `statistical_baseline_score >= 3.0`
- `detector_version`, `feature_version`, `algorithm`, `model_id`

The statistical baseline is deterministic: same input always produces the same score and flag.
It uses the 8 M6 robust-normalized-deviation features (RDS_on, VTH, IGSS, IDSS, VDS_on,
electrical_power, Tj, Tc). No ML model is involved.

Scoring a module at cycle N uses only that observation's (imputed) features and the frozen model.
Future observations of the same module do not change earlier scores.

Observation output columns:

```
module_id
test_id
lot_id
dataset_id
timestamp
cycle_number
observation_index_within_module
anomaly_score
is_anomaly
statistical_baseline_score
statistical_baseline_flag
detector_version
feature_version
algorithm
model_id
```

Module-level detection for evaluation uses the **maximum** causal observation score on the module,
compared with a threshold calibrated on **train-lot** module maxima (`quantile` at `1 - contamination`).
That summary is not a training feature.

---

## 6. Evaluation

Held-out lots are scored, then compared to ground truth **at module level**:

- precision, recall, F1
- false-positive rate, false-negative rate
- lead time vs `onset_cycle` and vs `cycle_measurable` (positive = earlier than the reference cycle)

Metrics are for the evaluated synthetic split only.

---

## 7. Module Summary

`aggregate_module_summary()` produces one row per module with:

| Column | Description |
| --- | --- |
| module_id, test_id, lot_id, dataset_id | Identifiers |
| n_observations | Number of observations |
| n_anomalous_observations | Sum of is_anomaly |
| anomaly_rate | n_anomalous / n_observations |
| max_anomaly_score | Maximum observation anomaly score |
| mean_anomaly_score | Mean observation anomaly score |
| first_anomalous_cycle | First cycle with is_anomaly=True |
| last_anomalous_cycle | Last cycle with is_anomaly=True |
| anomalous_cycle_span | last - first |
| statistical_baseline_max | Maximum statistical baseline score |
| statistical_baseline_flag_rate | Mean of statistical_baseline_flag |
| module_anomaly_status | clean / sporadic / persistent |

Module status classification:

- **clean**: 0 flagged observations
- **sporadic**: anomaly_rate < 0.1
- **persistent**: anomaly_rate >= 0.1

This is a descriptive anomaly summary. It is NOT a failure diagnosis.

---

## 8. Registry

```text
ml/models/<model_id>/
├── detector.joblib
└── model-record.json

ml/datasets/scores/<model_id>/
├── observation-scores.parquet
├── module-summary.parquet
└── evaluation.json
```

The record stores algorithm, hyperparameters, feature version, dataset id, split lots,
preprocessing, statistical baseline configuration, threshold, evaluation, and limitations.

---

## 9. CLI

Train and evaluate:

```bash
python3 scripts/train_anomaly_model.py ml/datasets/features/v1 \
  --dataset-dir ml/datasets/synthetic/syn-sic-pc-dev-001
```

Train without evaluation (does not load ground truth):

```bash
python3 scripts/train_anomaly_model.py ml/datasets/features/v1 --no-eval
```

Score new features with an existing model:

```bash
python3 scripts/score_anomaly.py ml/models/iforest-v1-<dataset>-s<seed> \
  ml/datasets/features/v1/
```

---

## 10. Tests

`backend/tests/test_m7_anomaly_detection.py` covers:

- lot-split isolation
- forbidden columns
- BLOCKED refusal
- ground-truth isolation during training
- refusal to load `module-features.parquet`
- registry write
- prefix-score stability
- statistical baseline score calculation and direction
- statistical baseline threshold at 3.0
- deterministic output
- module aggregation and status
- score semantics (higher = more anomalous)
- threshold determinism
- end-to-end M6 → M7 execution
- contamination configuration edge cases
- clean-healthy scenario behavior

Full suite: `python3 -m pytest -W error` — all M1-M7 tests pass.

---

## 11. M1–M6 compatibility

No M1–M6 contracts were modified. M6 feature parquet remains immutable.
M7 is not a degradation-rate model (later milestone) and not an investigation engine.