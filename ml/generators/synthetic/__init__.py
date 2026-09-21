"""Semi-synthetic SiC power-cycling dataset generator (M4-B).

This package produces development/benchmark telemetry. It is not measured
production data and is not a validated physical reliability model.
"""

from ml.generators.synthetic.config import GENERATOR_VERSION, GenerationConfig, Scenario
from ml.generators.synthetic.generator import generate_dataset

__all__ = ["GENERATOR_VERSION", "GenerationConfig", "Scenario", "generate_dataset"]
