"use client";

import { useActionState } from "react";
import { useFormStatus } from "react-dom";
import { MonoId } from "@/components/MonoId";
import { StatusChip } from "@/components/StatusChip";
import { inferenceChipStatus } from "@/lib/copy/status";
import { launchInvestigation, type LaunchState } from "@/app/investigations/new/actions";

/**
 * LaunchForm — configuration review then explicit run (UX.md §28; design.md §8.2).
 *
 * Two deliberate properties:
 *
 *  1. The configuration is REVIEWED before it is submitted. The engineer sees the
 *     module, model, dataset, evidence limit and — critically — whether inference
 *     will be real or mocked, before anything runs.
 *  2. No progress is simulated. `POST /investigations` is synchronous, so the
 *     pending state says exactly that: the request is open and stages will appear
 *     on completion (design.md §6.3, §21).
 */
export function LaunchForm({
  moduleId,
  modelId,
  datasetId,
  defaultMaxEvidence,
  llm,
}: {
  moduleId: string;
  modelId: string;
  datasetId: string;
  defaultMaxEvidence: number;
  llm: {
    provider: string | null;
    model: string | null;
    endpoint_host: string | null;
    configured: boolean;
    inference?: string | null;
  };
}) {
  const [state, action] = useActionState<LaunchState, FormData>(launchInvestigation, {
    status: "idle",
  });

  return (
    <form action={action} className="flex flex-col gap-[var(--ss-space-4)]">
      <input type="hidden" name="module_id" value={moduleId} />
      <input type="hidden" name="model_id" value={modelId} />
      <input type="hidden" name="dataset_id" value={datasetId} />

      {/* ── configuration review ─────────────────────────────────────── */}
      <dl className="grid grid-cols-1 gap-[var(--ss-space-3)] sm:grid-cols-2">
        <Row label="Module">
          <MonoId value={moduleId} />
        </Row>
        <Row label="Model">
          <MonoId value={modelId} />
        </Row>
        <Row label="Dataset">
          <MonoId value={datasetId} />
        </Row>
        <Row label="Data origin">
          <span className="ss-mono">SYNTHETIC</span>
        </Row>
      </dl>

      <div className="flex flex-col gap-[var(--ss-space-1)]">
        <label htmlFor="max_evidence" className="ss-field-label">
          Evidence limit (max_evidence)
        </label>
        <input
          id="max_evidence"
          name="max_evidence"
          type="number"
          min={1}
          max={50}
          defaultValue={defaultMaxEvidence}
          className="ss-mono w-[120px] border border-[var(--ss-border-strong)] bg-[var(--ss-bg-inset)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] text-[var(--ss-text-primary)]"
          style={{ borderRadius: "var(--ss-radius-sm)" }}
        />
        <span
          className="text-[var(--ss-text-muted)]"
          style={{ fontSize: "var(--ss-text-label-size)" }}
        >
          Caps how many evidence records the retrieval stage keeps. It also bounds how
          many of the generated queries actually execute.
        </span>
      </div>

      {/* ── execution mode: the honesty-critical disclosure ──────────── */}
      <div
        className={`flex flex-col gap-[var(--ss-space-2)] border p-[var(--ss-space-3)] ${
          llm.configured ? "" : "ss-hatch"
        }`}
        style={{
          borderRadius: "var(--ss-radius-sm)",
          borderColor: llm.configured
            ? "var(--ss-border-strong)"
            : "var(--ss-state-attention-strong)",
          borderStyle: llm.configured ? "solid" : "dashed",
        }}
      >
        <div className="flex flex-wrap items-center gap-[var(--ss-space-2)]">
          <span className="ss-field-label">Execution mode</span>
          <StatusChip status={inferenceChipStatus(llm)} />
        </div>
        <dl className="grid grid-cols-1 gap-[var(--ss-space-2)] sm:grid-cols-3">
          <Row label="LLM provider">
            <MonoId value={llm.provider} />
          </Row>
          <Row label="LLM model">
            <MonoId value={llm.model} />
          </Row>
          <Row label="Endpoint host">
            <MonoId value={llm.endpoint_host} />
          </Row>
        </dl>
        <p
          className="text-[var(--ss-text-secondary)]"
          style={{ maxWidth: "var(--ss-measure-prose)" }}
        >
          {llm.configured
            ? "A real inference request will be sent to the configured provider. This consumes provider quota and may take several minutes."
            : "No LLM provider is configured, so the hypothesis agent will use a mock client and produce no model-generated reasoning. The deterministic and evidence stages still run."}
        </p>
      </div>

      {/* ── what will happen ─────────────────────────────────────────── */}
      <div
        className="flex flex-col gap-[var(--ss-space-1)] border border-[var(--ss-border-subtle)] p-[var(--ss-space-3)]"
        style={{ borderRadius: "var(--ss-radius-sm)" }}
      >
        <span className="ss-field-label">What this will do</span>
        <ol className="flex flex-col gap-[var(--ss-space-1)] text-[var(--ss-text-secondary)]">
          <li>1. Load the frozen M6/M7/M8 artifacts for this module, read-only.</li>
          <li>2. Run the deterministic engineering tools over the signal trajectory.</li>
          <li>3. Build retrieval queries and search the reliability knowledge base.</li>
          <li>4. Ask the language model for competing candidate mechanisms.</li>
          <li>5. Validate every cited evidence id, with bounded retries.</li>
          <li>6. Synthesise the 15-section report and validate it.</li>
          <li>
            7. Write a new investigation record under{" "}
            <span className="ss-mono">ml/datasets/investigations/</span>.
          </li>
        </ol>
        <span
          className="text-[var(--ss-text-muted)]"
          style={{ fontSize: "var(--ss-text-label-size)" }}
        >
          No M1–M9 artifact is modified. The request is synchronous: the page will wait
          until the pipeline finishes, then open the resulting investigation.
        </span>
      </div>

      {state.status === "error" && (
        <div
          className="flex flex-col gap-[var(--ss-space-1)] border p-[var(--ss-space-3)]"
          style={{
            borderColor: "var(--ss-state-reject)",
            borderRadius: "var(--ss-radius-sm)",
          }}
          role="alert"
        >
          <span className="ss-field-label" style={{ color: "var(--ss-state-reject)" }}>
            INVESTIGATION NOT STARTED
          </span>
          <p className="text-[var(--ss-text-secondary)]">{state.message}</p>
          {state.detail && (
            <code className="ss-mono break-all text-[var(--ss-text-muted)]">
              {state.detail}
            </code>
          )}
        </div>
      )}

      <SubmitRow configured={llm.configured} />
    </form>
  );
}

