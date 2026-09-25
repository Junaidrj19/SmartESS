import Link from "next/link";

/**
 * NextAction — the explicit forward step from every workflow surface
 * (UX.md §29: avoid dead-end pages, avoid making the user guess how to continue).
 *
 * `disabledReason` renders the step as unavailable with the reason stated,
 * rather than hiding it — a missing next step is information.
 */
export function NextAction({
  href,
  label,
  hint,
  disabledReason,
}: {
  href?: string;
  label: string;
  hint?: string;
  disabledReason?: string;
}) {
  const body = (
    <>
      <span className="ss-field-label">Next</span>
      <span className="text-[var(--ss-text-primary)]">{label}</span>
      {hint && <span className="text-[var(--ss-text-muted)]">{hint}</span>}
    </>
  );

  if (!href || disabledReason) {
    return (
      <div
        className="flex flex-wrap items-baseline gap-[var(--ss-space-2)] border border-dashed border-[var(--ss-border-strong)] p-[var(--ss-space-3)]"
        style={{ borderRadius: "var(--ss-radius-sm)" }}
      >
        <span className="ss-field-label">Next</span>
        <span className="text-[var(--ss-text-muted)]">{label}</span>
        {disabledReason && (
          <span className="ss-mono text-[var(--ss-text-muted)]">— {disabledReason}</span>
        )}
      </div>
    );
  }

  return (
    <Link
      href={href}
      className="flex flex-wrap items-baseline gap-[var(--ss-space-2)] border border-[var(--ss-border-strong)] p-[var(--ss-space-3)] hover:border-[var(--ss-accent)]"
      style={{ borderRadius: "var(--ss-radius-sm)" }}
    >
      {body}
      <span aria-hidden="true" className="ml-auto text-[var(--ss-accent)]">
        →
      </span>
    </Link>
  );
}

/** A row of workflow steps with the current one marked, for orientation. */
export function WorkflowStrip({
  steps,
  current,
}: {
  steps: readonly { label: string; href?: string }[];
  current: string;
}) {
  return (
    <nav
      className="flex flex-wrap items-center gap-[var(--ss-space-1)]"
      aria-label="Workflow position"
    >
      {steps.map((s, i) => {
        const isCurrent = s.label === current;
        const content = (
          <span
            className="ss-field-label border px-[var(--ss-space-2)] py-[var(--ss-space-1)]"
            style={{
              borderRadius: "var(--ss-radius-sm)",
              borderColor: isCurrent ? "var(--ss-accent)" : "var(--ss-border-subtle)",
              color: isCurrent ? "var(--ss-text-primary)" : "var(--ss-text-muted)",
              backgroundColor: isCurrent ? "var(--ss-accent-muted)" : "transparent",
            }}
            aria-current={isCurrent ? "step" : undefined}
          >
            {s.label}
          </span>
        );
        return (
          <span key={s.label} className="flex items-center gap-[var(--ss-space-1)]">
            {s.href && !isCurrent ? <Link href={s.href}>{content}</Link> : content}
            {i < steps.length - 1 && (
              <span aria-hidden="true" className="text-[var(--ss-text-muted)]">
                ›
              </span>
            )}
          </span>
        );
      })}
    </nav>
  );
}
