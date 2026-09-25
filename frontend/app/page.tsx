import Link from "next/link";
import { AccessibleDataTable } from "@/components/AccessibleDataTable";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { MetricValue } from "@/components/MetricValue";
import { MissionFlow } from "@/components/MissionFlow";
import { Panel, SectionHeader, SplitPanel } from "@/components/Panel";
import { StatusChip } from "@/components/StatusChip";
import {
  getCorpus,
  getModulePopulation,
  getReadiness,
  listInvestigations,
  listModels,
} from "@/lib/api/endpoints";
import { ANOMALY_QUALIFICATION, ORIENTATION_SENTENCE, SYNTHETIC_NOTE } from "@/lib/copy/states";
import { inferenceChipStatus } from "@/lib/copy/status";
import { MODULE_ANOMALY_STATUS } from "@/lib/types/backend";

export const metadata = { title: "Mission Control — SmartESS" };

const CANONICAL_MODULE = "syn-mod-0042";

/**
 * Mission Control — the engineering workstation entry point (UX.md §5).
 *
 * Answers, in the first viewport: what am I looking at, what data exists, what
 * has SmartESS already evaluated, where does the investigation happen, what can I
 * inspect next.
 *
 * Every number is read from the backend. When a capability is unavailable the
 * panel says which one and why — it never substitutes a plausible figure.
 */
