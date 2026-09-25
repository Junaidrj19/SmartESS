import { notFound } from "next/navigation";
import { EmptyState } from "@/components/EmptyState";
import { GateResult } from "@/components/GateResult";
import { HypothesisCard } from "@/components/HypothesisCard";
import { MetricValue } from "@/components/MetricValue";
import { MonoId } from "@/components/MonoId";
import { NextAction } from "@/components/NextAction";
import { Panel, SectionHeader } from "@/components/Panel";
import { RegisterBadge } from "@/components/RegisterValue";
import { getInvestigation } from "@/lib/api/endpoints";
import { asString, gateOutcome, resolveEvidence } from "@/lib/investigation";

/**
 * Hypothesis Comparison (UX.md §17; design.md §14 competing hypotheses).
 *
 * The candidates are presented side by side as COMPETING explanations. There is
 * no ranking, no winner styling and no fabricated global score. `primary_mechanism`
 * is shown only as model-nominated.
 */
export default async function HypothesesPage({
  params,
}: {
  params: Promise<{ investigationId: string }>;
}) {
  const { investigationId } = await params;
  const result = await getInvestigation(investigationId);
  if (result.kind !== "ok") notFound();
  const record = result.data;

  const hypothesis = record.hypothesis;
  const candidates = hypothesis?.candidates ?? [];
  const gate = gateOutcome(record, "hypothesis_validation");

  // Ids cited by any candidate that do not resolve to a retrieved record.
  const unresolved = [
    ...new Set(
      candidates
        .flatMap((c) => [...c.supporting_evidence_ids, ...c.contradictory_evidence_ids])
        .filter((id) => resolveEvidence(record, id) === null),
    ),
  ];

  const byStatus = candidates.reduce<Record<string, number>>((acc, c) => {
    acc[c.status] = (acc[c.status] ?? 0) + 1;
    return acc;
  }, {});

  if (candidates.length === 0) {
    const clean = asString(record.m7_module_summary["module_anomaly_status"]) === "clean";
    return (
      <Panel>
        <SectionHeader
          level={1} title="Hypothesis Comparison" />
        <div className="p-[var(--ss-space-4)]">
          <EmptyState
            state={clean ? "INSUFFICIENT_EVIDENCE" : "MECHANISM_UNRESOLVED"}
            detail={hypothesis?.note || record.errors["hypothesis"] || undefined}
          />
        </div>
      </Panel>
    );
  }

  return (
    <>
      <Panel>
        <SectionHeader
          level={1}
          title="Hypothesis Comparison"
          subtitle="Candidate degradation mechanisms proposed by the language model, each bound to the evidence it cites. These are competing explanations, not a diagnosis — none is confirmed and none is ranked above the others."
          actions={<RegisterBadge register="LLM_REASONING" />}
        />
        <div className="flex flex-col gap-[var(--ss-space-3)] p-[var(--ss-space-4)]">
          <div className="grid grid-cols-2 gap-[var(--ss-space-4)] lg:grid-cols-4">
            <MetricValue label="Candidates" value={candidates.length} register="LLM_REASONING" />
            <MetricValue
              label="Hypothesis id"
              value={hypothesis?.hypothesis_id ?? null}
              register="LLM_REASONING"
            />
            <MetricValue
              label="Model-nominated primary"
              value={hypothesis?.primary_mechanism ?? null}
              register="LLM_REASONING"
              note="not a verdict"
            />
            <MetricValue
              label="Unresolved citations"
              value={unresolved.length}
              register="VALIDATION"
            />
          </div>

          <div className="flex flex-wrap items-center gap-[var(--ss-space-2)]">
            <span className="ss-field-label">Status distribution</span>
            {Object.entries(byStatus).map(([status, n]) => (
              <span
                key={status}
                className="ss-field-label border border-[var(--ss-border-subtle)] px-[var(--ss-space-1)] text-[var(--ss-text-secondary)]"
                style={{ borderRadius: "var(--ss-radius-sm)" }}
              >
                {status} · {n}
              </span>
            ))}
          </div>

          {hypothesis?.note && (
            <div className="flex flex-col gap-[var(--ss-space-1)]">
              <span className="ss-field-label">Model note</span>
              <p
                className="text-[var(--ss-text-secondary)]"
                style={{ maxWidth: "var(--ss-measure-prose)" }}
              >
                {hypothesis.note}
              </p>
            </div>
          )}
        </div>
      </Panel>

      {/* ── the gate that checked these candidates ─────────────────── */}
      <Panel>
        <SectionHeader title="Hypothesis validation" level={3} />
        <div className="p-[var(--ss-space-4)]">
          <GateResult outcome={gate} retryCounts={record.retry_counts} />
        </div>
      </Panel>

      {/* ── competing candidates, equal weight ─────────────────────── */}
      <div className="grid grid-cols-1 gap-[var(--ss-space-4)] xl:grid-cols-2">
        {candidates.map((c) => (
          <HypothesisCard
            key={c.candidate_id}
            candidate={c}
            investigationId={investigationId}
            isModelNominated={hypothesis?.primary_mechanism === c.mechanism}
            unresolvedIds={unresolved}
          />
        ))}
      </div>

      {unresolved.length > 0 && (
        <Panel>
          <SectionHeader title="Unresolved citations" level={3} />
          <div className="p-[var(--ss-space-4)]">
            <EmptyState
              state="VALIDATION_REJECTED"
              body="These evidence ids were cited by a candidate but do not resolve to any retrieved evidence record."
              detail={unresolved.join(", ")}
            />
          </div>
        </Panel>
      )}
      <NextAction
        href={`/investigations/${investigationId}/report`}
        label="Open Engineering Report"
        hint="the 15-section report and its validation"
      />
    </>
  );
}
