/**
 * Typed mirrors of the SmartESS backend contracts.
 *
 * SOURCE OF TRUTH — these types mirror Python models. Do not add a field here
 * that does not exist in the backend:
 *
 *   InvestigationRecord, InvestigationReport, InvestigationStatus,
 *   ModuleTrajectory, DeterministicResult, ProvenanceEntry
 *     → backend/agents/investigation/models/investigation.py
 *   Hypothesis, CandidateMechanism, HypothesisStatus, MechanismType
 *     → backend/agents/investigation/models/hypothesis.py
 *   Finding, FindingClassification, ReportSection
 *     → backend/agents/investigation/models/report.py
 *   EvidenceRecord
 *     → backend/knowledge/models.py
 *
 * Once the SmartESS API is running these can be regenerated from its OpenAPI
 * schema (`npm run types:generate`, see design.md §10.5). Until then they are
 * hand-mirrored, and `docs/m10/design.md` §18.2 applies: records are written
 * with `exclude_none=True`, so optional fields may be ABSENT rather than null.
 * Every optional field below is therefore `?: T | null`.
 */

/* ── enums ─────────────────────────────────────────────────────────────── */

export const INVESTIGATION_STATUS = [
  "PENDING",
  "LOADING",
  "INVESTIGATING",
  "RETRIEVING_EVIDENCE",
  "ANALYZING",
  "REPORTING",
  "VALIDATING",
  "COMPLETED",
  "FAILED",
  "PARTIAL",
] as const;
export type InvestigationStatus = (typeof INVESTIGATION_STATUS)[number];

export const MECHANISM_TYPE = [
  "bond_wire_interconnect",
  "die_attach_thermal_path",
  "gate_related",
  "thermal_path",
  "package_interconnect",
  "other",
] as const;
export type MechanismType = (typeof MECHANISM_TYPE)[number];

export const HYPOTHESIS_STATUS = [
  "CANDIDATE",
  "SUPPORTED",
  "CONTRADICTED",
  "INSUFFICIENT_EVIDENCE",
  "AMBIGUOUS",
] as const;
export type HypothesisStatus = (typeof HYPOTHESIS_STATUS)[number];

export const FINDING_CLASSIFICATION = [
  "OBSERVED",
  "CALCULATED",
  "PREDICTED",
  "HYPOTHESIZED",
  "CONFIRMED",
  "RECOMMENDED",
] as const;
export type FindingClassification = (typeof FINDING_CLASSIFICATION)[number];

/**
 * M7 `module_anomaly_status` — `docs/anomaly-detection/anomaly-detection.md`.
 * A descriptive anomaly summary. NOT a failure diagnosis.
 */
export const MODULE_ANOMALY_STATUS = ["clean", "sporadic", "persistent"] as const;
export type ModuleAnomalyStatus = (typeof MODULE_ANOMALY_STATUS)[number];

/**
 * The eight M6 v1 baseline/rolling signals. `VF` is an electrical passthrough
 * only and is deliberately NOT a member (design.md §3.2).
 */
export const BASELINE_SIGNALS = [
  "RDS_on",
  "VTH",
  "IGSS",
  "IDSS",
  "VDS_on",
  "electrical_power",
  "Tj",
  "Tc",
] as const;
export type BaselineSignal = (typeof BASELINE_SIGNALS)[number];

/** LangGraph node names, in topology order (orchestrator.py `_build`). */
export const PIPELINE_STEPS = [
  "load_investigation",
  "investigation_agent",
  "evidence_agent",
  "hypothesis_agent",
  "hypothesis_validation",
  "report_agent",
  "report_validation",
] as const;
export type PipelineStep = (typeof PIPELINE_STEPS)[number];

/* ── models ────────────────────────────────────────────────────────────── */

export interface ModuleTrajectory {
  module_id: string;
  n_observations: number;
  n_cycles: number;
  /** Keyed by signal name; NaN is serialised as null. */
  signals: Record<string, (number | null)[]>;
  cycle_numbers: number[];
  min_score: number;
  max_score: number;
  mean_score: number;
}

