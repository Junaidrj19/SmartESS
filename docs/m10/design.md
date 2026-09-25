# M10 — Engineer-Facing Scientific Investigation Platform: Design

> Status: DESIGN ONLY for the backend capabilities marked **[M10 REQUIREMENT]** — those are proposals,
> not existing features. M1–M9 behaviour is unchanged by this document.
>
> **UX contract:** `frontend/UX.md` is the authoritative UX implementation contract derived from this
> document. It owns the concrete design tokens (§44), the toolchain decisions (§43), register
> rendering, context-rail behaviour, status vocabulary and exact state copy. Where a visual idea in
> `frontend/UX.md` conflicts with scientific semantics here, this document wins.
>
> **Implementation status:** phase **M10-A is implemented** under `frontend/` (application shell,
> context rail, register primitives, typed API client, Mission Control, Investigation History,
> Pipeline Readiness). Phases M10-B … M10-H are not started.

## 1. M10 Objective

M10 is the engineer-facing scientific investigation platform over the completed SmartESS M1–M9
backend. Its objective is to make the depth of the existing engineering work **visible, navigable
and traceable** — not to summarise it.

M10 must let a reliability engineer answer, for one module under one reliability test:

| Question | Backed by |
| --- | --- |
| What was measured? | M6 `observation-features.parquet` — 8 baseline signals |
| Is anything statistically unusual? | M7 `observation-scores.parquet`, `module-summary.parquet` |
| How does the detector behave, and when does it fire? | M8 `module-evaluation.parquet`, `timing-analysis.parquet`, `baseline-comparison.parquet` |
| What did fixed engineering tools calculate? | M9 `deterministic_results` (9-tool registry) |
| What does the engineering literature say? | M9 `evidence_records` from the ChromaDB `evidence` collection |
| Which mechanisms compete, and what argues against each? | M9 `Hypothesis.candidates` with `supporting_evidence_ids` / `contradictory_evidence_ids` |
| Was the reasoning checked? | M9 `hypothesis_validation` / `report_validation` gate outcomes |
| What remains uncertain? | `HypothesisStatus`, `limitations`, `Uncertainty` report section |
| What should be measured next? | `distinguishing_measurements`, `Recommended Investigation` section |
| What exact configuration produced this? | `model_id`, `dataset_id`, `feature_version`, LLM provider/model, artifact hashes |

The success standard for the whole document is the single question in §22: **would an experienced
reliability engineer, opening SmartESS for the first time, immediately see the engineering work
underneath it?**

M10 is a presentation and interaction layer. It performs **no** analysis of its own.

## 2. Why M10 Follows M9

M9 is complete and produces provenance-complete structured artifacts, but they are reachable only
through `scripts/investigate.py` stdout and four thin API routes in `backend/api/investigations.py`.
Concretely, as the repository stands:

* `ml/datasets/investigations/` holds **69 investigation directories** — 47 `COMPLETED`, 21
  `PARTIAL`, plus one `reference/` directory holding `healthy-reference.json`.
* The canonical real-inference investigation `inv-70207e0ffd15` contains 40 deterministic results,
  5 evidence records with complete provenance, 5 candidate mechanisms, and a 15-section report —
  and none of it is viewable.
* The ChromaDB `evidence` collection holds **360 chunks** from 19 `VERIFIED` corpus documents. No
  interface can show an engineer which passage supported which candidate mechanism.
* Both validation gates (`hypothesis_validation`, `report_validation`) record `PASSED`/`REJECTED`
  into `provenance`, which is the strongest available evidence that SmartESS is not an LLM wrapper.
  It is currently invisible.

The roadmap in `docs/implementation-status.md` lists step 15 as **frontend integration**, and the
M9 section states *"Next milestone: frontend integration. Do not start M10 before M9 is reviewed and
accepted."* M10 is that step.

M10 follows M9 rather than preceding it because the epistemic vocabulary M10 must render —
`FindingClassification`, `HypothesisStatus`, `MechanismType`, `InvestigationStatus`,
`module_anomaly_status` — is defined by the M9 and M7 implementation. Designing the interface first
would have required inventing that vocabulary.

## 3. Existing M1–M9 Dependencies

M10 reads the following. **All of it is existing and frozen.** M10 must not recompute any numeric
value that appears here; it renders backend numbers verbatim.

### 3.1 Domain contracts (M1–M3)

| Contract | Location | JSON Schema |
| --- | --- | --- |
| `ModuleProfile` | `backend/domain/module_profiles/` | `schemas/sic-module-profile.schema.json` |
| `TestProfile` | `backend/domain/test_profiles/` | `schemas/test-profile.schema.json` |
| `TelemetryRecord` | `backend/domain/telemetry/` | `schemas/telemetry.schema.json` |

Reference instances exist under `examples/module-profiles/`, `examples/test-profiles/`,
`examples/telemetry/`.

> **Constraint.** These are Pydantic + JSON Schema contracts only. There is **no** SQLAlchemy
> persistence, no ingestion, and no API for them. A real `ModuleProfile` is therefore *not*
> currently reachable from an investigation — see §20.1.

### 3.2 Dataset and features (M4–M6)

* Canonical dataset id: `syn-sic-pc-dev-001` — 750 modules, 5 lots (`lot-01` … `lot-05`),
  375 750 telemetry rows, `data_origin=synthetic`.
* `ml/datasets/features/v1/observation-features.parquet` — 7 identifiers + 153 features = 160
  columns. Identifiers: `module_id`, `test_id`, `lot_id`, `dataset_id`, `timestamp`, `cycle_number`,
  `observation_index_within_module`.
* `ml/datasets/features/v1/module-features.parquet` — 929 columns.
* **The 8 baseline/rolling signals M10 visualises**: `RDS_on`, `VTH`, `IGSS`, `IDSS`, `VDS_on`,
  `electrical_power`, `Tj`, `Tc`. `VF` is an electrical passthrough only and is **not** in the v1
  baseline/rolling set — M10 must not chart it as a health signal.
* M5 validation status vocabulary: `PASS` / `WARNING` / `BLOCKED`.

### 3.3 M7 anomaly detection

Model id: `iforest-v1-syn-sic-pc-dev-001-s20260922` (`ml/models/<model_id>/model-record.json`).
Algorithm `isolation_forest`, `detector_version=v1`, `feature_version=v1`,
`contamination=0.10`, `random_state=20260922`, 153 input features, split
`lot_holdout` — train `lot-02, lot-03, lot-05`, test `lot-01, lot-04`.

`ml/datasets/scores/<model_id>/observation-scores.parquet` (375 750 rows):
`module_id`, `test_id`, `lot_id`, `dataset_id`, `timestamp`, `cycle_number`,
`observation_index_within_module`, `anomaly_score`, `is_anomaly`,
`statistical_baseline_score`, `statistical_baseline_flag`, `detector_version`,
`feature_version`, `algorithm`, `model_id`.

`ml/datasets/scores/<model_id>/module-summary.parquet` (750 rows):
`module_id`, `test_id`, `lot_id`, `dataset_id`, `n_observations`,
`n_anomalous_observations`, `anomaly_rate`, `max_anomaly_score`, `mean_anomaly_score`,
`first_anomalous_cycle`, `last_anomalous_cycle`, `anomalous_cycle_span`,
`statistical_baseline_max`, `statistical_baseline_flag_rate`, `module_anomaly_status`.

Semantics M10 must honour exactly:

* `anomaly_score` is an **inverted** Isolation Forest decision function — *higher = more anomalous*.
  Values are small and may be negative (canonical module `syn-mod-0042`: min `-0.0746`,
  max `0.0321`). A chart must not imply `0` is a floor or that negative means "good".
* `statistical_baseline_score` = `max(abs(robust_normalized_deviation))` over the 8 signals;
  `statistical_baseline_flag` when `>= 3.0`. This is an independent comparator, not the model.
* `module_anomaly_status` ∈ `clean` (0 flagged) | `sporadic` (`anomaly_rate < 0.1`) |
  `persistent` (`anomaly_rate >= 0.1`). `docs/anomaly-detection/anomaly-detection.md` states:
  *"This is a descriptive anomaly summary. It is NOT a failure diagnosis."*

### 3.4 M8 evaluation

`ml/datasets/evaluation/<model_id>/` — `evaluation-summary.json`, `module-evaluation.parquet` (750),
`timing-analysis.parquet` (86), `baseline-comparison.parquet` (750).

Module threshold: `0.09893178013560121`.

| View | Population | Precision | Recall | F1 | FPR |
| --- | --- | --- | --- | --- | --- |
| `overall_population` (all 5 lots, 750) | TP 86 / TN 517 / FP 8 / FN 139 | 0.9149 | 0.3822 | 0.5392 | 0.0152 |
| `m7_test_lot_compatibility` (`lot-01`,`lot-04`, 300) | TP 43 / TN 204 / FP 6 / FN 47 | 0.8776 | 0.4778 | 0.6187 | 0.0286 |

Timing is **negative** — mean `lead_vs_onset` ≈ `-37165` cycles, median `-36800`; i.e. the detector
flags *after* degradation onset, not before. `evaluation-summary.json` states *"Positive lead time
means the flag occurs before the reference cycle. Negative values are preserved."* M10 must present
this honestly and must not render it as "early warning" (§19.3).

`module-evaluation.parquet` columns include ground-truth-derived fields — `health_state`,
`degradation_mechanism`, `degradation_stage`, `onset_cycle`, `cycle_measurable`,
`degradation_severity`, `damage_index_end`, `rate_scale`, `y_true` — alongside prediction fields
`y_pred_module`, `first_flag_cycle`, `lead_vs_onset`, `lead_vs_measurable`,
`statistical_baseline_flag_module`, `y_pred_baseline`.

> **Binding rule.** `health_state`, `degradation_mechanism` and `y_true` are **synthetic ground
> truth, evaluation-only**. `evaluation-summary.json` records
> `ground_truth_used_for_training: false`. M10 must render them in a visually separate
> *Ground Truth (synthetic, evaluation-only)* register and must never show them as a SmartESS
> detection, prediction or conclusion. See §12.4.

`timing-analysis.parquet` contains only the 86 detected positives. For any other module
`DataAccess.timing_analysis()` returns `{"note": "module not in timing analysis (healthy or
undetected)"}` — a first-class state M10 must render (§14.4).

### 3.5 M9 investigation engine

Packages: `backend/agents/investigation/` (agents, `orchestrator.py`, `pipeline.py`,
`persistence.py`, `data_access.py`, `state.py`, `models/`, `tools/`), `backend/knowledge/`,
`backend/llm/`.

Deterministic tool registry — 9 tools (`tools/registry.py`):
`calculate_drift`, `calculate_slope`, `calculate_percent_change`, `compare_population`,
`analyze_temperature_dependence`, `detect_change_point`, `calculate_correlation`,
`check_acceptance_limits`, `calculate_degradation_rate`.

`InvestigationAgent` actually invokes, per signal: `calculate_drift`, `calculate_slope`,
`calculate_percent_change`, `calculate_degradation_rate`, plus `compare_population` against the
healthy reference. That yields **40 results / 5 tools** on the canonical investigation.
`analyze_temperature_dependence`, `detect_change_point`, `calculate_correlation` and
`check_acceptance_limits` are registered but **not currently called** — M10 must not display
markers derived from them (§20.3).

Enumerations M10 renders (these are the authoritative label vocabularies):

```text
InvestigationStatus   PENDING LOADING INVESTIGATING RETRIEVING_EVIDENCE ANALYZING
                      REPORTING VALIDATING COMPLETED FAILED PARTIAL
MechanismType         bond_wire_interconnect die_attach_thermal_path gate_related
                      thermal_path package_interconnect other
HypothesisStatus      CANDIDATE SUPPORTED CONTRADICTED INSUFFICIENT_EVIDENCE AMBIGUOUS
FindingClassification OBSERVED CALCULATED PREDICTED HYPOTHESIZED CONFIRMED RECOMMENDED
```

Bounded retries: `MAX_EVIDENCE_ROUNDS = 2`, `MAX_HYPOTHESIS_RETRIES = 2`,
`MAX_REPORT_RETRIES = 2`.

### 3.6 M9 knowledge base

* Manifest `knowledge_base/metadata/corpus.json` — `corpus_version` `1.0.0`, 37 document entries.
* Verification status: 19 `VERIFIED`, 13 `NEEDS_MANUAL_ACCESS`, 3 `UNVERIFIED`, 1 `OCR_REQUIRED`,
  1 `REJECTED`. Source type: 15 `manufacturer`, 12 `peer_reviewed`, 5 `standard`, 5 `review`.
  **Only `VERIFIED` documents enter the production collection.**
* ChromaDB at `knowledge_base/chroma`, collection `evidence`, **360 chunks**, embedding model
  `sentence-transformers/all-MiniLM-L6-v2`.
* Declared axes — mechanisms: `bond_wire_interconnect`, `die_attach_thermal_path`, `gate_related`,
  `thermal_path`, `package_interconnect`, `cross_cutting`; observables: the 8 signals plus
  `thermal_resistance`; test conditions: `power_cycling`, `thermal_cycling`, `gate_bias`, `HTRB`,
  `HTGB`, `HTOL`. Coverage per item is `EXPLICIT` / `PARTIAL` / `NONE`.
