import { RegisterBadge } from "@/components/RegisterValue";
import type { Register } from "@/lib/registers";

/**
 * MetricValue — a measured or calculated quantity.
 *
 * The value is rendered EXACTLY as the backend supplied it. This component
 * performs no rounding, no unit conversion and no derivation (UX.md §35 Rule 2;
 * design.md acceptance 19). If a display precision is ever required it must be
 * applied deliberately by the caller and the full value kept in `title`.
 *
 * `unit` is optional and must be omitted unless the unit is actually known.
 * No engineering unit is carried in the M6/M7 artifacts (design.md §20.4), so
 * fabricating one is forbidden.
 */
export function MetricValue({
  label,
  value,
  unit,
  register,
  note,
  className = "",
}: {
  label: string;
  /** Raw backend value. Numbers are stringified without reformatting. */
  value: string | number | boolean | null | undefined;
  unit?: string;
  register: Register;
  note?: string;
  className?: string;
}) {
  const notRecorded = value === null || value === undefined || value === "";
  const display = notRecorded
    ? "not recorded"
    : typeof value === "boolean"
      ? String(value)
      : String(value);

  return (
    <div className={`flex flex-col gap-[var(--ss-space-1)] ${className}`}>
      <div className="flex items-center justify-between gap-[var(--ss-space-2)]">
        <span className="ss-field-label">{label}</span>
        <RegisterBadge register={register} />
      </div>
      <span
        className={
          notRecorded
            ? "text-[var(--ss-text-muted)] italic"
            : "ss-mono text-[var(--ss-text-primary)]"
        }
        title={notRecorded ? undefined : display}
      >
        {display}
        {!notRecorded && unit ? (
          <span className="ml-[var(--ss-space-1)] text-[var(--ss-text-muted)]">{unit}</span>
        ) : null}
      </span>
      {note && (
        <span className="text-[var(--ss-text-muted)]" style={{ fontSize: "var(--ss-text-label-size)" }}>
          {note}
        </span>
      )}
    </div>
  );
}
