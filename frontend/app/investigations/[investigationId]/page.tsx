import Link from "next/link";
import { notFound } from "next/navigation";
import { EmptyState } from "@/components/EmptyState";
import { MetricValue } from "@/components/MetricValue";
import { MonoId } from "@/components/MonoId";
import { NextAction } from "@/components/NextAction";
import { Panel, SectionHeader, SplitPanel } from "@/components/Panel";
import { RegisterBadge } from "@/components/RegisterValue";
import { ReproducibilityBlock } from "@/components/ReproducibilityBlock";
import { StatusChip } from "@/components/StatusChip";
import { getInvestigation } from "@/lib/api/endpoints";
import {
  asNumber,
  asString,
  gateOutcome,
  provenanceComplete,
  resultsByTool,
} from "@/lib/investigation";
import { ANOMALY_QUALIFICATION } from "@/lib/copy/states";

export default async function WorkspacePage({
  params,
}: {
  params: Promise<{ investigationId: string }>;
}) {
  const { investigationId } = await params;
  const result = await getInvestigation(investigationId);
  if (result.kind !== "ok") notFound();
  const record = result.data;

  const m7 = record.m7_module_summary;
  const tools = resultsByTool(record);
  const evidence = provenanceComplete(record);
  const hypothesisGate = gateOutcome(record, "hypothesis_validation");
  const reportGate = gateOutcome(record, "report_validation");
  const candidates = record.hypothesis?.candidates ?? [];
  const trajectory = record.module_trajectory;

  return (
    <>
      {/* ── what this investigation produced ────────────────────────── */}
      <Panel>
        <SectionHeader
          level={1}
          title="Investigation Workspace"
          subtitle="Everything below is read from the stored investigation record. Values are rendered exactly as the backend produced them."
        />
        <div className="grid grid-cols-2 gap-[var(--ss-space-4)] p-[var(--ss-space-4)] lg:grid-cols-4">
          <MetricValue
            label="Deterministic results"
            value={record.deterministic_results.length}
            register="CALCULATION"
            note={`${tools.length} distinct tool${tools.length === 1 ? "" : "s"}`}
          />
          <MetricValue
            label="Evidence records"
            value={record.evidence_records.length}
            register="RETRIEVED_EVIDENCE"
            note={`${evidence.complete}/${evidence.total} provenance complete`}
          />
          <MetricValue
            label="Candidate mechanisms"
            value={candidates.length}
            register="LLM_REASONING"
            note="competing explanations"
          />
          <MetricValue
            label="Report sections"
            value={record.report?.sections.length ?? 0}
            register="CALCULATION"
            note={record.report ? undefined : "no report produced"}
          />
        </div>
      </Panel>

      <SplitPanel
        ratio="balanced"
        left={
          /* ── M7 summary (real) ──────────────────────────────────── */
          <Panel>
            <SectionHeader
              title="Anomaly summary (M7)"
              subtitle={ANOMALY_QUALIFICATION}
              level={3}
              actions={
                <Link
                  href={`/investigations/${investigationId}/anomaly`}
                  className="ss-field-label border border-[var(--ss-border-strong)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] hover:border-[var(--ss-accent)]"
                  style={{ borderRadius: "var(--ss-radius-sm)" }}
                >
                  Inspect
                </Link>
              }
            />
            <div className="grid grid-cols-2 gap-[var(--ss-space-4)] p-[var(--ss-space-4)]">
              <div className="col-span-2 flex items-center gap-[var(--ss-space-2)]">
                <StatusChip
                  status={asString(m7["module_anomaly_status"])}
                  suffix={asString(m7["anomaly_rate"]) ?? undefined}
                />
                <RegisterBadge register="DATA" />
              </div>
              <MetricValue label="Observations" value={asNumber(m7["n_observations"])} register="DATA" />
              <MetricValue
                label="Flagged observations"
                value={asNumber(m7["n_anomalous_observations"])}
                register="DATA"
              />
              <MetricValue
                label="Max anomaly score"
                value={asNumber(m7["max_anomaly_score"])}
                register="DATA"
                note="higher = more anomalous"
              />
              <MetricValue
                label="Mean anomaly score"
                value={asNumber(m7["mean_anomaly_score"])}
                register="DATA"
              />
            </div>
          </Panel>
        }
        right={
          /* ── validation gates (real) ────────────────────────────── */
          <Panel>
            <SectionHeader
              title="Validation"
              subtitle="Automated gates over the model's output. These are what make SmartESS more than an LLM wrapper."
              level={3}
              actions={
                <Link
                  href={`/investigations/${investigationId}/trace`}
                  className="ss-field-label border border-[var(--ss-border-strong)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] hover:border-[var(--ss-accent)]"
                  style={{ borderRadius: "var(--ss-radius-sm)" }}
                >
                  Trace
                </Link>
              }
            />
            <div className="flex flex-col gap-[var(--ss-space-3)] p-[var(--ss-space-4)]">
              <div className="flex items-center justify-between">
                <span className="ss-field-label">Hypothesis validation</span>
                <StatusChip
                  status={hypothesisGate.reached ? (hypothesisGate.passed ? "PASSED" : "REJECTED") : "NOT_REACHED"}
                  suffix={hypothesisGate.issues.length > 0 ? String(hypothesisGate.issues.length) : undefined}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="ss-field-label">Report validation</span>
                <StatusChip
                  status={reportGate.reached ? (reportGate.passed ? "PASSED" : "REJECTED") : "NOT_REACHED"}
                  suffix={reportGate.issues.length > 0 ? String(reportGate.issues.length) : undefined}
                />
              </div>
              <div className="flex flex-col gap-[var(--ss-space-1)] border-t border-[var(--ss-border-subtle)] pt-[var(--ss-space-2)]">
                <span className="ss-field-label">Retry counts</span>
                {Object.keys(record.retry_counts).length === 0 ? (
                  <span className="italic text-[var(--ss-text-muted)]">not recorded</span>
                ) : (
                  <span className="ss-mono text-[var(--ss-text-secondary)]">
                    {Object.entries(record.retry_counts)
                      .map(([k, v]) => `${k}=${v}`)
                      .join("  ·  ")}
                  </span>
                )}
              </div>
            </div>
          </Panel>
        }
      />

      {/* ── candidates at a glance ──────────────────────────────────── */}
      <Panel>
        <SectionHeader
          title="Candidate mechanisms"
          subtitle="Competing explanations. None is ranked, and none is a confirmed physical failure."
          level={3}
          actions={
            <Link
              href={`/investigations/${investigationId}/hypotheses`}
              className="ss-field-label border border-[var(--ss-border-strong)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] hover:border-[var(--ss-accent)]"
              style={{ borderRadius: "var(--ss-radius-sm)" }}
            >
              Compare
            </Link>
          }
        />
        <div className="p-[var(--ss-space-4)]">
          {candidates.length === 0 ? (
            <EmptyState
              state={
                asString(m7["module_anomaly_status"]) === "clean"
                  ? "INSUFFICIENT_EVIDENCE"
                  : "MECHANISM_UNRESOLVED"
              }
              detail={record.hypothesis?.note || undefined}
            />
          ) : (
            <ul className="flex flex-col gap-[var(--ss-space-2)]">
              {candidates.map((c) => (
                <li
                  key={c.candidate_id}
                  className="flex flex-wrap items-center gap-[var(--ss-space-3)] border border-[var(--ss-reg-llm-border)] p-[var(--ss-space-2)]"
                  style={{
                    backgroundColor: "var(--ss-reg-llm-surface)",
                    borderRadius: "var(--ss-radius-sm)",
                  }}
                >
                  <StatusChip status={c.status} />
                  <span className="ss-mono min-w-[200px] flex-1 text-[var(--ss-text-primary)]">
                    {c.mechanism}
                  </span>
                  <span className="ss-field-label text-[var(--ss-text-muted)]">
                    CONF <span className="ss-mono normal-case">{c.confidence}</span>
                  </span>
                  <span className="ss-field-label text-[var(--ss-state-pass)]">
                    SUP {c.supporting_evidence_ids.length}
                  </span>
                  <span className="ss-field-label text-[var(--ss-state-reject)]">
                    CON {c.contradictory_evidence_ids.length}
                  </span>
                  <MonoId value={c.candidate_id} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </Panel>

      {/* ── trajectory presence ─────────────────────────────────────── */}
      <Panel>
        <SectionHeader
          title="Signal trajectory"
          subtitle="Recorded in the investigation record at the time of the run."
          level={3}
          actions={
            <Link
              href={`/investigations/${investigationId}/signals`}
              className="ss-field-label border border-[var(--ss-border-strong)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] hover:border-[var(--ss-accent)]"
              style={{ borderRadius: "var(--ss-radius-sm)" }}
            >
              Inspect
            </Link>
          }
        />
        <div className="p-[var(--ss-space-4)]">
          {!trajectory ? (
            <EmptyState
              state="NO_DATA"
              body="No module trajectory was recorded for this investigation."
              detail="module_trajectory is null on the stored record"
            />
          ) : (
            <div className="grid grid-cols-2 gap-[var(--ss-space-4)] lg:grid-cols-4">
              <MetricValue label="Observations" value={trajectory.n_observations} register="DATA" />
              <MetricValue label="Signals" value={Object.keys(trajectory.signals).length} register="DATA" />
              <MetricValue label="Min score" value={trajectory.min_score} register="DATA" />
              <MetricValue label="Max score" value={trajectory.max_score} register="DATA" />
            </div>
          )}
        </div>
      </Panel>

      {/* ── limitations ─────────────────────────────────────────────── */}
      <Panel>
        <SectionHeader
          title="Limitations"
          subtitle="Recorded by the pipeline. Never hidden to make the output look decisive."
          level={3}
        />
        <div className="p-[var(--ss-space-4)]">
          {record.limitations.length === 0 ? (
            <span className="text-[var(--ss-text-muted)]">None recorded.</span>
          ) : (
            <ul className="flex flex-col gap-[var(--ss-space-1)]">
              {record.limitations.map((l, i) => (
                <li key={i} className="ss-mono text-[var(--ss-state-attention)]">
                  {l}
                </li>
              ))}
            </ul>
          )}
        </div>
      </Panel>

      {/* ── reproducibility ─────────────────────────────────────────── */}
      <Panel>
        <SectionHeader
          title="Reproducibility"
          subtitle="The exact configuration that produced this investigation, and what the record does not carry."
          level={3}
        />
        <ReproducibilityBlock record={record} />
      </Panel>
      <NextAction
        href={`/investigations/${investigationId}/trace`}
        label="Inspect Pipeline Trace"
        hint="the seven-stage LangGraph execution path"
      />
    </>
  );
}