* Known gaps (`knowledge_base/reports/corpus-coverage.md`): `HTOL` is thin (1 document);
  threshold-voltage hysteresis and high-temperature operating life are **not** supported.

### 3.7 Binding rules inherited from `agent-rules.md` and `architecture.md`

M10 is bound by these; they are not M10 inventions.

* *"The interface must never present an agent hypothesis as a confirmed physical failure."*
  (`architecture.md` §6)
* The UI must distinguish measured values, model predictions, statistical findings, agent
  hypotheses, and confirmed user decisions. (`architecture.md` §6)
* Every finding classified `Observed | Calculated | Predicted | Hypothesized | Confirmed |
  Recommended`. (`agent-rules.md` §14)
* Uncertainty vocabulary that must be renderable: `Insufficient Evidence`, `Ambiguous`,
  `Anomaly Detected — Mechanism Unresolved`, `Model Not Suitable for Decision Support`.
  (`agent-rules.md` §16)
* Synthetic data *"must never be represented as production telemetry."* (`agent-rules.md` §17)
* *"Every model result and engineering hypothesis should be traceable to telemetry, calculations,
  configuration, and supporting sources."* (`architecture.md` §3.7)

### 3.8 What M10 must never do to M1–M9

No retraining, no re-scoring, no re-evaluation, no threshold changes, no writes under
`ml/models/`, `ml/datasets/scores/`, `ml/datasets/evaluation/`, `ml/datasets/features/`,
`ml/datasets/synthetic/`, or `knowledge_base/`. `pipeline.py` already hash-verifies M7/M8
immutability around every run via `DataAccess.snapshot_m7_m8()`; M10 surfaces those hashes rather
than adding a second mechanism.

## 4. System Architecture

```text
┌──────────────────────────────────────────────────────────────────────┐
│ frontend/  Next.js App Router + React + TypeScript + Tailwind        │
│            Recharts       (stack mandated by tech-stack.md)          │
│                                                                      │
│  Investigation Workspace ── persistent context rail                  │
│   ├── Module Explorer        ├── Signal Analysis (synchronised x)    │
│   ├── Anomaly (M7)           ├── Detector Behaviour (M8)             │
│   ├── Pipeline Trace (M9)    ├── Evidence Explorer                   │
│   ├── Hypothesis Comparison  ├── Engineering Report                  │
│   └── Provenance Inspector   └── Investigation History               │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ REST / JSON  (typed client, no logic)
┌───────────────────────────────▼──────────────────────────────────────┐
│ backend/api/  FastAPI                                                │
│   EXISTING: /health, /investigations{,/{id},/{id}/report}            │
│   [M10 REQUIREMENT]: modules, telemetry, anomaly, evaluation,        │
│                      evidence, provenance, corpus, run-status        │
│   Read-only projection over frozen artifacts. NO analysis here.      │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ in-process Python calls only
┌───────────────────────────────▼──────────────────────────────────────┐
│ UNCHANGED M9 BACKEND                                                 │
│   DataAccess ─ frozen parquet/JSON reader + hash snapshots           │
│   InvestigationGraph (LangGraph, 7 nodes, bounded retries)           │
│   InvestigationPersistence ─ ml/datasets/investigations/<inv_id>/    │
│   ChromaRetriever ─ knowledge_base/chroma :: collection "evidence"   │
│   LLMSettings / create_llm_client ─ OpenRouter or MockLLMClient      │
└──────────────────────────────────────────────────────────────────────┘
                                │ read-only
┌───────────────────────────────▼──────────────────────────────────────┐
│ FROZEN ARTIFACTS                                                     │
│  ml/datasets/features/v1/ · ml/models/<model_id>/                    │
│  ml/datasets/scores/<model_id>/ · ml/datasets/evaluation/<model_id>/ │
│  ml/datasets/investigations/ · knowledge_base/                       │
└──────────────────────────────────────────────────────────────────────┘
```

Architectural rules:

1. **The frontend contains no investigation logic.** It does not compute drift, slopes, z-scores,
   thresholds, metrics, confidences or rankings. Every number is a backend number.
2. **The M10 API is a projection, not a second engine.** It composes `DataAccess`,
   `InvestigationPersistence` and `ChromaRetriever`. It introduces no new numeric method.
3. **Downsampling is the one permitted transformation**, it is explicit, it is a
   **[M10 REQUIREMENT]** on the API (not the client), it must be labelled in the response, and it
   must never drop a flagged observation (§19.2).
4. **Deployment split is preserved** per `tech-stack.md`: frontend on Vercel, FastAPI on a
   Python-compatible host. Both read the same repository-relative artifact paths, so a shared
   filesystem is an operational requirement for the prototype (§19.5).

## 5. Components

### 5.1 Frontend surfaces

| Surface | Purpose | Primary backend source |
| --- | --- | --- |
| **Context rail** (persistent) | module, test, lot, dataset, model, feature version, investigation id, status, data origin, anomaly status | `module-summary`, `model-record.json`, investigation record |
| **Mission Control** | population view: lot × `module_anomaly_status`, investigation coverage, corpus and LLM readiness | `module-summary`, investigations index, corpus manifest |
| **Module Explorer** | find and select a module; filter by lot, `module_anomaly_status`, split membership | `module-summary.parquet` |
| **Signal Analysis** | 8 signals on a shared cycle axis, stacked with anomaly score and flags | `observation-features`, `observation-scores` |
| **Anomaly View (M7)** | score trajectory, flag distribution, model identity, statistical-baseline comparator | `observation-scores`, `module-summary`, `model-record.json` |
| **Detector Behaviour (M8)** | module verdict, timing vs onset, baseline comparison, population metrics in context | `module-evaluation`, `timing-analysis`, `baseline-comparison`, `evaluation-summary.json` |
| **Pipeline Trace (M9)** | 7 LangGraph nodes as inspectable stages with retries and gate outcomes | investigation `provenance`, `retry_counts`, `errors` |
| **Evidence Explorer** | `EvidenceRecord` detail, passage, citation, page range, axes, source link | investigation `evidence_records`, `evidence_queries` |
| **Hypothesis Comparison** | competing `CandidateMechanism`s side by side, supporting vs contradictory | investigation `hypothesis` |
| **Engineering Report** | the 15 M9 sections with per-finding classification and evidence links | investigation `report` |
| **Provenance Inspector** | the full lineage chain of §9, plus artifact hashes | `provenance`, `_hash` fields, `snapshot_m7_m8()` |
| **Investigation History** | all 69+ investigations, reopenable, status-faceted | investigations index |

### 5.2 M10 API layer — new, thin

| Component | Responsibility |
| --- | --- |
| `backend/api/modules.py` **[M10 REQ]** | module list/detail projection over `module-summary` |
| `backend/api/telemetry.py` **[M10 REQ]** | signal series + scores, server-side downsampling |
| `backend/api/anomaly.py` **[M10 REQ]** | M7 projection incl. model record |
| `backend/api/evaluation.py` **[M10 REQ]** | M8 projection incl. `evaluation-summary.json` |
| `backend/api/evidence.py` **[M10 REQ]** | evidence detail + corpus manifest + collection health |
| `backend/api/investigations.py` (extend) | add async launch, run status, provenance, export |
| `backend/api/app.py` (extend) | register routers, add CORS, add readiness probe |

### 5.3 Unchanged M9 components M10 depends on

`DataAccess` (all reader methods + `snapshot_m7_m8`), `InvestigationGraph`, `run_investigation`,
`InvestigationPersistence` (`load`, `list_investigations`), `ChromaRetriever` (`retrieve`, `count`),
`LLMSettings` (`configured`, `provider`, `model`, `endpoint_host`), the 9-tool registry,
`validate_hypothesis`, `validate_report`, `HealthyReferenceSelector`.

**None of these are modified by M10.**

## 6. Agent Workflow

The M9 graph is compiled in `InvestigationGraph._build()`. M10 renders it as an **inspectable
execution trace**, never as decorative animation. Node names are the literal LangGraph node names, so
a trace row maps 1:1 to a `ProvenanceEntry.step`.

```text
START
  │
  ▼
load_investigation          source: orchestrator
  │
  ▼
investigation_agent         source: deterministic_tools
  │                         DETERMINISTIC — no LLM
  ▼
evidence_agent  ◄───────┐   source: chromadb_evidence_collection
  │                     │   RETRIEVAL — no LLM generation
  ▼                     │
hypothesis_agent ◄───┐  │   source: llm:<provider>/<model>
  │                  │  │   LLM REASONING — the only generative stage
  ▼                  │  │
hypothesis_validation│  │   source: hypothesis_validation_gate
  │                  │  │
  ├── PASSED ────────┼──┼──► report_agent
  ├── unknown evidence id  ─┘  (if evidence_round < 2)
  └── other issue ────┘        (if hypothesis_retries < 2)
  │
  ▼
report_agent  ◄─────┐       source: report_agent
  │                 │       DETERMINISTIC synthesis — "recalculates nothing"
  ▼                 │
report_validation ──┘       source: report_validation_gate
  │                         (retry only when report is None and retries < 2)
  ▼
END
```

### 6.1 Per-stage inspector contract

Each stage is expandable. The content is derived from real state, and where a value is not produced
by the backend the row reads `not recorded` — never a plausible-looking placeholder.

**`load_investigation`** — request accepted. Shows `module_id`, `model_id`, `dataset_id`, and the
`initialization` provenance entry from `pipeline.run_investigation`.

**`investigation_agent`** (deterministic register)
* artifacts loaded: `load_module_trajectory`, `module_summary`, `module_evaluation`,
  `timing_analysis`, `baseline_comparison`, `model_record`
* tools invoked and result count — e.g. *40 results, 5 distinct tools*, grouped by `tool_name` then
  `input_summary.signal`
* each `DeterministicResult` rendered as `tool_name` `tool_version` · `input_summary` · `output` ·
  `provenance.method`
* healthy-reference status: present (`n`, `mean`, `std` per signal from
  `ml/datasets/investigations/reference/healthy-reference.json`) or the recorded limitation
  `population_comparison_skipped: …`
* **explicit label: no LLM involvement in this stage**

**`evidence_agent`** (retrieval register)
* `evidence_queries` — the full generated list, up to `MAX_QUERIES = 8`, each shown verbatim
* which signals drove them: `changed_signals()` uses `MIN_CHANGE_PERCENT = 1.0` on
  `percent_drift`/`percent_change`; the UI states that this threshold only selects a query and
  *"is never used as a diagnostic conclusion"*
* round number from `retry_counts.evidence_round` (max 2)
* records retrieved, capped by `max_evidence` (API default 5)
* provenance completeness per record: `document_id`, `chunk_id`, `citation`, `url`,
  `page_start`–`page_end` all present → *complete*; otherwise the missing fields are named
* `evidence_status`: `available` | `unavailable`

**`hypothesis_agent`** (LLM register — visually distinct)
* `provider_name` / `model_name` from the client; `endpoint_host` from `LLMSettings`;
  `prompt_version` (`m9-v1`); `temperature=0.1`; `max_tokens=6000`
* inference mode: **real** when `LLMSettings.configured`, otherwise **mocked (MockLLMClient)** —
  this must be unmissable, since a mocked run carries no model reasoning
* candidates generated, with ids stamped deterministically by `_stamp_hypothesis_ids` as
  `<investigation_id>-hyp-c<N>`
* `Hypothesis.note`, and on failure the `errors["hypothesis"]` text plus the
  `llm_reasoning_unavailable` limitation
* context truncation limits actually applied: `MAX_EVIDENCE_CHARS=1200`,
  `MAX_DETERMINISTIC_RESULTS=40`, `MAX_CONTEXT_CHARS=24000` — disclosed because they bound what the
  model could see

**`hypothesis_validation`** (gate register)
* outcome `PASSED` / `REJECTED` with the issue count and first issue, exactly as written to
  provenance
* the four checks from `validate_hypothesis` + the orchestrator's empty-candidate check:
  confidence in `[0,1]`; `CANDIDATE`/`SUPPORTED`/`CONTRADICTED` require ≥1 supporting id; every
  cited id resolves to a retrieved record; `INSUFFICIENT_EVIDENCE`/`AMBIGUOUS` must explain
* rejected evidence ids listed individually
* the routing decision taken, and why

**`report_agent`** — 15 sections assembled; finding counts per section; the stated property that
synthesis *"recalculates nothing, invents nothing"*.

**`report_validation`** (gate register)
* outcome; missing-section list; unresolved citations by finding label; any
  `CONFIRMED`-classified mechanism finding (a hard rejection); empty narrative; matched
  `CERTAINTY_PATTERNS`; missing provenance

### 6.2 Terminology

The launch control is labelled **Run Investigation**, never "AI Analysis". Stage labels use the node
names. The three registers — deterministic, retrieval, LLM — are visually distinguished per §12.4 so
an engineer can see at a glance that exactly one stage is generative.

### 6.3 Live vs replayed

`run_investigation` is synchronous and `backend/api/investigations.py` states *"execution is
synchronous within the API process."* Therefore:

