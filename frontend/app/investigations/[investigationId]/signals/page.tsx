import { notFound } from "next/navigation";
import { AccessibleDataTable } from "@/components/AccessibleDataTable";
import { EmptyState } from "@/components/EmptyState";
import { MetricValue } from "@/components/MetricValue";
import { MonoId } from "@/components/MonoId";
import { NextAction } from "@/components/NextAction";
import { Panel, SectionHeader } from "@/components/Panel";
import { RegisterBadge } from "@/components/RegisterValue";
import { ScientificChart, type ChartPoint } from "@/components/ScientificChart";
import { getInvestigation } from "@/lib/api/endpoints";
import { asNumber, raw, resultsForSignal, signalOf } from "@/lib/investigation";
import { SIGNAL_ORDER, SIGNAL_STYLE } from "@/lib/signals";
import { ErrorState } from "@/components/ErrorState";

/**
 * Signal Analysis, investigation-scoped.
 *
 * The series come from `module_trajectory` on the stored record — the values the
 * investigation actually saw. They are NOT live module telemetry: a live view
 * needs `GET /modules/{id}/telemetry`, which does not exist (design.md §10.2).
 * The page says so explicitly.
 *
 * `is_anomaly` per observation is NOT in the record (only aggregate counts are),
 * so no per-point anomaly markers are drawn. Inventing marker positions from the
 * aggregate would be fabrication.
 */
export default async function SignalsPage({
  params,
}: {
  params: Promise<{ investigationId: string }>;
}) {
  const { investigationId } = await params;
  const result = await getInvestigation(investigationId);
  if (result.kind !== "ok") notFound();
  const record = result.data;
  const trajectory = record.module_trajectory;

  if (!trajectory) {
    return (
      <Panel>
        <SectionHeader
          level={1} title="Signal Analysis" />
        <div className="p-[var(--ss-space-4)]">
          <EmptyState
            state="NO_DATA"
            body="No module trajectory was recorded for this investigation."
            detail="module_trajectory is null on the stored record"
          />
        </div>
      </Panel>
    );
  }

  const cycles = trajectory.cycle_numbers;
  const present = SIGNAL_ORDER.filter((s) => Array.isArray(trajectory.signals[s]));

  return (
    <>
      <Panel>
        <SectionHeader
          level={1}
          title="Signal Analysis"
          subtitle="The eight M6 v1 baseline signals as recorded in this investigation, on a shared cycle_number axis. Per-signal y-scales are independent: the quantities are not comparable."
        />
        <div className="flex flex-col gap-[var(--ss-space-3)] p-[var(--ss-space-4)]">
          <div className="grid grid-cols-2 gap-[var(--ss-space-4)] lg:grid-cols-4">
            <MetricValue label="Observations" value={trajectory.n_observations} register="DATA" />
            <MetricValue
              label="Cycle range"
              value={
                cycles.length > 0 ? `${cycles[0]} – ${cycles[cycles.length - 1]}` : null
              }
              register="DATA"
            />
            <MetricValue label="Signals recorded" value={present.length} register="DATA" />
            <MetricValue
              label="Score range"
              value={`${trajectory.min_score} – ${trajectory.max_score}`}
              register="DATA"
              note="higher = more anomalous"
            />
          </div>

          {/* Honest scope statement. */}
          <div
            className="flex flex-col gap-[var(--ss-space-1)] border border-dashed border-[var(--ss-border-strong)] p-[var(--ss-space-3)]"
            style={{ borderRadius: "var(--ss-radius-sm)" }}
          >
            <span className="ss-field-label">Scope — replay, not live telemetry</span>
            <p className="text-[var(--ss-text-secondary)]" style={{ maxWidth: "var(--ss-measure-prose)" }}>
              These series are read from the investigation record, so they are exactly
              what this investigation analysed — not a re-read of current artifacts. For
              the interactive view with per-observation anomaly markers, signal selection
              and cycle-range zoom, open the module signal workbench.
            </p>
            <a
              href={`/modules/${record.module_id}/signals`}
              className="ss-field-label w-fit border border-[var(--ss-border-strong)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] text-[var(--ss-text-primary)] hover:border-[var(--ss-accent)]"
              style={{ borderRadius: "var(--ss-radius-sm)" }}
            >
              Open module signal workbench
            </a>
          </div>
        </div>
      </Panel>

      {/* ── one pane per signal, shared x-axis ──────────────────────── */}
      {present.map((signal) => {
        const values = trajectory.signals[signal] ?? [];
        const points: ChartPoint[] = cycles.map((c, i) => ({
          cycle: c,
          value: values[i] ?? null,
        }));
        const style = SIGNAL_STYLE[signal];
        const tools = resultsForSignal(record, signal);

        return (
          <Panel key={signal}>
            <SectionHeader
              title={style?.label ?? signal}
              subtitle={
                style?.unit
                  ? `Unit ${style.unit} — stated in the feature documentation, not carried in the data.`
                  : "No engineering unit is carried in the M6/M7 artifacts."
              }
              level={3}
              actions={<RegisterBadge register="DATA" />}
            />
            <div className="flex flex-col gap-[var(--ss-space-3)] p-[var(--ss-space-4)]">
              <ScientificChart signal={signal} points={points} />

              <p className="ss-sr-only">
                Line chart of {signal} against cycle_number, {points.length} points,
                from cycle {cycles[0]} to {cycles[cycles.length - 1]}. The tabular
                values follow.
              </p>

              {/* Deterministic findings for this exact signal. */}
              {tools.length > 0 && (
                <div className="flex flex-col gap-[var(--ss-space-2)]">
                  <span className="ss-field-label">
                    Deterministic findings for this signal
                  </span>
                  <AccessibleDataTable
                    caption={`Deterministic tool results computed for ${signal}`}
                    rows={tools}
                    rowKey={(r, i) => `${signal}-${r.tool_name}-${i}`}
                    columns={[
                      { key: "tool", header: "Tool", render: (r) => <MonoId value={r.tool_name} /> },
                      { key: "output", header: "Output", render: (r) => raw(r.output) ?? "—" },
                      {
                        key: "method",
                        header: "Method",
                        render: (r) => raw(r.provenance?.["method"]) ?? "—",
                      },
                    ]}
                  />
                </div>
              )}
            </div>
          </Panel>
        );
      })}

      {/* Signals declared by M6 but absent from this record. */}
      {present.length < SIGNAL_ORDER.length && (
        <Panel>
          <SectionHeader title="Signals not recorded" level={3} />
          <div className="p-[var(--ss-space-4)]">
            <EmptyState
              state="NO_DATA"
              body="These M6 baseline signals are not present in this investigation's trajectory."
              detail={SIGNAL_ORDER.filter((s) => !present.includes(s)).join(", ")}
            />
          </div>
        </Panel>
      )}
      <NextAction
        href={`/investigations/${investigationId}/anomaly`}
        label="Inspect Anomaly Context"
        hint="the M7 summary this investigation analysed"
      />
    </>
  );
}
