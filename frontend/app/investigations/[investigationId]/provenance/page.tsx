import { notFound } from "next/navigation";
import { AccessibleDataTable } from "@/components/AccessibleDataTable";
import { EmptyState } from "@/components/EmptyState";
import { MonoId } from "@/components/MonoId";
import { Panel, SectionHeader } from "@/components/Panel";
import { RegisterBadge } from "@/components/RegisterValue";
import { ReproducibilityBlock } from "@/components/ReproducibilityBlock";
import { getInvestigation, getInvestigationProvenance } from "@/lib/api/endpoints";
import { provenanceComplete } from "@/lib/investigation";

/**
 * Provenance Inspector (UX.md §20; design.md §12).
 *
 * Provenance is a first-class surface, not a developer debug screen. The ordered
 * trace is rendered WITH repeats, because a second `evidence_agent` entry means
 * the graph genuinely looped back (design.md §12.2).
 */
export default async function ProvenancePage({
  params,
}: {
  params: Promise<{ investigationId: string }>;
}) {
  const { investigationId } = await params;
  const result = await getInvestigation(investigationId);
  if (result.kind !== "ok") notFound();
  const record = result.data;

  const ev = provenanceComplete(record);
  const bundleResult = await getInvestigationProvenance(investigationId);
  const bundle = bundleResult.kind === "ok" ? bundleResult.data : null;

  return (
    <>
      <Panel>
        <SectionHeader
          level={1}
          title="Provenance Inspector"
          subtitle="The recorded execution trace, in order, including retries. Every model result and hypothesis in this investigation is traceable through these steps."
          actions={<RegisterBadge register="VALIDATION" />}
        />
        <div className="p-[var(--ss-space-4)]">
          {record.provenance.length === 0 ? (
            <EmptyState state="NO_DATA" body="No provenance was recorded for this investigation." />
          ) : (
            <AccessibleDataTable
              caption="Ordered provenance entries for this investigation, including repeated steps."
              rows={record.provenance}
              rowKey={(p, i) => `${p.step}-${i}`}
              columns={[
                { key: "n", header: "#", render: (_p, ) => "", mono: true },
                { key: "step", header: "Step", render: (p) => <MonoId value={p.step} /> },
                { key: "source", header: "Source", render: (p) => <MonoId value={p.source} /> },
                {
                  key: "description",
                  header: "Description",
                  render: (p) => (
                    <span className="text-[var(--ss-text-secondary)]">{p.description}</span>
                  ),
                  mono: false,
                },
                { key: "timestamp", header: "Timestamp", render: (p) => p.timestamp },
              ]}
            />
          )}
        </div>
      </Panel>

      {/* ── the lineage chain ───────────────────────────────────────── */}
      <Panel>
        <SectionHeader
          title="Lineage chain"
          subtitle="How a claim in this investigation connects back to a source document."
          level={3}
        />
        <div className="p-[var(--ss-space-4)]">
          <ol className="flex flex-col gap-[var(--ss-space-1)]">
            {[
              ["Signal sample", "module_trajectory.signals[signal][i] ↔ cycle_numbers[i]", "DATA"],
              ["Deterministic result", "tool_name · input_summary.signal · output", "CALCULATION"],
              ["Evidence query", "evidence_queries[]", "RETRIEVED_EVIDENCE"],
              ["Evidence record", "evidence_id = chunk_id · document_id · citation · pages", "RETRIEVED_EVIDENCE"],
              ["Candidate mechanism", "candidate_id · supporting / contradictory evidence ids", "LLM_REASONING"],
              ["Validation gate", "hypothesis_validation → report_validation", "VALIDATION"],
              ["Report finding", "Finding.classification · Finding.evidence_ids", "CALCULATION"],
            ].map(([label, detail], i) => (
              <li
                key={label}
                className="flex flex-wrap items-baseline gap-[var(--ss-space-3)] border border-[var(--ss-border-subtle)] p-[var(--ss-space-2)]"
                style={{ borderRadius: "var(--ss-radius-sm)" }}
              >
                <span className="ss-mono shrink-0 text-[var(--ss-text-muted)]">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span className="ss-field-label w-[184px] shrink-0 text-[var(--ss-text-primary)]">
                  {label}
                </span>
                <span className="ss-mono text-[var(--ss-text-secondary)]">{detail}</span>
              </li>
            ))}
          </ol>
          <p
            className="mt-[var(--ss-space-3)] text-[var(--ss-text-muted)]"
            style={{ fontSize: "var(--ss-text-label-size)" }}
          >
            The deterministic-result → evidence-query link is the one hop the backend
            does not record: queries are stored as a flat list with no back-reference
            to the finding that motivated them (design.md §9.2).
          </p>
        </div>
      </Panel>

      {/* ── evidence provenance completeness ───────────────────────── */}
      <Panel>
        <SectionHeader
          title="Evidence provenance completeness"
          subtitle="A record that cannot name its document_id, citation and url is not provenance-preserving."
          level={3}
        />
        <div className="p-[var(--ss-space-4)]">
          {ev.total === 0 ? (
            <EmptyState state="NO_EVIDENCE" />
          ) : (
            <AccessibleDataTable
              caption="Provenance completeness per retrieved evidence record."
              rows={record.evidence_records}
              rowKey={(e) => e.evidence_id}
              columns={[
                { key: "id", header: "Evidence id", render: (e) => <MonoId value={e.evidence_id} /> },
                { key: "doc", header: "Document", render: (e) => <MonoId value={e.document_id} /> },
                {
                  key: "pages",
                  header: "Pages",
                  render: (e) =>
                    e.page_start !== null && e.page_start !== undefined
                      ? `${e.page_start}–${e.page_end ?? e.page_start}`
                      : "—",
                },
                {
                  key: "status",
                  header: "Provenance",
                  render: (e) => {
                    const gaps = ev.missingByRecord.get(e.evidence_id);
                    return gaps ? (
                      <span style={{ color: "var(--ss-state-attention-strong)" }}>
                        missing: {gaps.join(", ")}
                      </span>
                    ) : (
                      <span style={{ color: "var(--ss-state-pass)" }}>complete</span>
                    );
                  },
                  mono: false,
                },
              ]}
            />
          )}
        </div>
      </Panel>

      {/* ── reproducibility ─────────────────────────────────────────── */}
      <Panel>
        <SectionHeader
          title="Reproducibility"
          subtitle="Deterministic findings and evidence queries reproduce on a re-run. LLM reasoning may not: temperature is 0.1, not 0."
          level={3}
        />
        <ReproducibilityBlock record={record} />
      </Panel>

      {/* ── frozen artifact identity ────────────────────────────────── */}
      <Panel>
        <SectionHeader
          title="Frozen artifact identity"
          subtitle="SHA-256 prefixes of the six M7/M8 artifacts this investigation reads."
          level={3}
        />
        <div className="flex flex-col gap-[var(--ss-space-3)] p-[var(--ss-space-4)]">
          {!bundle ? (
            <EmptyState
              state="SYSTEM_ERROR"
              body="Artifact identity could not be read."
            />
          ) : Object.keys(bundle.artifact_hashes_current).length === 0 ? (
            <EmptyState
              state="NO_DATA"
              body="No M7/M8 artifact is present for this model in this environment."
            />
          ) : (
            <>
              <AccessibleDataTable
                caption="Current SHA-256 prefix for each frozen M7/M8 artifact."
                rows={Object.entries(bundle.artifact_hashes_current)}
                rowKey={([path]) => path}
                columns={[
                  { key: "hash", header: "sha256 (16)", render: ([, h]) => h },
                  { key: "path", header: "artifact", render: ([path]) => path },
                ]}
              />
              <p
                className="text-[var(--ss-text-muted)]"
                style={{
                  fontSize: "var(--ss-text-label-size)",
                  maxWidth: "var(--ss-measure-prose)",
                }}
              >
                {bundle.artifact_hashes_note} A mismatch against the run-time state
                therefore cannot be detected from the record alone.
              </p>
            </>
          )}
        </div>
      </Panel>
    </>
  );
}