export default async function MissionControlPage() {
  const [readinessResult, populationResult, modelsResult, investigationsResult, corpusResult] =
    await Promise.all([
      getReadiness(),
      getModulePopulation(),
      listModels(),
      listInvestigations(),
      getCorpus(),
    ]);

  const readiness = readinessResult.kind === "ok" ? readinessResult.data : null;
  const population = populationResult.kind === "ok" ? populationResult.data : null;
  const models = modelsResult.kind === "ok" ? modelsResult.data : [];
  const investigations = investigationsResult.kind === "ok" ? investigationsResult.data : [];
  const corpus = corpusResult.kind === "ok" ? corpusResult.data : null;

  const model = models[0] ?? null;
  const absent = readiness?.artifacts.filter((a) => a.status !== "PRESENT") ?? [];

  const statusCounts = investigations.reduce<Record<string, number>>((acc, i) => {
    acc[i.status] = (acc[i.status] ?? 0) + 1;
    return acc;
  }, {});
  const canonical = investigations.filter((i) => i.module_id === CANONICAL_MODULE);

  return (
    <>
      {/* ── orientation: what is this ────────────────────────────────── */}
      <Panel>
        <div className="flex flex-col gap-[var(--ss-space-4)] p-[var(--ss-space-4)]">
          <h1
            className="font-medium text-[var(--ss-text-primary)]"
            style={{ fontSize: "var(--ss-text-title-size)", lineHeight: "var(--ss-leading-tight)" }}
          >
            Mission Control
          </h1>
          <p
            className="text-[var(--ss-text-primary)]"
            style={{
              fontSize: "var(--ss-text-section-size)",
              maxWidth: "var(--ss-measure-prose)",
            }}
          >
            {ORIENTATION_SENTENCE}
          </p>
          <div className="flex flex-wrap items-center gap-[var(--ss-space-4)]">
            <span className="ss-field-label">
              API{" "}
              <StatusChip status={readiness ? "READY" : "NOT_CONFIGURED"} />
            </span>
            {readiness && (
              <span className="ss-field-label">
                Inference{" "}
                <StatusChip status={inferenceChipStatus(readiness.llm)} />
              </span>
            )}
            {model && (
              <span className="ss-field-label">
                Detector{" "}
                <span className="ss-mono normal-case text-[var(--ss-text-secondary)]">
                  {model.model_id}
                </span>
              </span>
            )}
            <span className="ss-field-label">
              Data origin{" "}
              <span className="ss-mono normal-case text-[var(--ss-text-secondary)]">
                SYNTHETIC
              </span>
            </span>
          </div>
          {readinessResult.kind !== "ok" && <ErrorState result={readinessResult} />}
        </div>
      </Panel>

      {/* ── the workflow ─────────────────────────────────────────────── */}
      <Panel>
        <SectionHeader
          title="Investigation chain"
          subtitle="Each stage is a real computational stage. Register treatment shows whether a stage produces data, a calculation, retrieved evidence, model reasoning or a validation outcome."
        />
        <div className="p-[var(--ss-space-4)]">
          <MissionFlow />
        </div>
      </Panel>

      {/* ── primary action ──────────────────────────────────────────── */}
      <Panel>
        <SectionHeader
          title="Begin"
          subtitle="An investigation is always scoped to one module. Pick a module, review the configuration, then run."
        />
        <div className="flex flex-wrap items-center gap-[var(--ss-space-3)] p-[var(--ss-space-4)]">
          <Link
            href="/modules"
            className="ss-field-label border border-[var(--ss-accent)] px-[var(--ss-space-4)] py-[var(--ss-space-2)] text-[var(--ss-text-primary)]"
            style={{
              borderRadius: "var(--ss-radius-sm)",
              backgroundColor: "var(--ss-accent-muted)",
            }}
          >
            Select a module
          </Link>
          <Link
            href={`/modules/${CANONICAL_MODULE}`}
            className="ss-field-label border border-[var(--ss-border-strong)] px-[var(--ss-space-3)] py-[var(--ss-space-2)] hover:border-[var(--ss-accent)]"
            style={{ borderRadius: "var(--ss-radius-sm)" }}
          >
            Open canonical module {CANONICAL_MODULE}
          </Link>
          {canonical.length > 0 && (
            <Link
              href={`/investigations/${canonical[canonical.length - 1]!.investigation_id}`}
              className="ss-field-label border border-[var(--ss-border-strong)] px-[var(--ss-space-3)] py-[var(--ss-space-2)] hover:border-[var(--ss-accent)]"
              style={{ borderRadius: "var(--ss-radius-sm)" }}
            >
              Open latest canonical investigation
            </Link>
          )}
        </div>
      </Panel>

      <SplitPanel
        ratio="balanced"
        left={
          /* ── population: real, from the parquet ─────────────────── */
          <Panel>
            <SectionHeader
              title="Module population"
              subtitle={ANOMALY_QUALIFICATION}
              level={3}
              actions={
                <Link
                  href="/modules"
                  className="ss-field-label border border-[var(--ss-border-strong)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] hover:border-[var(--ss-accent)]"
                  style={{ borderRadius: "var(--ss-radius-sm)" }}
                >
                  Explore
                </Link>
              }
            />
            <div className="flex flex-col gap-[var(--ss-space-4)] p-[var(--ss-space-4)]">
              {!population ? (
                <>
                  <EmptyState
                    state="CAPABILITY_NOT_IMPLEMENTED"
                    body="Module population could not be read. The module-summary artifact is required."
                  />
                  <ErrorState result={populationResult} />
                </>
              ) : (
                <>
                  <div className="grid grid-cols-2 gap-[var(--ss-space-4)]">
                    <MetricValue
                      label="Modules scored"
                      value={population.n_modules}
                      register="DATA"
                      note={SYNTHETIC_NOTE}
                    />
                    <MetricValue
                      label="Lots"
                      value={Object.keys(population.by_lot).length}
                      register="DATA"
                    />
                  </div>
                  <AccessibleDataTable
                    caption="Module count by anomaly status, with a filtered link into the explorer."
                    rows={MODULE_ANOMALY_STATUS.map((s) => ({
                      status: s,
                      count: population.by_anomaly_status[s] ?? 0,
                    }))}
                    rowKey={(r) => r.status}
                    columns={[
                      {
                        key: "status",
                        header: "module_anomaly_status",
                        render: (r) => (
                          <Link
                            href={`/modules?anomaly_status=${r.status}`}
                            className="text-[var(--ss-accent)]"
                          >
                            {r.status}
                          </Link>
                        ),
                      },
                      { key: "count", header: "modules", render: (r) => r.count, align: "right" },
                    ]}
                  />
                </>
              )}
            </div>
          </Panel>
        }
        right={
          /* ── investigation coverage ─────────────────────────────── */
          <Panel>
            <SectionHeader
              title="Investigation coverage"
              subtitle="Stored investigations on this host."
              level={3}
              actions={
                <Link
                  href="/history"
                  className="ss-field-label border border-[var(--ss-border-strong)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] hover:border-[var(--ss-accent)]"
                  style={{ borderRadius: "var(--ss-radius-sm)" }}
                >
                  Review
                </Link>
              }
            />
            <div className="flex flex-col gap-[var(--ss-space-4)] p-[var(--ss-space-4)]">
              {investigationsResult.kind !== "ok" ? (
                <ErrorState result={investigationsResult} />
              ) : investigations.length === 0 ? (
                <EmptyState
                  state="NO_DATA"
                  body="No investigations have been recorded in this environment."
                  detail="ml/datasets/investigations/ — scripts/investigate.py"
                />
              ) : (
                <>
                  <div className="grid grid-cols-2 gap-[var(--ss-space-4)]">
                    <MetricValue label="Investigations" value={investigations.length} register="DATA" />
                    <MetricValue
                      label="Modules investigated"
                      value={new Set(investigations.map((i) => i.module_id)).size}
                      register="DATA"
                    />
                  </div>
                  <div className="flex flex-wrap gap-[var(--ss-space-2)]">
                    {Object.entries(statusCounts)
                      .sort(([a], [b]) => a.localeCompare(b))
                      .map(([status, count]) => (
                        <StatusChip key={status} status={status} suffix={String(count)} />
                      ))}
                  </div>
                  <div className="flex flex-col gap-[var(--ss-space-1)]">
                    <span className="ss-field-label">Most recent</span>
                    {investigations
                      .slice(-4)
                      .reverse()
                      .map((i) => (
                        <div
                          key={i.investigation_id}
                          className="flex flex-wrap items-center justify-between gap-[var(--ss-space-2)]"
                        >
                          <Link
                            href={`/investigations/${i.investigation_id}`}
                            className="ss-mono break-all text-[var(--ss-accent)] hover:text-[var(--ss-accent-hover)]"
                          >
                            {i.investigation_id}
                          </Link>
                          <StatusChip status={i.status} />
                        </div>
                      ))}
                  </div>
                </>
              )}
            </div>
          </Panel>
        }
      />

      {/* ── readiness summary ───────────────────────────────────────── */}
      <Panel>
        <SectionHeader
          title="Pipeline readiness"
          subtitle="What this environment can and cannot show."
          level={3}
          actions={
            <Link
              href="/system/readiness"
              className="ss-field-label border border-[var(--ss-border-strong)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] hover:border-[var(--ss-accent)]"
              style={{ borderRadius: "var(--ss-radius-sm)" }}
            >
              Inspect
            </Link>
          }
        />
        <div className="flex flex-col gap-[var(--ss-space-3)] p-[var(--ss-space-4)]">
          {!readiness ? (
            <ErrorState result={readinessResult} />
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-[var(--ss-space-4)]">
                <MetricValue
                  label="Artifacts present"
                  value={`${readiness.artifacts.length - absent.length}/${readiness.artifacts.length}`}
                  register="DATA"
                />
                <MetricValue
                  label="Knowledge base"
                  value={
                    corpus?.collection.chunk_count !== null && corpus?.collection.chunk_count !== undefined
                      ? `${corpus.collection.chunk_count} chunks`
                      : null
                  }
                  register="RETRIEVED_EVIDENCE"
                  note={
                    corpus
                      ? `${corpus.counts_by_verification_status["VERIFIED"] ?? 0} VERIFIED of ${corpus.n_documents} documents`
                      : undefined
                  }
                />
                <MetricValue
                  label="LLM provider"
                  value={readiness.llm.provider}
                  register="LLM_REASONING"
                  note={readiness.llm.endpoint_host ?? undefined}
                />
                <MetricValue
                  label="LLM model"
                  value={readiness.llm.model}
                  register="LLM_REASONING"
                  note={
                    inferenceChipStatus(readiness.llm) === "REAL_INFERENCE"
                      ? "real inference — the hypothesis agent will call this model"
                      : inferenceChipStatus(readiness.llm) === "NOT_CONFIGURED"
                        ? "provider is not configured — production will not mock a hypothesis"
                        : "hypothesis agent will be mocked"
                  }
                />
              </div>
              {absent.length > 0 && (
                <EmptyState
                  state="NO_DATA"
                  body={`${absent.length} artifact${absent.length === 1 ? " is" : "s are"} absent, so some surfaces cannot be inspected.`}
                  detail={absent.map((a) => `${a.artifact} — ${a.path}`).join(" · ")}
                />
              )}
            </>
          )}
        </div>
      </Panel>
    </>
  );
}
