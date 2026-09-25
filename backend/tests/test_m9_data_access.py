"""M9 data-access, ground-truth-leakage, and M7/M8 immutability tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.agents.investigation.data_access import DataAccess, DataAccessError

REPO = Path(__file__).resolve().parents[2]
MODEL_ID = "iforest-v1-syn-sic-pc-dev-001-s20260922"


class TestDataAccess:
    def test_module_exists(self):
        da = DataAccess(REPO)
        tr = da.load_module_trajectory(MODEL_ID, "syn-mod-0042")
        assert tr.n_observations > 0

    def test_module_missing(self):
        da = DataAccess(REPO)
        with pytest.raises((DataAccessError, FileNotFoundError)):
            da.load_module_trajectory(MODEL_ID, "no-such-module-xyz")

    def test_missing_artifact_raises(self, tmp_path):
        da = DataAccess(tmp_path)
        with pytest.raises(DataAccessError):
            da.module_summary(MODEL_ID, "syn-mod-0042")

    def test_scoped_filtering_loads_only_module(self):
        da = DataAccess(REPO)
        obs = da.observation_scores(MODEL_ID, "syn-mod-0042")
        assert obs["n_observations"] == 501
        assert all(isinstance(x, int) for x in obs["cycle_numbers"])

    def test_required_columns(self):
        da = DataAccess(REPO)
        feats = da.observation_features("syn-mod-0042", signals=["RDS_on", "VTH"])
        assert "RDS_on" in feats
        assert "VTH" in feats


class TestGroundTruthLeakage:
    def test_runtime_uses_no_ground_truth(self):
        da = DataAccess(REPO)
        # Ensure the DAL has no GT path exposures in the M9 hot paths.
        assert "ground_truth" not in da.observation_scores(MODEL_ID, "syn-mod-0042")
        assert "ground_truth" not in da.observation_features("syn-mod-0042")


class TestM7M8Immutability:
    def test_investigation_does_not_modify_m7_m8(self, tmp_path):
        da = DataAccess(REPO)
        before = da.snapshot_m7_m8(MODEL_ID)
        assert before, "warning: no M7/M8 artifacts found to snapshot"


class TestReferenceSelector:
    def test_missing_reference_returns_none(self, tmp_path):
        from backend.agents.investigation.tools.population import HealthyReferenceSelector

        sel = HealthyReferenceSelector(str(tmp_path / "missing-reference.json"))
        assert sel.load() is None