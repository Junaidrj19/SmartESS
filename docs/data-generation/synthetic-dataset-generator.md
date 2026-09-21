# Synthetic Dataset Generator (M4-B)

This dataset is synthetic and intended for development, benchmarking, and validation of SmartESS analytical pipelines. It is not measured production telemetry.

The generator implements `docs/data-generation/synthetic-dataset-specification.md`. It is **not** a validated physical reliability model, not manufacturer data, and not a lifetime predictor.

## How to run

From the repository root (after `pip install -e ".[dev]"`):

```text
python3 -m ml.generators.synthetic.cli \
  --scenario degradation_benchmark \
  --seed 20260921 \
  --dataset-id syn-sic-pc-dev-001
```

Smoke (small) run:

```text
python3 scripts/generate_synthetic_dataset.py \
  --dataset-id syn-smoke \
  --n-modules 20 \
  --n-lots 2 \
  --modules-per-lot 10 \
  --target-cycles 4000 \
  --stride 200 \
  --seed 11
```

Default profiles:

- `examples/module-profiles/sic-reference-module.json` (illustrative 1200 V SiC half-bridge)
- `examples/test-profiles/power-cycling-reference.json` (illustrative power cycling)

`--target-cycles` and `--stride` control **dataset observation cadence**. They do not replace TestProfile electrical/thermal setpoints. TestProfile `sampling_interval_s` is not the dataset stride.

## GenerationConfig

Pydantic model: `ml/generators/synthetic/config.py`.

Controls population size, lots, scenario, seed, mix, onset, mechanism amplitudes, manufacturing/stress/sensor σ, and data-quality rates. It does **not** duplicate VDS/ID/Tj windows; those are read from TestProfile.

Invalid configs fail with validation errors (mix must sum to 1, `n_modules == n_lots * modules_per_lot`, non-negative σ, UTC `t0`, known channels).

Development defaults (not prevalence, not factory volume): 750 modules, 5 lots × 150, 100,000 cycles, stride 200, mix 70/10/10/10 for `degradation_benchmark`.

## Scenarios

| Scenario | Intent |
| --- | --- |
| `clean_healthy` | Only healthy modules; Gaussian noise/bias; no quality defects |
| `degradation_benchmark` | Healthy + three simulation mechanism categories; clean measurements |
| `data_quality_stress` | Same mix intent plus missing/invalid/spikes/duplicates/time jumps |

Each run is independently seedable.

## Output

```text
ml/datasets/synthetic/<dataset_id>/
  metadata/dataset.json
  metadata/generation-config.json
  metadata/assumptions.json
  telemetry/telemetry.parquet
  ground_truth/ground-truth.parquet
  provenance/provenance.json
```

Parquet is required (pyarrow). The generator will not fall back to CSV.

Telemetry is a wide table that reconstructs to M3 `TelemetryRecord` (see `ml/generators/synthetic/validation.py`). Every row has `data_origin=synthetic`. Ground-truth mechanism fields are not telemetry columns.

## Reproducibility

`numpy.random.Generator` with `seed`. Spawn policy: root → population / healthy / sensor / quality / extra; lots spawned from the population stream so adding a later lot does not reshuffle earlier lots.

Identical ModuleProfile + TestProfile + GenerationConfig + seed + generator version (`1.0.0`) → identical telemetry and ground-truth tables. `generation_timestamp` in metadata may differ between wall-clock runs.

## Degradation categories

Simulation categories, **not** field prevalence and **not** diagnoses:

1. `healthy`
2. `bond_wire_interconnect` — T_ref RDS residual; VDS(on) and conduction loss follow Ohm / I²R approximations
3. `die_attach_thermal_path` — Rth increase and Tj–Tc gap; RDS at T_ref stays near baseline
4. `gate_related` — VTH shift + IGSS, weaker IDSS; power-cycling gate signatures are a simulation choice and may be revised

v1: one primary mechanism per degrading module. Progressive power-law damage after a per-module onset; heterogeneous `rate_scale`.

## Sensor model

Latent state + Gaussian noise + per-module bias; optional drift/quantization. Quality defects only in `data_quality_stress`. Missing → `status=missing` and no numeric value (never 0). No NaN/Inf.

## Ground truth

Separate parquet for evaluation (onset, stage cycles, severity, mechanism). **Not** an anomaly-detection input feature. Do not row-split telemetry for train/test; split by module or lot later.

## Provenance

Dataset JSON records seed, versions, profile hashes, schema versions, scenario, mechanism counts, and `data_origin=synthetic`. `source_references` is empty until verified evidence is ingested.

## Assumptions and limitations

See `metadata/assumptions.json` (classes A–E). Linear RDS(T), lumped Rth, power-law damage, and all σ / mix / onset windows are labeled approximations or simulation knobs. Illustrative profile numbers are placeholders.

## Validation

`validate_generated_dataset` checks M3 reconstructability (sampled records), UTC timestamps, id consistency, synthetic origin, finite values, missingness semantics, mix, onset ordering, and clean-scenario monotonic cycles.

## Example (Python)

```python
from pathlib import Path
from ml.generators.synthetic.config import GenerationConfig, Scenario
from ml.generators.synthetic.generator import generate_from_paths

config = GenerationConfig(
    dataset_id="syn-example",
    scenario=Scenario.CLEAN_HEALTHY,
    seed=1,
    n_modules=10,
    n_lots=2,
    modules_per_lot=5,
    target_cycles=2000,
)
generate_from_paths(
    config,
    Path("examples/module-profiles/sic-reference-module.json"),
    Path("examples/test-profiles/power-cycling-reference.json"),
    Path("ml/datasets/synthetic"),
)
```
