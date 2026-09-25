# SmartESS

Configurable agentic reliability-intelligence platform for SiC MOSFET power modules used in EV power electronics.

SmartESS detects abnormal degradation during reliability testing, runs deterministic engineering analysis on frozen ML artifacts, retrieves supporting evidence from a curated knowledge base, and produces traceable engineering reports with candidate failure mechanisms. The system assists engineers; it does not certify, reject, or release components.

**Current milestone:** M9 — Multi-Agent Investigation Engine (implemented and validated)

---

## Overview

SmartESS is organized as a milestone-driven data and ML pipeline (M1–M8) with an agentic investigation layer (M9) on top. The repository contains:

- Versioned domain contracts (Module Profile, Test Profile, Telemetry)
- A deterministic synthetic dataset generator and validation engine
- A versioned observation-feature contract and Isolation Forest anomaly detector
- An evaluation-only layer over frozen M7 artifacts
- A LangGraph-orchestrated multi-agent investigation engine with RAG

The primary output is a structured engineering investigation report with provenance, uncertainty, and human review as the final decision point.

**Product naming note:** Design documents (`PRD.md`, `architecture.md`, `agent-rules.md`) use *BurnInGuard AI*; the repository, package name, and `tech-stack.md` use *SmartESS*. They describe the same product.

---

## Problem Context

EV power modules operate under electrical, thermal, and mechanical stress. Reliability tests collect electrical and thermal measurements over time. Simple limit checks can miss gradual degradation while values remain within specification.

Relevant indicators include RDS(on), Vth, IGSS, IDSS, VDS(on), Tj, Tc, and thermal resistance. Abnormal trajectories may provide earlier warning than absolute limit violations, but a signal change does not uniquely identify a physical failure mechanism.

SmartESS addresses four engineering questions:

1. Is the module behaving abnormally before conventional limits are violated?
2. What quantitative evidence supports the observed anomaly?
3. Which failure mechanisms are plausible candidates?
4. What should an engineer investigate next?

---

## What SmartESS Does

| Capability | Status |
| --- | --- |
| Module Profile / Test Profile / Telemetry contracts (M1–M3) | Implemented |
| Synthetic dataset generation and validation (M4–M5) | Implemented |
| Versioned observation features (M6) | Implemented |
| Unsupervised anomaly detection (M7) | Implemented (frozen artifacts) |
| Offline model evaluation (M8) | Implemented (evaluation-only) |
| Multi-agent investigation with RAG (M9) | Implemented |
| Engineering knowledge base + ChromaDB retrieval | Implemented (partial corpus) |
| FastAPI investigation endpoint | Minimal (`/investigations`, `/health`) |
| Frontend UI | Not implemented (placeholder directory) |
| SQLAlchemy persistence / Clerk auth | Not implemented |
| Hardware integration / RUL / RL | Not in scope |

---

## System Architecture

Logical layers (from `architecture.md`):

```text
Module Profile + Test Profile + Telemetry
        ↓
Data Validation (M5) → Feature Engineering (M6)
        ↓
Anomaly Detection (M7, frozen) → Evaluation (M8, frozen)
        ↓
Investigation Engine (M9)
        ├── Deterministic engineering tools
        ├── ChromaDB evidence retrieval (RAG)
        ├── LLM hypothesis generation (Llama 3.3 70B via OpenRouter)
        └── Deterministic report synthesis
        ↓
Engineering Report → Engineer Review
```

M9 does not modify M7 or M8 artifacts. M7/M8 immutability is verified via hash snapshots at investigation time.

---

## End-to-End Data Flow

```text
1. Configure module and test context (M1 ModuleProfile, M2 TestProfile)
2. Define telemetry contract (M3 TelemetryRecord)
3. Generate or ingest labeled-synthetic dataset (M4)
4. Validate dataset quality → PASS / WARNING / BLOCKED (M5)
5. Build versioned observation features (M6 v1)
6. Train Isolation Forest on observation features; score modules (M7)
7. Evaluate frozen M7 artifacts against ground truth offline (M8)
8. Investigate an anomalous module (M9):
      M6/M7/M8 artifacts (read-only)
      → deterministic tools
      → evidence retrieval
      → hypothesis generation
      → report synthesis
9. Engineer reviews report and decides next steps
```

