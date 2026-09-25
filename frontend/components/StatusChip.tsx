import { statusDescriptor, type ChipShape } from "@/lib/copy/status";

/**
 * StatusChip — the canonical status vocabulary (UX.md §24, §44.3).
 *
 * Colour is always accompanied by uppercase TEXT and a SHAPE. `PARTIAL` is
 * separated from `persistent` by a dashed border rather than a second hue, per
 * the approved token decision.
 *
 * An unrecognised status renders neutrally with its raw text (design.md §18.3).
 */
export function StatusChip({
  status,
  suffix,
  className = "",
}: {
  status: string | null | undefined;
  /** Additional detail, e.g. an anomaly rate or an issue count. */
  suffix?: string;
  className?: string;
}) {
  const d = statusDescriptor(status);
  const color = `var(${d.colorVar})`;

  const shapeStyle: Record<ChipShape, React.CSSProperties> = {
    plain: { color, borderColor: color, borderWidth: "var(--ss-border-width)" },
    outlined: { color, borderColor: color, borderWidth: "var(--ss-border-width)" },
    filled: {
      color: "var(--ss-bg-base)",
      backgroundColor: color,
      borderColor: color,
      borderWidth: "var(--ss-border-width)",
    },
    struck: {
      color,
      borderColor: color,
      borderWidth: "var(--ss-border-width)",
      textDecoration: "line-through",
    },
    muted: {
      color: "var(--ss-text-muted)",
      borderColor: "var(--ss-border-subtle)",
      borderWidth: "var(--ss-border-width)",
    },
    dashed: {
      color,
      borderColor: color,
      borderWidth: "var(--ss-border-width)",
      borderStyle: "dashed",
    },
    gate: {
      color,
      borderColor: color,
      borderWidth: "var(--ss-border-width)",
      borderLeftWidth: "3px",
    },
  };

  return (
    <span
      className={`ss-field-label inline-flex shrink-0 items-center gap-[var(--ss-space-1)] border border-solid px-[var(--ss-space-1)] ${className}`}
      style={{ ...shapeStyle[d.shape], borderRadius: "var(--ss-radius-sm)" }}
      data-status={status ?? "not-recorded"}
      data-unknown={d.unknown ? "true" : undefined}
    >
      {d.glyph && <span aria-hidden="true">{d.glyph}</span>}
      <span>{d.label}</span>
      {suffix && <span className="ss-mono normal-case">{suffix}</span>}
    </span>
  );
}
