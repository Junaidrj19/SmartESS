import Link from "next/link";
import { AccessibleDataTable } from "@/components/AccessibleDataTable";
import { ErrorState } from "@/components/ErrorState";
import { MetricValue } from "@/components/MetricValue";
import { MonoId } from "@/components/MonoId";
import { Panel, SectionHeader } from "@/components/Panel";
import { ReadinessPanel } from "@/components/ReadinessPanel";
import { StatusChip } from "@/components/StatusChip";
import { getCorpus, getReadiness } from "@/lib/api/endpoints";
import { inferenceChipStatus } from "@/lib/copy/status";

export const metadata = { title: "Pipeline Readiness — SmartESS" };

/**
 * Pipeline Readiness (UX.md §21, §36).
 *
 * A real operational surface: which artifacts exist, which are absent, what
 * produces each one, and which capabilities are genuinely not implemented. Its
 * purpose is to explain **why** a surface cannot currently be inspected.
 */
export default async function ReadinessPage() {
  const [readinessResult, corpusResult] = await Promise.all([getReadiness(), getCorpus()]);

  const readiness = readinessResult.kind === "ok" ? readinessResult.data : null;
  const corpus = corpusResult.kind === "ok" ? corpusResult.data : null;

  return (
    <>
      <Panel>
        <SectionHeader
          level={1}
          title="Pipeline Readiness"
          subtitle="Which SmartESS artifacts exist in this environment, and the command that produces each one. A missing artifact is a setup state, not an error."
        />
        {readiness ? (
          <ReadinessPanel
            rows={readiness.artifacts.map((a) => ({
              artifact: a.artifact,
              status: a.status,
              path: a.path ?? "—",
              cli: a.produced_by,
            }))}
          />
        ) : (
          <div className="p-[var(--ss-space-4)]">
            <ErrorState result={readinessResult} />
          </div>
        )}
      </Panel>

      {/* ── LLM configuration ──────────────────────────────────────── */}
      <Panel>
        <SectionHeader
          title="Reasoning provider"
          subtitle="Only non-sensitive configuration is exposed. The API key is never returned by any endpoint and never reaches the browser."
          level={3}
        />
        <div className="p-[var(--ss-space-4)]">
          {!readiness ? (
            <ErrorState result={readinessResult} />
          ) : (
            <div className="flex flex-col gap-[var(--ss-space-4)]">
              <div className="flex flex-wrap items-center gap-[var(--ss-space-3)]">
                <StatusChip status={inferenceChipStatus(readiness.llm)} />
                <span className="ss-field-label">{readiness.llm.status}</span>
              </div>
              <dl className="grid grid-cols-2 gap-[var(--ss-space-4)] lg:grid-cols-4">
                <MetricValue label="provider" value={readiness.llm.provider} register="LLM_REASONING" />
                <MetricValue label="model" value={readiness.llm.model} register="LLM_REASONING" />
                <MetricValue label="endpoint_host" value={readiness.llm.endpoint_host} register="LLM_REASONING" />
                <MetricValue label="prompt_version" value={readiness.llm.prompt_version} register="LLM_REASONING" />
                <MetricValue label="timeout" value={readiness.llm.timeout} register="DATA" unit="s" />
                <MetricValue
                  label="embedding_model"
                  value={readiness.llm.embedding_model}
                  register="RETRIEVED_EVIDENCE"
                />
              </dl>
              <p
                className="text-[var(--ss-text-secondary)]"
                style={{ maxWidth: "var(--ss-measure-prose)" }}
              >
                {readiness.llm.note}
              </p>
            </div>
          )}
        </div>
      </Panel>

      {/* ── knowledge base ────────────────────────────────────────── */}
      <Panel>
        <SectionHeader
          title="Knowledge base"
          subtitle="Only VERIFIED documents enter the production collection. Coverage is incomplete and the gaps are recorded."
          level={3}
        />
        <div className="p-[var(--ss-space-4)]">
          {!corpus ? (
            <ErrorState result={corpusResult} />
          ) : (
            <div className="flex flex-col gap-[var(--ss-space-4)]">
              <div className="grid grid-cols-2 gap-[var(--ss-space-4)] lg:grid-cols-4">
                <MetricValue label="corpus_version" value={corpus.corpus_version} register="DATA" />
                <MetricValue label="manifest documents" value={corpus.n_documents} register="DATA" />
                <MetricValue
                  label="collection chunks"
                  value={corpus.collection.chunk_count}
                  register="RETRIEVED_EVIDENCE"
                  note={corpus.collection.reachable ? "reachable" : "unreachable"}
                />
                <MetricValue
                  label="VERIFIED documents"
                  value={corpus.counts_by_verification_status["VERIFIED"] ?? 0}
                  register="RETRIEVED_EVIDENCE"
                  note="production corpus"
                />
              </div>

              <AccessibleDataTable
                caption="Corpus document count by verification status."
                rows={Object.entries(corpus.counts_by_verification_status).sort()}
                rowKey={([status]) => status}
                columns={[
                  { key: "status", header: "verification_status", render: ([s]) => s },
                  { key: "n", header: "documents", render: ([, n]) => n, align: "right" },
                  {
                    key: "production",
                    header: "in production collection",
                    render: ([s]) => (s === "VERIFIED" ? "yes" : "no"),
                    mono: false,
                  },
                ]}
              />

              <AccessibleDataTable
                caption="Corpus document count by source type."
                rows={Object.entries(corpus.counts_by_source_type).sort()}
                rowKey={([t]) => t}
                columns={[
                  { key: "type", header: "source_type", render: ([t]) => t },
                  { key: "n", header: "documents", render: ([, n]) => n, align: "right" },
                ]}
              />
            </div>
          )}
        </div>
      </Panel>

      {/* ── capabilities that are genuinely not implemented ───────── */}
      <Panel>
        <SectionHeader
          title="Capabilities not implemented"
          subtitle="These are backend gaps, not display bugs. The surfaces that need them show an explicit unavailable state."
          level={3}
        />
        <div className="p-[var(--ss-space-4)]">
          <AccessibleDataTable
            caption="Capabilities the backend does not provide, with the reason."
            rows={[
              {
                capability: "Asynchronous investigation run + live stage progress",
                reason:
                  "POST /investigations is synchronous and emits no intermediate events. No progress is simulated.",
                ref: "design.md §10.3",
              },
              {
                capability: "ModuleProfile / TestProfile binding",
                reason:
                  "M1/M2 schemas exist but are not wired into an investigation; no ingestion or persistence. No datasheet ratings or acceptance limits can be shown.",
                ref: "design.md §20.1",
              },
              {
                capability: "Acceptance-limit checking",
                reason:
                  "check_acceptance_limits is registered but never invoked, and no acceptance limits are available. No limit lines are drawn.",
                ref: "design.md §20.2",
              },
              {
                capability: "Change-point and correlation markers",
                reason:
                  "detect_change_point, calculate_correlation and analyze_temperature_dependence are registered but never invoked by the investigation agent.",
                ref: "design.md §20.3",
              },
              {
                capability: "Engineer decision / sign-off",
                reason:
                  "No field exists anywhere for a verdict or review state. Human Review renders as awaiting review and cannot be recorded.",
                ref: "design.md §20.6",
              },
              {
                capability: "Per-investigation artifact hashes",
                reason:
                  "snapshot_m7_m8 is computed at run time but not persisted, so hashes shown are current-artifact identity, not run-time identity.",
                ref: "design.md §20.7",
              },
              {
                capability: "PDF report export",
                reason:
                  "reportlab is a dependency and the CLI has a --no-pdf flag, but no generator exists. PDF is not offered in the UI.",
                ref: "design.md §20.8",
              },
              {
                capability: "Global evidence browser",
                reason:
                  "ChromaRetriever has no get-by-chunk-id, so evidence is addressable only within an investigation.",
                ref: "design.md §20.12",
              },
              {
                capability: "Observation-level accuracy metrics",
                reason:
                  "Observation-level ground truth does not exist; only flag-rate summaries are produced. No precision/recall/F1/FPR is shown per observation.",
                ref: "design.md §20.13",
              },
            ]}
            rowKey={(r) => r.capability}
            columns={[
              { key: "cap", header: "capability", render: (r) => r.capability, mono: false },
              { key: "reason", header: "reason", render: (r) => r.reason, mono: false },
              { key: "ref", header: "reference", render: (r) => r.ref },
            ]}
          />
        </div>
      </Panel>

      {/* ── pipeline order ────────────────────────────────────────── */}
      <Panel>
        <SectionHeader
          title="Pipeline order"
          subtitle="Each stage consumes the frozen output of the previous one."
          level={3}
        />
        <div className="p-[var(--ss-space-4)]">
          <ol className="ss-mono flex flex-col gap-[var(--ss-space-1)] text-[var(--ss-text-secondary)]">
            <li>scripts/generate_synthetic_dataset.py</li>
            <li>scripts/validate_synthetic_dataset.py</li>
            <li>scripts/build_features.py</li>
            <li>scripts/train_anomaly_model.py</li>
            <li>scripts/evaluate_anomaly.py</li>
            <li>scripts/ingest_knowledge.py</li>
            <li>scripts/build_healthy_reference.py</li>
            <li>scripts/investigate.py</li>
          </ol>
          <p className="mt-[var(--ss-space-3)]">
            <Link href="/" className="text-[var(--ss-accent)]">
              Return to Mission Control
            </Link>
          </p>
        </div>
      </Panel>
    </>
  );
}
