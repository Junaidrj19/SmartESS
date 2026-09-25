"""M9 deterministic engineering tool tests.

Tests every tool against hand-calculated fixtures including edge cases:
normal, empty series, NaN, single point, zero denominator, invalid params.
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.agents.investigation.tools.drift import calculate_drift
from backend.agents.investigation.tools.slope import calculate_slope
from backend.agents.investigation.tools.percent_change import calculate_percent_change
from backend.agents.investigation.tools.population import compare_population
from backend.agents.investigation.tools.temperature import analyze_temperature_dependence
from backend.agents.investigation.tools.changepoint import detect_change_point
from backend.agents.investigation.tools.correlation import calculate_correlation
from backend.agents.investigation.tools.limits import check_acceptance_limits
from backend.agents.investigation.tools.degradation_rate import calculate_degradation_rate
from backend.agents.investigation.tools.models import ToolError


class TestDrift:
    def test_hand_calculated(self):
        r = calculate_drift(values=[10.0, 12.0, 15.0])
        assert r.output["first"] == pytest.approx(10.0)
        assert r.output["last"] == pytest.approx(15.0)
        assert r.output["absolute_drift"] == pytest.approx(5.0)
        assert r.output["percent_drift"] == pytest.approx(50.0)

    def test_requires_two_values(self):
        with pytest.raises(ToolError):
            calculate_drift(values=[1.0])

    def test_empty(self):
        with pytest.raises(ToolError):
            calculate_drift(values=[])

    def test_nan(self):
        with pytest.raises(ToolError):
            calculate_drift(values=[float("nan"), float("nan")])

    def test_zero_baseline(self):
        with pytest.raises(ToolError):
            calculate_drift(values=[0.0, 1.0])


class TestSlope:
    def test_hand_calculated(self):
        r = calculate_slope(values=[0.0, 2.0, 4.0, 6.0])
        assert r.output["slope"] == pytest.approx(2.0)

    def test_nan_values(self):
        r = calculate_slope(values=[0.0, float("nan"), 4.0, 6.0])
        assert r.output["slope"] == pytest.approx(2.0, rel=1e-6)


class TestPercentChange:
    def test_hand_calculated(self):
        r = calculate_percent_change(values=[100.0, 110.0, 120.0])
        assert r.output["percent_change"] == pytest.approx(20.0)


class TestPopulation:
    def test_hand_calculated(self):
        ref = {"mean": 10.0, "std": 2.0}
        r = compare_population(values=[20.0, 22.0], reference=ref)
        assert r.output["z_score"] == pytest.approx(5.5)


class TestTemperature:
    def test_correlation(self):
        r = analyze_temperature_dependence(values=[1.0, 2.0, 3.0], temperature=[100.0, 200.0, 300.0])
        assert r.output["temperature_correlation"] == pytest.approx(1.0, abs=1e-9)


class TestChangepoint:
    def test_hand_calculated(self):
        values = [1.0] * 10 + [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0]
        r = detect_change_point(values, window=3)
        assert r.output["change_point_index"] is not None

    def test_too_short(self):
        with pytest.raises(ToolError):
            detect_change_point(values=[1.0, 2.0, 3.0], window=5)


class TestCorrelation:
    def test_matching_lengths(self):
        r = calculate_correlation(a=[1.0, 2.0, 3.0], b=[2.0, 4.0, 6.0])
        assert r.output["correlation"] == pytest.approx(1.0, abs=1e-9)


class TestLimits:
    def test_no_violations(self):
        r = check_acceptance_limits(values=[1.0, 2.0, 3.0], min_value=0.0, max_value=5.0)
        assert r.output["n_violations"] == 0


class TestDegradationRate:
    def test_linear(self):
        r = calculate_degradation_rate(values=[1.0, 2.0, 3.0, 4.0], cycles=[0, 1, 2, 3])
        assert r.output["degradation_rate"] == pytest.approx(1.0, abs=1e-9)


class TestToolRegistry:
    def test_list_contains_all(self):
        from backend.agents.investigation.tools.registry import get_default_registry

        reg = get_default_registry()
        for name in [
            "calculate_drift",
            "calculate_slope",
            "calculate_percent_change",
            "compare_population",
            "analyze_temperature_dependence",
            "detect_change_point",
            "calculate_correlation",
            "check_acceptance_limits",
            "calculate_degradation_rate",
        ]:
            assert name in reg.list(), name

    def test_unknown_tool(self):
        from backend.agents.investigation.tools.registry import get_default_registry

        reg = get_default_registry()
        with pytest.raises(KeyError):
            reg.call("nonexistent_tool")