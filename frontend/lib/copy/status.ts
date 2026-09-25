/**
 * Canonical status vocabulary — frontend/UX.md §24 and §44.3.
 *
 * Every entry pairs a colour token with a TEXT LABEL and a SHAPE, because
 * colour is never sufficient by itself (UX.md §24, §34; design.md acceptance 21).
 *
 * `--ss-state-reject` (red) is reserved for system failure and validation
 * rejection. An anomaly never uses it.
 *
 * Unknown values are handled explicitly by `statusDescriptor`: a new backend
 * enum member renders neutrally with its raw string, never as SUPPORTED or as
 * `other` (design.md §18.3).
 */

export type ChipShape = "plain" | "outlined" | "filled" | "struck" | "muted" | "dashed" | "gate";

export interface StatusDescriptor {
  /** Uppercase text always rendered alongside the colour. */
  readonly label: string;
  readonly shape: ChipShape;
  /** CSS custom property name from UX.md §44.3. */
  readonly colorVar: string;
  /** True when the value was not recognised (design.md §18.3). */
  readonly unknown?: boolean;
  /** Optional glyph for non-colour differentiation. */
  readonly glyph?: string;
}

const NEUTRAL = "--ss-state-neutral";
const ATTENTION = "--ss-state-attention";
const ATTENTION_STRONG = "--ss-state-attention-strong";
const PASS = "--ss-state-pass";
const REJECT = "--ss-state-reject";

const DESCRIPTORS: Record<string, StatusDescriptor> = {
  /* M7 module_anomaly_status — descriptive, not diagnostic */
  clean: { label: "CLEAN", shape: "plain", colorVar: NEUTRAL },
  sporadic: { label: "SPORADIC", shape: "plain", colorVar: ATTENTION },
  persistent: { label: "PERSISTENT", shape: "plain", colorVar: ATTENTION_STRONG },

  /* HypothesisStatus */
  CANDIDATE: { label: "CANDIDATE", shape: "outlined", colorVar: NEUTRAL },
  SUPPORTED: { label: "SUPPORTED", shape: "filled", colorVar: PASS },
  CONTRADICTED: { label: "CONTRADICTED", shape: "struck", colorVar: REJECT },
  AMBIGUOUS: { label: "AMBIGUOUS", shape: "outlined", colorVar: ATTENTION, glyph: "≡" },
  INSUFFICIENT_EVIDENCE: {
    label: "INSUFFICIENT EVIDENCE",
    shape: "muted",
    colorVar: NEUTRAL,
  },

  /* InvestigationStatus — PARTIAL is separated by SHAPE, not a new hue */
  PENDING: { label: "PENDING", shape: "outlined", colorVar: NEUTRAL },
  LOADING: { label: "LOADING", shape: "outlined", colorVar: NEUTRAL },
  INVESTIGATING: { label: "INVESTIGATING", shape: "outlined", colorVar: ATTENTION },
  RETRIEVING_EVIDENCE: {
    label: "RETRIEVING EVIDENCE",
    shape: "outlined",
    colorVar: ATTENTION,
  },
  ANALYZING: { label: "ANALYZING", shape: "outlined", colorVar: ATTENTION },
  REPORTING: { label: "REPORTING", shape: "outlined", colorVar: ATTENTION },
  VALIDATING: { label: "VALIDATING", shape: "outlined", colorVar: ATTENTION },
  COMPLETED: { label: "COMPLETED", shape: "filled", colorVar: PASS },
  PARTIAL: { label: "PARTIAL", shape: "dashed", colorVar: ATTENTION_STRONG },
  FAILED: { label: "FAILED", shape: "filled", colorVar: REJECT },

  /* Module-level boolean verdicts (y_pred_module, y_pred_baseline, y_true).
     FLAGGED is attention, never reject: a flag is not a confirmed failure. */
  FLAGGED: { label: "FLAGGED", shape: "plain", colorVar: ATTENTION_STRONG },
  NOT_FLAGGED: { label: "NOT FLAGGED", shape: "muted", colorVar: NEUTRAL },

  /* Validation gates */
  PASSED: { label: "PASSED", shape: "gate", colorVar: PASS },
  REJECTED: { label: "REJECTED", shape: "gate", colorVar: REJECT },
  /** A graph node with no provenance entry: the graph never got there. */
  NOT_REACHED: { label: "NOT REACHED", shape: "muted", colorVar: NEUTRAL },

  /* Inference mode. Three distinct states — a provider failure must never be
     presentable as "not configured", and never as a successful mocked run. */
  REAL_INFERENCE: { label: "REAL INFERENCE", shape: "outlined", colorVar: PASS },
  MOCKED_INFERENCE: {
    label: "MOCKED INFERENCE",
    shape: "dashed",
    colorVar: ATTENTION_STRONG,
  },
  LLM_PROVIDER_ERROR: {
    label: "LLM PROVIDER ERROR",
    shape: "gate",
    colorVar: REJECT,
  },

  /* Readiness */
  PRESENT: { label: "PRESENT", shape: "outlined", colorVar: PASS },
  ABSENT: { label: "ABSENT", shape: "dashed", colorVar: ATTENTION_STRONG },
  READY: { label: "READY", shape: "outlined", colorVar: PASS },
  NOT_CONFIGURED: { label: "NOT CONFIGURED", shape: "dashed", colorVar: NEUTRAL },
  UNKNOWN: { label: "UNKNOWN", shape: "muted", colorVar: NEUTRAL },
};

/**
 * Resolves a backend status string. An unrecognised value keeps its raw text and
 * renders neutrally, so a future enum member is never silently given the
 * semantics of an existing one.
 */
/** Maps the readiness `inference` field onto the existing chip vocabulary. */
export function inferenceChipStatus(llm: {
  configured: boolean;
  inference?: string | null;
}): string {
  switch (llm.inference) {
    case "real":
      return "REAL_INFERENCE";
    case "mocked":
      return "MOCKED_INFERENCE";
    case "provider_error":
      return "LLM_PROVIDER_ERROR";
    case "not_configured":
      return "NOT_CONFIGURED";
    default:
      return llm.configured ? "REAL_INFERENCE" : "MOCKED_INFERENCE";
  }
}

export function statusDescriptor(value: string | null | undefined): StatusDescriptor {
  if (value === null || value === undefined || value === "") {
    return { label: "NOT RECORDED", shape: "muted", colorVar: NEUTRAL, unknown: true };
  }
  const known = DESCRIPTORS[value];
  if (known) return known;
  return { label: value.toUpperCase(), shape: "muted", colorVar: NEUTRAL, unknown: true };
}
