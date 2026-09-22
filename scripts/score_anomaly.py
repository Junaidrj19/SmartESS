#!/usr/bin/env python3
"""Score new M6 observation features with an existing registered M7 model.

Does not retrain. Loads detector.joblib + imputer from an existing model directory
and produces observation-scores.parquet and module-summary.parquet.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.anomaly.aggregate import aggregate_module_summary
from ml.anomaly.detector import IsolationForestDetector
from ml.anomaly.pipeline import load_feature_bundle, score_observations
from ml.anomaly.registry import load_registry


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score M6 v1 observation features with an existing registered M7 model"
    )
    parser.add_argument("model_dir", type=str, help="Path to ml/models/<model_id>")
    parser.add_argument("feature_dir", type=str, help="Path to ml/datasets/features/<version>")
    parser.add_argument("--scores-dir", type=str, default=None, help="Output directory (default: ml/datasets/scores/<model_id>)")
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    if not (model_dir / "model-record.json").exists():
        print(f"Error: no model-record.json in {model_dir}")
        sys.exit(1)

    record, detector, imputer = load_registry(model_dir)
    model_id = record.get("model_id", model_dir.name)

    observation, _feature_meta = load_feature_bundle(Path(args.feature_dir))
    scores = score_observations(observation, detector, imputer, model_id=model_id)
    module_summary = aggregate_module_summary(scores)

    if args.scores_dir:
        out_dir = Path(args.scores_dir)
    else:
        out_dir = Path("ml/datasets/scores") / model_id
    out_dir.mkdir(parents=True, exist_ok=True)
    scores.to_parquet(out_dir / "observation-scores.parquet", index=False)
    module_summary.to_parquet(out_dir / "module-summary.parquet", index=False)

    print(f"model_id: {model_id}")
    print(f"feature_version: {record.get('feature_version')}")
    print(f"observation scores: {len(scores)} rows -> {out_dir / 'observation-scores.parquet'}")
    print(f"module summary: {len(module_summary)} rows -> {out_dir / 'module-summary.parquet'}")


if __name__ == "__main__":
    main()
