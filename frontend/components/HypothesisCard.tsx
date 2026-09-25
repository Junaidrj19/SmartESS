import Link from "next/link";
import { MonoId } from "@/components/MonoId";
import { RegisterBadge } from "@/components/RegisterValue";
import { StatusChip } from "@/components/StatusChip";
import type { CandidateMechanism } from "@/lib/types/backend";

/**
 * HypothesisCard — one candidate mechanism (UX.md §17; design.md §19.7, §19.8).
 *
 * Rules enforced here:
 *
 *  · Candidates are COMPETING EXPLANATIONS. No card is styled as a winner and no
 *    global ranking score is invented (design.md §19.8, §21).
 *  · `confidence` is the model's own uncalibrated number. It is labelled as such
 *    and is NEVER rendered as a probability of physical failure (design.md §19.7).
 *  · Supporting and contradictory evidence occupy separate, equally weighted
 *    columns, so contradiction is as visible as support.
 *  · Everything on this card is LLM REASONING and is badged accordingly.
 */
export function HypothesisCard({
  candidate,
  investigationId,
  /** Set when the backend nominated this mechanism as primary. Not a verdict. */
  isModelNominated = false,
  /** Ids that do not resolve to a retrieved record (design.md §12.3). */
  unresolvedIds = [],
}: {
  candidate: CandidateMechanism;
  investigationId: string;
  isModelNominated?: boolean;
  unresolvedIds?: readonly string[];
}) {
  return (
    <article
      id={candidate.candidate_id}
      className="flex h-full flex-col gap-[var(--ss-space-3)] border p-[var(--ss-space-3)]"
      style={{
        borderColor: "var(--ss-reg-llm-border)",
        backgroundColor: "var(--ss-reg-llm-surface)",
        borderRadius: "var(--ss-radius-sm)",
      }}
      data-candidate-id={candidate.candidate_id}
      data-mechanism={candidate.mechanism}
    >
      <header className="flex flex-col gap-[var(--ss-space-2)]">
        <div className="flex items-start justify-between gap-[var(--ss-space-2)]">
          <span className="ss-mono text-[var(--ss-text-primary)]">{candidate.mechanism}</span>
          <RegisterBadge register="LLM_REASONING" />
        </div>
        <MonoId value={candidate.candidate_id} />
        <div className="flex flex-wrap items-center gap-[var(--ss-space-2)]">
          <StatusChip status={candidate.status} />
          {isModelNominated && (
            <span
              className="ss-field-label border px-[var(--ss-space-1)]"
              style={{
                color: "var(--ss-reg-llm-accent)",
                borderColor: "var(--ss-reg-llm-border)",
                borderRadius: "var(--ss-radius-sm)",
              }}
              title="The model nominated this mechanism as primary. This is not a verdict and does not rank the candidates."
            >
              MODEL-NOMINATED PRIMARY
            </span>
          )}
        </div>
      </header>

      {/* Confidence: the raw model number, explicitly not a failure probability. */}
      <div className="flex flex-col gap-[var(--ss-space-1)]">
        <span className="ss-field-label">Model-assigned confidence</span>
        <span className="ss-mono text-[var(--ss-text-primary)]">{candidate.confidence}</span>
        <span className="text-[var(--ss-text-muted)]" style={{ fontSize: "var(--ss-text-label-size)" }}>
          Uncalibrated model output. Not a probability of physical failure.
        </span>
      </div>

      {/* Reasoning. */}
      <div className="flex flex-col gap-[var(--ss-space-1)]">
        <span className="ss-field-label">Reasoning</span>
        <p className="text-[var(--ss-text-secondary)]" style={{ maxWidth: "var(--ss-measure-prose)" }}>
          {candidate.reasoning}
        </p>
      </div>

      {/* Supporting vs contradictory — equal weight, separate columns. */}
      <div className="grid grid-cols-1 gap-[var(--ss-space-3)] sm:grid-cols-2">
        <EvidenceColumn
          label="Supporting evidence"
          ids={candidate.supporting_evidence_ids}
          color="var(--ss-state-pass)"
          investigationId={investigationId}
          unresolvedIds={unresolvedIds}
          emptyText="none cited"
        />
        <EvidenceColumn
          label="Contradictory evidence"
          ids={candidate.contradictory_evidence_ids}
          color="var(--ss-state-reject)"
          investigationId={investigationId}
          unresolvedIds={unresolvedIds}
          emptyText="none cited"
        />
      </div>

      {/* What would actually separate this candidate from the alternatives. */}
      <div className="mt-auto flex flex-col gap-[var(--ss-space-1)] border-t border-[var(--ss-border-subtle)] pt-[var(--ss-space-2)]">
        <span className="ss-field-label">Distinguishing measurements</span>
        {candidate.distinguishing_measurements.length === 0 ? (
          <span className="italic text-[var(--ss-text-muted)]">none proposed</span>
        ) : (
          <ul className="flex flex-col gap-[var(--ss-space-1)]">
            {candidate.distinguishing_measurements.map((m, i) => (
              <li key={i} className="text-[var(--ss-text-secondary)]">
                {m}
              </li>
            ))}
          </ul>
        )}
      </div>
    </article>
  );
}

function EvidenceColumn({
  label,
  ids,
  color,
  investigationId,
  unresolvedIds,
  emptyText,
}: {
  label: string;
  ids: readonly string[];
  color: string;
  investigationId: string;
  unresolvedIds: readonly string[];
  emptyText: string;
}) {
  return (
    <div className="flex flex-col gap-[var(--ss-space-1)]">
      <span className="ss-field-label" style={{ color }}>
        {label}
      </span>
      {ids.length === 0 ? (
        <span className="italic text-[var(--ss-text-muted)]">{emptyText}</span>
      ) : (
        <ul className="flex flex-col gap-[var(--ss-space-1)]">
          {ids.map((id) => {
            const unresolved = unresolvedIds.includes(id);
            return (
              <li key={id}>
                {unresolved ? (
                  <span className="ss-mono text-[var(--ss-state-attention-strong)]" title="Does not resolve to a retrieved evidence record">
                    {id} — UNRESOLVED
                  </span>
                ) : (
                  <Link
                    href={`/investigations/${investigationId}/evidence#evidence-${id}`}
                    className="ss-mono break-all text-[var(--ss-accent)] hover:text-[var(--ss-accent-hover)]"
                  >
                    {id}
                  </Link>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
