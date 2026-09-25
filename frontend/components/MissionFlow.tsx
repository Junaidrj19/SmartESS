/**
 * MissionFlow — the investigation chain as a compact process map (UX.md §5).
 *
 * "This is an orientation device, not decorative animation." Each stage is a
 * real pipeline stage. Stages whose surfaces do not exist yet are rendered as
 * unavailable rather than linked to a dead end (design.md §10.2).
 *
 * The map exists to answer, in the first viewport, what SmartESS actually does:
 * measurement → detection → evaluation → deterministic analysis → evidence →
 * LLM hypotheses → validation → report.
 */

import Link from "next/link";
import type { Register } from "@/lib/registers";
import { registerDefinition } from "@/lib/registers";

interface FlowStage {
  readonly label: string;
  readonly register: Register;
  readonly detail: string;
  readonly href?: string;
}

const STAGES: readonly FlowStage[] = [
  {
    label: "DATA",
    register: "DATA",
    detail: "8 baseline signals per observation (M6 v1)",
  },
  {
    label: "M7 DETECTOR",
    register: "DATA",
    detail: "Isolation Forest anomaly score and flag",
  },
  {
    label: "M8 EVALUATION",
    register: "CALCULATION",
    detail: "Detector behaviour against a frozen population",
  },
  {
    label: "DETERMINISTIC ANALYSIS",
    register: "CALCULATION",
    detail: "Fixed engineering tools — no model involved",
  },
  {
    label: "EVIDENCE RETRIEVAL",
    register: "RETRIEVED_EVIDENCE",
    detail: "Passages from verified engineering documents",
  },
  {
    label: "LLM HYPOTHESES",
    register: "LLM_REASONING",
    detail: "Competing candidate mechanisms, cited to evidence",
  },
  {
    label: "VALIDATION",
    register: "VALIDATION",
    detail: "Hypothesis and report gates",
  },
  {
    label: "ENGINEERING REPORT",
    register: "DATA",
    detail: "15 sections, every finding classified",
  },
];

export function MissionFlow() {
  return (
    <ol className="flex flex-col gap-[var(--ss-space-1)]" aria-label="Investigation chain">
      {STAGES.map((stage, index) => {
        const def = registerDefinition(stage.register);
        const body = (
          <div
            className={`flex items-baseline gap-[var(--ss-space-3)] px-[var(--ss-space-3)] py-[var(--ss-space-2)] ${def.surface}`}
            style={{ borderRadius: "var(--ss-radius-sm)" }}
            data-register={stage.register}
          >
            <span className="ss-mono shrink-0 text-[var(--ss-text-muted)]">
              {String(index + 1).padStart(2, "0")}
            </span>
            <span className="ss-field-label shrink-0 w-[172px] text-[var(--ss-text-primary)]">
              {stage.label}
            </span>
            <span className="text-[var(--ss-text-secondary)]">{stage.detail}</span>
            {!stage.href && (
              <span className="ss-field-label ml-auto shrink-0 text-[var(--ss-text-muted)]">
                N/I
              </span>
            )}
          </div>
        );

        return (
          <li key={stage.label}>
            {stage.href ? (
              <Link href={stage.href} className="block">
                {body}
              </Link>
            ) : (
              body
            )}
          </li>
        );
      })}
    </ol>
  );
}
