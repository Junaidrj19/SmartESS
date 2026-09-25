import { StatusChip } from "@/components/StatusChip";
import type { GateOutcome } from "@/lib/investigation";

/**
 * GateResult — a validation gate outcome (UX.md §15; design.md §6.1).
 *
 * The gates are the strongest available evidence that SmartESS is not an LLM
 * wrapper, so they are rendered prominently with their issue list verbatim.
 *
 * Critical nuance (design.md §14.10): after the retry budget is exhausted the
 * graph proceeds to `report_agent` ANYWAY. A rejected gate therefore coexists
 * with a report, and that must never be presented as a clean result.
 */
export function GateResult({
  outcome,
  retryCounts,
}: {
  outcome: GateOutcome;
  retryCounts?: Record<string, number>;
}) {
  const title =
    outcome.gate === "hypothesis_validation" ? "Hypothesis Validation" : "Report Validation";

  const relevantRetry =
    outcome.gate === "hypothesis_validation"
      ? retryCounts?.["hypothesis_retries"]
      : retryCounts?.["report_retries"];

  if (!outcome.reached) {
    return (
      <div
        className="flex flex-col gap-[var(--ss-space-2)] border border-dashed border-[var(--ss-border-strong)] p-[var(--ss-space-3)]"
        style={{ borderRadius: "var(--ss-radius-sm)" }}
      >
        <div className="flex items-center gap-[var(--ss-space-2)]">
          <span className="ss-field-label">{title}</span>
          <StatusChip status="NOT_REACHED" />
        </div>
        <p className="text-[var(--ss-text-muted)]">
          This gate produced no provenance entry: the graph did not reach it.
        </p>
      </div>
    );
  }

  return (
    <div
      className="flex flex-col gap-[var(--ss-space-2)] border p-[var(--ss-space-3)]"
      style={{
        borderColor: outcome.passed ? "var(--ss-border-subtle)" : "var(--ss-state-reject)",
        borderLeftWidth: "3px",
        borderRadius: "var(--ss-radius-sm)",
        backgroundColor: "var(--ss-reg-validation-surface)",
      }}
      data-gate={outcome.gate}
      data-passed={String(outcome.passed)}
    >
      <div className="flex flex-wrap items-center gap-[var(--ss-space-2)]">
        <span className="ss-field-label">{title}</span>
        <StatusChip
          status={outcome.passed ? "PASSED" : "REJECTED"}
          suffix={outcome.passed ? undefined : String(outcome.issues.length)}
        />
        {typeof relevantRetry === "number" && (
          <span className="ss-field-label text-[var(--ss-text-muted)]">
            RETRIES {relevantRetry}
          </span>
        )}
      </div>

      {outcome.description && (
        <p className="text-[var(--ss-text-secondary)]" style={{ maxWidth: "var(--ss-measure-prose)" }}>
          {outcome.description}
        </p>
      )}

      {outcome.issues.length > 0 && (
        <ul className="flex flex-col gap-[var(--ss-space-1)]">
          {outcome.issues.map((issue, i) => (
            <li key={i} className="ss-mono break-words text-[var(--ss-state-reject)]">
              {issue}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