**Ground Truth boundary:** Ground truth (`ground_truth/ground-truth.parquet`) is used for M4 dataset generation and M8 offline evaluation only. The M9 runtime investigation pipeline does not read ground truth. Investigation operates on telemetry/features, M7 outputs, M8 outputs, deterministic findings, retrieved evidence, and LLM reasoning.

---

## Milestone Progression

### M1 — Module Profile

**Purpose:** Central versioned configuration object defining component identity, electrical/thermal specifications, health parameters, acceptance criteria, and provenance.

**Implementation:** Pydantic domain model (`backend/domain/module_profiles/`), JSON Schema (`schemas/sic-module-profile.schema.json`), validation, tests, and example profile.

**Feeds M2–M9:** Defines which parameters are available and critical for a given module type.

### M2 — Test Profile

**Purpose:** Defines how the module is stressed (power cycling, HTOL, HTGB, HTRB, etc.).

**Implementation:** Pydantic domain model (`backend/domain/test_profiles/`), JSON Schema (`schemas/test-profile.schema.json`), validation, tests, and example profile.

**Feeds M3–M9:** Provides test context for telemetry interpretation and investigation.

### M3 — Telemetry Data Contract

**Purpose:** Time-series observations over a module's stress history.

**Implementation:** `TelemetryRecord` Pydantic model (`backend/domain/telemetry/`), JSON Schema (`schemas/telemetry.schema.json`), validation, tests, and example.

**Feeds M4–M9:** Canonical telemetry shape for generation, features, and investigation.

### M4 — Synthetic Dataset Specification and Generator

**Purpose:** Deterministic staged synthetic reliability-data generation for SiC MOSFET power-module degradation scenarios.

**Implementation:**
- M4-A specification: `docs/data-generation/synthetic-dataset-specification.md`
- M4-B generator: `ml/generators/synthetic/`
- CLI: `python3 -m ml.generators.synthetic.cli` or `scripts/generate_synthetic_dataset.py`

Default dataset `syn-sic-pc-dev-001`: 750 modules, 5 lots, 375,750 telemetry rows. Artifacts are labeled `data_origin=synthetic` and are not production telemetry. Ground truth is emitted separately as `ground_truth/ground-truth.parquet`.

**Feeds M5:** Generated artifacts are validated before feature engineering.

### M5 — Validation Engine

**Purpose:** Independent dataset validation classifying datasets as `PASS`, `WARNING`, or `BLOCKED`.

**Implementation:** `ml/validators/synthetic/`, CLI (`scripts/validate_synthetic_dataset.py`), JSON/Markdown reports under `<dataset>/validation/`.

**Feeds M6:** Only validated datasets enter feature engineering. `BLOCKED` datasets are refused.

### M6 — Observation Feature Contract

**Purpose:** Deterministic, versioned, causal, leakage-safe feature contract for M7 consumption.

**Implementation:** `ml/features/` with authoritative registry in `ml/features/definitions.py`. CLI: `scripts/build_features.py`.

**v1 observation dataset** (`ml/datasets/features/v1/` on `syn-sic-pc-dev-001`):

| Dimension | Value |
| --- | --- |
| Observation rows | 375,750 |
| Module rows | 750 |
| Observation columns | 160 (7 identifiers + 153 features) |
| Module columns | 929 (4 identifiers + 7 metadata + 918 aggregates) |

**Identifier fields:** `module_id`, `test_id`, `lot_id`, `dataset_id`, `timestamp`, `cycle_number`, `observation_index_within_module`

**Core reliability signals** (baseline/rolling set): `RDS_on`, `VTH`, `IGSS`, `IDSS`, `VDS_on`, `electrical_power`, `Tj`, `Tc`

