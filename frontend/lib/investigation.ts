/**
 * Derivations over a stored InvestigationRecord.
 *
 * Everything here is READ-ONLY RESHAPING of values the backend already produced:
 * grouping, lookup, counting, parsing a recorded string. Nothing is computed
 * that the backend did not compute (UX.md §35 Rule 2; design.md §4 rule 1).
 *
 * Where a value is only inferable rather than recorded, the returned object says
 * so explicitly via a `derived` flag, so the UI can label it (design.md §13.4).
 */

import type {
  DeterministicResult,
  InvestigationRecord,
  PipelineStep,
  ProvenanceEntry,
  ReportSection,
} from "@/lib/types/backend";
import { PIPELINE_STEPS } from "@/lib/types/backend";

/* ── LLM identity (derived from provenance text) ────────────────────────── */

export interface LlmIdentity {
  readonly provider: string | null;
  readonly model: string | null;
  /** Always true: the record has no structured LLM fields (design.md §13.4). */
  readonly derived: true;
  /**
   * `true` when the recorded provider name indicates a mock client. Presented
   * with the caveat that this is inferred from the provenance string, never from
   * a dedicated field.
   */
  readonly mocked: boolean | null;
  /**
   * Three distinct inference outcomes. A provider failure is never reported as
   * `MOCKED` and never as `NOT_CONFIGURED`: a real request was attempted and the
   * provider rejected or failed it, which is a different engineering fact.
   */
  readonly mode: "REAL_INFERENCE" | "MOCKED_INFERENCE" | "LLM_PROVIDER_ERROR" | "UNKNOWN";
  /** Verbatim provider error recorded by the hypothesis agent, if any. */
  readonly error: string | null;
}

/**
 * Parses the `hypothesis_agent` provenance source, which the orchestrator writes
 * as `llm:<provider>/<model>`. This is the ONLY place the LLM identity is
 * recorded (design.md §13.4).
 *
 * The mode additionally consults `errors.hypothesis`, which `HypothesisAgent`
 * sets to `LLM failure (<provider>): <detail>` when a real request fails. That is
 * what separates a provider error from an unconfigured (mocked) run.
 */
export function llmIdentity(record: InvestigationRecord): LlmIdentity {
  const entry = record.provenance.find((p) => p.step === "hypothesis_agent");
  const source = entry?.source ?? "";
  const error = record.errors["hypothesis"] ?? null;
  const note = record.hypothesis?.note ?? "";

  if (!source.startsWith("llm:")) {
    return {
      provider: null,
      model: null,
      derived: true,
      mocked: null,
      mode: error ? "LLM_PROVIDER_ERROR" : "UNKNOWN",
      error,
    };
  }
  const rest = source.slice("llm:".length);
  const slash = rest.indexOf("/");
  const provider = slash === -1 ? rest : rest.slice(0, slash);
  const model = slash === -1 ? null : rest.slice(slash + 1);
  const lowered = provider.toLowerCase();
  const mocked = lowered.includes("mock") ? true : lowered === "" ? null : false;

  // A real provider that failed, or an explicit llm_failed/llm_unavailable note.
  const failed =
    Boolean(error) || note === "llm_failed" || note === "llm_unavailable";

  const mode: LlmIdentity["mode"] =
    mocked === true
      ? "MOCKED_INFERENCE"
      : failed
        ? "LLM_PROVIDER_ERROR"
        : mocked === false
          ? "REAL_INFERENCE"
          : "UNKNOWN";

  return { provider: provider || null, model, derived: true, mocked, mode, error };
}

/* ── pipeline stages ────────────────────────────────────────────────────── */

export type StageOutcome = "executed" | "rejected" | "not-reached";

export interface Stage {
  readonly step: PipelineStep;
  /** Every provenance entry for this node, in order. Repeats are retries. */
  readonly entries: readonly ProvenanceEntry[];
  readonly outcome: StageOutcome;
  /** Number of recorded executions. >1 means the graph looped back. */
  readonly executions: number;
  /** Recorded error for this stage, verbatim, if any. */
  readonly error: string | null;
}

const STAGE_ERROR_KEYS: Partial<Record<PipelineStep, string>> = {
  hypothesis_agent: "hypothesis",
  hypothesis_validation: "hypothesis_validation",
  report_validation: "report_validation",
};

/**
 * Reconstructs the execution trace from `provenance`.
 *
 * The provenance list is the authoritative record of the path actually taken,
 * including repeats, so it is never deduplicated (design.md §12.2).
 */
export function stages(record: InvestigationRecord): readonly Stage[] {
  return PIPELINE_STEPS.map((step) => {
    const entries = record.provenance.filter((p) => p.step === step);
    const errorKey = STAGE_ERROR_KEYS[step];
    const error = errorKey ? (record.errors[errorKey] ?? null) : null;
    const outcome: StageOutcome =
      entries.length === 0 ? "not-reached" : error ? "rejected" : "executed";
    return { step, entries, outcome, executions: entries.length, error };
  });
}

/** Gate outcome exactly as the validation node recorded it. */
export interface GateOutcome {
  readonly gate: "hypothesis_validation" | "report_validation";
  readonly passed: boolean;
  /** Verbatim issue text from `errors`, already `; `-joined by the backend. */
  readonly issues: readonly string[];
  readonly reached: boolean;
  /** The gate's own provenance description. */
  readonly description: string | null;
}

export function gateOutcome(
  record: InvestigationRecord,
  gate: GateOutcome["gate"],
): GateOutcome {
  const entries = record.provenance.filter((p) => p.step === gate);
  const raw = record.errors[gate];
  return {
    gate,
    passed: entries.length > 0 && !raw,
    issues: raw ? raw.split("; ") : [],
    reached: entries.length > 0,
    description: entries.at(-1)?.description ?? null,
  };
}

