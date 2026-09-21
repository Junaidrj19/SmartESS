# Synthetic datasets (M4-B)

This directory holds generated **synthetic** SmartESS datasets.

This dataset is synthetic and intended for development, benchmarking, and validation of SmartESS analytical pipelines. It is not measured production telemetry.

Generate:

```text
python3 -m ml.generators.synthetic.cli --help
python3 scripts/generate_synthetic_dataset.py --dataset-id syn-smoke --n-modules 20 --n-lots 2 --modules-per-lot 10 --target-cycles 4000
```

See `docs/data-generation/synthetic-dataset-generator.md`.
