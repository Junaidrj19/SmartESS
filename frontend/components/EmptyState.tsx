import type { ReactNode } from "react";
import { STATE_COPY, type StateCopy, type StateKey } from "@/lib/copy/states";

/**
 * EmptyState — renders one of the exact §44.9 state strings.
 *
 * The whole point of this component is that NO DATA, NO ANOMALY, INSUFFICIENT
 * EVIDENCE and SYSTEM ERROR are visually and textually distinguishable
 * (UX.md §30; design.md §14.16, acceptance 21). It is never a blank panel and
 * never a decorative illustration.
 */
export function EmptyState({
  state,
  detail,
  body,
  children,
}: {
  state: StateKey;
  /** Concrete detail: expected path, producing CLI, verbatim backend note. */
  detail?: ReactNode;
  /** Overrides the copy body only where §44.9 defines it as backend-supplied. */
  body?: string;
  children?: ReactNode;
}) {
  // Widened to StateCopy: `STATE_COPY` is `as const`, so the per-key literal
  // types do not all carry `note`.
  const copy: StateCopy = STATE_COPY[state];
  const isSetup = state === "NO_DATA";

  return (
    <div
      className="flex flex-col gap-[var(--ss-space-2)] border border-dashed border-[var(--ss-border-strong)] p-[var(--ss-space-4)]"
      style={{ borderRadius: "var(--ss-radius-sm)" }}
      data-state={state}
    >
      <span className="ss-field-label text-[var(--ss-text-secondary)]">{copy.title}</span>
      {(body ?? copy.body) && (
        <p className="text-[var(--ss-text-secondary)]" style={{ maxWidth: "var(--ss-measure-prose)" }}>
          {body ?? copy.body}
        </p>
      )}
      {detail && <div className="ss-mono text-[var(--ss-text-muted)]">{detail}</div>}
      {copy.note && (
        <p
          className={isSetup ? "text-[var(--ss-text-muted)]" : "text-[var(--ss-text-secondary)]"}
          style={{ fontSize: "var(--ss-text-label-size)" }}
        >
          {copy.note}
        </p>
      )}
      {children}
    </div>
  );
}
