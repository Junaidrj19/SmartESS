import { MonoId } from "@/components/MonoId";
import { StatusChip } from "@/components/StatusChip";
import { ANOMALY_QUALIFICATION, SYNTHETIC_NOTE } from "@/lib/copy/states";

/**
 * The investigation context the rail carries. Every field is optional because
 * nothing may be invented: a field with no backend value renders as
 * `not recorded` (UX.md §4; design.md §18.2).
 */
export interface InvestigationContext {
  moduleId?: string | null;
  testId?: string | null;
  lotId?: string | null;
  datasetId?: string | null;
  /** `SYNTHETIC` for every dataset in this repository (design.md §15.4). */
  dataOrigin?: string | null;
  modelId?: string | null;
  featureVersion?: string | null;
  detectorVersion?: string | null;
  /** `clean` | `sporadic` | `persistent` — descriptive, not diagnostic. */
  moduleStatus?: string | null;
  investigationId?: string | null;
  investigationStatus?: string | null;
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-[var(--ss-space-1)]">
      <span className="ss-field-label">{label}</span>
      <div className="text-[var(--ss-text-primary)]">{children}</div>
    </div>
  );
}

/**
 * ContextRail — persistent investigation context (UX.md §4).
 *
 * It must survive route changes and panel-level API errors, so it is rendered by
 * the root layout and never inside a panel that can fail. The engineer must
 * never wonder which module they are inspecting.
 */
export function ContextRail({ context }: { context: InvestigationContext }) {
  const hasModule = Boolean(context.moduleId);

  return (
    <aside
      className="flex w-full shrink-0 flex-col gap-[var(--ss-space-4)] border-b border-[var(--ss-border-subtle)] bg-[var(--ss-bg-inset)] p-[var(--ss-space-4)] lg:h-full lg:w-[264px] lg:border-b-0 lg:border-r lg:overflow-y-auto"
      aria-label="Investigation context"
    >
      <div className="flex flex-col gap-[var(--ss-space-1)]">
        <span className="ss-field-label">Context</span>
        {!hasModule && (
          <p className="text-[var(--ss-text-muted)]">
            No module selected. Investigation context appears here and persists
            across every view.
          </p>
        )}
      </div>

      {hasModule && (
        <>
          <Field label="Module">
            <MonoId value={context.moduleId} />
          </Field>
          <Field label="Test">
            <MonoId value={context.testId} />
          </Field>
          <Field label="Lot">
            <MonoId value={context.lotId} />
          </Field>
          <Field label="Dataset">
            <MonoId value={context.datasetId} />
          </Field>
          <Field label="Data origin">
            <div className="flex flex-col gap-[var(--ss-space-1)]">
              <MonoId value={context.dataOrigin} />
              <span
                className="text-[var(--ss-text-muted)]"
                style={{ fontSize: "var(--ss-text-label-size)" }}
              >
                {SYNTHETIC_NOTE}
              </span>
            </div>
          </Field>
          <Field label="Model">
            <MonoId value={context.modelId} />
          </Field>
          <div className="grid grid-cols-2 gap-[var(--ss-space-3)]">
            <Field label="Feature ver.">
              <MonoId value={context.featureVersion} />
            </Field>
            <Field label="Detector ver.">
              <MonoId value={context.detectorVersion} />
            </Field>
          </div>
          <Field label="Module status">
            <div className="flex flex-col gap-[var(--ss-space-1)]">
              <StatusChip status={context.moduleStatus} />
              <span
                className="text-[var(--ss-text-muted)]"
                style={{ fontSize: "var(--ss-text-label-size)" }}
              >
                {ANOMALY_QUALIFICATION}
              </span>
            </div>
          </Field>
          <Field label="Investigation">
            <MonoId value={context.investigationId} />
          </Field>
          <Field label="Status">
            <StatusChip status={context.investigationStatus} />
          </Field>
        </>
      )}
    </aside>
  );
}
