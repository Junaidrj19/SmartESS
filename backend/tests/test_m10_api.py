"""M10 API tests.

Scope: the additive read-only projection routes. These tests assert that the API
returns the frozen artifact values **verbatim** and never invents one, and that
the LLM API key never appears in a response.

Tests that need artifacts skip cleanly when those artifacts are absent, because
``ml/datasets/`` is gitignored local state (design.md §11.4).
"""

from __future__ import annotations

import json
import math
import warnings

import pytest

# The project suite runs under `-W error`. Importing FastAPI's TestClient emits a
# StarletteDeprecationWarning from inside the library itself, which would abort
# collection. It is suppressed only around this import, so every warning raised
# by SmartESS code is still an error.
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from fastapi.testclient import TestClient

from backend.api import projections as proj
from backend.api.app import app

client = TestClient(app)

MODEL_ID = "iforest-v1-syn-sic-pc-dev-001-s20260922"
MODULE_ID = "syn-mod-0042"

has_model = proj.exists(f"ml/models/{MODEL_ID}/model-record.json")
has_scores = proj.exists(f"ml/datasets/scores/{MODEL_ID}/module-summary.parquet")
has_features = proj.exists("ml/datasets/features/v1/observation-features.parquet")
has_evaluation = proj.exists(f"ml/datasets/evaluation/{MODEL_ID}/evaluation-summary.json")
has_corpus = proj.exists("knowledge_base/metadata/corpus.json")

needs_model = pytest.mark.skipif(not has_model, reason="model artifact absent")
needs_scores = pytest.mark.skipif(not has_scores, reason="score artifacts absent")
needs_features = pytest.mark.skipif(not has_features, reason="feature artifacts absent")
needs_evaluation = pytest.mark.skipif(not has_evaluation, reason="evaluation artifacts absent")
needs_corpus = pytest.mark.skipif(not has_corpus, reason="corpus manifest absent")


# --------------------------------------------------------------- sanitisation


def test_sanitize_maps_nan_and_inf_to_none():
    """NaN must become null, not 0 and not a substituted value."""
    payload = {
        "a": float("nan"),
        "b": float("inf"),
        "c": float("-inf"),
        "d": 1.5,
        "e": [float("nan"), 2],
        "f": {"g": float("nan")},
        "h": "text",
        "i": None,
        "j": True,
    }
    out = proj.sanitize(payload)
    assert out["a"] is None
    assert out["b"] is None
    assert out["c"] is None
    assert out["d"] == 1.5
    assert out["e"] == [None, 2]
    assert out["f"] == {"g": None}
    assert out["h"] == "text"
    assert out["i"] is None
    assert out["j"] is True
    # The result must be strictly JSON-encodable.
    json.dumps(out, allow_nan=False)


def test_sanitize_preserves_zero_and_negative():
    """Zero and negative values are meaningful and must survive untouched."""
    out = proj.sanitize({"zero": 0.0, "neg": -37165.11627906977})
    assert out["zero"] == 0.0
    assert out["neg"] == -37165.11627906977


# --------------------------------------------------------------------- health


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_readiness_reports_artifacts_and_never_leaks_the_api_key():
    r = client.get("/readiness")
    assert r.status_code == 200
    body = r.json()
    assert "artifacts" in body and isinstance(body["artifacts"], list)
    for item in body["artifacts"]:
        assert item["status"] in {"PRESENT", "ABSENT"}
        assert "path" in item and "produced_by" in item

    llm = body["llm"]
    assert llm["status"] in {"READY", "NOT_CONFIGURED"}
    assert "configured" in llm
    # The key must not be present under any spelling, at any depth.
    serialised = json.dumps(body).lower()
    assert "api_key" not in serialised
    assert "apikey" not in serialised
    assert "authorization" not in serialised
    assert "bearer" not in serialised
    assert body["llm"]["inference"] in {"real", "mocked", "not_configured"}
    assert body["status"] in {"READY", "NOT_READY"}


