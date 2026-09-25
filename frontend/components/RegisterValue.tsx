import type { ReactNode } from "react";
import { registerDefinition, type Register } from "@/lib/registers";

/**
 * RegisterBadge — renders the epistemic register label itself (UX.md §43.1).
 *
 * Always text, never colour alone.
 */
export function RegisterBadge({
  register,
  className = "",
}: {
  register: Register;
  className?: string;
}) {
  const def = registerDefinition(register);
  return (
    <span
      className={`ss-field-label inline-flex shrink-0 items-center border px-[var(--ss-space-1)] ${def.badge} ${className}`}
      style={{ borderRadius: "var(--ss-radius-sm)" }}
      title={def.meaning}
    >
      {def.label}
    </span>
  );
}

/**
 * RegisterValue — renders a single value in its epistemic register.
 *
 * `register` is REQUIRED (UX.md §37, §43.1; design.md §19.9). No value may
 * silently inherit an epistemic treatment, which is what prevents a measured
 * signal and an LLM sentence from ever sharing a visual treatment.
 *
 * This component never formats numbers. Use MetricValue for measured
 * quantities so that no rounding is introduced here (UX.md §35 Rule 2).
 */
export function RegisterValue({
  register,
  label,
  value,
  mono = false,
  showBadge = true,
  children,
}: {
  register: Register;
  label?: string;
  /** Pre-formatted display string, exactly as it should appear. */
  value?: string | null;
  mono?: boolean;
  showBadge?: boolean;
  children?: ReactNode;
}) {
  const def = registerDefinition(register);
  const notRecorded = value === null || value === undefined;

  return (
    <div
      className={`flex flex-col gap-[var(--ss-space-1)] p-[var(--ss-space-2)] ${def.surface}`}
      style={{ borderRadius: "var(--ss-radius-sm)" }}
      data-register={register}
    >
      {(label || showBadge) && (
        <div className="flex items-center justify-between gap-[var(--ss-space-2)]">
          {label ? <span className="ss-field-label">{label}</span> : <span />}
          {showBadge && <RegisterBadge register={register} />}
        </div>
      )}
      {children ?? (
        <span
          className={`${mono ? "ss-mono" : ""} ${
            notRecorded ? "text-[var(--ss-text-muted)] italic" : def.valueClass
          }`}
        >
          {notRecorded ? "not recorded" : value}
        </span>
      )}
    </div>
  );
}