| Signal | Role in pipeline |
| --- | --- |
| `RDS_on` | On-resistance; primary interconnect/channel degradation indicator |
| `VTH` | Threshold voltage; gate-related stress indicator |
| `IGSS` | Gate-source leakage; gate-oxide stress indicator |
| `IDSS` | Drain-source leakage |
| `VDS_on` | On-state voltage |
| `electrical_power` | Electrical stress proxy |
| `Tj` | Junction temperature |
| `Tc` | Case temperature |

`VF` is a v1 electrical passthrough only and is not in the baseline/rolling signal set. Module-level aggregates (929 columns) are retrospective and must not be used as observation-time model inputs.

**Feeds M7:** Observation features are the sole M7 model matrix.

### M7 — Anomaly Detection

**Purpose:** Unsupervised population-normality detection. Identifies anomalous behavior; does **not** establish a physical failure mechanism.

**Implementation:** `ml/anomaly/` — Isolation Forest on M6 v1 observation features with lot-level holdout. CLI: `scripts/train_anomaly_model.py`, `scripts/score_anomaly.py`.

**What M7 produces:**
- Observation-level `anomaly_score` and `is_anomaly` flags
- Module-level summary aggregates (`module-summary.parquet`)
- Frozen model artifacts under `ml/models/<model_id>/`
- Scores under `ml/datasets/scores/<model_id>/`
- Deterministic statistical baseline score alongside ML score

**Canonical model:** `iforest-v1-syn-sic-pc-dev-001-s20260922`

Held-out test lots (`lot-01`, `lot-04`, 300 modules): precision 0.8776, recall 0.4778, F1 0.6187, FPR 0.0286. These are split-specific metrics, not universal accuracy claims.

Ground truth is evaluation-only and is not passed to `fit()`.

**Feeds M8 and M9:** Frozen scores and model record are consumed read-only.

### M8 — Evaluation Layer

**Purpose:** Offline validation of frozen M7 artifacts. M8 never retrains, never changes thresholds, and writes exclusively under `ml/datasets/evaluation/`.

**Implementation:** `ml/evaluation/`, CLI: `scripts/evaluate_anomaly.py`.

**Evaluation views:**
- `overall_population` — all 750 modules
- `m7_test_lot_compatibility` — held-out lots `lot-01`, `lot-04` (regression gate reproducing M7 metrics)

**Artifacts:** `evaluation-summary.json`, `module-evaluation.parquet`, `timing-analysis.json`, `baseline-comparison.json`

**Feeds M9:** Module evaluation, timing, and baseline comparison are loaded read-only during investigation.

### M9 — Multi-Agent Investigation Engine

**Purpose:** Agentic investigation layer that combines deterministic engineering analysis, evidence retrieval, LLM hypothesis generation, and structured report synthesis.

**Implementation:**
- Agents: `backend/agents/investigation/`
- LangGraph orchestrator: `backend/agents/investigation/orchestrator.py`
- Deterministic tools: `backend/agents/investigation/tools/`
- Knowledge base / RAG: `backend/knowledge/`
- LLM abstraction: `backend/llm/`
- CLI: `scripts/investigate.py`
- FastAPI: `backend/api/investigations.py`
- Outputs: `ml/datasets/investigations/<investigation_id>/`

---

## M9 Multi-Agent Architecture

M9 is not a single LLM call. A LangGraph supervisor controls execution order, shared state, agent-to-agent information flow, validation gates, conditional routing, bounded retries, and failure handling.

### Graph topology

```text
START
  → load_investigation
  → investigation_agent
  → evidence_agent
  → hypothesis_agent
  → hypothesis_validation
      ├─ (pass) → report_agent
      ├─ (unknown evidence id, evidence rounds < 2) → evidence_agent
      ├─ (fail, hypothesis retries < 2) → hypothesis_agent
      └─ (exhausted retries) → report_agent
  → report_validation
      ├─ (pass) → END
      ├─ (fail, report retries < 2) → report_agent
      └─ (exhausted retries) → END
```

