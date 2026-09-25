import { notFound } from "next/navigation";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { MetricValue } from "@/components/MetricValue";
import { NextAction, WorkflowStrip } from "@/components/NextAction";
import { Panel, SectionHeader, SplitPanel } from "@/components/Panel";
import { RegisterBadge } from "@/components/RegisterValue";
import { StatusChip } from "@/components/StatusChip";
import { getModule, getModuleAnomaly } from "@/lib/api/endpoints";
import { asBoolean, asString } from "@/lib/investigation";
import { ANOMALY_QUALIFICATION } from "@/lib/copy/states";

/**
 * M7 Anomaly Detection (UX.md §8).
 *
 * M7 answers: which observations did the frozen detector flag?
 * It does not answer: what physically failed?
 *
 * Three quantities are kept visually separate here, because conflating them is
 * the core scientific error this product must avoid:
 *   MODEL ANOMALY   — the Isolation Forest output
 *   BASELINE FLAG   — an independent robust-deviation comparator
 *   GROUND TRUTH    — injected synthetic labels, evaluation-only
 */
export default async function ModuleAnomalyPage({
  params,
}: {
  params: Promise<{ moduleId: string }>;
}) {
  const { moduleId } = await params;

  const moduleResult = await getModule(moduleId);
  if (moduleResult.kind !== "ok") notFound();
  const detail = moduleResult.data;

  const anomalyResult = await getModuleAnomaly(moduleId, detail.model_id);

  if (anomalyResult.kind !== "ok") {
    return (
      <Panel>
        <SectionHeader
          level={1} title="M7 Anomaly Detection" />
        <div className="p-[var(--ss-space-4)]">
          <ErrorState result={anomalyResult} />
        </div>
      </Panel>
    );
  }

  const a = anomalyResult.data;
  const s = a.module_summary;
  const ev = detail.module_evaluation;
  const base = detail.baseline_comparison;

  const modelFlag = asBoolean(ev["y_pred_module"]) ?? asBoolean(base["if_flag_module"]);
  const baselineFlag =
    asBoolean(ev["y_pred_baseline"]) ?? asBoolean(base["base_flag_module"]);
  const groundTruth = asBoolean(ev["y_true"]);
  const disagree = modelFlag !== null && baselineFlag !== null && modelFlag !== baselineFlag;
  const noFlags = (s.n_anomalous_observations ?? 0) === 0;

  return (
    <>
      <Panel>
        <SectionHeader
          level={1}
          title="M7 Anomaly Detection"
          subtitle="Unsupervised Isolation Forest over M6 v1 observation features. Frozen: this page reads scores, it never re-scores."
          actions={<RegisterBadge register="DATA" />}
        />
        <div className="flex flex-col gap-[var(--ss-space-4)] p-[var(--ss-space-4)]">
          <WorkflowStrip
            current="M7 Anomaly"
            steps={[
              { label: "Module", href: `/modules/${moduleId}` },
              { label: "Signals", href: `/modules/${moduleId}/signals` },
              { label: "M7 Anomaly" },
              { label: "M8 Evaluation", href: `/modules/${moduleId}/evaluation` },
              { label: "Start Investigation", href: `/investigations/new?module_id=${moduleId}` },
            ]}
          />

          {/* What M7 does and does not answer. */}
          <div
            className="grid grid-cols-1 gap-[var(--ss-space-3)] border border-[var(--ss-border-strong)] p-[var(--ss-space-3)] sm:grid-cols-2"
            style={{ borderRadius: "var(--ss-radius-sm)" }}
          >
            <div className="flex flex-col gap-[var(--ss-space-1)]">
              <span className="ss-field-label" style={{ color: "var(--ss-state-pass)" }}>
                M7 answers
              </span>
              <p className="text-[var(--ss-text-secondary)]">
                Which observations and modules were flagged as statistically unusual by
                the frozen detector.
              </p>
            </div>
            <div className="flex flex-col gap-[var(--ss-space-1)]">
              <span className="ss-field-label" style={{ color: "var(--ss-state-reject)" }}>
                M7 does not answer
              </span>
              <p className="text-[var(--ss-text-secondary)]">
                What physically failed. {ANOMALY_QUALIFICATION}
              </p>
            </div>
          </div>

          {noFlags && (
            <EmptyState
              state="NO_ANOMALY"
              detail={`n_observations ${s.n_observations ?? "—"} · anomaly_rate ${s.anomaly_rate ?? "—"} · module_threshold ${a.thresholds.module_threshold ?? "—"}`}
            />
          )}
        </div>
      </Panel>

      {/* ── three verdicts, deliberately not merged ─────────────────── */}
      <Panel>
        <SectionHeader
          title="Module-level verdicts"
          subtitle="Three independent statements about the same module. They are not the same quantity and are never combined."
          level={3}
        />
        <div className="grid grid-cols-1 gap-[var(--ss-space-4)] p-[var(--ss-space-4)] lg:grid-cols-3">
          <VerdictCard
            title="Model anomaly"
            register="CALCULATION"
            flag={modelFlag}
            label="y_pred_module"
            note="Isolation Forest, module-level threshold"
          />
          <VerdictCard
            title="Statistical baseline flag"
            register="CALCULATION"
            flag={baselineFlag}
            label="y_pred_baseline"
            note="max |robust normalised deviation| ≥ 3.0 — not the model"
          />
          <VerdictCard
            title="Ground truth"
            register="GROUND_TRUTH"
            flag={groundTruth}
            label="y_true"
            note="Injected synthetic label. Evaluation-only; not a SmartESS output."
            hatched
          />
        </div>
        {disagree && (
          <div
            className="m-[var(--ss-space-4)] mt-0 flex flex-col gap-[var(--ss-space-1)] border p-[var(--ss-space-3)]"
            style={{
              borderColor: "var(--ss-state-attention-strong)",
              borderRadius: "var(--ss-radius-sm)",
            }}
          >
            <span className="ss-field-label" style={{ color: "var(--ss-state-attention-strong)" }}>
              COMPARATORS DISAGREE
            </span>
            <p
              className="text-[var(--ss-text-secondary)]"
              style={{ maxWidth: "var(--ss-measure-prose)" }}
            >
              The detector and the independent statistical baseline reach different
              module-level verdicts. That is a genuine analytical finding, not a defect:
              it means the evidence is mixed and the signals are worth inspecting before
              anyone draws a conclusion. It is exactly the kind of case an investigation
              exists to work through.
            </p>
          </div>
        )}
      </Panel>

      <SplitPanel
        ratio="balanced"
        left={
          /* ── the M7 row in full ─────────────────────────────────── */
          <Panel>
            <SectionHeader title="Detector output" subtitle="All 15 M7 summary fields." level={3} />
            <div className="grid grid-cols-2 gap-[var(--ss-space-4)] p-[var(--ss-space-4)]">
              <MetricValue label="module_anomaly_status" value={asString(s.module_anomaly_status)} register="CALCULATION" />
              <MetricValue label="n_observations" value={s.n_observations} register="DATA" />
              <MetricValue label="n_anomalous_observations" value={s.n_anomalous_observations} register="DATA" />
              <MetricValue label="anomaly_rate" value={s.anomaly_rate} register="CALCULATION" />
              <MetricValue label="max_anomaly_score" value={s.max_anomaly_score} register="DATA" note="higher = more anomalous" />
              <MetricValue label="mean_anomaly_score" value={s.mean_anomaly_score} register="DATA" />
              <MetricValue label="first_anomalous_cycle" value={s.first_anomalous_cycle} register="DATA" />
              <MetricValue label="last_anomalous_cycle" value={s.last_anomalous_cycle} register="DATA" />
              <MetricValue label="anomalous_cycle_span" value={s.anomalous_cycle_span} register="CALCULATION" />
              <MetricValue label="statistical_baseline_max" value={s.statistical_baseline_max} register="CALCULATION" />
              <MetricValue
                label="statistical_baseline_flag_rate"
                value={s.statistical_baseline_flag_rate}
                register="CALCULATION"
              />
            </div>
          </Panel>
        }
        right={
          /* ── model identity + thresholds ───────────────────────── */
          <Panel>
            <SectionHeader
              title="Detector identity and thresholds"
              subtitle="Two different boundaries. They are not interchangeable."
              level={3}
            />
            <div className="flex flex-col gap-[var(--ss-space-4)] p-[var(--ss-space-4)]">
              <dl className="grid grid-cols-2 gap-[var(--ss-space-4)]">
                <MetricValue label="model_id" value={a.model.model_id} register="DATA" />
                <MetricValue label="algorithm" value={a.model.algorithm} register="DATA" />
                <MetricValue label="detector_version" value={a.model.detector_version} register="DATA" />
                <MetricValue label="feature_version" value={a.model.feature_version} register="DATA" />
                <MetricValue label="n_input_features" value={a.model.n_input_features} register="DATA" />
                <MetricValue
                  label="contamination"
                  value={String(a.model.hyperparameters["contamination"] ?? "")}
                  register="DATA"
                />
              </dl>
              <dl className="grid grid-cols-2 gap-[var(--ss-space-4)]">
                <MetricValue
                  label="observation_threshold"
                  value={a.thresholds.observation_threshold}
                  register="CALCULATION"
                  note="per-observation boundary"
                />
                <MetricValue
                  label="module_threshold"
                  value={a.thresholds.module_threshold}
                  register="CALCULATION"
                  note="module-level boundary"
                />
              </dl>
              <p
                className="text-[var(--ss-text-muted)]"
                style={{ fontSize: "var(--ss-text-label-size)", maxWidth: "var(--ss-measure-prose)" }}
              >
                {a.thresholds.note}
              </p>
            </div>
          </Panel>
        }
      />

      <NextAction
        href={`/modules/${moduleId}/evaluation`}
        label="Inspect Detector Evaluation"
        hint="how the detector behaves across the evaluated population"
      />
    </>
  );
}

