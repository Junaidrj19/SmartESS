/**
 * MonoId — a machine identifier.
 *
 * UX.md §44.6 makes monospace with tabular numerals mandatory for module_id,
 * test_id, lot_id, dataset_id, model_id, investigation_id, evidence_id,
 * chunk_id, document_id, candidate_id, cycle numbers, hashes, enum values, tool
 * names, file paths and provider/model strings.
 */
export function MonoId({
  value,
  title,
  truncate = false,
  className = "",
}: {
  value: string | null | undefined;
  title?: string;
  truncate?: boolean;
  className?: string;
}) {
  if (value === null || value === undefined || value === "") {
    return (
      <span className="text-[var(--ss-text-muted)] italic">not recorded</span>
    );
  }
  return (
    <span
      className={`ss-mono ${truncate ? "truncate" : "break-all"} ${className}`}
      title={title ?? value}
    >
      {value}
    </span>
  );
}
