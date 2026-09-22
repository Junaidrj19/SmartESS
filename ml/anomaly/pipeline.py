"""Train, score, and evaluate the M7 baseline detector."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from ml.features.definitions import FEATURE_VERSION, FORBIDDEN_FEATURE_COLUMNS

from .aggregate import aggregate_module_summary
from .baseline import compute_statistical_baseline, baseline_config
from .config import AnomalyConfig, DETECTOR_VERSION
from .detector import IsolationForestDetector, fit_isolation_forest
from .evaluate import evaluate_scores, module_score_threshold
from .features import extract_feature_matrix, observation_model_feature_names
from .preprocess import MedianImputer, fit_median_imputer
from .registry import utc_now, write_registry
from .splits import LotSplit, lot_holdout_split, mask_lots

GROUND_TRUTH_RELATIVE = "ground_truth/ground-truth.parquet"


class BlockedFeaturesError(RuntimeError):
    pass


@dataclass
class AnomalyRunResult:
    model_id: str
    model_dir: Path
    record: Dict[str, Any]
    observation_scores: pd.DataFrame
    module_summary: pd.DataFrame
    evaluation: Optional[Dict[str, Any]]


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_feature_bundle(feature_dir: Path) -> tuple[pd.DataFrame, Dict[str, Any]]:
    obs_path = feature_dir / "observation-features.parquet"
    meta_path = feature_dir / "feature-metadata.json"
    if not obs_path.exists():
        raise FileNotFoundError(f"Missing observation features: {obs_path}")
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing feature metadata: {meta_path}")
    metadata = _read_json(meta_path)
    if metadata.get("feature_version") != FEATURE_VERSION:
        raise ValueError(f"Expected feature_version={FEATURE_VERSION}, got {metadata.get('feature_version')}")
    validation = metadata.get("validation_metadata") or {}
    if validation.get("validation_status") == "BLOCKED":
        raise BlockedFeaturesError("Refusing to train on BLOCKED features")
    observation = pd.read_parquet(obs_path)
    leaked = set(observation.columns) & FORBIDDEN_FEATURE_COLUMNS
    if leaked:
        raise ValueError(f"Feature parquet contains forbidden columns: {sorted(leaked)}")
    return observation, metadata


def train_detector(
    observation_features: pd.DataFrame,
    split: LotSplit,
    config: AnomalyConfig,
) -> tuple[IsolationForestDetector, MedianImputer]:
    train_df = mask_lots(observation_features, split.train_lots)
    if train_df.empty:
        raise ValueError("training split is empty")
    matrix = extract_feature_matrix(train_df)
    imputer = fit_median_imputer(matrix)
    x_train = imputer.transform(matrix)
    detector = fit_isolation_forest(x_train, config)
    return detector, imputer


def score_observations(
    observation_features: pd.DataFrame,
    detector: IsolationForestDetector,
    imputer: MedianImputer,
    model_id: str = "",
) -> pd.DataFrame:
    matrix = extract_feature_matrix(observation_features)
    x = imputer.transform(matrix)
    scores = detector.score(x)
    baseline = compute_statistical_baseline(observation_features)

    out = observation_features[
        [
            "module_id",
            "test_id",
            "lot_id",
            "dataset_id",
            "timestamp",
            "cycle_number",
            "observation_index_within_module",
        ]
    ].copy()
    out["anomaly_score"] = scores
    out["is_anomaly"] = detector.predict_is_anomaly(scores)
    out["statistical_baseline_score"] = baseline["statistical_baseline_score"]
    out["statistical_baseline_flag"] = baseline["statistical_baseline_flag"]
    out["detector_version"] = DETECTOR_VERSION
    out["feature_version"] = FEATURE_VERSION
    out["algorithm"] = detector.config.algorithm
    out["model_id"] = model_id
    return out.sort_values(["module_id", "cycle_number"]).reset_index(drop=True)


def evaluate_with_ground_truth(
    observation_scores: pd.DataFrame,
    ground_truth_path: Path,
    *,
    split: LotSplit,
    contamination: float,
) -> Dict[str, Any]:
    gt = pd.read_parquet(ground_truth_path)
    gt["module_id"] = gt["module_id"].astype(str)
    train_scores = observation_scores[observation_scores["module_id"].astype(str).isin(split.train_modules)]
    test_scores = observation_scores[observation_scores["module_id"].astype(str).isin(split.test_modules)]
    train_gt = gt[gt["module_id"].isin(split.train_modules)]
    test_gt = gt[gt["module_id"].isin(split.test_modules)]
    threshold = module_score_threshold(train_scores, contamination)
    return {
        "module_threshold": threshold,
        "module_threshold_rule": "quantile of train-lot max observation scores at 1-contamination",
        "train_lot_eval_not_for_selection": evaluate_scores(
            train_scores, train_gt, split_name="train_lots", module_threshold=threshold
        ),
        "test_lots": evaluate_scores(
            test_scores, test_gt, split_name="test_lots", module_threshold=threshold
        ),
        "ground_truth_path": str(ground_truth_path),
        "ground_truth_used_for_training": False,
    }


def run_anomaly_pipeline(
    feature_dir: str | Path,
    *,
    source_dataset_dir: str | Path | None = None,
    config: AnomalyConfig | None = None,
    evaluate: bool = True,
    write: bool = True,
) -> AnomalyRunResult:
    config = config or AnomalyConfig()
    feature_path = Path(feature_dir)
    observation, feature_meta = load_feature_bundle(feature_path)
    split = lot_holdout_split(
        observation,
        random_state=config.random_state,
        test_lot_fraction=config.test_lot_fraction,
        min_train_lots=config.min_train_lots,
    )
    detector, imputer = train_detector(observation, split, config)

    source_dataset_id = feature_meta.get("source_dataset_id", "unknown")
    model_id = f"iforest-{DETECTOR_VERSION}-{source_dataset_id}-s{config.random_state}"
    scores = score_observations(observation, detector, imputer, model_id=model_id)
    module_summary = aggregate_module_summary(scores)

    evaluation = None
    dataset_dir = Path(source_dataset_dir) if source_dataset_dir is not None else None
    if evaluate:
        if dataset_dir is None:
            raise ValueError("source_dataset_dir is required when evaluate=True")
        gt_path = dataset_dir / GROUND_TRUTH_RELATIVE
        if not gt_path.exists():
            raise FileNotFoundError(f"Ground truth for evaluation not found: {gt_path}")
        evaluation = evaluate_with_ground_truth(
            scores, gt_path, split=split, contamination=config.contamination
        )

    record: Dict[str, Any] = {
        "model_id": model_id,
        "status": "evaluated" if evaluation is not None else "trained",
        "algorithm": config.algorithm,
        "detector_version": DETECTOR_VERSION,
        "feature_version": FEATURE_VERSION,
        "source_dataset_id": source_dataset_id,
        "source_feature_dir": str(feature_path),
        "module_profile_id": (feature_meta.get("generation_metadata") or {}).get("source_dataset_id"),
        "training_timestamp": utc_now(),
        "hyperparameters": {
            "n_estimators": config.n_estimators,
            "contamination": config.contamination,
            "max_samples": config.max_samples,
            "random_state": config.random_state,
        },
        "split": {
            "type": "lot_holdout",
            "train_lots": list(split.train_lots),
            "test_lots": list(split.test_lots),
            "n_train_modules": len(split.train_modules),
            "n_test_modules": len(split.test_modules),
        },
        "preprocessing": imputer.to_dict(),
        "input_features": observation_model_feature_names(),
        "n_input_features": len(observation_model_feature_names()),
        "uses_module_retrospective_features": False,
        "uses_ground_truth_for_training": False,
        "threshold": detector.threshold,
        "statistical_baseline": baseline_config(),
        "validation_metadata": feature_meta.get("validation_metadata"),
        "evaluation": evaluation,
        "limitations": [
            "Isolation Forest is an unlabeled population detector, not a failure-mechanism classifier.",
            "An anomaly is not a confirmed physical failure.",
            "Module-level 929-column retrospective aggregates are not model inputs.",
            "Metrics are split-specific and must not be reported as universal accuracy.",
        ],
    }

    model_dir = Path(config.output_directory) / model_id
    if write:
        write_registry(model_dir, record=record, detector=detector, imputer=imputer)
        scores_dir = Path(config.scores_directory) / model_id
        scores_dir.mkdir(parents=True, exist_ok=True)
        scores.to_parquet(scores_dir / "observation-scores.parquet", index=False)
        module_summary.to_parquet(scores_dir / "module-summary.parquet", index=False)
        if evaluation is not None:
            (scores_dir / "evaluation.json").write_text(
                json.dumps(evaluation, indent=2, default=str) + "\n", encoding="utf-8"
            )
    return AnomalyRunResult(
        model_id=model_id,
        model_dir=model_dir,
        record=record,
        observation_scores=scores,
        module_summary=module_summary,
        evaluation=evaluation,
    )
