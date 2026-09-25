/**
 * LoadingState — a layout-preserving skeleton (UX.md §31).
 *
 * No spinner, no motion that carries meaning. Rows match the density of the
 * content they replace so the panel does not resize on load.
 */
export function LoadingState({
  rows = 3,
  label = "Loading",
}: {
  rows?: number;
  label?: string;
}) {
  return (
    <div
      className="flex flex-col gap-[var(--ss-space-2)] p-[var(--ss-space-4)]"
      aria-busy="true"
      aria-live="polite"
    >
      <span className="ss-sr-only">{label}</span>
      {Array.from({ length: rows }, (_, i) => (
        <div
          key={i}
          className="h-[var(--ss-space-4)] bg-[var(--ss-bg-raised)]"
          style={{
            borderRadius: "var(--ss-radius-sm)",
            width: i === rows - 1 ? "60%" : "100%",
          }}
        />
      ))}
    </div>
  );
}