export interface DeterministicResult {
  tool_name: string;
  tool_version: string;
  input_summary: Record<string, unknown>;
  output: Record<string, unknown>;
  provenance: Record<string, unknown>;
}

export interface ProvenanceEntry {
  step: string;
  source: string;
  description: string;
  timestamp: string;
}

export interface EvidenceRecord {
  evidence_id: string;
  source_type: string;
  title: string;
  source_identifier: string;
  section_or_page?: string | null;
  retrieved_text: string;
  /** `distance` is a vector distance (lower = closer), stored as a string. */
  retrieval_metadata: Record<string, string>;
  failure_mechanism?: string | null;
  observable_signature?: string | null;
  engineering_interpretation?: string | null;
  recommended_investigation?: string | null;
  /** Defaults to 0.5 and is not set by the retriever. Not a computed strength. */
  confidence: number;

  document_id?: string | null;
  chunk_id?: string | null;
  citation?: string | null;
  url?: string | null;
  page_start?: number | null;
  page_end?: number | null;

  mechanisms: string[];
  observables: string[];
  test_conditions: string[];
}

export interface CandidateMechanism {
  mechanism: MechanismType;
  status: HypothesisStatus;
  /** LLM-assigned, uncalibrated. NOT a probability of physical failure. */
  confidence: number;
  candidate_id: string;
  supporting_evidence_ids: string[];
  contradictory_evidence_ids: string[];
  reasoning: string;
  distinguishing_measurements: string[];
}

export interface Hypothesis {
  module_id: string;
  hypothesis_id: string;
  candidates: CandidateMechanism[];
  /** Model-nominated. Not a verdict, not a winner. */
  primary_mechanism?: MechanismType | null;
  note: string;
}

export interface Finding {
  label: string;
  classification: FindingClassification;
  detail: string;
  source: string;
  evidence_ids: string[];
}

export interface ReportSection {
  title: string;
  findings: Finding[];
  narrative: string;
}

export interface InvestigationReport {
  investigation_id: string;
  module_id: string;
  model_id: string;
  /** Serialised ReportSection objects. 15 required titles. */
  sections: ReportSection[];
  /** Pre-rendered Markdown narrative built by `_build_narrative`. */
  full_text: string;
  generated_at: string;
}

export interface InvestigationRecord {
  investigation_id: string;
  module_id: string;
  model_id: string;
  dataset_id: string;
  status: InvestigationStatus;
  created_at: string;
  module_trajectory?: ModuleTrajectory | null;
  m7_module_summary: Record<string, unknown>;
  m8_module_evaluation: Record<string, unknown>;
  /** May be `{note: "module not in timing analysis (healthy or undetected)"}`. */
  m8_timing: Record<string, unknown>;
  /** May be `{}` when the module is absent from baseline-comparison. */
  m8_baseline: Record<string, unknown>;
  deterministic_results: DeterministicResult[];
  evidence_records: EvidenceRecord[];
  evidence_queries: string[];
  hypothesis?: Hypothesis | null;
  report?: InvestigationReport | null;
  provenance: ProvenanceEntry[];
  agent_messages: Record<string, string>;
  retry_counts: Record<string, number>;
  errors: Record<string, string>;
  limitations: string[];
}

/** Row shape returned by `GET /investigations` (persistence.list_investigations). */
export interface InvestigationListItem {
  investigation_id: string;
  module_id: string;
  model_id: string;
  status: string;
  created_at: string;
}

/** Body accepted by `POST /investigations` (api/investigations.py). */
export interface InvestigationRequest {
  module_id: string;
  model_id?: string;
  dataset_id?: string;
  max_evidence?: number;
}

/** Response of `POST /investigations`. */
export interface InvestigationCreated {
  investigation_id: string;
  status: string;
  module_id: string;
  model_id: string;
}

/** Response of `GET /health`. */
export interface HealthResponse {
  status: string;
}
