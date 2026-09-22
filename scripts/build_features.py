#!/usr/bin/env python3
"""CLI for building versioned features from a validated dataset."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.features.definitions import FEATURE_VERSION
from ml.features.pipeline import BlockedDatasetError, build_features_from_dataset


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build ML-ready features from a validated telemetry dataset"
    )
    parser.add_argument("validated_dataset_dir", type=str, help="Path to the validated dataset directory")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="ml/datasets/features",
        help="Output directory for feature datasets (default: ml/datasets/features)",
    )
    parser.add_argument(
        "--feature-version",
        type=str,
        default=FEATURE_VERSION,
        help=f"Feature version to use (default: {FEATURE_VERSION})",
    )
    args = parser.parse_args()

    dataset_path = Path(args.validated_dataset_dir)
    if not dataset_path.exists():
        print(f"Error: Dataset directory '{args.validated_dataset_dir}' does not exist")
        sys.exit(1)

    try:
        result = build_features_from_dataset(
            dataset_path,
            output_dir=args.output_dir,
            feature_version=args.feature_version,
            write=True,
        )
    except BlockedDatasetError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Error building features: {exc}")
        raise

    obs = result.observation_features
    mod = result.module_features
    print("Features written successfully:")
    for key, path in result.output_paths.items():
        print(f"  {key}: {path}")
    print("\nSummary:")
    print(f"  source_dataset_id: {result.metadata['source_dataset_id']}")
    print(f"  feature_version: {result.metadata['feature_version']}")
    print(f"  validation_status: {result.metadata['validation_metadata'].get('validation_status')}")
    print(f"  observation feature rows: {len(obs)}")
    print(f"  module feature rows: {len(mod)}")
    print(f"  observation feature columns: {len(obs.columns)}")
    print(f"  observation feature columns (excluding identifiers): {result.metadata['feature_counts']['observation_feature_columns']}")
    print(f"  module feature columns: {len(mod.columns)}")
    print(f"  runtime_seconds: {result.elapsed_s:.4f}")


if __name__ == "__main__":
    main()
