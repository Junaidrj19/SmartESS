import Link from "next/link";
import { ErrorState } from "@/components/ErrorState";
import { EmptyState } from "@/components/EmptyState";
import { MonoId } from "@/components/MonoId";
import { Panel, SectionHeader } from "@/components/Panel";
import { StatusChip } from "@/components/StatusChip";
import { WorkflowStrip } from "@/components/NextAction";
import { LaunchForm } from "@/app/investigations/new/LaunchForm";
import { getModule, getReadiness, listModels } from "@/lib/api/endpoints";

export const metadata = { title: "Start Investigation — SmartESS" };

/**
 * Start Investigation — configuration and review (UX.md §28).
 *
 * Every default shown here is read from the backend: the model comes from
 * `GET /models`, the dataset from the module's own M7 row, and the execution mode
 * from `GET /readiness`. Nothing is hard-coded.
 */
export default async function NewInvestigationPage({
  searchParams,
}: {
  searchParams: Promise<{ module_id?: string; model_id?: string }>;
}) {
  const { module_id: moduleId, model_id: requestedModel } = await searchParams;

  if (!moduleId) {
    return (
      <Panel>
        <SectionHeader
          level={1} title="Start Investigation" />
        <div className="p-[var(--ss-space-4)]">
          <EmptyState
            state="NO_DATA"
            body="No module was selected. Choose a module first — an investigation is always scoped to one module."
            detail="expected query parameter: ?module_id=<module_id>"
          >
            <Link
              href="/modules"
              className="ss-field-label w-fit border border-[var(--ss-border-strong)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] hover:border-[var(--ss-accent)]"
              style={{ borderRadius: "var(--ss-radius-sm)" }}
            >
              Open Module Explorer
            </Link>
          </EmptyState>
        </div>
      </Panel>
    );
  }

  const [moduleResult, modelsResult, readinessResult] = await Promise.all([
    getModule(moduleId, requestedModel),
    listModels(),
    getReadiness(requestedModel),
  ]);

  if (moduleResult.kind !== "ok") {
    return (
      <Panel>
        <SectionHeader
          level={1} title="Start Investigation" />
        <div className="p-[var(--ss-space-4)]">
          <ErrorState result={moduleResult} />
        </div>
      </Panel>
    );
  }

  const detail = moduleResult.data;
  const modelId = detail.model_id;
  const datasetId = detail.module_summary.dataset_id ?? "";
  const models = modelsResult.kind === "ok" ? modelsResult.data : [];
  const llm =
    readinessResult.kind === "ok"
      ? readinessResult.data.llm
      : { provider: null, model: null, endpoint_host: null, configured: false };

  const existing = detail.investigations;

  return (
    <>
      <Panel>
        <SectionHeader
          level={1}
          title="Start Investigation"
          subtitle="Review the configuration before anything runs. The investigation reads frozen artifacts and writes one new record; no M1–M9 artifact is modified."
        />
        <div className="flex flex-col gap-[var(--ss-space-4)] p-[var(--ss-space-4)]">
          <WorkflowStrip
            current="Start Investigation"
            steps={[
              { label: "Module", href: `/modules/${moduleId}` },
              { label: "Signals", href: `/modules/${moduleId}/signals` },
              { label: "M7 Anomaly", href: `/modules/${moduleId}/anomaly` },
              { label: "M8 Evaluation", href: `/modules/${moduleId}/evaluation` },
              { label: "Start Investigation" },
            ]}
          />

          <LaunchForm
            moduleId={moduleId}
            modelId={modelId}
            datasetId={datasetId}
            defaultMaxEvidence={5}
            llm={llm}
          />
        </div>
      </Panel>

      {/* ── existing investigations for this module ─────────────────── */}
      <Panel>
        <SectionHeader
          title="Existing investigations for this module"
          subtitle="Each run creates a new record. Open an existing one instead of re-running if it already answers the question."
          level={3}
        />
        <div className="p-[var(--ss-space-4)]">
          {existing.length === 0 ? (
            <span className="text-[var(--ss-text-muted)]">
              No investigation has been recorded for this module.
            </span>
          ) : (
            <ul className="flex flex-col gap-[var(--ss-space-1)]">
              {existing
                .slice()
                .reverse()
                .slice(0, 12)
                .map((i) => (
                  <li
                    key={i.investigation_id}
                    className="flex flex-wrap items-center gap-[var(--ss-space-3)] border border-[var(--ss-border-subtle)] p-[var(--ss-space-2)]"
                    style={{ borderRadius: "var(--ss-radius-sm)" }}
                  >
                    <Link
                      href={`/investigations/${i.investigation_id}`}
                      className="ss-mono text-[var(--ss-accent)] hover:text-[var(--ss-accent-hover)]"
                    >
                      {i.investigation_id}
                    </Link>
                    <StatusChip status={i.status} />
                    <span className="ss-mono text-[var(--ss-text-muted)]">{i.created_at}</span>
                  </li>
                ))}
            </ul>
          )}
          {existing.length > 12 && (
            <p
              className="mt-[var(--ss-space-2)] text-[var(--ss-text-muted)]"
              style={{ fontSize: "var(--ss-text-label-size)" }}
            >
              Showing the 12 most recent of {existing.length}.{" "}
              <Link href="/history" className="text-[var(--ss-accent)]">
                Full history
              </Link>
            </p>
          )}
        </div>
      </Panel>

      {/* ── model identity ──────────────────────────────────────────── */}
      <Panel>
        <SectionHeader title="Detector that will be used" level={3} />
        <div className="p-[var(--ss-space-4)]">
          {models.length === 0 ? (
            <ErrorState result={modelsResult} />
          ) : (
            <dl className="grid grid-cols-2 gap-[var(--ss-space-3)] lg:grid-cols-4">
              {models
                .filter((m) => m.model_id === modelId)
                .map((m) => (
                  <>
                    <Field label="model_id" key="mid">
                      <MonoId value={m.model_id} />
                    </Field>
                    <Field label="algorithm" key="alg">
                      <MonoId value={m.algorithm} />
                    </Field>
                    <Field label="detector_version" key="dv">
                      <MonoId value={m.detector_version} />
                    </Field>
                    <Field label="feature_version" key="fv">
                      <MonoId value={m.feature_version} />
                    </Field>
                  </>
                ))}
            </dl>
          )}
        </div>
      </Panel>
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-[var(--ss-space-1)]">
      <dt className="ss-field-label">{label}</dt>
      <dd className="m-0">{children}</dd>
    </div>
  );
}