**Validation gates:**
- `hypothesis_validation` rejects unresolved evidence citations, candidates without supporting evidence, and empty hypothesis sets. Rejection reasons are fed back on retry.
- `report_validation` rejects missing sections, unresolved citations, mechanisms asserted as `CONFIRMED`, empty narratives, unwarranted-certainty phrasing, and incomplete provenance.

**Retry bounds:** `MAX_EVIDENCE_ROUNDS = 2`, `MAX_HYPOTHESIS_RETRIES = 2`, `MAX_REPORT_RETRIES = 2`

### Shared investigation state

`InvestigationState` (`backend/agents/investigation/state.py`) carries module trajectory, M7/M8 summaries, deterministic results, evidence records, hypothesis, report, provenance, retry counts, errors, and limitations across all graph nodes.

### The four agents

#### InvestigationAgent

- Loads scoped M6/M7/M8 information via `DataAccess`
- Runs nine deterministic engineering tools on module trajectory signals
- Optionally compares against a healthy reference population
- Produces structured `DeterministicResult` objects
- Does not invent numerical results

#### EvidenceAgent

- Constructs evidence queries from actual investigation findings (signal magnitudes, tool outputs)
- Retrieves engineering evidence from ChromaDB collection `evidence`
- Returns structured `EvidenceRecord` objects with full provenance
- Does not fabricate sources

#### HypothesisAgent

- Receives deterministic findings and retrieved evidence
- Uses `meta-llama/llama-3.3-70b-instruct` through OpenRouter (or `MockLLMClient` when `LLM_PROVIDER`/`LLM_API_KEY` are unset)
- Generates candidate degradation mechanisms with uncertainty
- Includes supporting and contradictory evidence references
- Does not treat a signal as proof of physical failure

#### ReportAgent

- Synthesizes validated findings, evidence, and hypotheses into a structured report
- Deterministic synthesis — recalculates nothing, invents no measurements
- Preserves provenance, uncertainty, and limitations
- Maintains human engineering review as the final decision point

---

## Deterministic Engineering Analysis

Numerical engineering calculations are deterministic Python operations. The LLM interprets those results; it is not trusted to invent numerical calculations.

**Registered tools** (`backend/agents/investigation/tools/registry.py`):

| Tool | Purpose |
| --- | --- |
| `calculate_drift` | Drift from baseline over a signal trajectory |
| `calculate_slope` | Linear-regression slope over a signal |
| `calculate_percent_change` | Percent change from baseline |
| `compare_population` | Compare module signal against healthy reference population |
| `analyze_temperature_dependence` | Temperature dependence of electrical parameters |
| `detect_change_point` | Change-point detection in a signal |
| `calculate_correlation` | Cross-signal correlation |
| `check_acceptance_limits` | Check signals against module acceptance limits |
| `calculate_degradation_rate` | Degradation rate per cycle |

Healthy reference: `ml/datasets/investigations/reference/healthy-reference.json` (built by `scripts/build_healthy_reference.py` from M7 un-flagged modules, independent of ground truth).

---

## Engineering Knowledge Base

Curated engineering evidence corpus for M9 hypothesis support. Located at `knowledge_base/`. See `knowledge_base/README.md` for full rules.

### Current corpus (verified 2026-09-24)

| Metric | Value |
| --- | --- |
| Corpus version | `1.0.0` |
| Manifest entries | 37 |
| Production (`VERIFIED`) documents | 19 |
| ChromaDB collection | `evidence` |
| ChromaDB chunks | 360 |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |

**Source-type distribution (production):** 1 standard, 12 manufacturer documents, 4 peer-reviewed papers, 2 reviews.

**Mechanism coverage** (declared from document content, not inferred from titles):
- Bond-wire / interconnect degradation
- Die-attach and thermal-path degradation
- Gate-related degradation
- Package / interconnect effects
- Thermal behavior
- Cross-cutting reliability mechanisms

