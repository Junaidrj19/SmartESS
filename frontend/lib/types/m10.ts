/**
 * Types for the additive M10 read-only projection routes
 * (`backend/api/modules.py`, `backend/api/system.py`, `backend/api/projections.py`).
 *
 * Mirrors the actual response shapes. Any field the backend does not return is
 * absent here; nothing is added because a component would like it.
 */

import type { ModuleAnomalyStatus } from "@/lib/types/backend";

/* ── models ────────────────────────────────────────────────────────────── */

export interface ModelSplit {
  type?: string;
  train_lots?: string[];
  test_lots?: string[];
  n_train_modules?: number;
  n_test_modules?: number;
}

export interface ModelListItem {
  model_id: string;
  status: string | null;
  algorithm: string | null;
  detector_version: string | null;
  feature_version: string | null;
  source_dataset_id: string | null;
  module_profile_id: string | null;
  training_timestamp: string | null;
  n_input_features: number | null;
  hyperparameters: Record<string, unknown>;
  split: ModelSplit;
  /** Per-observation decision boundary from model-record.json. */
  observation_threshold: number | null;
}

/* ── modules ───────────────────────────────────────────────────────────── */

/** One row of `module-summary.parquet` — all 15 M7 columns. */
export interface ModuleSummary {
  module_id: string;
  test_id: string | null;
  lot_id: string | null;
  dataset_id: string | null;
  n_observations: number | null;
  n_anomalous_observations: number | null;
  anomaly_rate: number | null;
  max_anomaly_score: number | null;
  mean_anomaly_score: number | null;
  first_anomalous_cycle: number | null;
  last_anomalous_cycle: number | null;
  anomalous_cycle_span: number | null;
  statistical_baseline_max: number | null;
  statistical_baseline_flag_rate: number | null;
  module_anomaly_status: ModuleAnomalyStatus | string | null;
}

export interface ModulePage {
  model_id: string;
  total: number;
  offset: number;
  limit: number;
  returned: number;
  items: ModuleSummary[];
}

export interface ModulePopulation {
  model_id: string;
  n_modules: number;
  by_anomaly_status: Record<string, number>;
  by_lot: Record<string, number>;
  by_lot_and_status: Record<string, Record<string, number>>;
  note: string;
}

export interface SplitMembership {
  lot_id: string | null;
  split_type: string | null;
  train_lots: string[];
  test_lots: string[];
  in_train_lots: boolean;
  in_test_lots: boolean;
}

export interface ModuleDetail {
  model_id: string;
  module_summary: ModuleSummary;
  /** Contains ground-truth fields. Evaluation-only; never a SmartESS output. */
  module_evaluation: Record<string, unknown>;
  /** May be `{note: "module not in timing analysis (healthy or undetected)"}`. */
  timing_analysis: Record<string, unknown>;
  baseline_comparison: Record<string, unknown>;
  model: {
    model_id: string | null;
    algorithm: string | null;
    detector_version: string | null;
    feature_version: string | null;
    module_profile_id: string | null;
    training_timestamp: string | null;
    n_input_features: number | null;
    hyperparameters: Record<string, unknown>;
    observation_threshold: number | null;
  };
  split_membership: SplitMembership;
  data_origin: string;
  investigations: {
    investigation_id: string;
    module_id: string;
    model_id: string;
    status: string;
    created_at: string;
  }[];
}

/* ── telemetry ─────────────────────────────────────────────────────────── */

/**
 * One observation. Signal keys are dynamic (whichever signals were requested),
 * so they are reached through the index signature. `null` means the sample was
 * missing — the chart must break the line, not interpolate.
 */
export interface TelemetryPoint {
  cycle_number: number;
  anomaly_score: number | null;
  is_anomaly: boolean | null;
  statistical_baseline_score: number | null;
  statistical_baseline_flag: boolean | null;
  [signal: string]: number | boolean | null;
}

export interface TelemetrySeries {
  module_id: string;
  model_id: string;
  signals: string[];
  source_points: number;
  returned_points: number;
  downsampled: boolean;
  downsample_method: string | null;
  points: TelemetryPoint[];
  score_semantics: {
    anomaly_score: string;
    statistical_baseline_flag_threshold: number;
  };
  units_note: string;
}

