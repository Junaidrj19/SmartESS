import { notFound } from "next/navigation";
import { EmptyState } from "@/components/EmptyState";
import { FindingBlock } from "@/components/FindingBlock";
import { GateResult } from "@/components/GateResult";
import { MetricValue } from "@/components/MetricValue";
import { NextAction } from "@/components/NextAction";
import { Panel, SectionHeader } from "@/components/Panel";
import { getInvestigation, getInvestigationReport } from "@/lib/api/endpoints";
import { gateOutcome, missingReportSections, resolveEvidence } from "@/lib/investigation";

/**
 * Engineering Report (UX.md §18, §19).
 *
 * The report is presented as an engineering document, not a chat response. Each
 * finding carries its own classification, and evidence ids are traceable links.
 *
 * Human Review is rendered as an explicit awaiting state: the backend stores no
 * engineer verdict anywhere (design.md §20.6), so nothing is pre-filled.
 */
export default async function ReportPage({
  params,
}: {
  params: Promise<{ investigationId: string }>;
}) {
  const { investigationId } = await params;
  const [recordResult, reportResult] = await Promise.all([
    getInvestigation(investigationId),
    getInvestigationReport(investigationId),
  ]);
  if (recordResult.kind !== "ok") notFound();
  const record = recordResult.data;

  const report = reportResult.kind === "ok" ? reportResult.data : record.report;
  const gate = gateOutcome(record, "report_validation");

  if (!report) {
    return (
      <Panel>
        <SectionHeader
          level={1} title="Engineering Report" />
        <div className="flex flex-col gap-[var(--ss-space-3)] p-[var(--ss-space-4)]">
          <EmptyState
            state="NO_DATA"
            body="No report was produced for this investigation."
            detail={Object.entries(record.errors)
              .map(([k, v]) => `${k}: ${v}`)
              .join(" | ")}
          />
        </div>
      </Panel>
    );
  }

  const missing = missingReportSections(report.sections);
  const allEvidenceIds = report.sections.flatMap((s) =>
    s.findings.flatMap((f) => f.evidence_ids),
  );
  const unresolved = [
    ...new Set(allEvidenceIds.filter((id) => resolveEvidence(record, id) === null)),
  ];

  const findingCount = report.sections.reduce((n, s) => n + s.findings.length, 0);
  const byClassification = report.sections
    .flatMap((s) => s.findings)
    .reduce<Record<string, number>>((acc, f) => {
      acc[f.classification] = (acc[f.classification] ?? 0) + 1;
      return acc;
    }, {});

  return (
    <>
      <Panel>
        <SectionHeader
          level={1}
          title="Engineering Report"
          subtitle="Composed deterministically from the investigation state. Every finding declares whether it is observed, calculated, hypothesised or recommended."
        />
        <div className="flex flex-col gap-[var(--ss-space-3)] p-[var(--ss-space-4)]">
          <div className="grid grid-cols-2 gap-[var(--ss-space-4)] lg:grid-cols-4">
            <MetricValue label="Sections" value={report.sections.length} register="CALCULATION" note="15 required" />
            <MetricValue label="Findings" value={findingCount} register="CALCULATION" />
            <MetricValue label="Unresolved citations" value={unresolved.length} register="VALIDATION" />
            <MetricValue label="Generated at" value={report.generated_at} register="DATA" />
          </div>

          <div className="flex flex-wrap items-center gap-[var(--ss-space-2)]">
            <span className="ss-field-label">Findings by classification</span>
            {Object.entries(byClassification).map(([k, n]) => (
              <span
                key={k}
                className="ss-field-label border border-[var(--ss-border-subtle)] px-[var(--ss-space-1)] text-[var(--ss-text-secondary)]"
                style={{ borderRadius: "var(--ss-radius-sm)" }}
              >
                {k} · {n}
              </span>
            ))}
            {byClassification["CONFIRMED"] === undefined && (
              <span className="ss-field-label text-[var(--ss-text-muted)]">
                CONFIRMED · 0 — the report gate rejects any confirmed mechanism
              </span>
            )}
          </div>

          {missing.length > 0 && (
            <EmptyState
              state="VALIDATION_REJECTED"
              body="Required report sections are missing."
              detail={missing.join(", ")}
            />
          )}
        </div>
      </Panel>

      {/* ── the gate ────────────────────────────────────────────────── */}
      <Panel>
        <SectionHeader title="Report validation" level={3} />
        <div className="p-[var(--ss-space-4)]">
          <GateResult outcome={gate} retryCounts={record.retry_counts} />
        </div>
      </Panel>

      {/* ── section navigator ──────────────────────────────────────── */}
      <Panel>
        <SectionHeader title="Sections" level={3} />
        <nav className="flex flex-wrap gap-[var(--ss-space-1)] p-[var(--ss-space-4)]" aria-label="Report sections">
          {report.sections.map((s) => (
            <a
              key={s.title}
              href={`#section-${encodeURIComponent(s.title)}`}
              className="ss-field-label border border-[var(--ss-border-subtle)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] text-[var(--ss-text-secondary)] hover:border-[var(--ss-accent)] hover:text-[var(--ss-text-primary)]"
              style={{ borderRadius: "var(--ss-radius-sm)" }}
            >
              {s.title}
            </a>
          ))}
        </nav>
      </Panel>

      {/* ── the report itself ──────────────────────────────────────── */}
      {report.sections.map((section) => {
        const isHumanReview = section.title === "Human Review";
        return (
          <Panel key={section.title}>
            <div id={`section-${encodeURIComponent(section.title)}`}>
              <SectionHeader
                title={section.title}
                subtitle={
                  isHumanReview
                    ? "The final engineering decision remains with the human engineer. SmartESS stores no verdict."
                    : undefined
                }
                level={3}
              />
            </div>
            <div className="flex flex-col gap-[var(--ss-space-3)] p-[var(--ss-space-4)]">
              {section.narrative && (
                <p
                  className="text-[var(--ss-text-secondary)]"
                  style={{ maxWidth: "var(--ss-measure-prose)" }}
                >
                  {section.narrative}
                </p>
              )}
              {section.findings.length === 0 ? (
                <span className="italic text-[var(--ss-text-muted)]">No findings recorded.</span>
              ) : (
                section.findings.map((f, i) => (
                  <FindingBlock
                    key={`${section.title}-${f.label}-${i}`}
                    finding={f}
                    investigationId={investigationId}
                    unresolvedIds={unresolved}
                  />
                ))
              )}
              {isHumanReview && (
                <div
                  className="flex flex-col gap-[var(--ss-space-1)] border border-dashed p-[var(--ss-space-3)]"
                  style={{
                    borderColor: "var(--ss-reg-human-border)",
                    borderRadius: "var(--ss-radius-sm)",
                  }}
                >
                  <span className="ss-field-label text-[var(--ss-text-muted)]">
                    AWAITING ENGINEER REVIEW
                  </span>
                  <p className="text-[var(--ss-text-muted)]" style={{ maxWidth: "var(--ss-measure-prose)" }}>
                    No engineer decision is recorded. SmartESS has no field for a
                    verdict, sign-off or review state, so this cannot be captured here
                    (design.md §20.6).
                  </p>
                </div>
              )}
            </div>
          </Panel>
        );
      })}

      {/* ── export ──────────────────────────────────────────────────── */}
      <Panel>
        <SectionHeader
          title="Export"
          subtitle="Both formats are produced by the backend. PDF generation is not implemented and is therefore not offered."
          level={3}
        />
        <div className="flex flex-wrap gap-[var(--ss-space-2)] p-[var(--ss-space-4)]">
          <a
            href={`/api/export/${investigationId}/report.json`}
            className="ss-field-label border border-[var(--ss-border-strong)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] text-[var(--ss-text-primary)] hover:border-[var(--ss-accent)]"
            style={{ borderRadius: "var(--ss-radius-sm)" }}
          >
            Export JSON
          </a>
          <a
            href={`/api/export/${investigationId}/report.md`}
            className="ss-field-label border border-[var(--ss-border-strong)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] text-[var(--ss-text-primary)] hover:border-[var(--ss-accent)]"
            style={{ borderRadius: "var(--ss-radius-sm)" }}
          >
            Export Markdown
          </a>
          <span className="ss-field-label text-[var(--ss-text-muted)]">
            PDF — NOT IMPLEMENTED
          </span>
        </div>
      </Panel>
      <NextAction
        href={`/investigations/${investigationId}/provenance`}
        label="Inspect Provenance"
        hint="trace a claim back to its source document"
      />
    </>
  );
}
