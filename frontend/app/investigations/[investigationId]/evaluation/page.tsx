import { notFound } from "next/navigation";
import { EmptyState } from "@/components/EmptyState";
import { MetricValue } from "@/components/MetricValue";
import { NextAction } from "@/components/NextAction";
import { Panel, SectionHeader, SplitPanel } from "@/components/Panel";
import { RegisterBadge } from "@/components/RegisterValue";
import { StatusChip } from "@/components/StatusChip";
import { AccessibleDataTable } from "@/components/AccessibleDataTable";
import { getEvaluation, getInvestigation } from "@/lib/api/endpoints";
import { asBoolean, asNumber, asString, raw } from "@/lib/investigation";

/**
 * M8 Detector Evaluation, investigation-scoped (UX.md §9).
 *
 * Sources on the stored record: `m8_module_evaluation` (27 fields), `m8_timing`,
 * `m8_baseline`.
 *
 * Three rules enforced here:
 *  · Ground truth (`health_state`, `degradation_mechanism`, `degradation_stage`,
 *    `onset_cycle`, `cycle_measurable`, `degradation_severity`, `damage_index_end`,
 *    `y_true`) is SYNTHETIC and EVALUATION-ONLY. It is quarantined in its own
 *    hatched register and never shown as a SmartESS output (design.md §3.4).
 *  · `lead_vs_onset` is negative in this dataset — the detector fires AFTER onset.
 *    It is labelled with its direction and never framed as early warning
 *    (design.md §19.3).
 *  · `m8_timing` may be a one-key `{note: ...}` for a module absent from the
 *    timing analysis. The note is rendered verbatim (design.md §14.4).
 */
