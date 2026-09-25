import Link from "next/link";
import { MonoId } from "@/components/MonoId";
import { RegisterBadge } from "@/components/RegisterValue";
import type { EvidenceRecord as EvidenceRecordData } from "@/lib/types/backend";

/**
 * EvidenceRecord — a retrieved knowledge-base passage (UX.md §16; design.md §12.3).
 *
 * Provenance is mandatory: `backend/knowledge/models.py` states that a record
 * which cannot name its `document_id`, `citation` and `url` is not
 * provenance-preserving. Missing fields are NAMED, never hidden.
 *
 * `retrieval_metadata.distance` is a raw vector distance where LOWER IS CLOSER.
 * It is never rendered as a percentage, bar or star rating (design.md §19.1).
 * `confidence` defaults to 0.5 and is not set by the retriever, so it is not
 * presented as a computed strength.
 */
export function EvidenceRecord({
  record,
  missingProvenance = [],
  citedBy = [],
  investigationId,
}: {
  record: EvidenceRecordData;
  missingProvenance?: readonly string[];
  citedBy?: readonly { candidateId: string; mechanism: string; relation: "supporting" | "contradictory" }[];
  investigationId?: string;
}) {
  const distance = record.retrieval_metadata["distance"];
  const pages =
    record.page_start !== null && record.page_start !== undefined
      ? `${record.page_start}–${record.page_end ?? record.page_start}`
      : null;

  return (
    <article
      className="flex flex-col gap-[var(--ss-space-3)] border border-[var(--ss-border-subtle)] border-l-2 p-[var(--ss-space-3)]"
      style={{
        borderLeftColor: "var(--ss-reg-evidence-rule)",
        backgroundColor: "var(--ss-reg-evidence-surface)",
        borderRadius: "var(--ss-radius-sm)",
      }}
      id={`evidence-${record.evidence_id}`}
      data-evidence-id={record.evidence_id}
    >
      <header className="flex flex-wrap items-start justify-between gap-[var(--ss-space-2)]">
        <div className="flex flex-col gap-[var(--ss-space-1)]">
          <MonoId value={record.evidence_id} />
          <span className="text-[var(--ss-text-primary)]">{record.title}</span>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-[var(--ss-space-1)]">
          <RegisterBadge register="RETRIEVED_EVIDENCE" />
          <span className="ss-field-label">{record.source_type}</span>
        </div>
      </header>

      {/* The passage itself, in quotation treatment. */}
      <blockquote
        className="border-l border-[var(--ss-reg-evidence-rule)] pl-[var(--ss-space-3)] text-[var(--ss-text-secondary)]"
        style={{ maxWidth: "var(--ss-measure-prose)" }}
      >
        {record.retrieved_text}
      </blockquote>

      {/* Provenance chain. */}
      <dl className="grid grid-cols-1 gap-[var(--ss-space-2)] sm:grid-cols-2">
        <Field label="Document">
          <MonoId value={record.document_id} />
        </Field>
        <Field label="Chunk">
          <MonoId value={record.chunk_id} />
        </Field>
        <Field label="Pages">
          {pages ? <span className="ss-mono">{pages}</span> : <NotRecorded />}
        </Field>
        <Field label="Vector distance (lower = closer)">
          {distance ? <span className="ss-mono">{distance}</span> : <NotRecorded />}
        </Field>
      </dl>

      {record.citation && (
        <footer className="border-t border-[var(--ss-border-subtle)] pt-[var(--ss-space-2)]">
          <span className="ss-field-label">Citation</span>
          <p className="text-[var(--ss-text-secondary)]" style={{ maxWidth: "var(--ss-measure-prose)" }}>
            {record.citation}
          </p>
          {record.url && (
            <a
              href={record.url}
              target="_blank"
              rel="noreferrer noopener"
              className="ss-mono break-all text-[var(--ss-accent)] hover:text-[var(--ss-accent-hover)]"
            >
              {record.url}
            </a>
          )}
        </footer>
      )}

      {/* Declared axes — independent, never one-to-one mappings. */}
      <div className="flex flex-col gap-[var(--ss-space-1)]">
        <Axis label="Mechanisms" values={record.mechanisms} />
        <Axis label="Observables" values={record.observables} />
        <Axis label="Test conditions" values={record.test_conditions} />
      </div>

      {missingProvenance.length > 0 && (
        <p
          className="border border-dashed border-[var(--ss-state-attention-strong)] p-[var(--ss-space-2)] text-[var(--ss-state-attention-strong)]"
          style={{ borderRadius: "var(--ss-radius-sm)" }}
        >
          UNRESOLVED PROVENANCE — missing:{" "}
          <span className="ss-mono">{missingProvenance.join(", ")}</span>
        </p>
      )}

      {citedBy.length > 0 && (
        <div className="flex flex-col gap-[var(--ss-space-1)] border-t border-[var(--ss-border-subtle)] pt-[var(--ss-space-2)]">
          <span className="ss-field-label">Cited by</span>
          <ul className="flex flex-col gap-[var(--ss-space-1)]">
            {citedBy.map((c) => (
              <li key={`${c.candidateId}-${c.relation}`} className="flex items-center gap-[var(--ss-space-2)]">
                <span
                  className="ss-field-label"
                  style={{
                    color:
                      c.relation === "supporting"
                        ? "var(--ss-state-pass)"
                        : "var(--ss-state-reject)",
                  }}
                >
                  {c.relation.toUpperCase()}
                </span>
                {investigationId ? (
                  <Link
                    href={`/investigations/${investigationId}/hypotheses#${c.candidateId}`}
                    className="ss-mono text-[var(--ss-accent)] hover:text-[var(--ss-accent-hover)]"
                  >
                    {c.candidateId}
                  </Link>
                ) : (
                  <MonoId value={c.candidateId} />
                )}
                <span className="ss-mono text-[var(--ss-text-muted)]">{c.mechanism}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-[var(--ss-space-1)]">
      <dt className="ss-field-label">{label}</dt>
      <dd className="m-0 text-[var(--ss-text-secondary)]">{children}</dd>
    </div>
  );
}

function Axis({ label, values }: { label: string; values: readonly string[] }) {
  return (
    <div className="flex flex-wrap items-baseline gap-[var(--ss-space-2)]">
      <span className="ss-field-label shrink-0 w-[124px]">{label}</span>
      {values.length === 0 ? (
        <NotRecorded />
      ) : (
        <span className="ss-mono text-[var(--ss-text-secondary)]">{values.join(", ")}</span>
      )}
    </div>
  );
}

function NotRecorded() {
  return <span className="italic text-[var(--ss-text-muted)]">not recorded</span>;
}
