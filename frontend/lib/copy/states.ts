/**
 * Exact state copy — frontend/UX.md §44.9.
 *
 * These strings are the contract. They must never be reworded into each other:
 * NO DATA, NO ANOMALY, INSUFFICIENT EVIDENCE and SYSTEM ERROR have to read as
 * unmistakably different things (UX.md §30, design.md §14.16, acceptance 21).
 */

export interface StateCopy {
  readonly title: string;
  readonly body: string;
  readonly detailHint?: string;
  readonly note?: string;
}

export const STATE_COPY = {
  NO_DATA: {
    title: "ARTIFACT NOT AVAILABLE",
    body: "This artifact has not been generated in this environment.",
    detailHint: "expected path + producing CLI",
    note: "This is a setup state, not an error.",
  },
  NO_ANOMALY: {
    title: "NO ANOMALY DETECTED",
    body: "No observation exceeded the detector threshold for this module.",
    detailHint: "observation count · anomaly rate · threshold · baseline comparator",
  },
  NOT_APPLICABLE: {
    title: "NOT APPLICABLE",
    body: "",
    detailHint: "Timing is defined only for detected positives.",
  },
  ANALYSIS_NOT_PERFORMED: {
    title: "ANALYSIS NOT PERFORMED",
    body: "This calculation was not run for this investigation.",
    detailHint: "recorded limitation + producing CLI",
  },
  NO_EVIDENCE: {
    title: "KNOWLEDGE BASE NOT INGESTED",
    body: "No evidence records are available, so no citation can be resolved.",
    detailHint: "scripts/ingest_knowledge.py",
  },
  INSUFFICIENT_EVIDENCE: {
    title: "INSUFFICIENT EVIDENCE",
    body: "The retrieved evidence cannot discriminate this mechanism.",
    note: "This does not mean the mechanism is false.",
  },
  MECHANISM_UNRESOLVED: {
    title: "ANOMALY DETECTED — MECHANISM UNRESOLVED",
    body: "No candidate mechanism was proposed for this investigation.",
  },
  REASONING_UNAVAILABLE: {
    title: "LLM REASONING UNAVAILABLE",
    body: "The hypothesis stage did not complete.",
    detailHint: "verbatim backend error",
  },
  MOCKED_INFERENCE: {
    title: "MOCKED INFERENCE",
    body: "No model-generated reasoning. This investigation ran without a configured LLM provider.",
  },
  VALIDATION_REJECTED: {
    title: "VALIDATION REJECTED",
    body: "Issues were recorded by the validation gate.",
  },
  PARTIAL: {
    title: "PARTIAL",
    body: "One or more stages did not complete. Completed stages remain inspectable.",
    detailHint: "failed stage names",
  },
  SYSTEM_ERROR: {
    title: "SYSTEM ERROR",
    body: "The request failed. Module context is preserved.",
    detailHint: "status code + detail from the API",
  },
  CAPABILITY_NOT_IMPLEMENTED: {
    title: "NOT IMPLEMENTED",
    body: "This capability does not exist in the current backend.",
    detailHint: "design.md reference",
  },
} as const satisfies Record<string, StateCopy>;

export type StateKey = keyof typeof STATE_COPY;

/** The single orientation sentence for Mission Control (UX.md §5). */
export const ORIENTATION_SENTENCE =
  "SmartESS traces abnormal electrical behaviour from measured signals through anomaly detection, engineering calculations, evidence retrieval, competing hypotheses, validation, and a traceable report.";

/**
 * Mandatory qualification wherever `module_anomaly_status` appears (UX.md §5).
 * An anomaly is not a confirmed failure.
 */
export const ANOMALY_QUALIFICATION = "Anomaly summary — not a failure diagnosis.";

/** Persistent synthetic-data label (design.md §15.4, agent-rules.md §17). */
export const SYNTHETIC_LABEL = "SYNTHETIC";
export const SYNTHETIC_NOTE =
  "Development dataset. Not production telemetry.";