/* ── deterministic results ──────────────────────────────────────────────── */

export interface ToolGroup {
  readonly toolName: string;
  readonly toolVersion: string;
  readonly results: readonly DeterministicResult[];
  /** `provenance.method`, identical across a tool's results. */
  readonly method: string | null;
}

/** Groups the 40 results by tool, preserving backend order within each group. */
export function resultsByTool(record: InvestigationRecord): readonly ToolGroup[] {
  const map = new Map<string, DeterministicResult[]>();
  for (const r of record.deterministic_results) {
    const list = map.get(r.tool_name);
    if (list) list.push(r);
    else map.set(r.tool_name, [r]);
  }
  return [...map.entries()].map(([toolName, results]) => ({
    toolName,
    toolVersion: results[0]?.tool_version ?? "",
    results,
    method: asString(results[0]?.provenance?.["method"]),
  }));
}

/** Results for one signal, across every tool that examined it. */
export function resultsForSignal(
  record: InvestigationRecord,
  signal: string,
): readonly DeterministicResult[] {
  return record.deterministic_results.filter(
    (r) => asString(r.input_summary?.["signal"]) === signal,
  );
}

export function signalOf(result: DeterministicResult): string | null {
  return asString(result.input_summary?.["signal"]);
}

/* ── evidence ───────────────────────────────────────────────────────────── */

/** Evidence records whose provenance chain is complete (design.md §12.3). */
export function provenanceComplete(record: InvestigationRecord): {
  complete: number;
  total: number;
  missingByRecord: ReadonlyMap<string, readonly string[]>;
} {
  const missing = new Map<string, readonly string[]>();
  for (const e of record.evidence_records) {
    const gaps: string[] = [];
    if (!e.document_id) gaps.push("document_id");
    if (!e.chunk_id) gaps.push("chunk_id");
    if (!e.citation) gaps.push("citation");
    if (!e.url) gaps.push("url");
    if (e.page_start === null || e.page_start === undefined) gaps.push("page_start");
    if (e.page_end === null || e.page_end === undefined) gaps.push("page_end");
    if (gaps.length > 0) missing.set(e.evidence_id, gaps);
  }
  return {
    complete: record.evidence_records.length - missing.size,
    total: record.evidence_records.length,
    missingByRecord: missing,
  };
}

/** Candidate ids citing a given evidence record — the reverse index. */
export function candidatesCiting(
  record: InvestigationRecord,
  evidenceId: string,
): readonly { candidateId: string; mechanism: string; relation: "supporting" | "contradictory" }[] {
  const out: { candidateId: string; mechanism: string; relation: "supporting" | "contradictory" }[] = [];
  for (const c of record.hypothesis?.candidates ?? []) {
    if (c.supporting_evidence_ids.includes(evidenceId)) {
      out.push({ candidateId: c.candidate_id, mechanism: c.mechanism, relation: "supporting" });
    }
    if (c.contradictory_evidence_ids.includes(evidenceId)) {
      out.push({ candidateId: c.candidate_id, mechanism: c.mechanism, relation: "contradictory" });
    }
  }
  return out;
}

/** Resolves an evidence id against the records actually retrieved. */
export function resolveEvidence(record: InvestigationRecord, evidenceId: string) {
  return record.evidence_records.find((e) => e.evidence_id === evidenceId) ?? null;
}

/* ── report ─────────────────────────────────────────────────────────────── */

export const REQUIRED_REPORT_SECTIONS = [
  "Component Information",
  "Test Configuration",
  "Data Quality",
  "Observed Degradation",
  "Anomaly Analysis",
  "Model Results",
  "Candidate Failure Mechanisms",
  "Supporting Evidence",
  "Contradictory Evidence",
  "Uncertainty",
  "Engineering Interpretation",
  "Recommended Investigation",
  "Limitations",
  "Provenance",
  "Human Review",
] as const;

export function reportSection(
  sections: readonly ReportSection[],
  title: string,
): ReportSection | null {
  return sections.find((s) => s.title === title) ?? null;
}

export function missingReportSections(sections: readonly ReportSection[]): readonly string[] {
  const titles = new Set(sections.map((s) => s.title));
  return REQUIRED_REPORT_SECTIONS.filter((t) => !titles.has(t));
}

/* ── context rail ───────────────────────────────────────────────────────── */

/**
 * Builds the rail context from the record.
 *
 * `feature_version` and `detector_version` are NOT present in
 * `m7_module_summary` (they live on `observation-scores.parquet` and
 * `model-record.json`, neither of which is exposed), so they are returned as
 * null and render as `not recorded`.
 */
export function railContext(record: InvestigationRecord) {
  const m7 = record.m7_module_summary;
  return {
    moduleId: record.module_id,
    testId: asString(m7["test_id"]),
    lotId: asString(m7["lot_id"]),
    datasetId: record.dataset_id || asString(m7["dataset_id"]),
    dataOrigin: "SYNTHETIC",
    modelId: record.model_id,
    featureVersion: null,
    detectorVersion: null,
    moduleStatus: asString(m7["module_anomaly_status"]),
    investigationId: record.investigation_id,
    investigationStatus: record.status,
  };
}

/* ── primitive coercion ─────────────────────────────────────────────────── */

/**
 * The M7/M8 summaries arrive as `Record<string, unknown>` because they are
 * parquet row projections. These helpers read a field without inventing a value:
 * anything absent or of the wrong type becomes null.
 */
export function asString(value: unknown): string | null {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return null;
}

export function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function asBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

/** Renders a raw backend value for display without reformatting it. */
export function raw(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
