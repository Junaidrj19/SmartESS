import { notFound } from "next/navigation";
import { AccessibleDataTable } from "@/components/AccessibleDataTable";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { MetricValue } from "@/components/MetricValue";
import { NextAction, WorkflowStrip } from "@/components/NextAction";
import { Panel, SectionHeader, SplitPanel } from "@/components/Panel";
import { RegisterBadge } from "@/components/RegisterValue";
import { getEvaluation, getModule } from "@/lib/api/endpoints";
import { asBoolean, asNumber, asString } from "@/lib/investigation";
import type { ModuleLevelMetrics } from "@/lib/types/m10";

/**
 * M8 Detector Evaluation (UX.md §9).
 *
 * M8 answers: how does the detector behave over the evaluated population?
 *
 * Two populations are reported separately and are never blended:
 *   overall_population          — all lots
 *   m7_test_lot_compatibility   — the held-out test lots only
 *
 * Lead time is negative in this dataset: the detector fires AFTER degradation
 * onset. The sign is preserved and labelled; it is never shown as early warning.
 */
export default async function ModuleEvaluationPage({
  params,
}: {
  params: Promise<{ moduleId: string }>;
}) {
  const { moduleId } = await params;

  const moduleResult = await getModule(moduleId);
  if (moduleResult.kind !== "ok") notFound();
  const detail = moduleResult.data;

  const evalResult = await getEvaluation(detail.model_id);

  const ev = detail.module_evaluation;
  const timing = detail.timing_analysis;
  const timingNote = asString(timing["note"]);

  return (
    <>
      <Panel>
        <SectionHeader
          level={1}
          title="M8 Detector Evaluation"
          subtitle="Evaluation-only layer over the frozen M7 artifacts. It never retrains and never changes a threshold."
          actions={<RegisterBadge register="CALCULATION" />}
        />
        <div className="flex flex-col gap-[var(--ss-space-4)] p-[var(--ss-space-4)]">
          <WorkflowStrip
            current="M8 Evaluation"
            steps={[
              { label: "Module", href: `/modules/${moduleId}` },
              { label: "Signals", href: `/modules/${moduleId}/signals` },
              { label: "M7 Anomaly", href: `/modules/${moduleId}/anomaly` },
              { label: "M8 Evaluation" },
              { label: "Start Investigation", href: `/investigations/new?module_id=${moduleId}` },
            ]}
          />
          <div
            className="grid grid-cols-1 gap-[var(--ss-space-3)] border border-[var(--ss-border-strong)] p-[var(--ss-space-3)] sm:grid-cols-2"
            style={{ borderRadius: "var(--ss-radius-sm)" }}
          >
            <div className="flex flex-col gap-[var(--ss-space-1)]">
              <span className="ss-field-label" style={{ color: "var(--ss-state-pass)" }}>
                M8 answers
              </span>
              <p className="text-[var(--ss-text-secondary)]">
                How the frozen detector behaves across the evaluated population, and when
                it fires relative to degradation onset.
              </p>
            </div>
            <div className="flex flex-col gap-[var(--ss-space-1)]">
              <span className="ss-field-label" style={{ color: "var(--ss-state-reject)" }}>
                M8 does not answer
              </span>
              <p className="text-[var(--ss-text-secondary)]">
                Whether this particular module failed. Population behaviour is not a
                per-module diagnosis.
              </p>
            </div>
          </div>
        </div>
      </Panel>

      {/* ── this module's evaluation row ────────────────────────────── */}
      <SplitPanel
        ratio="balanced"
        left={
          <Panel>
            <SectionHeader
              title="This module"
              subtitle="Model output for this module, kept separate from ground truth."
              level={3}
            />
            <div className="grid grid-cols-2 gap-[var(--ss-space-4)] p-[var(--ss-space-4)]">
              <MetricValue label="y_pred_module" value={asBoolean(ev["y_pred_module"])} register="CALCULATION" />
              <MetricValue label="y_pred_baseline" value={asBoolean(ev["y_pred_baseline"])} register="CALCULATION" />
              <MetricValue label="first_flag_cycle" value={asNumber(ev["first_flag_cycle"])} register="CALCULATION" />
              <MetricValue label="max_anomaly_score" value={asNumber(ev["max_anomaly_score"])} register="DATA" />
            </div>
          </Panel>
        }
        right={
          <Panel>
            <SectionHeader
              title="Ground truth"
              subtitle="Injected synthetic labels. Evaluation-only."
              level={3}
              actions={<RegisterBadge register="GROUND_TRUTH" />}
            />
            <div
              className="ss-hatch m-[var(--ss-space-4)] grid grid-cols-2 gap-[var(--ss-space-4)] border p-[var(--ss-space-3)]"
              style={{
                borderColor: "var(--ss-reg-groundtruth-border)",
                borderRadius: "var(--ss-radius-sm)",
              }}
            >
              <MetricValue label="y_true" value={asBoolean(ev["y_true"])} register="GROUND_TRUTH" />
              <MetricValue label="health_state" value={asString(ev["health_state"])} register="GROUND_TRUTH" />
              <MetricValue label="onset_cycle" value={asNumber(ev["onset_cycle"])} register="GROUND_TRUTH" />
              <MetricValue label="cycle_measurable" value={asNumber(ev["cycle_measurable"])} register="GROUND_TRUTH" />
            </div>
          </Panel>
        }
      />

      {/* ── timing, honestly signed ─────────────────────────────────── */}
      <Panel>
        <SectionHeader
          title="Detection timing"
          subtitle="Negative lead time means the flag occurred AFTER the reference cycle. Negative values are preserved, never shown as magnitudes."
          level={3}
        />
        <div className="p-[var(--ss-space-4)]">
          {timingNote ? (
            <EmptyState
              state="NOT_APPLICABLE"
              body={timingNote}
              detail="Timing is defined only for detected positives."
            />
          ) : (
            <div className="grid grid-cols-2 gap-[var(--ss-space-4)] lg:grid-cols-4">
              <MetricValue
                label="lead_vs_onset"
                value={asNumber(timing["lead_vs_onset"]) ?? asNumber(ev["lead_vs_onset"])}
                register="CALCULATION"
                unit="cycles"
                note="negative = flagged after onset"
              />
              <MetricValue
                label="lead_vs_measurable"
                value={asNumber(timing["lead_vs_measurable"]) ?? asNumber(ev["lead_vs_measurable"])}
                register="CALCULATION"
                unit="cycles"
                note="negative = flagged after measurable"
              />
              <MetricValue label="first_flag_cycle" value={asNumber(timing["first_flag_cycle"])} register="CALCULATION" />
              <MetricValue
                label="n_flagged_observations"
                value={asNumber(timing["n_flagged_observations"])}
                register="DATA"
              />
            </div>
          )}
        </div>
      </Panel>

      {/* ── population metrics, both views ─────────────────────────── */}
      {evalResult.kind !== "ok" ? (
        <Panel>
          <SectionHeader title="Population metrics" level={3} />
          <div className="p-[var(--ss-space-4)]">
            <ErrorState result={evalResult} />
          </div>
        </Panel>
      ) : (
        <PopulationMetrics summary={evalResult.data} />
      )}

      <NextAction
        href={`/investigations/new?module_id=${moduleId}`}
        label="Start Investigation"
        hint="deterministic analysis, evidence retrieval, competing mechanisms, validation, report"
      />
    </>
  );
}

