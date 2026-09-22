#!/usr/bin/env python3
"""Evaluate the frozen M7 detector against synthetic ground truth.

Usage:

    python3 scripts/evaluate_anomaly.py iforest-v1-syn-sic-pc-dev-001-s20260922

M8 reads the frozen M7 scores + model record and the synthetic dataset ground truth,
computes evaluation metrics, and writes artifacts to
``ml/datasets/evaluation/<model_id>/``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.evaluation import EvaluationConfig, GroundTruthError, run_evaluation


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate the frozen M7 detector against synthetic ground truth (M8)"
    )
    parser.add_argument(
        "model_id",
        type=str,
        nargs="?",
        default=EvaluationConfig().model_id,
        help="M7 model_id (default: %(default)s)",
    )
    parser.add_argument(
        "--dataset-dir",
        type=str,
        default="ml/datasets/synthetic/syn-sic-pc-dev-001",
        help="Dataset directory containing ground_truth/ground-truth.parquet",
    )
    parser.add_argument(
        "--scores-dir",
        type=str,
        default="ml/datasets/scores",
        help="M7 scores directory root",
    )
    parser.add_argument(
        "--models-dir",
        type=str,
        default="ml/models",
        help="M7 models directory root",
    )
    parser.add_argument(
        "--output-root",
        type=str,
        default="ml/datasets/evaluation",
        help="Root directory for M8 evaluation output",
    )
    args = parser.parse_args()

    config = EvaluationConfig(
        model_id=args.model_id,
        scores_dir=args.scores_dir,
        models_dir=args.models_dir,
        output_root=args.output_root,
    )
    dataset_dir = Path(args.dataset_dir)
    if not dataset_dir.exists():
        print(f"Error: dataset directory not found: {dataset_dir}")
        sys.exit(1)

    try:
        result = run_evaluation(dataset_dir, config=config, write=True)
    except (FileNotFoundError, GroundTruthError, ValueError) as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    # Print concise summary.
    s = result.summary
    print(f"model_id: {config.model_id}")
    print(f"output_dir: {result.output_dir}")
    print(f"n_modules: {s.get('n_modules_total')}")
    mm = s.get("module_level_metrics", {})
    print(
        f"module-level: precision={mm.get('precision'):.4f}  "
        f"recall={mm.get('recall'):.4f}  "
        f"F1={mm.get('f1'):.4f}  "
        f"FPR={mm.get('false_positive_rate'):.4f}"
    )
    compat = s.get("m7_test_lot_compatibility") or {}
    compat_m = compat.get("metrics") or {}
    if compat_m:
        print(
            f"m7_test_lot_compatibility (test lots {compat.get('test_lots')}, "
            f"{compat.get('n_modules')} modules): "
            f"precision={compat_m.get('precision'):.4f}  "
            f"recall={compat_m.get('recall'):.4f}  "
            f"F1={compat_m.get('f1'):.4f}  "
            f"FPR={compat_m.get('false_positive_rate'):.4f}"
        )
    t = s.get("timing", {})
    print(
        f"mean lead vs onset: {t.get('mean_lead_vs_onset_cycles')}  "
        f"median lead vs onset: {t.get('median_lead_vs_onset_cycles')}"
    )
    bc = s.get("baseline_comparison", {})
    if_comp = bc.get("isolation_forest", {})
    bs_comp = bc.get("statistical_baseline", {})
    if_m = if_comp.get("metrics", {})
    bs_m = bs_comp.get("metrics", {})
    print(
        f'IF: precision={if_m.get("precision"):.4f}  '
        f'recall={if_m.get("recall"):.4f}  '
        f'F1={if_m.get("f1"):.4f}'
    )
    print(
        f'Baseline: precision={bs_m.get("precision"):.4f}  '
        f'recall={bs_m.get("recall"):.4f}  '
        f'F1={bs_m.get("f1"):.4f}'
    )
    fp = s.get("false_positive_summary", {})
    print(f'false positives: {fp.get("n_false_positives")} / {fp.get("n_healthy_modules")} healthy')
    print(f"artifacts written to {result.output_dir}")


if __name__ == "__main__":
    main()