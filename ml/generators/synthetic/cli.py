"""CLI for the M4 synthetic dataset generator."""

from __future__ import annotations

import argparse
from pathlib import Path

from ml.generators.synthetic.config import GENERATOR_VERSION, GenerationConfig, Scenario
from ml.generators.synthetic.generator import generate_from_paths


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a synthetic SmartESS development dataset. "
            "Output is not measured production telemetry."
        )
    )
    parser.add_argument("--dataset-id", default=None)
    parser.add_argument("--scenario", choices=[item.value for item in Scenario], default=Scenario.DEGRADATION_BENCHMARK.value)
    parser.add_argument("--seed", type=int, default=20260921)
    parser.add_argument("--n-modules", type=int, default=None)
    parser.add_argument("--n-lots", type=int, default=None)
    parser.add_argument("--modules-per-lot", type=int, default=None)
    parser.add_argument("--target-cycles", type=int, default=None)
    parser.add_argument("--stride", type=int, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--module-profile", type=Path, default=None)
    parser.add_argument("--test-profile", type=Path, default=None)
    parser.add_argument("--skip-validation", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = _repo_root()
    module_path = args.module_profile or (root / "examples" / "module-profiles" / "sic-reference-module.json")
    test_path = args.test_profile or (root / "examples" / "test-profiles" / "power-cycling-reference.json")
    output_root = args.output_root or (root / "ml" / "datasets" / "synthetic")

    kwargs = {
        "scenario": Scenario(args.scenario),
        "seed": args.seed,
        "generator_version": GENERATOR_VERSION,
    }
    if args.dataset_id:
        kwargs["dataset_id"] = args.dataset_id
    if args.n_modules is not None:
        kwargs["n_modules"] = args.n_modules
    if args.n_lots is not None:
        kwargs["n_lots"] = args.n_lots
    if args.modules_per_lot is not None:
        kwargs["modules_per_lot"] = args.modules_per_lot
    if args.target_cycles is not None:
        kwargs["target_cycles"] = args.target_cycles
    if args.stride is not None:
        kwargs["observation_stride_cycles"] = args.stride

    config = GenerationConfig(**kwargs)
    result = generate_from_paths(
        config,
        module_path,
        test_path,
        output_root,
        run_validation=not args.skip_validation,
    )
    print(f"dataset_id={config.dataset_id}")
    print(f"scenario={config.scenario.value}")
    print(f"path={result.dataset_dir}")
    print(f"modules={result.n_modules} lots={result.n_lots}")
    print(f"telemetry_records={result.n_telemetry_records}")
    print(f"ground_truth_records={result.n_ground_truth_records}")
    print(f"mechanism_counts={result.mechanism_counts}")
    print(f"elapsed_s={result.elapsed_s:.3f}")
    print("This dataset is synthetic and intended for development, benchmarking, and validation of SmartESS analytical pipelines. It is not measured production telemetry.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
