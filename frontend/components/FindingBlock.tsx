import Link from "next/link";
import { RegisterBadge } from "@/components/RegisterValue";
import type { Register } from "@/lib/registers";
import type { Finding, FindingClassification } from "@/lib/types/backend";

/**
 * FindingBlock — one report finding (UX.md §18; design.md §12.4).
 *
 * `FindingClassification` maps onto the epistemic registers, so a finding declares
 * its own status. `CONFIRMED` is mapped to HUMAN_DECISION and in practice never
 * appears: `validate_report` REJECTS any CONFIRMED mechanism finding. The mapping
 * is implemented anyway, and its absence is a feature (design.md §12.4).
 */
const CLASSIFICATION_REGISTER: Record<FindingClassification, Register> = {
  OBSERVED: "DATA",
  CALCULATED: "CALCULATION",
  PREDICTED: "CALCULATION",
  HYPOTHESIZED: "LLM_REASONING",
  CONFIRMED: "HUMAN_DECISION",
  RECOMMENDED: "DATA",
};

export function FindingBlock({
  finding,
  investigationId,
  unresolvedIds = [],
}: {
  finding: Finding;
  investigationId: string;
  unresolvedIds?: readonly string[];
}) {
  const register = CLASSIFICATION_REGISTER[finding.classification] ?? "DATA";
  const isRecommendation = finding.classification === "RECOMMENDED";

  return (
    <div
      className="flex flex-col gap-[var(--ss-space-2)] border border-[var(--ss-border-subtle)] p-[var(--ss-space-3)]"
      style={{
        borderRadius: "var(--ss-radius-sm)",
        borderLeftWidth: "2px",
        borderLeftStyle: isRecommendation ? "dashed" : "solid",
        borderLeftColor:
          register === "LLM_REASONING"
            ? "var(--ss-reg-llm-border)"
            : register === "CALCULATION"
              ? "var(--ss-reg-calc-rule)"
              : "var(--ss-border-strong)",
        backgroundColor:
          register === "LLM_REASONING"
            ? "var(--ss-reg-llm-surface)"
            : register === "CALCULATION"
              ? "var(--ss-reg-calc-surface)"
              : "var(--ss-bg-surface)",
      }}
      data-classification={finding.classification}
      data-register={register}
    >
      <div className="flex flex-wrap items-start justify-between gap-[var(--ss-space-2)]">
        <span className="ss-mono text-[var(--ss-text-primary)]">{finding.label}</span>
        <div className="flex shrink-0 items-center gap-[var(--ss-space-2)]">
          <span className="ss-field-label text-[var(--ss-text-label)]">
            {finding.classification}
          </span>
          <RegisterBadge register={register} />
        </div>
      </div>

      <p
        className="whitespace-pre-wrap break-words text-[var(--ss-text-secondary)]"
        style={{ maxWidth: "var(--ss-measure-prose)" }}
      >
        {finding.detail}
      </p>

      <div className="flex flex-wrap items-center gap-[var(--ss-space-4)]">
        {finding.source && (
          <span className="ss-field-label">
            SOURCE <span className="ss-mono normal-case">{finding.source}</span>
          </span>
        )}
        {finding.evidence_ids.length > 0 && (
          <div className="flex flex-wrap items-center gap-[var(--ss-space-2)]">
            <span className="ss-field-label">Trace</span>
            {finding.evidence_ids.map((id) =>
              unresolvedIds.includes(id) ? (
                <span
                  key={id}
                  className="ss-mono text-[var(--ss-state-attention-strong)]"
                  title="Does not resolve to a retrieved evidence record"
                >
                  {id} — UNRESOLVED
                </span>
              ) : (
                <Link
                  key={id}
                  href={`/investigations/${investigationId}/evidence#evidence-${id}`}
                  className="ss-mono break-all text-[var(--ss-accent)] hover:text-[var(--ss-accent-hover)]"
                >
                  {id}
                </Link>
              ),
            )}
          </div>
        )}
      </div>
    </div>
  );
}
