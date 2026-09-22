#!/usr/bin/env python3
"""Train and evaluate the M7 Isolation Forest baseline on v1 observation features."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.anomaly import AnomalyConfig, BlockedFeaturesError, run_anomaly_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train an unsupervised Isolation Forest on M6 v1 observation features"
    )
    parser.add_argument("feature_dir", type=str, help="Path to ml/datasets/features/v1")
    parser.add_argument(
        "--dataset-dir",
        type=str,
        default=None,
        help="Source dataset directory (required for evaluation / ground-truth load)",
    )
    parser.add_argument("--output-dir", type=str, default="ml/models")
    parser.add_argument("--scores-dir", type=str, default="ml/datasets/scores")
    parser.add_argument("--seed", type=int, default=20260922)
    parser.add_argument("--no-eval", action="store_true", help="Train and score without loading ground truth")
    args = parser.parse_args()

    evaluate = not args.no_eval
    if evaluate and not args.dataset_dir:
        print("Error: --dataset-dir is required unless --no-eval is set")
        sys.exit(1)

    config = AnomalyConfig(
        random_state=args.seed,
        output_directory=args.output_dir,
        scores_directory=args.scores_dir,
    )
    try:
        result = run_anomaly_pipeline(
            args.feature_dir,
            source_dataset_dir=args.dataset_dir,
            config=config,
            evaluate=evaluate,
            write=True,
        )
    except BlockedFeaturesError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    print(f"model_id: {result.model_id}")
    print(f"model_dir: {result.model_dir}")
    print(f"observation scores: {len(result.observation_scores)}")
    print(f"module summary: {len(result.module_summary)} rows")
    print(f"threshold: {result.record['threshold']}")
    if result.evaluation:
        test = result.evaluation["test_lots"]["metrics"]
        print("held-out lot metrics (module-level, not a universal claim):")
        for key in ("n_modules", "precision", "recall", "f1", "false_positive_rate"):
            print(f"  {key}: {test.get(key)}")
        print("limitations:")
        for line in result.record["limitations"]:
            print(f"  - {line}")


if __name__ == "__main__":
    main()