* **Replay (available today):** any of the 69 stored investigations renders a complete, real trace
  from `provenance`. This is the primary path and needs no new backend capability.
* **Live (requires [M10 REQUIREMENT] §10.3):** a job-backed launch endpoint plus status polling. Until
  that exists, M10 must show a single indeterminate *Investigation running — stages will appear on
  completion* state and must **not** fake per-stage progress. Simulated progress is a violation of
  §21.

## 7. Data Flow

```text
   M4 synthetic telemetry (data_origin=synthetic, 375 750 rows)
                    │  [not read directly by M10]
                    ▼
   M6  observation-features.parquet ──────────┐  8 signals + cycle_number
                    │                         │
                    ▼                         │
   M7  observation-scores.parquet ────────────┤  anomaly_score, is_anomaly,
       module-summary.parquet                 │  statistical_baseline_*
       model-record.json                      │
                    │                         │
                    ▼                         │
   M8  module-evaluation / timing-analysis ───┤  y_pred_module, lead_vs_onset,
       baseline-comparison / eval-summary     │  health_state (GROUND TRUTH)
                    │                         │
                    ▼                         │
   M9  DataAccess.load_module_trajectory() ◄──┘
                    │
                    ├─► deterministic_results  (40, from 5 tools)
                    │
                    ├─► evidence_queries ──► ChromaRetriever.retrieve(k)
                    │                          └─► evidence_records
                    │                               (EvidenceRecord + provenance)
                    ├─► hypothesis  (LLM, cites evidence_id only)
                    │
                    └─► report  (15 sections, Findings cite evidence_id)
                              │
                              ▼
        ml/datasets/investigations/<investigation_id>/
          investigation-record.json   (full InvestigationRecord)
          investigation-report.json   (InvestigationReport)
          deterministic-results.json
          provenance.json
                              │
                              ▼
        M10 API projection ──► typed client ──► workspace
```

### 7.1 Signal series flow

`DataAccess.load_module_trajectory(model_id, module_id)` returns a `ModuleTrajectory` whose
`signals` dict is keyed by the 8 signal names and whose `cycle_numbers` come from
`observation_scores`. Canonical module `syn-mod-0042` has `n_observations = 501`, so all 8 series and
the score series share length 501 and one x-axis.

`ModuleTrajectory.signals` values are floats with `NaN` substituted for `None`. **JSON cannot carry
`NaN`.** The **[M10 REQUIREMENT]** telemetry endpoint must serialise missing samples as `null` and
the chart must break the line rather than interpolate across a gap.

### 7.2 Evidence flow

`ChromaRetriever.retrieve(query, k)` → per-chunk `_to_evidence()` → `EvidenceRecord`. Mechanism,
observable and test-condition axes arrive as comma-joined metadata strings and are split into
`mechanisms` / `observables` / `test_conditions` lists. `retrieval_metadata` carries
`distance` (a string) and `chunk_index`.

`distance` is a vector distance — **lower = closer**. It is not a relevance percentage and must never
be rendered as one (§19.1). `EvidenceRecord.confidence` defaults to `0.5` and is not set by the
retriever, so M10 must not present it as a computed strength.

### 7.3 Report flow

`report.sections` is a `List[Dict[str, Any]]` (serialised `ReportSection`), each with `title`,
`findings[]`, `narrative`. `report.full_text` is a pre-rendered Markdown narrative built by
`_build_narrative` as `## <title>` + `- [<CLASSIFICATION>] <label>: <detail>`. M10 renders the
structured `sections` for interaction and offers `full_text` for Markdown export (§10.6).

## 8. Control Flow

### 8.1 Primary journey

```text
Mission Control
   │ select lot / anomaly status
   ▼
Module Explorer ──────────── select module_id
   │
   ▼
Module Context  (M6 signals · M7 anomaly · M8 detector behaviour)
   │                                     │
   │ existing investigation?             │ none?
   ▼                                     ▼
Open investigation              [Run Investigation]  ← explicit human action
   │                                     │
   └──────────────┬──────────────────────┘
                  ▼
        Pipeline Trace (7 stages, inspectable)
                  │
     ┌────────────┼────────────┬───────────────┐
     ▼            ▼            ▼               ▼
Deterministic  Evidence   Hypothesis      Validation
 findings      Explorer   Comparison        gates
     └────────────┴────────────┴───────────────┘
                  ▼
        Engineering Report (15 sections)
                  │
                  ▼
        Trace claim → finding → evidence → chunk → source document
                  │
                  ▼
        Human decision  (recorded outside SmartESS — see §20.6)
```

The first screen is Mission Control / Module Explorer — **not** a marketing landing page. Context is
established before anything is interpreted.

### 8.2 Explicit actions only

Permitted verbs: **Select · Inspect · Run Investigation · Compare · Trace · Review · Export**.

* No action mutates M1–M9 artifacts.
* `Run Investigation` is the only state-creating action; it writes a new
  `ml/datasets/investigations/<investigation_id>/` directory and nothing else.
* It always requires explicit confirmation showing what will be used: `module_id`, `model_id`,
  `dataset_id`, `max_evidence`, LLM provider/model, and whether inference will be **real or mocked**.
* Nothing is auto-run on page load. No conclusion is ever presented as an automatic decision.

### 8.3 Concurrency and idempotency

`run_investigation` mints a fresh `investigation_id` (`inv-` + 12 hex) on every call, so repeated
launches create additional records rather than overwriting. The UI must therefore warn when an
investigation already exists for the same `(module_id, model_id)` pair and offer *Open existing*
alongside *Run new*, to keep the 69-directory store interpretable.

### 8.4 Failure routing

A failed stage does not blank the workspace. `InvestigationRecord.status` becomes `PARTIAL` whenever
`errors` is non-empty (per `pipeline.py`), and 21 of the 69 stored investigations are `PARTIAL`.
Every stage that did complete stays inspectable; the failed stage shows its `errors` entry. See §14.

## 9. ML → Investigation → Evidence → Hypothesis → Report Lineage

This is the chain M10 exists to make walkable. Every hop below is a real field relation in the
current implementation.

```text
[1] SIGNAL SAMPLE            observation-features.parquet
    module_id · cycle_number · RDS_on|VTH|IGSS|IDSS|VDS_on|electrical_power|Tj|Tc
        │  loaded by DataAccess.load_module_trajectory()
        ▼
[2] MODULE TRAJECTORY        ModuleTrajectory.signals[signal][i] ↔ cycle_numbers[i]
        │
        ├──────────────► [2a] ANOMALY SCORE   observation-scores.parquet
        │                     anomaly_score[i], is_anomaly[i]   (same i)
        │                          │
        │                          ▼
        │                [2b] MODULE VERDICT  module-evaluation.parquet
        │                     y_pred_module, first_flag_cycle, lead_vs_onset
        │
        ▼
[3] DETERMINISTIC RESULT     DeterministicResult
    tool_name · tool_version · input_summary.signal · output · provenance.method
        │  e.g. calculate_drift on IGSS → percent_drift
        ▼
[4] EVIDENCE QUERY           evidence_queries[] (built from changed_signals())
        │  SIGNAL_QUERIES / SIGNAL_GROUPS / TOOL_QUERIES
        ▼
[5] EVIDENCE RECORD          EvidenceRecord
    evidence_id = chunk_id · document_id · citation · url · page_start–page_end
    source_type · mechanisms[] · observables[] · test_conditions[] · retrieved_text
        │
        ▼
[6] SOURCE CHUNK / DOCUMENT  ChromaDB "evidence" chunk → corpus.json document entry
    verification_status must be VERIFIED · local_path · official url
        │
        ▼
[7] CANDIDATE MECHANISM      CandidateMechanism
    candidate_id = <inv_id>-hyp-c<N> · mechanism · status · confidence
    supporting_evidence_ids[] ──┐   contradictory_evidence_ids[] ──┐
    reasoning · distinguishing_measurements                        │
        │                       └─── resolve back to [5] ─────────┘
        ▼
[8] VALIDATION GATE          hypothesis_validation → PASSED | REJECTED
        │                    every cited id must resolve to [5]
        ▼
[9] REPORT FINDING           Finding
    label · classification ∈ {OBSERVED, CALCULATED, PREDICTED, HYPOTHESIZED,
                              CONFIRMED, RECOMMENDED}
    source · evidence_ids[] ──── resolve back to [5]
        │
        ▼
[10] REPORT SECTION          one of the 15 required titles
        │
        ▼
[11] REPORT VALIDATION       report_validation → PASSED | REJECTED
```

### 9.1 Navigation affordances (bidirectional)

| From | To | Mechanism |
| --- | --- | --- |
| Report finding | evidence records | `Finding.evidence_ids` → `EvidenceRecord.evidence_id` |
| Candidate mechanism | supporting / contradictory evidence | the two id lists, shown as separate columns |
| Evidence record | source document | `document_id` → `corpus.json`; `url` opens the official source |
| Evidence record | candidates citing it | reverse index over all `supporting_evidence_ids` |
| Deterministic result | signal region | `input_summary.signal` selects and highlights that series |
| Deterministic result | driven queries | `TOOL_QUERIES[tool_name]`, `SIGNAL_QUERIES[signal]` |
| Provenance entry | stage inspector | `ProvenanceEntry.step` → node name |
| Investigation | frozen inputs | `model_id`, `dataset_id`, `snapshot_m7_m8()` hashes |

### 9.2 The one hop that is not machine-linked

`DeterministicResult` → `evidence_queries` is **reconstructed by M10 from the query-construction
tables** in `evidence_agent.py`, because the backend stores `evidence_queries` as a flat
`List[str]` with no back-reference to the result that motivated each query.

M10 must label this link **derived** and must not present it as recorded provenance. Making it
authoritative is an optional backend change listed in §10.7, not an assumption.

### 9.3 Register separation across the chain

Steps [1]–[2b] are **data**. Step [3] is **engineering calculation**. Steps [4]–[6] are **retrieved
knowledge**. Step [7] is **LLM-generated reasoning**. Steps [8] and [11] are **validation**. Steps
[9]–[10] are a **composed artifact** whose per-finding classification declares its own register.
M10 renders these five registers distinctly (§12.4) so that a value's epistemic status is readable
without clicking.

## 10. Interfaces and Contracts

### 10.1 What exists today (verbatim)

`backend/api/app.py` — `FastAPI(title="SmartESS API", version="0.1.0")`, includes the investigations
router, and defines:

```text
GET  /health                              → {"status": "ok"}
```

`backend/api/investigations.py` — `APIRouter(prefix="/investigations", tags=["investigations"])`:

```text
POST /investigations                      body: InvestigationRequest
     InvestigationRequest = {
       module_id: str                            (required)
       model_id:  str = "iforest-v1-syn-sic-pc-dev-001-s20260922"
       dataset_id: str = "syn-sic-pc-dev-001"
       max_evidence: int = 5
     }
     → {investigation_id, status, module_id, model_id}
     → 500 {detail: str} on any exception
     SYNCHRONOUS — blocks for the whole graph run, including LLM calls

GET  /investigations?module_id=&model_id=  → [{investigation_id, module_id,
                                               model_id, status, created_at}]
GET  /investigations/{investigation_id}    → full InvestigationRecord | 404
GET  /investigations/{investigation_id}/report → InvestigationReport | 404
```

That is the entire HTTP surface. There is **no** CORS middleware, **no** authentication, **no**
pagination, and **no** endpoint for modules, telemetry, M7 scores, M8 evaluation, evidence, the
corpus, or provenance.

### 10.2 [M10 REQUIREMENT] Read projection endpoints

All read-only. All compose existing `DataAccess` / `ChromaRetriever` methods. None introduces a new
numeric computation.