function PopulationMetrics({
  summary,
}: {
  summary: Awaited<ReturnType<typeof getEvaluation>> extends never ? never : import("@/lib/types/m10").EvaluationSummary;
}) {
  const overall = summary.module_level_metrics;
  const testLot = summary.m7_test_lot_compatibility as unknown as Record<string, unknown>;
  const testLotMetrics = (testLot["metrics"] ?? testLot) as unknown as Partial<ModuleLevelMetrics>;
  const timing = summary.timing as unknown as Record<string, unknown>;

  const rows: {
    view: string;
    population: string;
    m: Partial<ModuleLevelMetrics>;
  }[] = [
    {
      view: "overall_population",
      population: "all evaluated lots",
      m: overall,
    },
    {
      view: "m7_test_lot_compatibility",
      population: "held-out test lots only",
      m: testLotMetrics,
    },
  ];

  return (
    <>
      <Panel>
        <SectionHeader
          title="Population metrics"
          subtitle="Two evaluation views, reported separately. They are different populations and are never averaged into one figure."
          level={3}
          actions={<RegisterBadge register="CALCULATION" />}
        />
        <div className="flex flex-col gap-[var(--ss-space-4)] p-[var(--ss-space-4)]">
          <AccessibleDataTable
            caption="Module-level detector metrics for each evaluation population."
            rows={rows}
            rowKey={(r) => r.view}
            columns={[
              { key: "view", header: "view", render: (r) => r.view },
              { key: "pop", header: "population", render: (r) => r.population, mono: false },
              { key: "n", header: "n_modules", render: (r) => r.m.n_modules ?? "—", align: "right" },
              { key: "tp", header: "tp", render: (r) => r.m.tp ?? "—", align: "right" },
              { key: "tn", header: "tn", render: (r) => r.m.tn ?? "—", align: "right" },
              { key: "fp", header: "fp", render: (r) => r.m.fp ?? "—", align: "right" },
              { key: "fn", header: "fn", render: (r) => r.m.fn ?? "—", align: "right" },
              { key: "p", header: "precision", render: (r) => r.m.precision ?? "—", align: "right" },
              { key: "r", header: "recall", render: (r) => r.m.recall ?? "—", align: "right" },
              { key: "f1", header: "f1", render: (r) => r.m.f1 ?? "—", align: "right" },
              {
                key: "fpr",
                header: "false_positive_rate",
                render: (r) => r.m.false_positive_rate ?? "—",
                align: "right",
              },
            ]}
          />
          <p
            className="text-[var(--ss-text-muted)]"
            style={{ maxWidth: "var(--ss-measure-prose)" }}
          >
            {typeof testLot["note"] === "string" ? String(testLot["note"]) : null}
          </p>
        </div>
      </Panel>

      <Panel>
        <SectionHeader
          title="Evaluation identity"
          subtitle="What was evaluated, against which ground truth, and when."
          level={3}
        />
        <div className="flex flex-col gap-[var(--ss-space-4)] p-[var(--ss-space-4)]">
          <dl className="grid grid-cols-2 gap-[var(--ss-space-4)] lg:grid-cols-4">
            <MetricValue label="model_id" value={summary.model_id} register="DATA" />
            <MetricValue label="dataset_id" value={summary.dataset_id} register="DATA" />
            <MetricValue label="feature_version" value={summary.feature_version} register="DATA" />
            <MetricValue label="detector_version" value={summary.detector_version} register="DATA" />
            <MetricValue label="evaluation_timestamp" value={summary.evaluation_timestamp} register="DATA" />
            <MetricValue label="module_threshold" value={summary.module_threshold} register="CALCULATION" />
            <MetricValue
              label="ground_truth_used_for_training"
              value={summary.ground_truth_used_for_training}
              register="DATA"
              note="ground truth is evaluation-only"
            />
            <MetricValue
              label="mean_lead_vs_onset_cycles"
              value={asNumber(timing["mean_lead_vs_onset_cycles"])}
              register="CALCULATION"
              unit="cycles"
              note="negative = flagged after onset"
            />
          </dl>
          {summary.disclaimer && (
            <p
              className="text-[var(--ss-text-secondary)]"
              style={{ maxWidth: "var(--ss-measure-prose)" }}
            >
              {summary.disclaimer}
            </p>
          )}
          <p
            className="text-[var(--ss-text-muted)]"
            style={{ fontSize: "var(--ss-text-label-size)", maxWidth: "var(--ss-measure-prose)" }}
          >
            Observation-level ground truth does not exist, so no observation-level
            precision, recall, F1 or FPR is reported anywhere — only flag-rate summaries.
          </p>
        </div>
      </Panel>
    </>
  );
}