function VerdictCard({
  title,
  register,
  flag,
  label,
  note,
  hatched = false,
}: {
  title: string;
  register: "CALCULATION" | "GROUND_TRUTH";
  flag: boolean | null;
  label: string;
  note: string;
  hatched?: boolean;
}) {
  return (
    <div
      className={`flex flex-col gap-[var(--ss-space-2)] border p-[var(--ss-space-3)] ${hatched ? "ss-hatch" : ""}`}
      style={{
        borderRadius: "var(--ss-radius-sm)",
        borderColor: hatched ? "var(--ss-reg-groundtruth-border)" : "var(--ss-border-subtle)",
      }}
    >
      <div className="flex items-start justify-between gap-[var(--ss-space-2)]">
        <span className="ss-field-label">{title}</span>
        <RegisterBadge register={register} />
      </div>
      <div className="flex items-center gap-[var(--ss-space-2)]">
        {flag === null ? (
          <span className="italic text-[var(--ss-text-muted)]">not recorded</span>
        ) : (
          <>
            <span className="ss-mono text-[var(--ss-text-primary)]">{String(flag)}</span>
            <StatusChip status={flag ? "FLAGGED" : "NOT_FLAGGED"} />
          </>
        )}
      </div>
      <span className="ss-mono text-[var(--ss-text-muted)]">{label}</span>
      <span className="text-[var(--ss-text-muted)]" style={{ fontSize: "var(--ss-text-label-size)" }}>
        {note}
      </span>
    </div>
  );
}
