import { notFound } from "next/navigation";
import { AccessibleDataTable } from "@/components/AccessibleDataTable";
import { EmptyState } from "@/components/EmptyState";
import { GateResult } from "@/components/GateResult";
import { MetricValue } from "@/components/MetricValue";
import { MonoId } from "@/components/MonoId";
import { NextAction } from "@/components/NextAction";
import { Panel, SectionHeader } from "@/components/Panel";
import { StageNode, STAGE_META } from "@/components/StageNode";
import { StatusChip } from "@/components/StatusChip";
import { getInvestigation } from "@/lib/api/endpoints";
import {
  gateOutcome,
  llmIdentity,
  provenanceComplete,
  raw,
  resultsByTool,
  signalOf,
  stages,
} from "@/lib/investigation";
import type { InvestigationRecord, PipelineStep } from "@/lib/types/backend";

export default async function TracePage({
  params,
}: {
  params: Promise<{ investigationId: string }>;
}) {
  const { investigationId } = await params;
  const result = await getInvestigation(investigationId);
  if (result.kind !== "ok") notFound();
  const record = result.data;

  const allStages = stages(record);
  const TOOL_REGISTRY = [
    "calculate_drift",
    "calculate_slope",
    "calculate_percent_change",
    "compare_population",
    "analyze_temperature_dependence",
    "detect_change_point",
    "calculate_correlation",
    "check_acceptance_limits",
    "calculate_degradation_rate",
  ] as const;
  const invoked = new Set(record.deterministic_results.map((r) => r.tool_name));

  return (
    <>
      <Panel>
        <SectionHeader
          level={1}
          title="Pipeline Trace"
          subtitle="The LangGraph execution path, reconstructed from the recorded provenance. Repeated nodes are genuine retries, not a display artefact."
        />
        <div className="p-[var(--ss-space-4)]">
          <ol className="flex flex-col gap-[var(--ss-space-2)]">
            {allStages.map((stage, i) => (
              <StageNode key={stage.step} stage={stage} index={i}>
                <StageDetail step={stage.step} record={record} />
              </StageNode>
            ))}
          </ol>
        </div>
      </Panel>

      {/* ── validation gates ────────────────────────────────────────── */}
      <Panel>
        <SectionHeader title="Validation gates" level={3} />
        <div className="flex flex-col gap-[var(--ss-space-3)] p-[var(--ss-space-4)]">
          <GateResult
            outcome={gateOutcome(record, "hypothesis_validation")}
            retryCounts={record.retry_counts}
          />
          <GateResult
            outcome={gateOutcome(record, "report_validation")}
            retryCounts={record.retry_counts}
          />
        </div>
      </Panel>

      {/* ── tool registry: invoked vs registered ────────────────────── */}
      <Panel>
        <SectionHeader
          title="Deterministic tool registry"
          subtitle="Nine tools are registered. The investigation agent invokes a subset; the others are shown as not invoked rather than implied."
          level={3}
        />
        <div className="p-[var(--ss-space-4)]">
          <ul className="grid grid-cols-1 gap-[var(--ss-space-1)] sm:grid-cols-2 lg:grid-cols-3">
            {TOOL_REGISTRY.map((tool) => {
              const count = record.deterministic_results.filter((r) => r.tool_name === tool).length;
              return (
                <li
                  key={tool}
                  className="flex items-center justify-between gap-[var(--ss-space-2)] border border-[var(--ss-border-subtle)] p-[var(--ss-space-2)]"
                  style={{ borderRadius: "var(--ss-radius-sm)" }}
                >
                  <MonoId value={tool} />
                  {invoked.has(tool) ? (
                    <span className="ss-field-label text-[var(--ss-state-pass)]">{count}×</span>
                  ) : (
                    <span className="ss-field-label text-[var(--ss-text-muted)]">NOT INVOKED</span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      </Panel>
      <NextAction
        href={`/investigations/${investigationId}/evidence`}
        label="Inspect Evidence"
        hint="the retrieved technical sources and their provenance"
      />
    </>
  );
}

/** Per-stage inspector content (design.md §6.1). */
function StageDetail({
  step,
  record,
}: {
  step: PipelineStep;
  record: InvestigationRecord;
}) {
  const meta = STAGE_META[step];
  const entries = record.provenance.filter((p) => p.step === step);

  return (
    <div className="border-t border-[var(--ss-border-subtle)] px-[var(--ss-space-3)] py-[var(--ss-space-3)]">
      {/* Recorded provenance for this node. */}
      {entries.length > 0 && (
        <div className="mb-[var(--ss-space-3)] flex flex-col gap-[var(--ss-space-1)]">
          <span className="ss-field-label">Recorded provenance</span>
          {entries.map((e, i) => (
            <div key={i} className="flex flex-col gap-[var(--ss-space-1)]">
              <span className="ss-mono text-[var(--ss-text-muted)]">
                {e.timestamp} · {e.source}
              </span>
              <span className="text-[var(--ss-text-secondary)]">{e.description}</span>
            </div>
          ))}
        </div>
      )}

      {step === "investigation_agent" && <InvestigationAgentDetail record={record} />}
      {step === "evidence_agent" && <EvidenceAgentDetail record={record} />}
      {step === "hypothesis_agent" && <HypothesisAgentDetail record={record} />}
      {step === "report_agent" && <ReportAgentDetail record={record} />}
      {(step === "hypothesis_validation" || step === "report_validation") && (
        <p className="text-[var(--ss-text-muted)]">{meta.summary}</p>
      )}
      {step === "load_investigation" && (
        <div className="grid grid-cols-2 gap-[var(--ss-space-3)] lg:grid-cols-4">
          <MetricValue label="module_id" value={record.module_id} register="DATA" />
          <MetricValue label="model_id" value={record.model_id} register="DATA" />
          <MetricValue label="dataset_id" value={record.dataset_id} register="DATA" />
        </div>
      )}
    </div>
  );
}

function InvestigationAgentDetail({ record }: { record: InvestigationRecord }) {
  const groups = resultsByTool(record);
  if (groups.length === 0) {
    return <EmptyState state="ANALYSIS_NOT_PERFORMED" />;
  }
  return (
    <div className="flex flex-col gap-[var(--ss-space-3)]">
      <p className="text-[var(--ss-text-muted)]">
        No LLM involvement in this stage. Every value below is the output of a fixed
        numeric method.
      </p>
      {groups.map((g) => (
        <div key={g.toolName} className="flex flex-col gap-[var(--ss-space-2)]">
          <div className="flex flex-wrap items-center gap-[var(--ss-space-2)]">
            <MonoId value={g.toolName} />
            <span className="ss-field-label text-[var(--ss-text-muted)]">v{g.toolVersion}</span>
            <span className="ss-field-label text-[var(--ss-text-muted)]">
              {g.results.length} result{g.results.length === 1 ? "" : "s"}
            </span>
            {g.method && (
              <span className="ss-field-label text-[var(--ss-text-muted)]">
                METHOD <span className="ss-mono normal-case">{g.method}</span>
              </span>
            )}
          </div>
          <AccessibleDataTable
            caption={`Deterministic results produced by ${g.toolName}`}
            rows={g.results}
            rowKey={(r, i) => `${g.toolName}-${i}`}
            columns={[
              { key: "signal", header: "Signal", render: (r) => signalOf(r) ?? "—" },
              {
                key: "input",
                header: "Input summary",
                render: (r) => raw(r.input_summary) ?? "—",
              },
              { key: "output", header: "Output", render: (r) => raw(r.output) ?? "—" },
            ]}
          />
        </div>
      ))}
    </div>
  );
}

function EvidenceAgentDetail({ record }: { record: InvestigationRecord }) {
  const ev = provenanceComplete(record);
  return (
    <div className="flex flex-col gap-[var(--ss-space-3)]">
      <p className="text-[var(--ss-text-muted)]">
        Retrieval only — no generation. Queries are built from the deterministic
        findings by fixed lookup tables.
      </p>
      <div className="grid grid-cols-2 gap-[var(--ss-space-3)] lg:grid-cols-4">
        <MetricValue
          label="Queries generated"
          value={record.evidence_queries.length}
          register="RETRIEVED_EVIDENCE"
          note="max 8"
        />
        <MetricValue
          label="Records retrieved"
          value={record.evidence_records.length}
          register="RETRIEVED_EVIDENCE"
        />
        <MetricValue
          label="Provenance complete"
          value={`${ev.complete}/${ev.total}`}
          register="RETRIEVED_EVIDENCE"
        />
        <MetricValue
          label="Evidence round"
          value={record.retry_counts["evidence_round"] ?? null}
          register="VALIDATION"
          note="max 2"
        />
      </div>
      {record.evidence_queries.length > 0 && (
        <div className="flex flex-col gap-[var(--ss-space-1)]">
          <span className="ss-field-label">Queries (verbatim)</span>
          <ol className="flex flex-col gap-[var(--ss-space-1)]">
            {record.evidence_queries.map((q, i) => (
              <li key={i} className="ss-mono text-[var(--ss-text-secondary)]">
                {i + 1}. {q}
              </li>
            ))}
          </ol>
          <span className="text-[var(--ss-text-muted)]" style={{ fontSize: "var(--ss-text-label-size)" }}>
            The backend stores queries as a flat list with no back-reference to the
            result that motivated each one, so query→finding attribution is not
            available (design.md §9.2).
          </span>
        </div>
      )}
    </div>
  );
}

function HypothesisAgentDetail({ record }: { record: InvestigationRecord }) {
  const llm = llmIdentity(record);
  const candidates = record.hypothesis?.candidates ?? [];
  const error = record.errors["hypothesis"];

  return (
    <div
      className="flex flex-col gap-[var(--ss-space-3)] border p-[var(--ss-space-3)]"
      style={{
        borderColor: "var(--ss-reg-llm-border)",
        backgroundColor: "var(--ss-reg-llm-surface)",
        borderRadius: "var(--ss-radius-sm)",
      }}
    >
      <div className="flex flex-wrap items-center gap-[var(--ss-space-2)]">
        <StatusChip status={llm.mode} />
        <span className="ss-field-label text-[var(--ss-text-muted)]">
          {llm.provider ?? "provider not recorded"} /{" "}
          <span className="ss-mono normal-case">{llm.model ?? "model not recorded"}</span>
        </span>
      </div>
      <p className="text-[var(--ss-text-secondary)]">
        The only generative stage in the pipeline. Its output is a set of candidate
        mechanisms requiring engineering confirmation.
      </p>
      <div className="grid grid-cols-2 gap-[var(--ss-space-3)] lg:grid-cols-4">
        <MetricValue label="Provider" value={llm.provider} register="LLM_REASONING" note="derived from provenance" />
        <MetricValue label="Model" value={llm.model} register="LLM_REASONING" note="derived from provenance" />
        <MetricValue
          label="Inference"
          value={llm.mode === "UNKNOWN" ? null : llm.mode.replace(/_/g, " ").toLowerCase()}
          register="LLM_REASONING"
          note="derived from provenance + recorded errors"
        />
        <MetricValue label="Candidates" value={candidates.length} register="LLM_REASONING" />
      </div>
      {record.hypothesis?.note && (
        <div className="flex flex-col gap-[var(--ss-space-1)]">
          <span className="ss-field-label">Note</span>
          <p className="text-[var(--ss-text-secondary)]" style={{ maxWidth: "var(--ss-measure-prose)" }}>
            {record.hypothesis.note}
          </p>
        </div>
      )}
      {error && (
        <div className="flex flex-col gap-[var(--ss-space-1)]">
          <span className="ss-field-label" style={{ color: "var(--ss-state-reject)" }}>
            Recorded error
          </span>
          <code className="ss-mono break-all text-[var(--ss-state-reject)]">{error}</code>
        </div>
      )}
      <p className="text-[var(--ss-text-muted)]" style={{ fontSize: "var(--ss-text-label-size)" }}>
        Context limits applied by the agent: MAX_EVIDENCE_CHARS 1200 ·
        MAX_DETERMINISTIC_RESULTS 40 · MAX_CONTEXT_CHARS 24000. These bound what the
        model could see.
      </p>
    </div>
  );
}

function ReportAgentDetail({ record }: { record: InvestigationRecord }) {
  const sections = record.report?.sections ?? [];
  if (sections.length === 0) {
    return <EmptyState state="NO_DATA" body="No report was produced for this investigation." />;
  }
  return (
    <div className="flex flex-col gap-[var(--ss-space-2)]">
      <p className="text-[var(--ss-text-muted)]">
        Deterministic synthesis: composed only from values already in the
        investigation state. Recalculates nothing, invents nothing.
      </p>
      <div className="flex flex-wrap gap-[var(--ss-space-1)]">
        {sections.map((s) => (
          <span
            key={s.title}
            className="ss-field-label border border-[var(--ss-border-subtle)] px-[var(--ss-space-1)] text-[var(--ss-text-secondary)]"
            style={{ borderRadius: "var(--ss-radius-sm)" }}
          >
            {s.title} · {s.findings.length}
          </span>
        ))}
      </div>
    </div>
  );
}
