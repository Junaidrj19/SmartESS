import { notFound } from "next/navigation";
import { EmptyState } from "@/components/EmptyState";
import { EvidenceRecord } from "@/components/EvidenceRecord";
import { MetricValue } from "@/components/MetricValue";
import { NextAction } from "@/components/NextAction";
import { Panel, SectionHeader } from "@/components/Panel";
import { AccessibleDataTable } from "@/components/AccessibleDataTable";
import { getCorpus, getInvestigation } from "@/lib/api/endpoints";
import { candidatesCiting, provenanceComplete } from "@/lib/investigation";

/**
 * Evidence Explorer (UX.md §16).
 *
 * Every record shown is one the investigation actually retrieved. Nothing is
 * displayed that cannot be traced to the knowledge base, and provenance gaps are
 * named rather than hidden (design.md §12.3).
 */
export default async function EvidencePage({
  params,
}: {
  params: Promise<{ investigationId: string }>;
}) {
  const { investigationId } = await params;
  const result = await getInvestigation(investigationId);
  if (result.kind !== "ok") notFound();
  const record = result.data;

  const ev = provenanceComplete(record);
  const corpusResult = await getCorpus();
  const corpus = corpusResult.kind === "ok" ? corpusResult.data : null;
  const emptyKb = record.limitations.some((l) => l.startsWith("knowledge_base_empty"));

  return (
    <>
      <Panel>
        <SectionHeader
          level={1}
          title="Evidence Explorer"
          subtitle="Passages retrieved from the reliability knowledge base, with the provenance chain required to trace each one back to a real page of a real document."
        />
        <div className="grid grid-cols-2 gap-[var(--ss-space-4)] p-[var(--ss-space-4)] lg:grid-cols-4">
          <MetricValue
            label="Records retrieved"
            value={record.evidence_records.length}
            register="RETRIEVED_EVIDENCE"
          />
          <MetricValue
            label="Provenance complete"
            value={`${ev.complete}/${ev.total}`}
            register="RETRIEVED_EVIDENCE"
            note="document_id, chunk_id, citation, url, pages"
          />
          <MetricValue
            label="Distinct documents"
            value={new Set(record.evidence_records.map((e) => e.document_id).filter(Boolean)).size}
            register="RETRIEVED_EVIDENCE"
          />
          <MetricValue
            label="Queries generated"
            value={record.evidence_queries.length}
            register="RETRIEVED_EVIDENCE"
            note="max 8"
          />
        </div>
      </Panel>

      {/* ── the queries that drove retrieval ───────────────────────── */}
      {record.evidence_queries.length > 0 && (
        <Panel>
          <SectionHeader
            title="Retrieval queries"
            subtitle="Built from the deterministic findings by fixed lookup tables. The selection threshold decides which query to run and is never a diagnostic conclusion."
            level={3}
          />
          <div className="p-[var(--ss-space-4)]">
            <ol className="flex flex-col gap-[var(--ss-space-1)]">
              {record.evidence_queries.map((q, i) => (
                <li key={i} className="ss-mono text-[var(--ss-text-secondary)]">
                  {String(i + 1).padStart(2, "0")}. {q}
                </li>
              ))}
            </ol>
          </div>
        </Panel>
      )}

      {/* ── the records ─────────────────────────────────────────────── */}
      <Panel>
        <SectionHeader title="Evidence records" level={3} />
        <div className="flex flex-col gap-[var(--ss-space-4)] p-[var(--ss-space-4)]">
          {record.evidence_records.length === 0 ? (
            <EmptyState
              state={emptyKb ? "NO_EVIDENCE" : "NO_DATA"}
              body={
                emptyKb
                  ? undefined
                  : "No evidence records were retrieved for this investigation."
              }
              detail={
                emptyKb
                  ? "knowledge_base_empty — scripts/ingest_knowledge.py"
                  : undefined
              }
            >
              {emptyKb && (
                <p className="text-[var(--ss-state-attention)]">
                  Without evidence, any CANDIDATE, SUPPORTED or CONTRADICTED candidate
                  will be rejected by the hypothesis validation gate, which requires at
                  least one resolvable supporting id.
                </p>
              )}
            </EmptyState>
          ) : (
            record.evidence_records.map((e) => (
              <EvidenceRecord
                key={e.evidence_id}
                record={e}
                missingProvenance={ev.missingByRecord.get(e.evidence_id) ?? []}
                citedBy={candidatesCiting(record, e.evidence_id)}
                investigationId={investigationId}
              />
            ))
          )}
        </div>
      </Panel>

      {/* ── corpus context needs the endpoint ──────────────────────── */}
      <Panel>
        <SectionHeader
          title="Corpus context"
          subtitle="Document verification status and coverage gaps."
          level={3}
        />
        <div className="flex flex-col gap-[var(--ss-space-3)] p-[var(--ss-space-4)]">
          {!corpus ? (
            <EmptyState state="NO_DATA" body="The corpus manifest could not be read." />
          ) : (
            <>
              <AccessibleDataTable
                caption="Corpus documents cited by this investigation, with their verification status."
                rows={[...new Set(record.evidence_records.map((e) => e.document_id).filter(Boolean))].map(
                  (id) => {
                    const doc = corpus.documents.find((d) => d.document_id === id);
                    return {
                      document_id: String(id),
                      status: doc?.verification_status ?? "NOT IN MANIFEST",
                      source_type: doc?.source_type ?? "—",
                      title: doc?.title ?? "—",
                      url: doc?.url ?? null,
                    };
                  },
                )}
                rowKey={(r) => r.document_id}
                columns={[
                  { key: "doc", header: "document_id", render: (r) => r.document_id },
                  { key: "status", header: "verification_status", render: (r) => r.status },
                  { key: "type", header: "source_type", render: (r) => r.source_type },
                  { key: "title", header: "title", render: (r) => r.title, mono: false },
                ]}
              />
              <div className="grid grid-cols-2 gap-[var(--ss-space-4)] lg:grid-cols-4">
                <MetricValue label="corpus_version" value={corpus.corpus_version} register="DATA" />
                <MetricValue label="manifest documents" value={corpus.n_documents} register="DATA" />
                <MetricValue
                  label="VERIFIED"
                  value={corpus.counts_by_verification_status["VERIFIED"] ?? 0}
                  register="RETRIEVED_EVIDENCE"
                  note="production corpus"
                />
                <MetricValue
                  label="collection chunks"
                  value={corpus.collection.chunk_count}
                  register="RETRIEVED_EVIDENCE"
                />
              </div>
              <p
                className="text-[var(--ss-text-muted)]"
                style={{ fontSize: "var(--ss-text-label-size)", maxWidth: "var(--ss-measure-prose)" }}
              >
                {corpus.production_note} Coverage is incomplete: some candidate standards
                and papers are paywalled or publisher-blocked, so parts of the mechanism
                and test-condition space are not supported by this corpus.
              </p>
            </>
          )}
        </div>
      </Panel>
      <NextAction
        href={`/investigations/${investigationId}/hypotheses`}
        label="Compare Hypotheses"
        hint="competing candidate mechanisms bound to this evidence"
      />
    </>
  );
}