function SubmitRow({ configured }: { configured: boolean }) {
  const { pending } = useFormStatus();
  return (
    <div className="flex flex-col gap-[var(--ss-space-2)]">
      <button
        type="submit"
        disabled={pending}
        className="ss-field-label w-fit border px-[var(--ss-space-4)] py-[var(--ss-space-2)] disabled:opacity-60"
        style={{
          borderRadius: "var(--ss-radius-sm)",
          borderColor: "var(--ss-accent)",
          color: pending ? "var(--ss-text-muted)" : "var(--ss-text-primary)",
          backgroundColor: pending ? "transparent" : "var(--ss-accent-muted)",
        }}
      >
        {pending ? "Investigation running…" : "Run Investigation"}
      </button>
      {pending && (
        <p
          className="text-[var(--ss-text-secondary)]"
          style={{ maxWidth: "var(--ss-measure-prose)" }}
          aria-live="polite"
        >
          The request is open. Execution is synchronous and no per-stage progress is
          reported by the backend, so the pipeline trace becomes available when the run
          completes.{" "}
          {configured
            ? "A real inference run can take several minutes."
            : "A mocked run is fast."}{" "}
          Do not reload this page.
        </p>
      )}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-[var(--ss-space-1)]">
      <dt className="ss-field-label">{label}</dt>
      <dd className="m-0 text-[var(--ss-text-primary)]">{children}</dd>
    </div>
  );
}
