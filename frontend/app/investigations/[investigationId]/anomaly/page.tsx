import { notFound } from "next/navigation";
import { EmptyState } from "@/components/EmptyState";
import { MetricValue } from "@/components/MetricValue";
import { NextAction } from "@/components/NextAction";
import { Panel, SectionHeader, SplitPanel } from "@/components/Panel";
import { RegisterBadge } from "@/components/RegisterValue";
import { StatusChip } from "@/components/StatusChip";
import { getInvestigation } from "@/lib/api/endpoints";
import { asNumber, asString } from "@/lib/investigation";
import { ANOMALY_QUALIFICATION } from "@/lib/copy/states";

/**
 * M7 Anomaly Detection, investigation-scoped (UX.md §8).
 *
 * Every field comes from `m7_module_summary` on the stored record — all 15
 * `module-summary.parquet` columns.
 *
 * Two rules are enforced visually:
 *  · ANOMALY DETECTED is not FAILURE CONFIRMED. The status carries its
 *    qualification everywhere and red is never used for it.
 *  · The statistical baseline is an INDEPENDENT comparator, not the model. Where
 *    the two disagree, that disagreement is presented as a real analytical finding
 *    (design.md §14.3).
 */
export default async function AnomalyPage({
  params,
}: {
  params: Promise<{ investigationId: string }>;
}) {
  const { investigationId } = await params;
  const result = await getInvestigation(investigationId);
  if (result.kind !== "ok") notFound();
  const record = result.data;

  const m7 = record.m7_module_summary;
  const status = asString(m7["module_anomaly_status"]);
  const nFlagged = asNumber(m7["n_anomalous_observations"]);

  if (Object.keys(m7).length === 0) {
    return (
      <Panel>
        <SectionHeader
          level={1} title="M7 Anomaly Detection" />
        <div className="p-[var(--ss-space-4)]">
          <EmptyState state="NO_DATA" body="No M7 summary was recorded for this investigation." />
        </div>
      </Panel>
    );
  }

  return (
    <>
      <Panel>
        <SectionHeader
          level={1}
          title="M7 Anomaly Detection"
          subtitle="Unsupervised Isolation Forest over M6 v1 observation features. An anomaly is a statistical observation, not a confirmed physical failure."
          actions={<RegisterBadge register="DATA" />}
        />
        <div className="flex flex-col gap-[var(--ss-space-4)] p-[var(--ss-space-4)]">
          {/* The distinction that matters most. */}
          <div
            className="flex flex-col gap-[var(--ss-space-2)] border border-[var(--ss-border-strong)] p-[var(--ss-space-3)]"
            style={{ borderRadius: "var(--ss-radius-sm)" }}
          >
            <div className="flex flex-wrap items-center gap-[var(--ss-space-3)]">
              <StatusChip status={status} />
              <span className="ss-field-label text-[var(--ss-text-secondary)]">
                ANOMALY STATUS
              </span>
              <span className="ss-field-label text-[var(--ss-text-muted)]">
                FAILURE CONFIRMED — NO
              </span>
            </div>
            <p className="text-[var(--ss-text-secondary)]" style={{ maxWidth: "var(--ss-measure-prose)" }}>
              {ANOMALY_QUALIFICATION} SmartESS does not confirm a physical failure;
              confirmation requires engineering work on the hardware.
            </p>
          </div>

          {nFlagged === 0 && (
            <EmptyState
              state="NO_ANOMALY"
              detail={`n_observations ${asNumber(m7["n_observations"]) ?? "—"} · anomaly_rate ${
                asNumber(m7["anomaly_rate"]) ?? "—"
              }`}
            />
          )}

          <div className="grid grid-cols-2 gap-[var(--ss-space-4)] lg:grid-cols-4">
            <MetricValue label="n_observations" value={asNumber(m7["n_observations"])} register="DATA" />
            <MetricValue
              label="n_anomalous_observations"
              value={nFlagged}
              register="DATA"
            />
            <MetricValue label="anomaly_rate" value={asNumber(m7["anomaly_rate"])} register="CALCULATION" />
            <MetricValue
              label="module_anomaly_status"
              value={status}
              register="CALCULATION"
              note="clean <> sporadic <0.1 <> persistent >=0.1"
            />
            <MetricValue
              label="max_anomaly_score"
              value={asNumber(m7["max_anomaly_score"])}
              register="DATA"
              note="higher = more anomalous"
            />
            <MetricValue
              label="mean_anomaly_score"
              value={asNumber(m7["mean_anomaly_score"])}
              register="DATA"
            />
            <MetricValue
              label="first_anomalous_cycle"
              value={asNumber(m7["first_anomalous_cycle"])}
              register="DATA"
            />
            <MetricValue
              label="last_anomalous_cycle"
              value={asNumber(m7["last_anomalous_cycle"])}
              register="DATA"
            />
            <MetricValue
              label="anomalous_cycle_span"
              value={asNumber(m7["anomalous_cycle_span"])}
              register="CALCULATION"
            />
            <MetricValue label="test_id" value={asString(m7["test_id"])} register="DATA" />
            <MetricValue label="lot_id" value={asString(m7["lot_id"])} register="DATA" />
            <MetricValue label="dataset_id" value={asString(m7["dataset_id"])} register="DATA" />
          </div>
        </div>
      </Panel>

      <SplitPanel
        ratio="balanced"
        left={
          /* ── independent statistical comparator ─────────────────── */
          <Panel>
            <SectionHeader
              title="Statistical baseline comparator"
              subtitle="An independent robust-deviation check, not the model. It can disagree with the detector, and that disagreement is informative."
              level={3}
            />
            <div className="grid grid-cols-2 gap-[var(--ss-space-4)] p-[var(--ss-space-4)]">
              <MetricValue
                label="statistical_baseline_max"
                value={asNumber(m7["statistical_baseline_max"])}
                register="CALCULATION"
                note="max |robust normalised deviation| over the 8 signals"
              />
              <MetricValue
                label="statistical_baseline_flag_rate"
                value={asNumber(m7["statistical_baseline_flag_rate"])}
                register="CALCULATION"
                note="flag threshold 3.0"
              />
            </div>
          </Panel>
        }
        right={
          /* ── what needs the missing endpoint ────────────────────── */
          <Panel>
            <SectionHeader
              title="Beyond this record"
              subtitle="The investigation record stores the M7 summary only."
              level={3}
            />
            <div className="flex flex-col gap-[var(--ss-space-3)] p-[var(--ss-space-4)]">
              <p
                className="text-[var(--ss-text-secondary)]"
                style={{ maxWidth: "var(--ss-measure-prose)" }}
              >
                Per-observation score trajectory, is_anomaly markers, both decision
                thresholds and the full model record are not part of the investigation
                record. They are available on the module anomaly view, read from the
                frozen M7 artifacts.
              </p>
              <a
                href={`/modules/${record.module_id}/anomaly`}
                className="ss-field-label w-fit border border-[var(--ss-border-strong)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] text-[var(--ss-text-primary)] hover:border-[var(--ss-accent)]"
                style={{ borderRadius: "var(--ss-radius-sm)" }}
              >
                Open module anomaly view
              </a>
            </div>
          </Panel>
        }
      />
      <NextAction
        href={`/investigations/${investigationId}/evaluation`}
        label="Inspect Detector Evaluation"
        hint="how the detector behaved for this module"
      />
    </>
  );
}