def test_production_missing_llm_refuses_the_investigation(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    for name in ("LLM_API_KEY", "OPENROUTER_API_KEY", "LLM_PROVIDER", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    readiness = client.get("/readiness")
    assert readiness.status_code == 200
    body = readiness.json()
    assert body["llm"]["configured"] is False
    assert body["llm"]["inference"] == "not_configured"
    assert body["llm"]["status"] == "NOT_CONFIGURED"
    assert body["status"] == "NOT_READY"
    assert "llm_not_configured" in body["blockers"]
    serialised = json.dumps(body).lower()
    assert "api_key" not in serialised
    assert "bearer" not in serialised

    created = client.post("/investigations", json={"module_id": MODULE_ID})
    assert created.status_code == 503
    assert "mock" in created.json()["detail"].lower()
    assert "not" in created.json()["detail"].lower()


def test_unknown_route_is_404():
    response = client.get("/does-not-exist")
    assert response.status_code == 404


def test_malformed_investigation_is_422():
    response = client.post("/investigations", json={})
    assert response.status_code == 422


# --------------------------------------------------------------------- models


@needs_model
def test_list_models_matches_the_record_on_disk():
    r = client.get("/models")
    assert r.status_code == 200
    models = r.json()
    assert any(m["model_id"] == MODEL_ID for m in models)

    record = proj.model_record(MODEL_ID)
    listed = next(m for m in models if m["model_id"] == MODEL_ID)
    assert listed["algorithm"] == record["algorithm"]
    assert listed["detector_version"] == record["detector_version"]
    assert listed["feature_version"] == record["feature_version"]
    assert listed["n_input_features"] == record["n_input_features"]
    # Observation threshold is read verbatim, not rounded.
    assert listed["observation_threshold"] == record["threshold"]


@needs_model
def test_get_model_returns_the_record_verbatim():
    r = client.get(f"/models/{MODEL_ID}")
    assert r.status_code == 200
    assert r.json() == proj.sanitize(proj.model_record(MODEL_ID))


def test_unknown_model_is_404_not_500():
    r = client.get("/models/no-such-model")
    assert r.status_code == 404


# -------------------------------------------------------------------- modules


@needs_scores
def test_module_population_counts_match_the_parquet():
    r = client.get("/modules/population")
    assert r.status_code == 200
    body = r.json()
    direct = proj.module_status_counts(MODEL_ID)
    assert body["n_modules"] == direct["n_modules"]
    assert body["by_anomaly_status"] == direct["by_anomaly_status"]
    assert body["by_lot"] == direct["by_lot"]
    # Counts must sum to the population; nothing is dropped or invented.
    assert sum(body["by_anomaly_status"].values()) == body["n_modules"]
    assert sum(body["by_lot"].values()) == body["n_modules"]
    assert "not a failure diagnosis" in body["note"]


@needs_scores
def test_list_modules_paginates_without_changing_values():
    first = client.get("/modules?limit=5&offset=0").json()
    assert first["returned"] == len(first["items"]) <= 5
    assert first["total"] >= first["returned"]

    second = client.get("/modules?limit=5&offset=5").json()
    assert second["offset"] == 5
    ids_first = {i["module_id"] for i in first["items"]}
    ids_second = {i["module_id"] for i in second["items"]}
    assert ids_first.isdisjoint(ids_second)

    # A listed row equals the single-module projection exactly.
    sample = first["items"][0]
    direct = proj.sanitize(proj.module_summary(MODEL_ID, sample["module_id"]))
    assert sample == direct


@needs_scores
@pytest.mark.parametrize("status", ["clean", "sporadic", "persistent"])
def test_anomaly_status_filter_is_exact(status):
    body = client.get(f"/modules?anomaly_status={status}&limit=500").json()
    for item in body["items"]:
        assert item["module_anomaly_status"] == status
    counts = proj.module_status_counts(MODEL_ID)["by_anomaly_status"]
    assert body["total"] == counts.get(status, 0)


@needs_scores
def test_invalid_anomaly_status_is_rejected():
    r = client.get("/modules?anomaly_status=broken")
    assert r.status_code == 422


@needs_scores
def test_module_detail_exposes_split_membership_and_ground_truth_separately():
    r = client.get(f"/modules/{MODULE_ID}")
    assert r.status_code == 200
    body = r.json()

    assert body["module_summary"] == proj.sanitize(proj.module_summary(MODEL_ID, MODULE_ID))
    assert body["data_origin"] == "synthetic"

    split = body["split_membership"]
    assert split["split_type"] == "lot_holdout"
    assert split["in_train_lots"] is not split["in_test_lots"]
    assert split["lot_id"] in split["train_lots"] + split["test_lots"]

    # Ground-truth fields live on module_evaluation, never on module_summary.
    assert "health_state" not in body["module_summary"]
    if body["module_evaluation"]:
        assert "health_state" in body["module_evaluation"]


@needs_scores
def test_unknown_module_is_404_not_500():
    r = client.get("/modules/syn-mod-does-not-exist")
    assert r.status_code == 404


@needs_scores
def test_timing_analysis_note_is_preserved_for_untimed_modules():
    body = client.get(f"/modules/{MODULE_ID}").json()
    timing = body["timing_analysis"]
    if "note" in timing:
        assert timing["note"] == "module not in timing analysis (healthy or undetected)"


# ------------------------------------------------------------------ telemetry


@needs_features
@needs_scores
def test_telemetry_returns_the_eight_baseline_signals_and_never_vf():
    r = client.get(f"/modules/{MODULE_ID}/telemetry")
    assert r.status_code == 200
    body = r.json()
    assert body["signals"] == proj.BASELINE_SIGNALS
    assert "VF" not in body["signals"]
    assert body["downsampled"] is False
    assert body["returned_points"] == body["source_points"]

    point = body["points"][0]
    for key in (
        "cycle_number",
        "anomaly_score",
        "is_anomaly",
        "statistical_baseline_score",
        "statistical_baseline_flag",
    ):
        assert key in point
    assert "higher = more anomalous" in body["score_semantics"]["anomaly_score"]


@needs_features
@needs_scores
def test_telemetry_is_json_compliant_with_no_nan():
    raw = client.get(f"/modules/{MODULE_ID}/telemetry").text
    assert "NaN" not in raw
    assert "Infinity" not in raw


@needs_features
@needs_scores
def test_downsampling_retains_every_flagged_observation():
    full = client.get(f"/modules/{MODULE_ID}/telemetry").json()
    flagged_full = {
        p["cycle_number"]
        for p in full["points"]
        if p["is_anomaly"] or p["statistical_baseline_flag"]
    }

    reduced = client.get(f"/modules/{MODULE_ID}/telemetry?max_points=50").json()
    assert reduced["downsampled"] is True
    assert reduced["downsample_method"] is not None
    assert reduced["returned_points"] < reduced["source_points"]

    flagged_reduced = {
        p["cycle_number"]
        for p in reduced["points"]
        if p["is_anomaly"] or p["statistical_baseline_flag"]
    }
    # This is the guard against a reduced view hiding an anomaly.
    assert flagged_full == flagged_reduced


@needs_features
@needs_scores
def test_downsampled_values_are_not_resampled_or_averaged():
    full = {p["cycle_number"]: p for p in client.get(f"/modules/{MODULE_ID}/telemetry").json()["points"]}
    reduced = client.get(f"/modules/{MODULE_ID}/telemetry?max_points=60").json()["points"]
    for p in reduced:
        assert p == full[p["cycle_number"]]


@needs_features
@needs_scores
def test_cycle_range_filter_bounds_the_series():
    body = client.get(f"/modules/{MODULE_ID}/telemetry?from_cycle=1000&to_cycle=5000").json()
    cycles = [p["cycle_number"] for p in body["points"]]
    assert cycles
    assert min(cycles) >= 1000
    assert max(cycles) <= 5000


@needs_features
@needs_scores
def test_signal_selection_is_honoured():
    body = client.get(f"/modules/{MODULE_ID}/telemetry?signals=RDS_on,VTH").json()
    assert body["signals"] == ["RDS_on", "VTH"]
    assert "IGSS" not in body["points"][0]


# -------------------------------------------------------------------- anomaly


@needs_scores
@needs_model
def test_anomaly_route_separates_the_two_thresholds():
    r = client.get(f"/modules/{MODULE_ID}/anomaly")
    assert r.status_code == 200
    body = r.json()

    record = proj.model_record(MODEL_ID)
    assert body["thresholds"]["observation_threshold"] == record["threshold"]
    if has_evaluation:
        assert body["thresholds"]["module_threshold"] == proj.evaluation_summary(MODEL_ID)["module_threshold"]
        assert body["thresholds"]["observation_threshold"] != body["thresholds"]["module_threshold"]

    assert body["score_semantics"]["direction"] == "higher_is_more_anomalous"
    assert body["score_semantics"]["statistical_baseline_flag_threshold"] == 3.0
    assert body["qualification"] == "Anomaly summary — not a failure diagnosis."


# ----------------------------------------------------------------- evaluation


@needs_evaluation
def test_evaluation_summary_metrics_are_verbatim():
    r = client.get(f"/evaluation/{MODEL_ID}")
    assert r.status_code == 200
    body = r.json()
    disk = proj.evaluation_summary(MODEL_ID)

    assert body["module_level_metrics"] == proj.sanitize(disk["module_level_metrics"])
    assert body["module_threshold"] == disk["module_threshold"]
    # Ground truth is declared as evaluation-only.
    assert body["ground_truth_used_for_training"] is False
    # Both evaluation populations are exposed separately, never blended.
    assert "m7_test_lot_compatibility" in body
    assert body["m7_test_lot_compatibility"]["n_modules"] != body["module_level_metrics"]["n_modules"]


@needs_evaluation
def test_negative_lead_time_is_preserved_not_absolute():
    body = client.get(f"/evaluation/{MODEL_ID}").json()
    mean_lead = body["timing"]["mean_lead_vs_onset_cycles"]
    if mean_lead is not None:
        disk = proj.evaluation_summary(MODEL_ID)["timing"]["mean_lead_vs_onset_cycles"]
        assert mean_lead == disk
        # The dataset's detector fires after onset; the sign must survive.
        assert not math.isclose(mean_lead, abs(mean_lead)) or mean_lead >= 0


@needs_evaluation
def test_evaluation_response_has_no_nan():
    assert "NaN" not in client.get(f"/evaluation/{MODEL_ID}").text


# ------------------------------------------------------------------ knowledge


@needs_corpus
def test_corpus_counts_match_the_manifest_and_only_verified_is_production():
    r = client.get("/corpus")
    assert r.status_code == 200
    body = r.json()
    disk = proj.corpus()
    assert body["n_documents"] == disk["n_documents"]
    assert body["counts_by_verification_status"] == disk["counts_by_verification_status"]
    assert sum(body["counts_by_verification_status"].values()) == body["n_documents"]
    assert "VERIFIED" in body["production_note"]
    assert "collection" in body


@needs_corpus
def test_unknown_corpus_document_is_404():
    assert client.get("/corpus/documents/not-a-document").status_code == 404


# -------------------------------------------- investigations (M10 additions)


def _any_investigation_id() -> str | None:
    items = client.get("/investigations").json()
    return items[0]["investigation_id"] if items else None


def test_investigation_sub_resources_are_consistent_with_the_full_record():
    inv = _any_investigation_id()
    if inv is None:
        pytest.skip("no stored investigations in this environment")

    full = client.get(f"/investigations/{inv}").json()

    det = client.get(f"/investigations/{inv}/deterministic-results").json()
    assert det["n_results"] == len(full["deterministic_results"])

    ev = client.get(f"/investigations/{inv}/evidence").json()
    assert ev["n_records"] == len(full["evidence_records"])
    assert ev["n_queries"] == len(full["evidence_queries"])
    assert ev["evidence_queries"] == full["evidence_queries"]

    prov = client.get(f"/investigations/{inv}/provenance").json()
    assert len(prov["provenance"]) == len(full["provenance"])
    assert prov["errors"] == full["errors"]
    assert prov["limitations"] == full["limitations"]
    assert "artifact_hashes_current" in prov
    assert "not persisted" in prov["artifact_hashes_note"]

    hyp = client.get(f"/investigations/{inv}/hypothesis").json()
    if full.get("hypothesis"):
        assert hyp["hypothesis_id"] == full["hypothesis"]["hypothesis_id"]
        assert len(hyp["candidates"]) == len(full["hypothesis"]["candidates"])
    else:
        assert hyp is None


def test_unknown_investigation_sub_resources_are_404():
    for suffix in ("", "/report", "/provenance", "/deterministic-results", "/evidence", "/hypothesis"):
        r = client.get(f"/investigations/inv-does-not-exist{suffix}")
        assert r.status_code == 404, suffix


def test_investigation_request_shape_is_unchanged():
    """M10 must not alter the existing POST contract (design.md §18.1)."""
    from backend.api.investigations import InvestigationRequest

    fields = InvestigationRequest.model_fields
    assert set(fields) == {"module_id", "model_id", "dataset_id", "max_evidence"}
    assert fields["model_id"].default == MODEL_ID
    assert fields["dataset_id"].default == "syn-sic-pc-dev-001"
    assert fields["max_evidence"].default == 5


def test_unknown_module_post_is_404_not_500():
    """A bad module id is a client error, so the UI can distinguish it."""
    if not has_scores:
        pytest.skip("score artifacts absent")
    r = client.post("/investigations", json={"module_id": "syn-mod-does-not-exist"})
    assert r.status_code == 404


# ------------------------------------------------------------- no fabrication


@needs_scores
def test_no_route_invents_a_module_count():
    """The population count must equal the parquet row count exactly."""
    import pyarrow.parquet as pq

    path = proj._require(f"ml/datasets/scores/{MODEL_ID}/module-summary.parquet")
    expected = pq.ParquetFile(path).metadata.num_rows
    assert client.get("/modules/population").json()["n_modules"] == expected
    assert client.get("/modules?limit=1").json()["total"] == expected