**Observable coverage** includes `RDS_on`, `VTH`, `IGSS`, `IDSS`, `VDS_on`, `electrical_power`, `Tj`, `Tc`, and `thermal_resistance` where supported by verified documents. No single observable maps uniquely to one physical failure mechanism.

Only `VERIFIED` documents enter the production ChromaDB collection. Paywalled or blocked sources are recorded as `NEEDS_MANUAL_ACCESS` with official URLs; access controls are never bypassed.

---

## RAG and Evidence Provenance

Retrieval (`backend/knowledge/retrieval.py`) is provenance-preserving. Each `EvidenceRecord` retains:

- `document_id`, `chunk_id`
- `source_type`, `citation`, `url`
- `page_start`, `page_end`
- Mechanism, observable, and test-condition metadata from the manifest

Citation validation in M9 rejects any hypothesis or report citation that does not resolve to a retrieved `EvidenceRecord`. Fabricated citations are rejected at validation gates.

**Ingestion commands:**

```bash
python3 scripts/ingest_knowledge.py --validate    # validate manifest + PDFs
python3 scripts/ingest_knowledge.py --stats       # corpus statistics
python3 scripts/ingest_knowledge.py --coverage  # mechanism/observable coverage
python3 scripts/ingest_knowledge.py --ingest      # ingest verified corpus into ChromaDB
python3 scripts/ingest_knowledge.py --ingest --reset  # drop and re-ingest
```

---

## ML Pipeline

```text
M4 synthetic telemetry (parquet)
    → M5 validation (PASS required)
    → M6 feature engineering (v1, 160 observation columns)
    → M7 Isolation Forest training + scoring (frozen)
    → M8 evaluation (frozen M7 + ground truth, offline only)
    → M9 investigation (frozen M7/M8, no ground truth)
```

**M7 algorithm:** `sklearn.ensemble.IsolationForest` with `contamination=0.10`, `n_estimators=100`, lot-level holdout. Full 153-column M6 observation feature matrix is used (including temporal position features from the frozen M6 contract).

**M7 outputs per observation:** `anomaly_score`, `is_anomaly`, `statistical_baseline_score`, `statistical_baseline_flag`

**M7 outputs per module:** max score, flag count, first anomaly cycle, and related aggregates in `module-summary.parquet`

---

## LLM Integration (OpenRouter / Llama)

LLM configuration (`backend/llm/settings.py`) uses environment variables:

| Variable | Purpose |
| --- | --- |
| `LLM_PROVIDER` | Provider name (e.g. `openrouter`) |
| `LLM_MODEL` | Model identifier |
| `LLM_BASE_URL` | OpenAI-compatible base URL |
| `LLM_API_KEY` | Bearer token (never committed) |
| `LLM_TIMEOUT` | Per-request timeout (default 120s) |
| `EMBEDDING_MODEL` | Embedding model (default `sentence-transformers/all-MiniLM-L6-v2`) |
| `CHROMA_PATH` | ChromaDB persist path (default `knowledge_base/chroma`) |

`OPENROUTER_API_KEY` is honoured as a fallback key source.

**Verified OpenRouter configuration:**
- Provider: `openrouter`
- Model: `meta-llama/llama-3.3-70b-instruct`
- Base URL: `https://openrouter.ai/api/v1`

`LLM_PROVIDER` must be set explicitly. If it is unset, `LLMSettings.configured` is `False` and `create_llm_client` returns `MockLLMClient`, so the hypothesis stage produces no model-generated reasoning even when a valid `OPENROUTER_API_KEY` is present. The active model is `meta-llama/llama-3.3-70b-instruct`, verified against the live OpenRouter `/v1/models` catalogue. Historical investigation records retain the model that actually produced them.

When no API key is configured, `MockLLMClient` is used and hypothesis generation is mocked.

**Never put an API key in this file or in committed configuration.** Copy `.env.example` to `.env` and supply credentials at runtime.

---

## Epistemic and Engineering Safety

SmartESS intentionally avoids simplistic signal-to-failure mappings:

