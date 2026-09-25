import type { ReactNode } from "react";
import { StatusChip } from "@/components/StatusChip";
import type { Register } from "@/lib/registers";
import { RegisterBadge } from "@/components/RegisterValue";
import type { Stage } from "@/lib/investigation";
import type { PipelineStep } from "@/lib/types/backend";

/**
 * Stage metadata — UX.md §10, §11; design.md §6.1.
 *
 * The four agents and the two validation gates are named, first-class concepts.
 * `register` declares what KIND of thing each stage produces, which is what makes
 * the deterministic / retrieval / generative boundary visible at a glance.
 */
export const STAGE_META: Record<
  PipelineStep,
  { title: string; agent: string | null; register: Register; summary: string }
> = {
  load_investigation: {
    title: "Load Investigation",
    agent: null,
    register: "DATA",
    summary: "Request accepted; frozen M7/M8 artifacts identified.",
  },
  investigation_agent: {
    title: "Investigation Agent",
    agent: "Investigation Agent",
    register: "CALCULATION",
    summary: "Fixed deterministic engineering tools. No model involved.",
  },
  evidence_agent: {
    title: "Evidence Agent",
    agent: "Evidence Agent",
    register: "RETRIEVED_EVIDENCE",
    summary: "Knowledge-base retrieval. No generation.",
  },
  hypothesis_agent: {
    title: "Hypothesis Agent",
    agent: "Hypothesis Agent",
    register: "LLM_REASONING",
    summary: "The only generative stage. Output requires engineering confirmation.",
  },
  hypothesis_validation: {
    title: "Hypothesis Validation",
    agent: null,
    register: "VALIDATION",
    summary: "Every cited evidence id must resolve to a retrieved record.",
  },
  report_agent: {
    title: "Report Agent",
    agent: "Report Agent",
    register: "CALCULATION",
    summary: "Deterministic synthesis. Recalculates nothing, invents nothing.",
  },
  report_validation: {
    title: "Report Validation",
    agent: null,
    register: "VALIDATION",
    summary: "Section completeness, citation resolution, no asserted certainty.",
  },
};

/**
 * StageNode — one node of the LangGraph topology as an inspectable row.
 *
 * This is NOT decorative animation: `outcome` and `executions` come from the
 * recorded provenance, so a repeated node genuinely means the graph looped back
 * (design.md §6, §12.2).
 */
export function StageNode({
  stage,
  index,
  children,
}: {
  stage: Stage;
  index: number;
  children?: ReactNode;
}) {
  const meta = STAGE_META[stage.step];
  const statusFor =
    stage.outcome === "executed" ? "PASSED" : stage.outcome === "rejected" ? "REJECTED" : "UNKNOWN";

  return (
    <li
      className="border border-[var(--ss-border-subtle)] bg-[var(--ss-bg-surface)]"
      style={{ borderRadius: "var(--ss-radius-sm)" }}
      data-step={stage.step}
      data-outcome={stage.outcome}
    >
      <div className="flex flex-wrap items-baseline gap-[var(--ss-space-3)] p-[var(--ss-space-3)]">
        <span className="ss-mono shrink-0 text-[var(--ss-text-muted)]">
          {String(index + 1).padStart(2, "0")}
        </span>
        <div className="flex min-w-[220px] flex-col gap-[var(--ss-space-1)]">
          <span className="ss-mono text-[var(--ss-text-primary)]">{stage.step}</span>
          <span className="ss-field-label">{meta.title}</span>
        </div>
        <span className="min-w-[240px] flex-1 text-[var(--ss-text-secondary)]">{meta.summary}</span>
        <div className="flex shrink-0 items-center gap-[var(--ss-space-2)]">
          <RegisterBadge register={meta.register} />
          {stage.outcome === "not-reached" ? (
            <StatusChip status="NOT_REACHED" />
          ) : (
            <StatusChip status={statusFor} />
          )}
          {stage.executions > 1 && (
            <span className="ss-field-label text-[var(--ss-state-attention-strong)]">
              {stage.executions}× EXECUTED
            </span>
          )}
        </div>
      </div>
      {children}
    </li>
  );
}
