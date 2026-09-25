import { notFound } from "next/navigation";
import { ErrorState } from "@/components/ErrorState";
import { MetricValue } from "@/components/MetricValue";
import { NextAction, WorkflowStrip } from "@/components/NextAction";
import { Panel, SectionHeader } from "@/components/Panel";
import { SignalWorkbench } from "@/components/SignalWorkbench";
import { getHealthyReference, getModule, getTelemetry } from "@/lib/api/endpoints";

/**
 * Signal Analysis (UX.md §7).
 *
 * Real per-observation telemetry from `GET /modules/{id}/telemetry`, joined with
 * the detector's own `is_anomaly` and `statistical_baseline_flag` for the same
 * observation. The healthy-reference overlay is drawn only from the declared
 * reference artifact — never from a value computed here.
 */
export default async function ModuleSignalsPage({
  params,
}: {
  params: Promise<{ moduleId: string }>;
}) {
  const { moduleId } = await params;

  const moduleResult = await getModule(moduleId);
  if (moduleResult.kind !== "ok") notFound();
  const modelId = moduleResult.data.model_id;

  const [telemetryResult, referenceResult] = await Promise.all([
    getTelemetry(moduleId, { model_id: modelId }),
    getHealthyReference(modelId),
  ]);

  if (telemetryResult.kind !== "ok") {
    return (
      <Panel>
        <SectionHeader
          level={1}
          title="Signal Analysis"
          subtitle="SIGNAL DATA UNAVAILABLE — the telemetry projection could not be read."
        />
        <div className="p-[var(--ss-space-4)]">
          <ErrorState result={telemetryResult} />
          <p
            className="mt-[var(--ss-space-3)] text-[var(--ss-text-muted)]"
            style={{ maxWidth: "var(--ss-measure-prose)" }}
          >
            No curve is drawn when the series cannot be read. The M6 feature parquet and
            the M7 score parquet are both required; see Pipeline Readiness.
          </p>
        </div>
      </Panel>
    );
  }

  const series = telemetryResult.data;

  // Declared reference means only — nothing is derived if the artifact is absent.
  const referenceMeans =
    referenceResult.kind === "ok"
      ? Object.fromEntries(
          Object.entries(referenceResult.data.signals).map(([k, v]) => [k, v.mean ?? null]),
        )
      : undefined;

  const flagged = series.points.filter((p) => p.is_anomaly).length;
  const baselineFlagged = series.points.filter((p) => p.statistical_baseline_flag).length;
  const cycles = series.points.map((p) => p.cycle_number);

  return (
    <>
      <Panel>
        <SectionHeader
          level={1}
          title="Signal Analysis"
          subtitle="Measured baseline signals on a shared cycle_number axis. Per-signal y-scales are independent because the quantities are not comparable."
        />
        <div className="flex flex-col gap-[var(--ss-space-4)] p-[var(--ss-space-4)]">
          <WorkflowStrip
            current="Signals"
            steps={[
              { label: "Module", href: `/modules/${moduleId}` },
              { label: "Signals" },
              { label: "M7 Anomaly", href: `/modules/${moduleId}/anomaly` },
              { label: "M8 Evaluation", href: `/modules/${moduleId}/evaluation` },
              { label: "Start Investigation", href: `/investigations/new?module_id=${moduleId}` },
            ]}
          />

          <div className="grid grid-cols-2 gap-[var(--ss-space-4)] lg:grid-cols-4">
            <MetricValue label="Observations" value={series.source_points} register="DATA" />
            <MetricValue
              label="Cycle range"
              value={cycles.length > 0 ? `${Math.min(...cycles)} – ${Math.max(...cycles)}` : null}
              register="DATA"
            />
            <MetricValue label="Detector flagged" value={flagged} register="DATA" />
            <MetricValue
              label="Baseline flagged"
              value={baselineFlagged}
              register="DATA"
              note="independent comparator, threshold 3.0"
            />
          </div>

          <p
            className="text-[var(--ss-text-muted)]"
            style={{ maxWidth: "var(--ss-measure-prose)" }}
          >
            {series.units_note}
          </p>

          {referenceResult.kind !== "ok" && (
            <p className="ss-mono text-[var(--ss-text-muted)]">
              Healthy-reference overlay not drawn: the declared reference artifact could
              not be read.
            </p>
          )}
        </div>
      </Panel>

      <Panel>
        <SectionHeader
          title="Workbench"
          subtitle="Select signals and narrow the cycle window. Selection and zoom filter the fetched observations; no value is resampled, smoothed or fitted."
          level={3}
        />
        <div className="p-[var(--ss-space-4)]">
          <SignalWorkbench series={series} referenceMeans={referenceMeans} />
        </div>
      </Panel>

      <NextAction
        href={`/modules/${moduleId}/anomaly`}
        label="Inspect Anomaly Detection"
        hint="what the frozen M7 detector flagged, and what it does not claim"
      />
    </>
  );
}