- RDS_on increase does not automatically mean bond-wire failure
- VTH shift does not automatically mean permanent gate-oxide damage
- IGSS increase does not automatically mean gate-oxide breakdown
- Tj increase does not automatically mean die-attach degradation

The system uses evidence retrieval, competing hypotheses, uncertainty, contradictory evidence, provenance, validation gates, and human engineering review as architectural properties.

Binding rules from `agent-rules.md`:

- Evidence before conclusions
- Deterministic tools before LLM reasoning
- Anomaly ≠ confirmed physical failure
- Hypotheses are candidates, not diagnoses
- Engineers retain final disposition authority

---

## Current Capabilities

- M1–M3 domain contracts with Pydantic models, JSON Schemas, validation, and tests
- M4 deterministic synthetic dataset generator with separate ground truth
- M5 independent dataset validation engine
- M6 versioned observation-feature contract (375,750 rows × 160 columns on default dataset)
- M7 frozen Isolation Forest anomaly detection with lot holdout
- M8 evaluation-only layer with timing and baseline analysis
- M9 LangGraph investigation with four agents, nine deterministic tools, validation gates
- Curated engineering knowledge base with ChromaDB retrieval (19 verified documents, 360 chunks)
- OpenRouter / Llama integration, with an explicit mock path when unconfigured
- FastAPI investigation endpoint (minimal)
- 359 passing tests across M1–M9

### Verified M9 run (canonical example)

| Field | Value |
| --- | --- |
| Investigation ID | `inv-70207e0ffd15` |
| Module | `syn-mod-0042` |
| Model | `iforest-v1-syn-sic-pc-dev-001-s20260922` |
| LLM | OpenRouter / `meta-llama/llama-3.3-70b-instruct` |
| Graph path | `load_investigation → investigation_agent → evidence_agent → hypothesis_agent → hypothesis_validation → report_agent → report_validation` |
| Deterministic results | 40 (5 tools) |
| Evidence records | 5, all with complete provenance |
| Hypothesis / report validation | PASSED / PASSED |

Generated hypotheses are candidate mechanisms for engineering review, not guaranteed diagnoses.

---

## Current Limitations

**Knowledge base:**
- VTH hysteresis knowledge coverage is absent
- Temperature-compensated RDS_on monitoring coverage is thin
- HTOL coverage is thin (1 document, incidental)
- VDS_on and Tc coverage is comparatively thin
- Limited diversity of primary power-cycling research sources
- 13 manifest entries need manual access (paywalled/blocked)
- 1 document requires OCR
- 3 candidate source titles remain unresolved
- Possible rate limiting on the free OpenRouter endpoint

**Platform:**
- No frontend UI (placeholder `frontend/` directory only)
- No SQLAlchemy persistence, Clerk authentication, or full REST API
- No production telemetry ingestion pipeline
- No model registry or promotion workflow beyond frozen M7 artifacts
- Synthetic data only in the default pipeline; not validated as a physics model
- Lint/type-check toolchain (ruff, mypy) not configured

These are known boundaries of the current corpus and infrastructure, not failures of the entire system.

---

## Repository Structure