export default async function EvaluationPage({
  params,
}: {
  params: Promise<{ investigationId: string }>;
}) {
  const { investigationId } = await params;
  const result = await getInvestigation(investigationId);
  if (result.kind !== "ok") notFound();
  const record = result.data;

  const ev = record.m8_module_evaluation;
  const timing = record.m8_timing;
  const baseline = record.m8_baseline;
  const evalResult = await getEvaluation(record.model_id);
  const summary = evalResult.kind === "ok" ? evalResult.data : null;

  const timingNote = asString(timing["note"]);
  const yPred = asBoolean(ev["y_pred_module"]);
  const yPredBaseline = asBoolean(ev["y_pred_baseline"]);
  const disagree = yPred !== null && yPredBaseline !== null && yPred !== yPredBaseline;

  if (Object.keys(ev).length === 0) {
    return (
      <Panel>
        <SectionHeader
          level={1} title="M8 Detector Evaluation" />
        <div className="p-[var(--ss-space-4)]">
          <EmptyState state="NO_DATA" body="No M8 evaluation was recorded for this investigation." />
        </div>
      </Panel>
    );
  }

  return (
    <>
      <Panel>
        <SectionHeader
          level={1}
          title="M8 Detector Evaluation"
          subtitle="Evaluation-only layer over the frozen M7 artifacts. It never retrains and never changes a threshold — it measures how the detector behaved."
          actions={<RegisterBadge register="CALCULATION" />}
        />
        <div className="grid grid-cols-2 gap-[var(--ss-space-4)] p-[var(--ss-space-4)] lg:grid-cols-4">
          <MetricValue
            label="y_pred_module"
            value={yPred}
            register="CALCULATION"
            note="detector verdict for this module"
          />
          <MetricValue
            label="first_flag_cycle"
            value={asNumber(ev["first_flag_cycle"])}
            register="CALCULATION"
          />
          <MetricValue
            label="n_anomalous_observations"
            value={asNumber(ev["n_anomalous_observations"])}
            register="DATA"
          />
          <MetricValue
            label="max_anomaly_score"
            value={asNumber(ev["max_anomaly_score"])}
            register="DATA"
          />
        </div>
      </Panel>

      {/* ── detection timing, honestly signed ───────────────────────── */}
      <Panel>
        <SectionHeader
          title="Detection timing"
          subtitle="Negative lead time means the flag occurred AFTER the reference cycle. Negative values are preserved, not shown as magnitudes."
          level={3}
        />
        <div className="flex flex-col gap-[var(--ss-space-4)] p-[var(--ss-space-4)]">
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
              <MetricValue
                label="first_flag_cycle"
                value={asNumber(timing["first_flag_cycle"])}
                register="CALCULATION"
              />
              <MetricValue
                label="n_flagged_observations"
                value={asNumber(timing["n_flagged_observations"])}
                register="DATA"
              />
            </div>
          )}
        </div>
      </Panel>

      <SplitPanel
        ratio="balanced"
        left={
          /* ── detector vs independent baseline ───────────────────── */
          <Panel>
            <SectionHeader
              title="Detector vs statistical baseline"
              subtitle="Two independent verdicts on the same module."
              level={3}
            />
            <div className="flex flex-col gap-[var(--ss-space-3)] p-[var(--ss-space-4)]">
              <div className="grid grid-cols-2 gap-[var(--ss-space-4)]">
                <MetricValue
                  label="if_flag_module"
                  value={asBoolean(baseline["if_flag_module"]) ?? yPred}
                  register="CALCULATION"
                  note="Isolation Forest"
                />
                <MetricValue
                  label="base_flag_module"
                  value={asBoolean(baseline["base_flag_module"]) ?? yPredBaseline}
                  register="CALCULATION"
                  note="statistical baseline"
                />
                <MetricValue
                  label="max_anomaly_score"
                  value={asNumber(baseline["max_anomaly_score"])}
                  register="DATA"
                />
                <MetricValue
                  label="statistical_baseline_max"
                  value={asNumber(baseline["statistical_baseline_max"])}
                  register="DATA"
                />
              </div>
              {disagree && (
                <div
                  className="flex flex-col gap-[var(--ss-space-1)] border border-[var(--ss-state-attention-strong)] p-[var(--ss-space-3)]"
                  style={{ borderRadius: "var(--ss-radius-sm)" }}
                >
                  <span
                    className="ss-field-label"
                    style={{ color: "var(--ss-state-attention-strong)" }}
                  >
                    COMPARATORS DISAGREE
                  </span>
                  <p className="text-[var(--ss-text-secondary)]" style={{ maxWidth: "var(--ss-measure-prose)" }}>
                    The Isolation Forest and the independent statistical baseline reach
                    different module-level verdicts. This is a genuine analytical
                    finding, not an error, and it is a reason to inspect the signals
                    rather than trust either verdict alone.
                  </p>
                </div>
              )}
            </div>
          </Panel>
        }
        right={
          /* ── ground truth, quarantined ──────────────────────────── */
          <Panel>
            <SectionHeader
              title="Ground truth"
              subtitle="Injected synthetic labels. Evaluation-only — never used for training, never a SmartESS output."
              level={3}
              actions={<RegisterBadge register="GROUND_TRUTH" />}
            />
            <div
              className="ss-hatch m-[var(--ss-space-4)] flex flex-col gap-[var(--ss-space-3)] border p-[var(--ss-space-3)]"
              style={{
                borderColor: "var(--ss-reg-groundtruth-border)",
                borderRadius: "var(--ss-radius-sm)",
              }}
            >
              <div className="grid grid-cols-2 gap-[var(--ss-space-4)]">
                <MetricValue label="health_state" value={asString(ev["health_state"])} register="GROUND_TRUTH" />
                <MetricValue
                  label="degradation_mechanism"
                  value={asString(ev["degradation_mechanism"])}
                  register="GROUND_TRUTH"
                />
                <MetricValue
                  label="degradation_stage"
                  value={asString(ev["degradation_stage"])}
                  register="GROUND_TRUTH"
                />
                <MetricValue label="y_true" value={asBoolean(ev["y_true"])} register="GROUND_TRUTH" />
                <MetricValue label="onset_cycle" value={asNumber(ev["onset_cycle"])} register="GROUND_TRUTH" />
                <MetricValue
                  label="cycle_measurable"
                  value={asNumber(ev["cycle_measurable"])}
                  register="GROUND_TRUTH"
                />
                <MetricValue
                  label="degradation_severity"
                  value={asNumber(ev["degradation_severity"])}
                  register="GROUND_TRUTH"
                />
                <MetricValue
                  label="damage_index_end"
                  value={asNumber(ev["damage_index_end"])}
                  register="GROUND_TRUTH"
                />
              </div>
              <p className="text-[var(--ss-text-muted)]" style={{ fontSize: "var(--ss-text-label-size)" }}>
                Comparing y_true against y_pred_module is how M8 measures the detector.
                It is not what SmartESS tells an engineer about the hardware.
              </p>
            </div>
          </Panel>
        }
      />

      {/* ── population metrics need the endpoint ────────────────────── */}
      <Panel>
        <SectionHeader
          title="Population metrics"
          subtitle="Precision, recall, F1 and FPR for the two evaluation populations."
          level={3}
        />
        <div className="flex flex-col gap-[var(--ss-space-3)] p-[var(--ss-space-4)]">
          {!summary ? (
            <EmptyState
              state="NO_DATA"
              body="The evaluation summary for this model could not be read."
            />
          ) : (
            <>
              <AccessibleDataTable
                caption="Module-level detector metrics per evaluation population."
                rows={[
                  {
                    view: "overall_population",
                    m: summary.module_level_metrics as unknown as Record<string, unknown>,
                  },
                  {
                    view: "m7_test_lot_compatibility",
                    m: summary.m7_test_lot_compatibility as unknown as Record<string, unknown>,
                  },
                ]}
                rowKey={(r) => r.view}
                columns={[
                  { key: "view", header: "view", render: (r) => r.view },
                  { key: "n", header: "n_modules", render: (r) => String(r.m["n_modules"] ?? "—"), align: "right" },
                  { key: "p", header: "precision", render: (r) => String(r.m["precision"] ?? "—"), align: "right" },
                  { key: "r", header: "recall", render: (r) => String(r.m["recall"] ?? "—"), align: "right" },
                  { key: "f1", header: "f1", render: (r) => String(r.m["f1"] ?? "—"), align: "right" },
                  {
                    key: "fpr",
                    header: "false_positive_rate",
                    render: (r) => String(r.m["false_positive_rate"] ?? "—"),
                    align: "right",
                  },
                ]}
              />
              <div className="grid grid-cols-2 gap-[var(--ss-space-4)] lg:grid-cols-4">
                <MetricValue label="module_threshold" value={summary.module_threshold} register="CALCULATION" />
                <MetricValue
                  label="ground_truth_used_for_training"
                  value={summary.ground_truth_used_for_training}
                  register="DATA"
                />
                <MetricValue label="evaluation_timestamp" value={summary.evaluation_timestamp} register="DATA" />
                <MetricValue
                  label="mean_lead_vs_onset_cycles"
                  value={asNumber((summary.timing as unknown as Record<string, unknown>)["mean_lead_vs_onset_cycles"])}
                  register="CALCULATION"
                  unit="cycles"
                  note="negative = flagged after onset"
                />
              </div>
              <p
                className="text-[var(--ss-text-muted)]"
                style={{ fontSize: "var(--ss-text-label-size)", maxWidth: "var(--ss-measure-prose)" }}
              >
                Population behaviour is not a per-module diagnosis. These two views are
                different populations and are never averaged into one figure.
              </p>
            </>
          )}
        </div>
      </Panel>
      <NextAction
        href={`/investigations/${investigationId}/trace`}
        label="Inspect Pipeline Trace"
        hint="what the investigation did with this context"
      />
    </>
  );
}