/* ── anomaly ───────────────────────────────────────────────────────────── */

export interface ModuleAnomaly {
  model_id: string;
  module_summary: ModuleSummary;
  model: {
    model_id: string | null;
    algorithm: string | null;
    detector_version: string | null;
    feature_version: string | null;
    n_input_features: number | null;
    hyperparameters: Record<string, unknown>;
  };
  thresholds: {
    observation_threshold: number | null;
    module_threshold: number | null;
    note: string;
  };
  score_semantics: {
    direction: string;
    statistical_baseline_flag_threshold: number;
  };
  qualification: string;
}

/* ── evaluation ────────────────────────────────────────────────────────── */

export interface ModuleLevelMetrics {
  n_modules: number;
  n_positive: number;
  n_negative: number;
  tp: number;
  tn: number;
  fp: number;
  fn: number;
  precision: number | null;
  recall: number | null;
  f1: number | null;
  false_positive_rate: number | null;
  false_negative_rate: number | null;
}

export interface EvaluationSummary {
  model_id: string;
  evaluation_timestamp: string | null;
  dataset_id: string | null;
  feature_version: string | null;
  detector_version: string | null;
  evaluation_population: Record<string, unknown>;
  ground_truth_path: string | null;
  ground_truth_used_for_training: boolean;
  provenance: Record<string, unknown>;
  module_threshold: number | null;
  module_level_metrics: ModuleLevelMetrics;
  observation_level_flag_rates: Record<string, unknown>;
  timing: Record<string, unknown>;
  timing_by_mechanism: Record<string, unknown>;
  false_positive_summary: Record<string, unknown>;
  baseline_comparison: Record<string, unknown>;
  m7_test_lot_compatibility: Record<string, unknown>;
  stratified?: Record<string, unknown>;
  detection_rate_by_severity?: Record<string, unknown>;
  disclaimer?: string;
}

export interface HealthyReference {
  model_id: string | null;
  declared_by: string | null;
  selection: string | null;
  declaration_note: string | null;
  signals: Record<string, { n: number | null; mean: number | null; std: number | null }>;
  _model_mismatch?: string;
}

/* ── knowledge base ────────────────────────────────────────────────────── */

export interface CorpusDocument {
  document_id: string;
  title: string | null;
  source_type: string | null;
  organization: string | null;
  authors: string[];
  publication_year: number | null;
  publisher: string | null;
  url: string | null;
  local_filename: string | null;
  local_path: string | null;
  citation: string | null;
  access_type: string | null;
  mechanisms: string[];
  observables: string[];
  test_conditions: string[];
  tags: string[];
  description: string | null;
  verification_status: string;
}

export interface Corpus {
  corpus_version: string | null;
  generated_at: string | null;
  note: string | null;
  n_documents: number;
  counts_by_verification_status: Record<string, number>;
  counts_by_source_type: Record<string, number>;
  documents: CorpusDocument[];
  production_note: string;
  collection: {
    reachable: boolean;
    collection?: string;
    chunk_count: number | null;
    path: string | null;
    detail?: string;
  };
}

/* ── readiness ─────────────────────────────────────────────────────────── */

export interface ReadinessArtifact {
  artifact: string;
  status: "PRESENT" | "ABSENT" | string;
  path: string | null;
  produced_by: string;
  detail?: string;
}

export interface Readiness {
  model_id: string | null;
  artifacts: ReadinessArtifact[];
  status?: "READY" | "NOT_READY" | string;
  blockers?: string[];
  llm: {
    provider: string | null;
    model: string | null;
    endpoint_host: string | null;
    configured: boolean;
    /** real | mocked | not_configured | provider_error */
    inference?: "real" | "mocked" | "not_configured" | "provider_error" | string;
    prompt_version: string;
    timeout: number;
    embedding_model: string;
    status: "READY" | "NOT_CONFIGURED" | string;
    note: string;
  };
}

/* ── investigation sub-resources ───────────────────────────────────────── */

export interface ProvenanceBundle {
  investigation_id: string;
  provenance: { step: string; source: string; description: string; timestamp: string }[];
  retry_counts: Record<string, number>;
  errors: Record<string, string>;
  limitations: string[];
  artifact_hashes_current: Record<string, string>;
  artifact_hashes_note: string;
}