```text
SmartESS/
├── README.md                          # This file
├── PRD.md                             # Product requirements (BurnInGuard AI naming)
├── architecture.md                    # System architecture
├── tech-stack.md                      # Technology choices
├── agent-rules.md                     # Agent safety and evidence rules
├── pyproject.toml                     # Python package (smartess, >=3.11)
├── .env.example                       # Environment variable template (no secrets)
│
├── backend/
│   ├── domain/                        # M1–M3 Pydantic domain models
│   │   ├── module_profiles/           # M1 ModuleProfile
│   │   ├── test_profiles/             # M2 TestProfile
│   │   └── telemetry/                 # M3 TelemetryRecord
│   ├── agents/investigation/          # M9 agents, orchestrator, tools, models
│   ├── knowledge/                     # Corpus validation, ingestion, ChromaDB retrieval
│   ├── llm/                           # LLM abstraction, OpenRouter provider, settings
│   ├── api/                           # FastAPI app and investigation routes
│   └── tests/                         # All pytest tests (M1–M9)
│
├── ml/
│   ├── generators/synthetic/          # M4 synthetic dataset generator
│   ├── validators/synthetic/          # M5 dataset validation engine
│   ├── features/                      # M6 feature engineering (v1 registry)
│   ├── anomaly/                       # M7 Isolation Forest detector
│   ├── evaluation/                    # M8 evaluation pipeline
│   └── datasets/
│       ├── synthetic/                 # Generated synthetic datasets
│       ├── features/v1/               # M6 observation/module feature artifacts
│       ├── scores/                    # M7 observation/module scores
│       ├── evaluation/                # M8 evaluation artifacts
│       └── investigations/            # M9 investigation outputs
│
├── knowledge_base/
│   ├── corpus/                        # Source PDFs by category
│   ├── metadata/corpus.json           # Versioned document manifest
│   ├── reports/corpus-coverage.md     # Coverage and gap analysis
│   └── chroma/                        # ChromaDB persist directory (local)
│
├── schemas/                           # Committed JSON Schemas (M1–M3)
├── examples/                          # Reference module, test, telemetry profiles
├── scripts/                           # Operational CLIs (see Setup section)
├── docs/                              # Implementation docs per milestone
│   └── implementation-status.md       # Detailed milestone status and validation results
└── frontend/                          # Placeholder (not implemented)
```

---

## Technology Stack

Technologies actually present in the repository:

| Category | Technology |
| --- | --- |
| Language | Python >= 3.11 |
| Validation / models | Pydantic 2, pydantic-settings |
| Data | NumPy, Pandas, PyArrow (Parquet) |
| ML | scikit-learn (Isolation Forest), joblib |
| Agents | LangGraph |
| Vector DB | ChromaDB |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) |
| LLM | OpenRouter API, `meta-llama/llama-3.3-70b-instruct` |
| API | FastAPI, Uvicorn, httpx |
| PDF | pypdf, reportlab |
| Testing | pytest, jsonschema |

**Documented but not implemented:** Next.js/React frontend, Clerk auth, SQLAlchemy/SQLite persistence, LangChain (LangGraph is used directly), Recharts.

---

## Setup

### Prerequisites

- Python 3.11+
- pip

### Install

```bash
python3 -m pip install -e ".[dev]"
```

### Configure environment

```bash
cp .env.example .env
# Edit .env — set LLM_API_KEY=<your-openrouter-api-key> for real inference
```

### Validate installation

```bash
python3 -m compileall -q backend ml scripts
python3 -m pytest -W error
```

Expected: **359 passed, 0 failed**

### Regenerate JSON Schemas

```bash
python3 scripts/export_module_profile_schema.py
```

---

## Running Tests

```bash
python3 -m pytest -W error
```

Test coverage spans M1 (ModuleProfile), M2 (TestProfile), M3 (Telemetry), M4 (synthetic generator), M5 (dataset validation), M6 (feature engineering), M7 (anomaly detection), M8 (evaluation), and M9 (investigation, tools, RAG, corpus, LLM, data access).

---

## Running the Pipeline

### Generate synthetic dataset (M4)

```bash
python3 -m ml.generators.synthetic.cli --dataset-id syn-sic-pc-dev-001 --seed 20260921
```

### Validate dataset (M5)

```bash
python3 scripts/validate_synthetic_dataset.py ml/datasets/synthetic/syn-sic-pc-dev-001
```

### Build features (M6)

```bash
python3 scripts/build_features.py ml/datasets/synthetic/syn-sic-pc-dev-001
```

### Train anomaly model (M7)

```bash
python3 scripts/train_anomaly_model.py ml/datasets/features/v1 \
  --dataset-dir ml/datasets/synthetic/syn-sic-pc-dev-001
```

### Evaluate model (M8)

```bash
python3 scripts/evaluate_anomaly.py iforest-v1-syn-sic-pc-dev-001-s20260922 \
  --dataset-dir ml/datasets/synthetic/syn-sic-pc-dev-001
```