```text
GET /models
    → [{model_id, algorithm, detector_version, feature_version,
        source_dataset_id, module_profile_id, training_timestamp,
        hyperparameters, split, status}]
    source: ml/models/*/model-record.json

GET /models/{model_id}
    → full model-record.json + {artifact_hash}          (DataAccess.model_record)

GET /modules?model_id=&lot_id=&anomaly_status=&limit=&offset=
    → {total, items: [ all 15 module-summary.parquet columns ]}
    source: DataAccess module-summary projection; requires a full-column read
    NOTE: DataAccess.module_summary() is single-module. A list projection is new
          code in the M10 API layer, reading the same parquet. [M10 REQ]

GET /modules/{module_id}?model_id=
    → {module_summary, module_evaluation, m8_timing, m8_baseline,
       split_membership: {lot_id, in_train_lots, in_test_lots},
       investigations: [{investigation_id, status, created_at}]}

GET /modules/{module_id}/telemetry?model_id=&signals=&from_cycle=&to_cycle=&max_points=
    → {module_id, model_id, n_observations, cycle_numbers: int[],
       signals: {<signal>: (number|null)[]},
       anomaly_score: number[], is_anomaly: boolean[],
       statistical_baseline_score: number[], statistical_baseline_flag: boolean[],
       downsampled: bool, downsample_method: str|null,
       returned_points: int, source_points: int}
    RULES: NaN → null; every flagged observation retained when downsampled;
           default signals = the 8 baseline signals

GET /modules/{module_id}/anomaly?model_id=
    → {module_summary, model: {model_id, algorithm, detector_version,
       feature_version, contamination, random_state, n_features},
       score_semantics: {direction: "higher_is_more_anomalous",
                         statistical_baseline_flag_threshold: 3.0},
       module_threshold}

GET /evaluation/{model_id}
    → evaluation-summary.json verbatim + {artifact_hash}

GET /healthy-reference/{model_id}
    → healthy-reference.json verbatim (model_id, declared_by, selection,
      declaration_note, signals{<signal>:{n,mean,std}})   | 404 if absent

GET /corpus
    → {corpus_version, generated_at, note,
       counts_by_verification_status, counts_by_source_type,
       collection: {name: "evidence", chunk_count, embedding_model},
       documents: [corpus.json entry fields]}

GET /corpus/documents/{document_id}
    → single corpus.json entry | 404

GET /evidence/{evidence_id}?investigation_id=
    → EvidenceRecord as stored on that investigation + resolved corpus document
    NOTE: retrieval is query-driven and not addressable by chunk id in
          ChromaRetriever, so evidence lookup is scoped to an investigation. [M10 REQ]

GET /investigations/{investigation_id}/provenance
    → [ProvenanceEntry] + {artifact_hashes: snapshot_m7_m8(model_id)}

GET /investigations/{investigation_id}/deterministic-results
    → [DeterministicResult]        (deterministic-results.json)

GET /investigations/{investigation_id}/hypothesis
    → Hypothesis | null

GET /investigations/{investigation_id}/evidence
    → {evidence_queries: str[], evidence_records: EvidenceRecord[],
       provenance_complete: bool}
```

Also required on `/investigations` (list): `status` facet, `limit`/`offset`, and
`sort=created_at`, because `InvestigationPersistence.list_investigations()` currently loads and
validates **every** record on every call — see §19.4.

### 10.3 [M10 REQUIREMENT] Asynchronous investigation execution

Needed because a real OpenRouter run takes minutes (`LLM_TIMEOUT` default `120` s per request, with
up to 2 hypothesis retries and 2 evidence rounds) and the current `POST /investigations` blocks.

```text
POST /investigations/runs        body: InvestigationRequest (unchanged shape)
     → 202 {run_id, investigation_id, status: "PENDING", accepted_at}

GET  /investigations/runs/{run_id}
     → {run_id, investigation_id, status: InvestigationStatus,
        current_step: str|null,          # last ProvenanceEntry.step
        completed_steps: str[],          # provenance steps so far
        retry_counts: {evidence_round, hypothesis_retries, report_retries},
        errors: {}, started_at, finished_at|null}

DELETE /investigations/runs/{run_id}     → cancel a queued run only
```

`current_step` / `completed_steps` must be derived from real accumulated provenance, not a timer.
`architecture.md` §31 already states *"Long-running operations such as training and investigation
should execute asynchronously."*

**Constraint on this requirement:** `run_investigation` returns only on completion and does not emit
intermediate events, so per-stage live progress requires either (a) a worker that persists partial
state, or (b) LangGraph streaming. Until one is implemented, the run endpoint can report only
`PENDING` → `COMPLETED`/`PARTIAL`/`FAILED`, and the UI must degrade per §6.3.

`POST /investigations` is **kept unchanged** for backward compatibility (§18).

### 10.4 [M10 REQUIREMENT] Platform concerns on the API

* **CORS** — required for the Vercel-hosted frontend; allowed origins from configuration, never `*`
  once auth exists.
* **Readiness probe** extending `/health`:
  `GET /readiness` → `{artifacts: {features, scores, evaluation, models, healthy_reference},
  chroma: {reachable, chunk_count}, llm: {provider, model, endpoint_host, configured}}`.
  **Never** the API key.