### Ingest knowledge base (M9)

```bash
python3 scripts/ingest_knowledge.py --validate
python3 scripts/ingest_knowledge.py --ingest
```

### Build healthy reference (M9)

```bash
python3 scripts/build_healthy_reference.py
```

### Check LLM connectivity (M9)

```bash
python3 scripts/check_llm.py
```

### Run investigation (M9)

Canonical example:

```bash
python3 scripts/investigate.py \
  --module-id syn-mod-0042 \
  --model-id iforest-v1-syn-sic-pc-dev-001-s20260922
```

This runs the full LangGraph investigation pipeline: loads frozen M7/M8 artifacts for the module, executes deterministic tools, retrieves evidence from ChromaDB, generates hypotheses via Nemotron (or mock), validates citations, synthesizes a report, and writes output to `ml/datasets/investigations/<investigation_id>/`.

### Start API (optional)

```bash
uvicorn backend.api.app:app --reload
```

Endpoints: `GET /health`, `POST /investigations`, `GET /investigations/{id}`

---

## Development Principles

From `agent-rules.md` and `architecture.md`:

1. **Configuration before analysis** — Module Profile and data validation precede training and investigation
2. **Validation before training** — Never train on `BLOCKED` data; preserve raw data
3. **Deterministic tools before LLM reasoning** — Numerical calculations are code, not prompts
4. **Evidence before conclusions** — Observation → evidence → interpretation
5. **Held-out evaluation** — Lot-level or module-level splits; no temporal leakage
6. **Provenance everywhere** — Profiles, datasets, features, models, tools, evidence, reports
7. **Human-in-the-loop** — Engineers confirm specs, review hypotheses, retain final authority
8. **Synthetic data labeling** — Never represent synthetic telemetry as production data
9. **Uncertainty exposure** — Prefer "mechanism unresolved" over false certainty

---

## Project Status

| Milestone | Status |
| --- | --- |
| M1 — Module Profile | Complete |
| M2 — Test Profile | Complete |
| M3 — Telemetry Data Contract | Complete |
| M4 — Synthetic Dataset | Complete |
| M5 — Validation Engine | Complete |
| M6 — Observation Feature Contract | Complete |
| M7 — Anomaly Detection | Complete (frozen) |
| M8 — Evaluation | Complete (frozen) |
| M9 — Multi-Agent Investigation | Complete (validated) |
| Frontend integration | Not started |

**Next milestone:** Frontend integration. Do not start before M9 is reviewed and accepted.

For detailed validation results, artifact paths, and per-milestone commands, see [`docs/implementation-status.md`](docs/implementation-status.md).

---

## Authoritative Documents

| Document | Description |
| --- | --- |
| [`PRD.md`](PRD.md) | Product requirements |
| [`architecture.md`](architecture.md) | System architecture |
| [`tech-stack.md`](tech-stack.md) | Technology choices |
| [`agent-rules.md`](agent-rules.md) | Agent safety and evidence rules |
| [`docs/implementation-status.md`](docs/implementation-status.md) | Repository state, milestone deliverables, validation results |
| [`knowledge_base/README.md`](knowledge_base/README.md) | Knowledge base rules and ingestion |
| [`docs/data-model/module-profile.md`](docs/data-model/module-profile.md) | ModuleProfile data model |
| [`docs/data-model/test-profile.md`](docs/data-model/test-profile.md) | TestProfile data model |
| [`docs/data-model/telemetry.md`](docs/data-model/telemetry.md) | Telemetry data model |
| [`docs/anomaly-detection/anomaly-detection.md`](docs/anomaly-detection/anomaly-detection.md) | M7 anomaly detection |
| [`docs/feature-engineering/feature-engineering.md`](docs/feature-engineering/feature-engineering.md) | M6 feature engineering |
| [`knowledge_base/reports/corpus-coverage.md`](knowledge_base/reports/corpus-coverage.md) | Knowledge base gap analysis |