* **Error envelope** — a consistent `{detail}` (FastAPI's default) with correct status codes.
  `POST /investigations` currently maps *every* exception to `500`; M10 requires `404` for an unknown
  `module_id`/`model_id` (raised as `DataAccessError`) and `503` when the LLM endpoint is
  unreachable, so the UI can distinguish §14 states.
* **Auth** — Clerk is the documented mechanism (`tech-stack.md`); §15.3.

### 10.5 Frontend types

Generated from the FastAPI OpenAPI schema so they cannot drift from the Pydantic models. Names follow
`architecture.md`/`PRD.md` (`ModuleProfile`, `TestProfile`), not the older `tech-stack.md` list
(`Component`, `TestRun`) — consistent with reconciliation note 3 in `docs/implementation-status.md`.

```ts
InvestigationRecord  InvestigationReport  InvestigationStatus
ModuleTrajectory     DeterministicResult  ProvenanceEntry
EvidenceRecord       Hypothesis  CandidateMechanism  HypothesisStatus  MechanismType
ReportSection        Finding     FindingClassification
ModuleSummary        ModuleEvaluation     TimingAnalysis  BaselineComparison
ModelRecord          EvaluationSummary    CorpusDocument  HealthyReference
TelemetrySeries      RunStatus
```

Enum members are rendered from these unions; **no string literal may be hand-written in a component**.

### 10.6 Export contracts

| Format | Basis | Status |
| --- | --- | --- |
| JSON — investigation record | `GET /investigations/{id}` | **exists** |
| JSON — report | `GET /investigations/{id}/report` | **exists** |
| JSON — deterministic results, provenance | files on disk | **[M10 REQ]** endpoint |
| Markdown — report | `InvestigationReport.full_text` (already Markdown) | **[M10 REQ]** endpoint or client-side download |
| PDF | `reportlab` is a declared dependency and `scripts/investigate.py` has a `--no-pdf` flag, but **no PDF generation code exists** | **NOT IMPLEMENTED — must not be offered** |

Every export carries `investigation_id`, `module_id`, `model_id`, `dataset_id`, `created_at`, the
provenance list, and the synthetic-data label.

### 10.7 Optional backend changes M10 would benefit from (not assumed)

1. `evidence_queries` as structured objects carrying the motivating `tool_name`/`signal`, which would
   make §9.2 authoritative instead of derived.
2. A stable `investigations/index.json` to avoid the O(n) full-record scan in
   `list_investigations()`.
3. Persisting `evidence_status` on `InvestigationRecord` — the `EvidenceAgent` returns it but
   `InvestigationRecord` has no such field, so it is lost.

M10 must work correctly without any of these.

## 11. Persistence and Artifacts

### 11.1 Layout M10 reads

```text
ml/
├── models/<model_id>/model-record.json
├── datasets/
│   ├── features/v1/observation-features.parquet      (160 cols)
│   │                module-features.parquet          (929 cols)
│   ├── scores/<model_id>/observation-scores.parquet   (375 750 rows)
│   │                     module-summary.parquet       (750 rows)
│   ├── evaluation/<model_id>/evaluation-summary.json
│   │                         module-evaluation.parquet (750)
│   │                         timing-analysis.parquet   (86)
│   │                         baseline-comparison.parquet (750)
│   └── investigations/
│       ├── reference/healthy-reference.json
│       └── inv-<12hex>/
│             investigation-record.json     InvestigationRecord (full)
│             investigation-report.json     InvestigationReport
│             deterministic-results.json    List[DeterministicResult]
│             provenance.json               List[ProvenanceEntry]
knowledge_base/
├── metadata/corpus.json          37 entries, corpus_version 1.0.0
├── corpus/{standards,manufacturers,papers,reviews,internal}/*.pdf
├── chroma/                       collection "evidence", 360 chunks
└── reports/corpus-coverage.md
```

### 11.2 Write boundary

M10 writes **nothing** directly. The only filesystem effect of using M10 is that
`Run Investigation` calls the existing `run_investigation`, which creates one new
`ml/datasets/investigations/inv-<12hex>/` directory through `InvestigationPersistence`.

All other paths are read-only to M10. This is enforced by construction: the M10 API layer calls only
reader methods.

### 11.3 Size and self-containment

`investigation-record.json` embeds `module_trajectory.signals` — 8 × 501 floats for the canonical
module — making the canonical record ~217 KB. Consequences:

* Records are **self-contained**: a stored investigation can be replayed without re-reading M6/M7
  parquet. M10 should prefer the record for historical views to guarantee it shows what the
  investigation actually saw.
* `GET /investigations/{id}` is heavy. The workspace must not fetch it to render a list row; that is
  what the list projection and the narrower sub-resources in §10.2 are for.
* `InvestigationRecord` is written with `exclude_none=True`, so optional fields may be **absent**
  rather than `null`. Clients must treat absent and null identically (§18.2).

### 11.4 Artifacts M10 must not treat as durable

`ml/datasets/synthetic/`, `ml/datasets/features/`, `ml/datasets/scores/`,
`ml/datasets/evaluation/` and `ml/datasets/investigations/` are **gitignored local artifacts**. A
fresh clone has none of them. M10 must therefore treat every artifact as possibly absent and render
the §14.1 uninitialised state rather than erroring — including the canonical
`inv-70207e0ffd15` used by demonstration mode.

## 12. Provenance

### 12.1 Provenance is a primary surface, not a debug panel

`architecture.md` §3.7 requires that *"every model result and engineering hypothesis should be
traceable to telemetry, calculations, configuration, and supporting sources."* M10 gives provenance
a dedicated inspector reachable from any claim, plus an always-available trace affordance on
findings, candidates and evidence records.

### 12.2 Recorded provenance entries

`ProvenanceEntry` = `step`, `source`, `description`, `timestamp`. The canonical investigation has 8
entries, and the exact `(step, source)` pairs the backend writes are:

| `step` | `source` |
| --- | --- |
| `initialization` | `run_investigation` |
| `load_investigation` | `orchestrator` |
| `investigation_agent` | `deterministic_tools` |
| `evidence_agent` | `chromadb_evidence_collection` |
| `hypothesis_agent` | `llm:<provider>/<model>` |
| `hypothesis_validation` | `hypothesis_validation_gate` |
| `report_agent` | `report_agent` |
| `report_validation` | `report_validation_gate` |

Because retries append entries, the provenance list is the authoritative record of the **path
actually taken**, including repeats. M10 renders it as an ordered trace, not a deduplicated set —
a second `evidence_agent` entry is meaningful information.

### 12.3 Evidence provenance completeness

`backend/knowledge/models.py` states that *"a record that cannot name its `document_id`, `citation`
and `url` is not provenance-preserving."* M10 renders a per-record completeness indicator over
`document_id`, `chunk_id`, `citation`, `url`, `page_start`, `page_end`, and names any missing field.

An evidence record that cannot be resolved to a corpus document must be shown as
**unresolved provenance**, never silently displayed as a citation. `verification_status` of the
resolved document is always shown; only `VERIFIED` documents should appear, and anything else is an
integrity warning.

### 12.4 The five registers (epistemic visual language)

Non-negotiable separation, each with a distinct treatment and a **text/shape label as well as
colour** (§ accessibility, Appendix A):

| Register | Contains | Sourced from |
| --- | --- | --- |
| **DATA** | signal samples, cycle numbers, counts, `anomaly_score`, `is_anomaly` | M6/M7 parquet |
| **CALCULATION** | `DeterministicResult.output`, M8 metrics, thresholds | fixed tools / M8 |
| **RETRIEVED EVIDENCE** | passages, citations, page ranges, axes | ChromaDB + corpus |
| **LLM REASONING** | `CandidateMechanism.reasoning`, `confidence`, `status`, `Hypothesis.note` | hypothesis agent |
| **VALIDATION** | gate outcomes, rejected ids, retry counts | validation gates |

Two additional presentational registers:

* **GROUND TRUTH (synthetic, evaluation-only)** — `health_state`, `degradation_mechanism`,
  `degradation_stage`, `onset_cycle`, `cycle_measurable`, `degradation_severity`,
  `damage_index_end`, `y_true`. Always explicitly labelled; never shown as a SmartESS output.
* **HUMAN DECISION** — currently always empty, because the backend stores no engineer verdict
  (§20.6). It is rendered as an explicit *awaiting engineer review* placeholder, never pre-filled.

`FindingClassification` maps onto these registers: `OBSERVED` → DATA, `CALCULATED` → CALCULATION,
`PREDICTED` → CALCULATION (model-derived), `HYPOTHESIZED` → LLM REASONING, `RECOMMENDED` → a
recommendation treatment, `CONFIRMED` → HUMAN DECISION. In practice `CONFIRMED` never appears:
`validate_report` **rejects** any `CONFIRMED` mechanism finding. M10 still implements the treatment
and surfaces its absence as a feature.

### 12.5 Artifact hashes

`DataAccess._hash_file` yields a 16-char SHA-256 prefix. `snapshot_m7_m8(model_id)` hashes the six
M7/M8 artifacts, and `model_record()` attaches `_hash` and `_source_path`. M10 displays these in the
Provenance Inspector in monospace as reproducibility identity, and shows the `pipeline._verify_immutable`
outcome — noting that a mismatch currently raises a Python `warnings.warn`, which is **not captured
into the record** and so cannot be displayed (§20.7).

## 13. Determinism and Reproducibility

### 13.1 What is deterministic

| Deterministic | Why |
| --- | --- |
| M6 features | documented as deterministic, versioned, causal, leakage-safe |
| M7 scores | frozen artifacts, `random_state=20260922`; M10 never re-scores |
| M8 metrics | evaluation-only over frozen scores |
| All 9 deterministic tools | fixed numeric methods (`first_vs_last`, `linear_regression_polyfit_degree_1`, `endpoint_percent_change`, `linear_regression_value_vs_cycle`, `sliding_window_mean_difference`, `pearson_correlation`) |
| `evidence_queries` | built by fixed lookup tables from deterministic results |
| `investigation_id` / `hypothesis_id` / `candidate_id` | `investigation_id` is random per run, but `_stamp_hypothesis_ids` derives `<inv_id>-hyp-c<N>` deterministically from candidate order, *"so they never depend on model behaviour"* |
| Report structure | 15 fixed sections; `ReportAgent` *"recalculates nothing, invents nothing"* |
| Validation gates | pure functions of hypothesis/report + retrieved evidence |

### 13.2 What is not deterministic

* **LLM output.** `temperature=0.1`, not `0`; the provider is remote and versioned outside SmartESS.
  `CandidateMechanism.reasoning`, `confidence`, `status`, ordering, and `primary_mechanism` can all
  differ between runs on identical inputs.
* **Retrieval ordering** can shift if the collection is re-ingested (chunk ids are stable, but
  neighbour ordering depends on collection contents).
* **Evidence selection** depends on `max_evidence` and on the loop short-circuit in
  `EvidenceAgent.run` (`if len(records) >= self.max_evidence: break`), so a different
  `max_evidence` changes which queries actually execute.

### 13.3 Reproducibility surface

Every investigation view shows a **Reproducibility** block:

```text
investigation_id  inv-70207e0ffd15
created_at        2026-09-24T08:16:07.090184+00:00
module_id         syn-mod-0042
model_id          iforest-v1-syn-sic-pc-dev-001-s20260922
dataset_id        syn-sic-pc-dev-001
feature_version   v1        detector_version v1
algorithm         isolation_forest      contamination 0.10   random_state 20260922
split             lot_holdout · train lot-02,lot-03,lot-05 · test lot-01,lot-04
corpus_version    1.0.0     collection evidence · 360 chunks
embedding_model   sentence-transformers/all-MiniLM-L6-v2
llm_provider      openrouter
llm_model         nvidia/nemotron-3-ultra-550b-a55b:free   # historical run
inference         real | mocked
prompt_version    m9-v1     temperature 0.1
retry_counts      evidence_round 1 · hypothesis_retries 0 · report_retries 0
artifact_hashes   6 M7/M8 artifacts (16-char sha256 prefixes)
```

The UI states plainly that re-running will reproduce the deterministic findings and the evidence
queries, but **may** produce different LLM reasoning — and never implies a run is bit-reproducible.

### 13.4 Provenance gaps M10 must not paper over

Fields **not** recorded on `InvestigationRecord`, and therefore shown as `not recorded` rather than
inferred:

* `corpus_version` and the ChromaDB chunk count at investigation time (only current values are
  readable);
* the LLM provider/model as structured fields — they exist only inside the
  `hypothesis_agent` provenance `source` string `llm:<provider>/<model>`, which M10 parses and labels
  as **derived from provenance text**;
* whether inference was real or mocked — inferable only from that same string (a mock client reports
  its own provider name), so it is presented with that caveat;
* `evidence_status`, which the agent computes but the record does not persist.

## 14. Failure Handling

The design requirement is that these states are **mutually distinguishable**. "No data", "no
anomaly", "insufficient evidence" and "system error" must never share a presentation.

### 14.1 Uninitialised / missing artifacts

`DataAccess._path` raises `DataAccessError(f"Artifact not found: {p}")`. A fresh clone has no
`ml/datasets/` at all (§11.4).

Presentation: a **Pipeline Readiness** panel listing each required artifact with present/absent and
the exact expected path, plus the CLI that produces it —
`scripts/generate_synthetic_dataset.py` → `scripts/build_features.py` →
`scripts/train_anomaly_model.py` → `scripts/evaluate_anomaly.py` → `scripts/ingest_knowledge.py` →
`scripts/build_healthy_reference.py`. This is a setup state, not an error.

### 14.2 Unknown module or model

`DataAccessError(f"module_id {module_id} not in module-summary")`. Presentation: *module not present
in this model's scored population*, with the model's `dataset_id` and a link back to Module Explorer.
Requires the `404` mapping in §10.4 — today this surfaces as `500`.

### 14.3 No anomaly — explicitly not "no data"

`module_anomaly_status = clean` (60 of 750 modules), or `y_pred_module = False`.

Presentation: a neutral, affirmative statement — *no observation exceeded the detector threshold for
this module* — with `n_observations`, `anomaly_rate = 0.0`, and the threshold value. Neutral styling,
never an empty chart and never an alarm. The statistical-baseline comparator is shown alongside,
because it can disagree (canonical `syn-mod-0042`: `if_flag_module = false` but
`base_flag_module = true`) — a disagreement M10 must present as a genuine analytical finding.

### 14.4 Module absent from timing analysis

`m8_timing = {"note": "module not in timing analysis (healthy or undetected)"}`; only 86 of 750
modules appear.

Presentation: render the note verbatim and state that timing is defined only for detected positives.
Never draw a zero-lead marker, and never imply lead time is `0`.

### 14.5 Missing healthy reference

`HealthyReferenceSelector.load()` returns `None`, and the agent records
`population_comparison_skipped: no healthy reference artifact at
ml/datasets/investigations/reference/healthy-reference.json`.

Presentation: the population-comparison panel shows *not performed* with the recorded limitation and
the producing CLI. No `compare_population` results exist, so no z-score is displayed. M10 must not
compute one.

### 14.6 Empty knowledge base

`ChromaRetriever.count() == 0` → `evidence_status = "unavailable"` and the limitation
`knowledge_base_empty: no ingested evidence; returning no evidence records`.

Presentation: Evidence Explorer shows *knowledge base not ingested*, the `scripts/ingest_knowledge.py`
remedy, and an explicit warning that **hypotheses generated without evidence will be rejected by
`hypothesis_validation`** — because any `CANDIDATE`/`SUPPORTED`/`CONTRADICTED` candidate needs at
least one resolvable supporting id.

### 14.7 Retrieval failure mid-run

`EvidenceAgent.run` wraps each query in `try/except Exception: continue`, so an individual query can
fail silently and is **not** recorded.

Presentation: because failures are invisible, M10 shows *n of m queries returned records* computed
from the stored `evidence_queries` and `evidence_records`, and states that per-query failures are not
recorded by the backend. This is an honest limitation, not an inference.

### 14.8 LLM unavailable, unauthenticated, rate-limited, or paying

`HypothesisAgent.run` catches every exception and returns an empty `Hypothesis` with
`note="llm_failed"`, `errors["hypothesis"] = f"LLM failure ({provider}): {e}"`, and the limitation
`llm_reasoning_unavailable`. `note="llm_unavailable"` when the client is `None`. The record status
becomes `PARTIAL`.

Presentation: the hypothesis stage renders as **failed**, the deterministic and evidence stages remain
fully inspectable, and the LLM register is empty rather than substituted. The `errors["hypothesis"]`
text is shown verbatim in monospace, since it is the only signal distinguishing an auth failure from
a rate limit.

Known real case: the repository records that the paid
`nvidia/nemotron-3-ultra-550b-a55b` endpoint returned `402 Payment Required` for an
investigation-sized request and the `:free` endpoint was used instead. M10 must surface such provider
errors literally and must never retry a paid endpoint automatically or silently substitute a model.

The `errors` map values are truncated to 2000 characters by the orchestrator for the validation keys;
M10 must not present a truncated message as complete.

### 14.9 Mocked inference

When `LLMSettings.configured` is false, `create_llm_client` yields a mock client. Reasoning is not
model-generated.

Presentation: a persistent, non-dismissible banner on the investigation — *mocked inference: no
model-generated reasoning* — and the LLM register marked mocked throughout. This is the single most
important honesty state in M10, because a mocked run can otherwise look identical to a real one.

### 14.10 Hypothesis validation rejected

After `MAX_HYPOTHESIS_RETRIES = 2` (and up to `MAX_EVIDENCE_ROUNDS = 2`), routing proceeds to
`report_agent` **anyway** with `errors["hypothesis_validation"]` set.

Presentation: this is a critical nuance — the report exists *despite* a failed gate. The report view
must carry a prominent *hypothesis validation REJECTED* marker, list the specific issues, and show
the retry counts that were exhausted. Rendering such a report as clean would misrepresent the system.

### 14.11 Report validation rejected

`_route_after_report_validation` retries only when `report is None`; otherwise it ends with
`errors["report_validation"]` recorded. `ReportAgent` also appends
`report_validation_failed: <error>` into the `Limitations` section on a subsequent build.

Presentation: report shown with a *validation REJECTED* header and the enumerated issues — missing
sections, unresolved citations by finding label, `CONFIRMED` mechanism findings, empty narrative,
matched certainty phrases, absent provenance.

### 14.12 No candidates

`Hypothesis.candidates == []` with a `note`. Presentation: **Anomaly Detected — Mechanism
Unresolved** (the `agent-rules.md` §16 phrase) when M7 flagged the module, otherwise *no candidate
mechanism proposed*, with the note verbatim. Never an empty panel.

### 14.13 Partial investigation

21 of 69 stored investigations are `PARTIAL`. Presentation: `PARTIAL` is rendered as a first-class
status with the `errors` keys naming which stages failed, and every successful stage remains
inspectable. A `PARTIAL` record is never shown as `COMPLETED`.

### 14.14 Report absent

`InvestigationRecord.report` is `Optional`; `GET /investigations/{id}/report` can return `null` for an
existing investigation. Presentation: *report not produced*, with the reason from `errors` if present.

### 14.15 Network and client-side states

Per-panel loading skeletons that preserve layout; per-panel error states with retry that never
discard already-loaded context; the persistent context rail remains populated during any failure so
the engineer never loses track of which module is being investigated.

### 14.16 State disambiguation matrix

| State | Signal | Register |
| --- | --- | --- |
| NO DATA | `DataAccessError`, artifact absent | setup |
| NO ANOMALY | `module_anomaly_status = clean`, `y_pred_module = false` | data |
| NOT APPLICABLE | `m8_timing.note` | data |
| ANALYSIS NOT PERFORMED | `population_comparison_skipped` | calculation |
| NO EVIDENCE | `evidence_status = unavailable`, `knowledge_base_empty` | retrieval |
| INSUFFICIENT EVIDENCE | `HypothesisStatus.INSUFFICIENT_EVIDENCE` | LLM reasoning |
| AMBIGUOUS | `HypothesisStatus.AMBIGUOUS` | LLM reasoning |
| MECHANISM UNRESOLVED | flagged + no candidates | LLM reasoning |
| REASONING UNAVAILABLE | `llm_failed` / `llm_unavailable` | system |
| MOCKED | `LLMSettings.configured == false` | system |
| VALIDATION REJECTED | `errors[*_validation]` | validation |
| PARTIAL | `status = PARTIAL` | system |
| SYSTEM ERROR | HTTP 5xx | system |

## 15. Security and Configuration

### 15.1 Secrets

`LLM_API_KEY` (with `OPENROUTER_API_KEY` as a fallback source) *"is never hard-coded, printed, logged,
or persisted."* M10 inherits this absolutely:

* The key is **never** returned by any endpoint, including `/readiness`.
* The key never reaches the browser. All LLM calls originate in the backend.
* `LLMSettings.endpoint_host` exists precisely because it is *"safe to log"*; M10 displays
  `provider`, `model`, `endpoint_host`, `configured`, `prompt_version`, `timeout` — and nothing else.
* Provider error text (e.g. `402 Payment Required`) is displayed, so the API must ensure such
  messages never echo an Authorization header. This is a review item for the §10.3 run endpoint.

`.env` is git-ignored; `.env.example` carries empty key fields. M10 adds no new secret.

### 15.2 Configuration surfaced

Read-only. M10 **never writes** configuration, never offers a model picker that changes server
settings, and never lets the UI select an LLM provider — that is environment configuration.

| Variable | Use in M10 |
| --- | --- |
| `LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_TIMEOUT` | displayed as provenance |
| `LLM_API_KEY` / `OPENROUTER_API_KEY` | presence only, as `configured: true/false` |
| `EMBEDDING_MODEL` / `LLM_EMBEDDING_MODEL` | displayed as retrieval provenance |
| `CHROMA_PATH` / `LLM_CHROMA_PATH` | displayed as knowledge-base identity |
| `DATABASE_URL` | unused by M10 — no persistence layer exists |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY` | §15.3 |
| `OBJECT_STORAGE_PATH`, `KNOWLEDGE_BASE_PATH` | artifact roots |

**[M10 REQUIREMENT]** `SMARTESS_API_BASE_URL` for the frontend, and a CORS allow-list variable.

### 15.3 Authentication

Clerk is documented but not implemented anywhere in the repository. M10's position:

* The **design** assumes Clerk protects the frontend and that the API validates the session, matching
  `tech-stack.md`.
* The **implementation phasing** puts auth in M10-H, and until then the API must bind to localhost
  and the UI must display an *unauthenticated prototype* indicator.
* `PRD.md` lists five roles (reliability, test, failure-analysis, quality engineers; engineering
  managers). No role model, permission or ownership field exists in any backend model. M10 therefore
  ships **one role** — engineer — and must not render a role-based UI it cannot enforce (§20.5).

### 15.4 Data-sensitivity posture

Every dataset in the repository is `data_origin=synthetic`. The synthetic label is **mandatory and
persistent**: context rail, every chart, every report view, every export. `agent-rules.md` §17:
synthetic data *"must never be represented as production telemetry."*

### 15.5 Execution safety

`Run Investigation` triggers a remote LLM call and costs money. Confirmation is mandatory and states
the provider, model and endpoint host. No auto-run, no retry-on-failure without explicit user action,
no background pre-warming that issues inference. `DELETE` on a queued run (§10.3) cancels only
queued work — the current synchronous graph cannot be interrupted mid-flight.

## 16. Observability and Auditability

### 16.1 The audit question

From the UI alone, a reviewer must be able to reconstruct: which module, which frozen model and
dataset, which deterministic calculations, which retrieved passages from which verified documents,
which model produced which reasoning, whether both gates passed, what was uncertain, and what is
still unconfirmed.

Every element of that answer exists in `InvestigationRecord` today. M10's contribution is exposure,
not new instrumentation.

### 16.2 Audit view content

Per investigation: the reproducibility block (§13.3); the ordered provenance trace including repeats;
both gate outcomes with issue lists; `retry_counts`; the full `errors` map; the `limitations` list;
per-evidence provenance completeness; the six M7/M8 artifact hashes; and the count summary
(deterministic results by tool, evidence queries, evidence records, candidates by status, report
sections, findings by classification).

### 16.3 Cross-investigation observability

Derived only from the investigations index and stored records:
`COMPLETED` vs `PARTIAL` counts (47/21 today); gate rejection frequency; retry-count distribution;
which modules have been investigated; mechanism-status distribution; and how often runs were mocked.

These are **operational statistics about SmartESS**, not engineering claims about the hardware, and
must be labelled as such so no one mistakes a mechanism frequency for a failure-rate finding.

### 16.4 What is not observable

* No structured application logging or event table exists; the backend prints only via the CLI.
  M10 cannot show backend logs.
* No per-stage timing is recorded — only `created_at` on the record and `timestamp` per provenance
  entry, from which inter-stage deltas can be derived and must be labelled **derived**.
* No token usage, cost or latency is recorded by the LLM layer.
* Per-query retrieval failures are swallowed (§14.7).

M10 must not display any of these as if measured.

## 17. Validation and Testing

### 17.1 Constraint

The existing suite is **359 passing, 0 failed, 0 skipped** (`python3 -m pytest -W error`), covering
M1–M9 including `test_m9_investigation.py`, `test_m9_tools.py`, `test_m9_llm.py`, `test_m9_rag.py`,
`test_m9_corpus.py`, `test_m9_data_access.py`. M10 must not modify or weaken any of it. No ruff, mypy
or frontend toolchain is configured yet — M10 introduces the frontend toolchain.

### 17.2 Backend tests for the M10 API layer (new files only)

`backend/tests/test_m10_api.py` and `backend/tests/test_m10_projection.py`, using FastAPI's
`TestClient`:

* every new endpoint returns the documented shape and status codes;
* projection endpoints return values **byte-identical** to `DataAccess` return values — the
  regression guard against the API recomputing anything;
* unknown `module_id`/`model_id` → `404`, not `500`;
* telemetry endpoint: `NaN` → `null`; downsampling preserves every `is_anomaly == true` point;
  `returned_points <= max_points`; `downsampled` flag correct;
* `/readiness` never contains the API key — assert against the serialised body;
* missing-artifact paths produce the documented readiness response, not an unhandled exception;
* `POST /investigations` request/response shape is unchanged (backward-compatibility test);
* a `PARTIAL` fixture record round-trips with `errors` and `limitations` intact;
* `exclude_none=True` records parse correctly when optional fields are absent.

### 17.3 Frontend tests

* **Type generation check** in CI: regenerate types from the live OpenAPI schema and fail on drift.
* **Component tests** for every §14 state, asserting that each renders a *distinct* string —
  explicitly asserting that "no anomaly", "no data" and "insufficient evidence" differ.
* **Register-rendering tests**: a `HYPOTHESIZED` finding must not render with `OBSERVED` treatment;
  every `HypothesisStatus` and `FindingClassification` member has a defined treatment; an unknown
  enum value renders as unknown rather than defaulting (§18.3).
* **Numeric fidelity tests**: rendered values equal API values at documented precision; no client-side
  rounding that changes a reported figure.
* **Traceability tests**: from a finding with `evidence_ids`, the evidence record is reachable; from a
  candidate, both id lists resolve; an unresolvable id renders as unresolved.
* **Honesty tests**: a mocked-inference fixture renders the mocked banner; a rejected-gate fixture
  renders the rejection on the report; `distance` is never rendered with a `%` sign; PDF export is
  never offered.
* **Accessibility tests**: axe checks, keyboard traversal of the workspace, and an assertion that no
  state is conveyed by colour alone.

### 17.4 End-to-end validation

Against the canonical artifacts, asserting M10 displays exactly the backend's numbers:

1. Module `syn-mod-0042` shows `n_observations = 501`, `anomaly_rate = 0.027944111776447105`,
   `max_anomaly_score = 0.032073692884248106`, `module_anomaly_status = sporadic`.
2. M8 panel shows `y_true = false`, `y_pred_module = false`,
   `statistical_baseline_flag_module = true`, `y_pred_baseline = true`, and the
   *module not in timing analysis* note — with `health_state = healthy` in the ground-truth register.
3. Investigation `inv-70207e0ffd15` shows 40 deterministic results across 5 tools, 8 evidence
   queries, 5 evidence records with complete provenance, 5 candidates
   (`inv-70207e0ffd15-hyp-c1..c5`), both gates `PASSED`, 15 report sections, and
   `retry_counts = {1, 0, 0}`.
4. Report claims trace to evidence records and on to corpus documents.
5. Population metrics render as 0.9149 / 0.3822 / 0.5392 / 0.0152 (overall) and
   0.8776 / 0.4778 / 0.6187 / 0.0286 (test lots) — never averaged, blended or rounded into one figure.
6. Negative `lead_vs_onset` values render as negative (§19.3).

### 17.5 Regression guard on M1–M9

CI runs `python3 -m pytest -W error` and requires the same pass count before and after M10 work, plus
`python3 -m compileall -q backend ml scripts`. A hash check asserts the six M7/M8 artifacts are
unchanged by any M10 test run.

## 18. Migration and Backward Compatibility

### 18.1 Nothing to migrate, everything to read

M10 introduces no schema change, no database and no artifact rewrite. The 69 existing investigation
directories must be readable **as they are**, unmodified. M10 is additive: new routers, new frontend.

`POST /investigations`, `GET /investigations`, `GET /investigations/{id}` and
`GET /investigations/{id}/report` keep their exact current shapes so `scripts/investigate.py` and any
existing consumer continue to work. The async run endpoint (§10.3) is added **alongside**, never as a
replacement.

### 18.2 Tolerating existing record variation

The stored records were written across the M9 development period and are not uniform. M10 must handle:

* **`exclude_none=True` omissions** — optional fields are absent rather than `null`. Absent and null
  are treated identically; never rendered as `0`, `""` or `false`.
* **`module_trajectory = null`** — possible when the investigation agent failed. Signal panels show
  *trajectory not recorded*.
* **`hypothesis = null` / `report = null`** — §14.12, §14.14.
* **`m8_timing = {"note": ...}`** — a one-key dict, not a timing row (§14.4).
* **`m8_baseline = {}`** — `baseline_comparison` returns `{}` when the module is absent.
* **`agent_messages = {}`** — always empty in practice; no producer writes it. Render nothing.
* **`retry_counts` missing keys** — default to `0` for display only, labelled as absent if the map
  itself is missing.
* **`status` as a string or an enum value** — `list_investigations` already normalises via
  `rec.status.value if hasattr(...)`. Clients accept the string form.
* **21 `PARTIAL` records** whose `errors` keys vary. No key set may be assumed.

### 18.3 Forward compatibility with enum growth

M9 enums may gain members. Every enum-driven component must have an explicit **unknown** branch that
renders the raw string in the neutral treatment and never falls back to a semantically loaded style.
A new `MechanismType` must never be rendered as `other`, and a new `HypothesisStatus` must never be
rendered as `SUPPORTED`. The §17.3 register tests enforce this.

### 18.4 Multi-model and multi-dataset readiness

Only one model and one dataset exist today. Every endpoint and view is nonetheless keyed by
`model_id` (and `dataset_id` where relevant) so a second model requires no redesign. The UI must not
hard-code `iforest-v1-syn-sic-pc-dev-001-s20260922`; it is a default obtained from `GET /models`.

### 18.5 Naming reconciliation

`docs/implementation-status.md` records that the product is called **SmartESS** in the repository and
`tech-stack.md`, but **BurnInGuard AI** in `PRD.md`, `architecture.md` and `agent-rules.md`. M10 uses
**SmartESS** throughout the interface, consistent with the repository, and does not modify the source
documents. Domain entities use the `architecture.md`/`PRD.md` names (`ModuleProfile`, `TestProfile`)
per reconciliation note 3.

## 19. Risks

### 19.1 Misrepresenting retrieval distance as relevance

`retrieval_metadata.distance` is a raw vector distance (canonical example `0.4682258367538452`),
stored as a string, where **lower is closer**. Rendering it as "53% relevant" or sorting it as a score
would fabricate a quantity.
**Mitigation:** display the raw value with the label *vector distance (lower = closer)*; never a
percentage, bar or star rating; §17.3 asserts no `%` is rendered for `distance`. The same applies to
`EvidenceRecord.confidence`, which is an unset default of `0.5`.

### 19.2 Downsampling hiding anomalies

501 points per module is trivial, but `observation-scores.parquet` holds 375 750 rows and a
population view could require aggressive reduction. Naive decimation can drop the very observations
that matter.
**Mitigation:** downsampling happens server-side, is flagged in the response, preserves every
`is_anomaly == true` and `statistical_baseline_flag == true` point, and is tested. The UI states when
a view is downsampled.

### 19.3 Presenting negative lead time as early warning

Mean `lead_vs_onset` is approximately `-37165` cycles: the detector fires **long after** onset. An
absolute-value axis, a "lead time" label, or a positive-framed KPI would invert the finding.
**Mitigation:** the metric is labelled `lead_vs_onset (cycles; negative = flagged after onset)`, the
axis crosses zero, and the M8 view states the direction explicitly. This is also a demonstration-mode
requirement (§ Appendix B, M10-H).

### 19.4 Investigation list performance

`InvestigationPersistence.list_investigations()` iterates every directory and fully validates each
`investigation-record.json` — including embedded trajectories — on every call. At 69 records this is
already wasteful; it grows linearly and unboundedly.
**Mitigation:** the M10 list endpoint adds pagination and caching, and §10.7 proposes an index file.
M10 must not call the list endpoint on every route transition.

### 19.5 Deployment path assumptions

`DataAccess` and `InvestigationPersistence` resolve paths relative to the repository root via
`Path(__file__).resolve().parents[3]`. A Vercel frontend plus a separately hosted API means the API
host must have the gitignored `ml/datasets/` and `knowledge_base/` artifacts on its own filesystem.
**Mitigation:** documented as an operational prerequisite; `/readiness` reports artifact presence so
a misconfigured deployment is immediately visible rather than silently empty.

### 19.6 The canonical demonstration module is healthy

`inv-70207e0ffd15` investigates `syn-mod-0042`, whose ground truth is `health_state = healthy`,
`y_true = false`, and whose module-level prediction is `y_pred_module = false` — yet the LLM produced
five candidates including `gate_related` with status `SUPPORTED` and `confidence = 0.85`.

This is a genuine and instructive result: the module is `sporadic` at observation level, the
statistical baseline flags it (`base_flag_module = true`) while the model does not, and the LLM
reasoned over real deterministic drift on `IGSS` and `VTH`. But a UI that showed the hypothesis
prominently without that context would imply a failure in a healthy part.
**Mitigation:** the module context — `module_anomaly_status`, `y_pred_module`, the baseline
disagreement, and the ground-truth register — is displayed adjacent to the hypothesis panel at all
times; `confidence` is labelled *model-assigned confidence in the candidate, not probability of
physical failure*; and demonstration mode uses this case explicitly to teach the anomaly-vs-failure
distinction rather than hiding it.

### 19.7 Confidence read as failure probability

`CandidateMechanism.confidence` is an LLM-assigned float in `[0,1]` with no calibration.
**Mitigation:** never rendered as a percentage-of-failure, never used to rank candidates into a
winner, never aggregated across candidates. Rendered as a bounded qualitative indicator with the
numeric value and an explicit label. `agent-rules.md` §13 offers the coarser vocabulary
*Low / Moderate / High Confidence* which M10 may show alongside the raw value, never instead of it.

### 19.8 The competing-hypotheses view collapsing into a verdict

`Hypothesis.primary_mechanism` exists (canonical value `gate_related`). Treating it as "the answer"
would defeat the scientific design.
**Mitigation:** `primary_mechanism` is shown as *model-nominated primary*, in the LLM register, with
equal visual weight given to all candidates in a side-by-side comparison. No global ranking score is
invented, and no candidate is styled as a winner.

### 19.9 Register bleed

The core failure mode for this product: a deterministic drift value and an LLM sentence rendered in
the same visual treatment.
**Mitigation:** register treatment is enforced at the component level — a shared primitive takes the
register as a required prop, so no ad-hoc text node can render a value without declaring its register.
Tested in §17.3.

### 19.10 Synchronous API blocking

A real investigation may exceed common gateway timeouts, producing a client error while the backend
completes and persists a record — leaving the UI wrong about what happened.
**Mitigation:** the async endpoint (§10.3); until then a long, explicit, non-cancellable progress
state, and on timeout the UI directs the engineer to Investigation History rather than declaring
failure.

## 20. Limitations

These are backend limitations M10 must expose rather than work around. **None of them may be
simulated.**

1. **No real `ModuleProfile` or `TestProfile` in an investigation.** `InvestigationAgent`
   `_build_module_profile` returns only `{module_id, feature_version}`, and `_build_test_profile`
   returns only `{split_type, test_lots}`. The rich M1/M2 contracts exist but are not wired in, and
   there is no ingestion or persistence for them. M10 therefore cannot show datasheet-derived
   ratings, thermal specifications, acceptance criteria or real test conditions. It shows the two
   stub objects and states that profile binding is not implemented.
2. **No acceptance-limit checking in practice.** `check_acceptance_limits` exists and reads
   `module_profile_acceptance_limits`, but the agent never calls it and no acceptance limits are
   available. No limit lines can be drawn on any chart.
3. **Four registered tools are never invoked** — `analyze_temperature_dependence`,
   `detect_change_point`, `calculate_correlation`, `check_acceptance_limits`. Consequently M10 has
   **no change-point markers**, no correlation matrix and no temperature-dependence panel derived
   from tool output, despite §19 of the original design brief asking for change-point markers. The
   tool registry is shown with invoked/not-invoked status, which is itself informative.
4. **`electrical_power` and other units are not carried in the data.** No engineering unit is
   attached to any signal in the feature or score artifacts; units would come from `ModuleProfile`,
   which is not wired in (limitation 1). M10 shows signal names without fabricated units, except
   where a document states them (`RDS_on` in mOhm, temperatures in °C per the feature docs), and
   those are labelled as documentation-derived.
5. **No user, role, project or ownership model.** No `User` or `Project` entity is implemented. The
   five `PRD.md` personas cannot be differentiated, and investigations have no owner.
6. **No human-decision persistence.** There is no field anywhere for an engineer's verdict, sign-off,
   comment or review state. The report's `Human Review` section contains only a fixed
   `RECOMMENDED` finding stating that the decision remains with the engineer. M10 renders an
   *awaiting engineer review* state and **cannot** record a decision. Adding it is a future backend
   change, explicitly out of M10 scope.
7. **Immutability warnings are not captured.** `_verify_immutable` emits `warnings.warn` and writes
   nothing to the record, so a hash mismatch cannot be displayed per investigation.
8. **No PDF export.** `reportlab` is a dependency and the CLI has `--no-pdf`, but no generator
   exists.
9. **No per-stage timing, token usage, cost or latency.**
10. **No lot-comparison or population artifact per lot.** `tech-stack.md` lists a "Lot Comparison"
    view; `lot_id` exists on every row, so lot facets and groupings are possible from
    `module-summary`, but no lot-level aggregate artifact exists and M10 must not compute reliability
    statistics per lot.
11. **Knowledge-base coverage is incomplete.** 13 `NEEDS_MANUAL_ACCESS`, 3 `UNVERIFIED`,
    1 `OCR_REQUIRED`, 1 `REJECTED`; `HTOL` thin; threshold-voltage hysteresis and
    high-temperature operating life unsupported. M10 surfaces the coverage report so an engineer can
    see what the evidence base cannot answer.
12. **Evidence is not addressable outside an investigation.** `ChromaRetriever` has no
    get-by-chunk-id, so there is no global evidence browser — only per-investigation evidence plus the
    corpus manifest.
13. **Observation-level ground truth does not exist.** `evaluation-summary.json` states that
    observation-level metrics are *"flag-rate summaries only"* with no precision/recall/F1/FPR. M10
    must not present any observation-level accuracy metric.
14. **Everything is synthetic.** No production telemetry exists. All metrics are split-specific and,
    per `docs/anomaly-detection/anomaly-detection.md`, *"not a universal accuracy claim."*

## 21. Explicit Non-Goals

M10 must **not**:

* retrain, re-score, re-evaluate, or change any threshold;
* modify M7, M8 or M9 code, artifacts or behaviour;
* redesign the LangGraph topology, replace LangGraph, or add a fifth agent;
* add or remove deterministic tools;
* re-ingest, re-embed or modify the knowledge base;
* introduce RUL, remaining-useful-life estimation, reinforcement learning, or any new model;
* add hardware control, test-equipment integration or any actuation;
* invent telemetry signals, units, acceptance limits, change points or correlations;
* fabricate evidence, citations, page numbers or sources;
* fabricate engineering conclusions, or assert any mechanism as a confirmed physical failure;
* compute any engineering value client-side;
* invent a global hypothesis ranking score or declare a winning mechanism;
* present `confidence` or `distance` as a probability of physical failure;
* simulate pipeline progress, or animate stages not backed by real state;
* offer PDF export, role-based views, human sign-off, or any other unimplemented capability;
* become a chatbot — no message-bubble transcript as the primary interaction model, no free-text
  question box implying conversational analysis;
* become a generic SaaS dashboard — no hero section, no marketing landing page, no decorative KPI
  cards, no gauge or donut charts for engineering data;
* hide uncertainty, limitations or validation rejections to make output look decisive.

## 22. Acceptance Criteria

M10 is **not** complete because the application renders. Each criterion is verifiable against the
canonical artifacts.

**Data and context**
1. An engineer can select a real module from the 750 in `module-summary.parquet`, faceted by
   `lot_id` and `module_anomaly_status`.
2. The persistent context rail always shows `module_id`, `test_id`, `lot_id`, `dataset_id`,
   `model_id`, `feature_version`, data origin (synthetic), `module_anomaly_status`, and the current
   `investigation_id`/status.
3. All 8 baseline signals render on a shared cycle axis with real values, correct null gaps, and no
   fabricated units.

**M7 and M8**
4. The M7 view shows `anomaly_score` with higher-is-more-anomalous semantics stated, `is_anomaly`
   markers, all 15 `module-summary` fields, and the model identity from `model-record.json`.
5. `ANOMALY DETECTED` is visually and textually distinct from `FAILURE CONFIRMED`, and the
   *"NOT a failure diagnosis"* qualification is present.
6. The M8 view shows both evaluation populations with their own metric sets, the module threshold,
   the baseline comparator (including the canonical disagreement on `syn-mod-0042`), and
   `lead_vs_onset` with its negative sign and direction label.
7. Ground-truth fields appear only in the labelled *Ground Truth (synthetic, evaluation-only)*
   register.

**M9**
8. All seven LangGraph nodes are visible as named, inspectable stages; the four-agent architecture is
   evident without reading documentation.
9. Each stage exposes its real inputs, outputs, counts and status as specified in §6.1; tool
   invocation shows 40 results across 5 tools for the canonical investigation, and the four
   never-invoked tools are shown as not invoked.
10. Both validation gates show `PASSED`/`REJECTED` with issue detail and retry counts; a report
    produced after a rejected hypothesis gate carries the rejection marker.
11. The LLM stage is visually distinct from every deterministic stage, and states provider, model,
    endpoint host, and whether inference was real or mocked.
12. Investigation progress reflects real backend state; no simulated progress exists anywhere.

**Evidence, hypotheses, report, provenance**
13. Every evidence record shows `evidence_id`, `document_id`, `chunk_id`, `citation`, `url`, page
    range, `source_type`, the three axes, and the retrieved passage; provenance completeness is
    indicated; no source is displayed that cannot be traced to the knowledge base.
14. Candidates are presented as competing explanations with supporting and contradictory evidence in
    separate, equally weighted columns; no candidate is styled as the winner; no fabricated global
    score exists.
15. Every hypothesis status and finding classification uses the exact backend vocabulary; uncertainty
    is preserved and never upgraded.
16. All 15 report sections render, each finding carries its classification, and evidence links
    resolve.
17. A report claim can be traced to a finding, to an evidence record, to a chunk, to a corpus
    document, without losing module context.
18. The Provenance Inspector shows the ordered trace with repeats, the six artifact hashes, and the
    reproducibility block.

**Integrity**
19. No numeric value displayed by M10 differs from the backend value; spot-checked against the
    §17.4 canonical figures.
20. No fabricated data, unit, marker, metric or citation appears anywhere.
21. Every §14.16 state is reachable and visually distinct; `NO DATA`, `NO ANOMALY`,
    `INSUFFICIENT EVIDENCE` and `SYSTEM ERROR` cannot be confused.
22. `PARTIAL` investigations render correctly with successful stages still inspectable.
23. API errors are handled per panel without losing context; the API key never appears in any
    response or in the browser.
24. `python3 -m pytest -W error` still reports 359 passed, 0 failed, 0 skipped, plus the new M10 API
    tests; the six M7/M8 artifact hashes are unchanged.
25. Every unimplemented capability in §20 is either absent from the UI or explicitly labelled as not
    implemented — no capability is implied that the backend does not have.

**The standard**
26. An experienced reliability engineer, opening SmartESS for the first time with no documentation,
    can identify — from the interface alone — that the system contains domain contracts, versioned
    feature engineering, an evaluated anomaly detector, deterministic engineering analysis, a
    provenance-preserving evidence retrieval layer, multi-agent reasoning, validation gates,
    structured competing hypotheses, and a traceable engineering report.

## Appendix A — Visual and Interaction Design System

### A.1 Product identity

SmartESS presents as a **scientific reliability investigation platform** — closer to semiconductor
characterisation software, aerospace diagnostics and forensic analysis tooling than to consumer SaaS.
It should read as *engineered*, not *decorated*.

Explicitly rejected: hero sections, marketing landing pages, decorative gradients, glow effects, neon
cyberpunk styling, heavily rounded cards, giant single-number KPI tiles, chat bubbles as the primary
interaction model, and "AI-powered" marketing language.

### A.2 Typography

* **Sans** (UI): one neutral, technical grotesque for labels, prose and section titles.
* **Mono** (mandatory) for all machine identity and measured values: `module_id`, `model_id`,
  `dataset_id`, `investigation_id`, `evidence_id`, `chunk_id`, `document_id`, `candidate_id`, cycle
  numbers, scores, metrics, hashes, enum values, tool names, file paths, provider/model strings.
* Tabular numerals everywhere numbers are compared in a column.
* A strong, small-step hierarchy: workspace title → section → panel → field label → value. Field
  labels are small, uppercase-tracked, and low-emphasis; values carry the emphasis.
* Minimum 13 px for data values, 12 px for labels. Long passages (`retrieved_text`, `reasoning`) get a
  comfortable measure (~80 ch) and normal-case sans.

### A.3 Colour and state semantics

A restrained, dark analytical base (deep neutral greys), one cool structural accent for interactive
affordances, and a small set of semantic hues used **only** for state. No decorative colour.

**Every state is encoded by at least two channels** — colour plus a text label, and where useful a
shape or border treatment. Colour is never the sole carrier (§A.8).

| Register (§12.4) | Treatment |
| --- | --- |
| DATA | plain mono values on the base surface; no chrome |
| CALCULATION | left rule + `CALCULATED` tag; slightly raised surface |
| RETRIEVED EVIDENCE | quotation treatment, distinct surface tint, citation footer |
| LLM REASONING | clearly demarcated container, `LLM` tag, provider/model in mono in the header |
| VALIDATION | gate chip `PASSED` / `REJECTED` with issue count |
| GROUND TRUTH (synthetic, eval-only) | hatched/striped border + persistent explicit label |
| HUMAN DECISION | dashed outline, empty-by-default, `awaiting engineer review` |

| Semantic state | Encoding |
| --- | --- |
| `clean` | neutral; text *no flagged observations* |
| `sporadic` | low-emphasis attention hue + `sporadic` text + `anomaly_rate` |
| `persistent` | higher-emphasis attention hue + `persistent` text + `anomaly_rate` |
| `SUPPORTED` | filled chip |
| `CANDIDATE` | outlined chip |
| `AMBIGUOUS` | outlined chip + ambiguity glyph |
| `INSUFFICIENT_EVIDENCE` | muted chip + explicit text |
| `CONTRADICTED` | struck/inverted chip |
| `COMPLETED` / `PARTIAL` / `FAILED` | distinct chips; `PARTIAL` never styled like `COMPLETED` |
| mocked inference | persistent banner, hatched treatment |

Red is reserved for **system failure and validation rejection** — not for anomalies. An anomaly is
analytically emphasised, never alarmed, because it is not a confirmed failure.

### A.4 Layout

* **Desktop-first**, optimised for 1440–2560 px. Laptop (1280 px) fully supported. Below 1024 px the
  workspace degrades to stacked read-only panels with a notice that investigation work expects a
  larger viewport. Mobile does not drive the layout.
* **Persistent context rail** — top or left, always visible, never scrolled away.
* **Split, resizable panels** with a 4 px base spacing scale and an 8 px rhythm. Subtle 1 px borders
  and a restrained technical grid define structure instead of shadows and rounding.
* **High information density without clutter**: an engineer sees signals, scores, deterministic
  findings and stage status without navigating away.
* **Progressive disclosure**: summary row → expand for full `input_summary`/`output`/`provenance`.
  Depth is available, not forced.

### A.5 Component principles

* Every value-rendering primitive takes a **required** `register` prop (§19.9).
* Every enum-driven component has an explicit `unknown` branch (§18.3).
* No component fabricates a value, unit, threshold or marker.
* Empty states are informative sentences naming the backend condition, never blank space or a shrug
  illustration.
* Tables are dense, sortable, with mono numerics and sticky headers; no card grid where a table is
  correct.

### A.6 Scientific visualisation rules

**Required**
* Meaningful axes with named quantities; `cycle_number` as the shared x-axis.
* Synchronised x across the 8 signal panes, the anomaly-score pane and the flag strip; one hover
  crosshair reports the same cycle across all panes.
* Per-signal independent y-scaling (the 8 signals have incomparable magnitudes), with the scale stated.
* `is_anomaly` markers and `statistical_baseline_flag` markers as separate, distinguishable series.
* Healthy-reference overlay drawn **only** from `healthy-reference.json` `mean` ± `std`, labelled as a
  declared reference population.
* Tooltips with exact values at full available precision, plus `cycle_number` and `observation_index`.
* Null gaps rendered as breaks, never interpolated.
* Signal selection, cycle-range zoom, and reset.
* Explicit statement when a view is downsampled.
* Zero-crossing axes where values are signed (`anomaly_score`, `lead_vs_onset`).

**Forbidden**
* Gauges or donuts for engineering data; 3D charts; dual y-axes without explicit labelling.
* Chart junk, decorative sparklines, animated transitions that obscure values.
* Percentages that are not percentages (`distance`, `confidence`).
* Confidence bands or error bars — the backend produces none.
* Change-point or acceptance-limit markers — the producing tools are never invoked (§20.2, §20.3).
* Any trend line or fit computed in the browser.

Every chart must answer a stated engineering question; a chart that answers none is removed.

### A.7 Interaction patterns

Verbs are **Select · Inspect · Run Investigation · Compare · Trace · Review · Export**. Destructive or
irreversible actions do not exist. `Run Investigation` always confirms, showing the exact
configuration and whether inference will be real or mocked. Trace is always available from a claim.
Deep links carry `module_id` / `investigation_id` so any workspace state is shareable.

### A.8 Accessibility

* WCAG AA contrast for text and UI; AA for chart strokes against the plot surface.
* **No state by colour alone** — every chip carries text; every chart series is distinguishable by
  dash pattern or marker shape as well as hue; flagged points use a shape change.
* Full keyboard navigation: panel traversal, stage expansion, table navigation, trace links; visible
  focus rings with a 3:1 contrast minimum.
* Charts expose an accessible description plus a tabular data view of the same series.
* Respects `prefers-reduced-motion`; no motion is load-bearing.
* Semantic headings and landmarks matching the information architecture.

## Appendix B — Implementation Phases

Each phase lists objective, backend dependencies, frontend components, API dependencies and
acceptance criteria. **[M10 REQ]** marks work that does not exist yet.

### M10-A — Application shell and investigation context

* **Objective.** Next.js App Router project in `frontend/`, typed API client, persistent context rail,
  layout primitives, register primitives (§A.5), and the pipeline-readiness surface.
* **Backend deps.** `GET /health`; existing `/investigations` list.
* **API deps.** **[M10 REQ]** CORS; `GET /readiness`; `GET /models`; OpenAPI type generation.
* **Frontend.** app shell, context rail, `RegisterValue`, `StatusChip`, `MonoId`, panel/split
  primitives, error/loading/empty primitives, readiness panel.
* **Acceptance.** App builds and type-checks; types generated from live OpenAPI with a CI drift check;
  context rail persists across routes; every required artifact's presence is reported with its path
  and producing CLI; API key absent from all responses.

### M10-B — Module explorer and population overview

* **Objective.** Find and select a real module; population-level orientation.
* **Backend deps.** `module-summary.parquet` (750), `model-record.json`.
* **API deps.** **[M10 REQ]** `GET /modules` (paginated, faceted), `GET /modules/{id}`,
  `GET /models/{model_id}`.
* **Frontend.** module table (all 15 summary columns, mono numerics, sort, facets by `lot_id` and
  `module_anomaly_status`), lot × status distribution, split-membership indicator, model identity
  panel.
* **Acceptance.** 750 modules listable and filterable; counts reconcile (`clean` 60, `sporadic` 491,
  `persistent` 199); `module_anomaly_status` shown with its *not a failure diagnosis* qualification;
  unknown module → `404` state, not a crash.

### M10-C — Signal analysis

* **Objective.** Scientifically correct, synchronised visualisation of the 8 baseline signals with
  anomaly context.
* **Backend deps.** `observation-features.parquet`, `observation-scores.parquet`,
  `healthy-reference.json`.
* **API deps.** **[M10 REQ]** `GET /modules/{id}/telemetry`, `GET /healthy-reference/{model_id}`.
* **Frontend.** synchronised multi-pane chart, signal selector, cycle-range zoom, crosshair tooltip,
  flag strip, healthy-reference overlay, tabular data view.
* **Acceptance.** 501 canonical points render with values identical to the parquet; null gaps break
  lines; shared x-axis confirmed across panes; flagged points survive downsampling;
  `VF` is not offered as a health signal; no client-side computation; accessible chart description
  present.

### M10-D — M7 anomaly and M8 detector-behaviour views

* **Objective.** Make detection and its evaluation legible, including honest timing and the
  anomaly-vs-failure distinction.
* **Backend deps.** M7 scores + summary; M8 `evaluation-summary.json`, `module-evaluation`,
  `timing-analysis`, `baseline-comparison`.
* **API deps.** **[M10 REQ]** `GET /modules/{id}/anomaly`, `GET /evaluation/{model_id}`.
* **Frontend.** anomaly-score pane with threshold, module summary panel, statistical-baseline
  comparator, model provenance panel, dual-population metrics (confusion counts + precision/recall/
  F1/FPR per population), timing panel with signed axis, ground-truth register block.
* **Acceptance.** Both populations shown separately and never blended; canonical metrics exact;
  `lead_vs_onset` negative and labelled *negative = flagged after onset*; the
  *module not in timing analysis* note rendered verbatim; the `syn-mod-0042` baseline disagreement
  visible; ground-truth fields only in the labelled register; no observation-level accuracy metric
  anywhere.

### M10-E — M9 investigation workspace

* **Objective.** Expose the four-agent LangGraph pipeline as an inspectable execution trace and allow
  an engineer to launch an investigation.
* **Backend deps.** `InvestigationGraph`, `run_investigation`, `InvestigationPersistence`,
  stored `provenance` / `retry_counts` / `errors`.
* **API deps.** existing `POST /investigations`, `GET /investigations{,/{id}}`;
  **[M10 REQ]** `POST /investigations/runs`, `GET /investigations/runs/{run_id}`,
  `GET /investigations/{id}/provenance`, `GET /investigations/{id}/deterministic-results`.
* **Frontend.** stage trace (7 named nodes), per-stage inspectors (§6.1), deterministic-results table
  grouped by tool and signal, tool-registry panel with invoked/not-invoked, retry and gate chips,
  launch dialog with explicit configuration confirmation, mocked-inference banner.
* **Acceptance.** All 7 nodes visible and expandable; 40 results / 5 tools for the canonical
  investigation; the 4 never-invoked tools marked not invoked; gate outcomes with issue detail;
  provenance repeats preserved in order; launch requires confirmation; **no simulated progress** —
  verified by test; mocked runs unmistakably marked.

### M10-F — Evidence explorer and hypothesis comparison

* **Objective.** First-class RAG interface and genuine competing-hypotheses comparison.
* **Backend deps.** stored `evidence_records` / `evidence_queries`, `Hypothesis.candidates`,
  `corpus.json`, ChromaDB collection count.
* **API deps.** **[M10 REQ]** `GET /investigations/{id}/evidence`, `GET /investigations/{id}/hypothesis`,
  `GET /evidence/{evidence_id}`, `GET /corpus`, `GET /corpus/documents/{document_id}`.
* **Frontend.** evidence list + detail (passage, citation, page range, axes, `document_id`,
  `chunk_id`, raw `distance` labelled), provenance-completeness indicator, corpus document view with
  `verification_status`, query list with derived signal/tool attribution labelled *derived*,
  side-by-side candidate comparison with separate supporting/contradictory columns, reverse index from
  evidence to citing candidates.
* **Acceptance.** All 5 canonical evidence records shown with complete provenance; every candidate id
  `inv-70207e0ffd15-hyp-c1..c5` present; supporting and contradictory evidence visually separated; no
  winner styling; `primary_mechanism` labelled *model-nominated*; `distance` never shown as a
  percentage; `confidence` labelled as non-probability; corpus coverage gaps surfaced; unresolvable
  evidence ids render as unresolved.

### M10-G — Engineering report and provenance

* **Objective.** The report as an engineering document with end-to-end traceability.
* **Backend deps.** `InvestigationReport` (15 sections), `Finding.evidence_ids`, `provenance`,
  `snapshot_m7_m8`, `model_record._hash`.
* **API deps.** existing `GET /investigations/{id}/report`; **[M10 REQ]** Markdown export endpoint or
  client download from `full_text`.
* **Frontend.** section navigator, per-finding classification treatment, evidence links, uncertainty
  and limitations sections given real prominence, `Human Review` rendered as *awaiting engineer
  review*, validation-rejection headers, Provenance Inspector with the full chain and the six artifact
  hashes, reproducibility block, JSON/Markdown export.
* **Acceptance.** All 15 sections render with correct titles; every finding shows its classification;
  a claim traces to evidence to chunk to corpus document without losing module context; a report
  behind a rejected gate shows the rejection; `CONFIRMED` treatment defined but demonstrably absent;
  exports carry provenance and the synthetic label; **PDF is not offered**.

### M10-H — Investigation history, performance, accessibility, demonstration mode, auth

* **Objective.** Operational completeness and a rigorous demonstration path.
* **Backend deps.** investigations index (69 records, 47 `COMPLETED` / 21 `PARTIAL`).
* **API deps.** **[M10 REQ]** pagination/faceting/sort on `GET /investigations`; optionally the
  `investigations/index.json` of §10.7; Clerk session validation.
* **Frontend.** history table (investigation id, module, model, dataset, timestamp, status, evidence
  count, candidate count, report status, mocked flag), reopen with preserved context, cross-run
  operational statistics labelled as such, virtualised tables, request caching, accessibility pass,
  Clerk integration, demonstration mode.
* **Demonstration mode.** Uses only real stored artifacts — default `inv-70207e0ffd15` on
  `syn-mod-0042` — and walks: canonical module → signals → M7 anomaly behaviour → M8 detector
  behaviour including negative timing → run or open investigation → LangGraph trace → deterministic
  findings → retrieved evidence → five competing hypotheses → both validation gates → report → trace
  a claim back to a source document. It must explicitly teach the `syn-mod-0042` case of §19.6:
  ground-truth healthy, model not flagging, statistical baseline flagging, and an LLM-`SUPPORTED`
  candidate — as a lesson in anomaly ≠ failure. It is a scientific walkthrough, not a product tour,
  and it fabricates nothing; if artifacts are absent it shows the §14.1 readiness state.
* **Acceptance.** All 69 investigations listable and reopenable with `PARTIAL` correctly distinguished;
  history loads without fetching full records; axe passes with no critical violations; full keyboard
  traversal; no state by colour alone; demonstration mode runs end to end on real artifacts and
  degrades honestly without them; `python3 -m pytest -W error` still reports 359 passed plus the new
  M10 API tests; the six M7/M8 artifact hashes unchanged.

### B.1 Phase dependency order

```text
M10-A ──► M10-B ──► M10-C ──► M10-D
            │                   │
            └────► M10-E ◄──────┘
                     │
            ┌────────┴────────┐
            ▼                 ▼
         M10-F ──────────► M10-G
                              │
                              ▼
                           M10-H
```

M10-A is a hard prerequisite for everything. M10-E requires M10-B (module selection) and benefits
from M10-D (context for the hypothesis panel per §19.6). M10-G requires M10-F for evidence links.
M10-H is last because it depends on every prior surface.
