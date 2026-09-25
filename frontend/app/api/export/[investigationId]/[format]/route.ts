import { getInvestigation, getInvestigationReport } from "@/lib/api/endpoints";

/**
 * Report export (UX.md §33; design.md §10.6).
 *
 * This route re-serves backend output as a download. It composes nothing and
 * reformats nothing except wrapping the already-Markdown `full_text` with a
 * provenance header.
 *
 * Supported: `report.json` (the InvestigationReport verbatim) and `report.md`
 * (`full_text`, which `_build_narrative` already emits as Markdown).
 * PDF is NOT supported: no generator exists in the backend (design.md §10.6).
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ investigationId: string; format: string }> },
) {
  const { investigationId, format } = await params;

  const [recordResult, reportResult] = await Promise.all([
    getInvestigation(investigationId),
    getInvestigationReport(investigationId),
  ]);

  if (reportResult.kind === "not-found" || recordResult.kind === "not-found") {
    return new Response("Investigation not found", { status: 404 });
  }
  if (reportResult.kind !== "ok" || recordResult.kind !== "ok") {
    const detail =
      reportResult.kind !== "ok" && "detail" in reportResult
        ? reportResult.detail
        : "upstream API unavailable";
    return new Response(`Export unavailable: ${detail}`, { status: 502 });
  }

  const report = reportResult.data;
  const record = recordResult.data;

  if (!report) {
    return new Response("No report was produced for this investigation", { status: 404 });
  }

  if (format === "report.json") {
    return new Response(JSON.stringify(report, null, 2), {
      headers: {
        "content-type": "application/json; charset=utf-8",
        "content-disposition": `attachment; filename="${investigationId}-report.json"`,
      },
    });
  }

  if (format === "report.md") {
    // Provenance and the synthetic label must survive export (design.md §10.6).
    const header = [
      `# SmartESS Engineering Report`,
      ``,
      `- investigation_id: \`${report.investigation_id}\``,
      `- module_id: \`${report.module_id}\``,
      `- model_id: \`${report.model_id}\``,
      `- dataset_id: \`${record.dataset_id}\``,
      `- created_at: \`${record.created_at}\``,
      `- generated_at: \`${report.generated_at}\``,
      `- status: \`${record.status}\``,
      `- data_origin: \`SYNTHETIC\` — development dataset, not production telemetry`,
      ``,
      `## Provenance`,
      ``,
      ...record.provenance.map(
        (p) => `- \`${p.step}\` · ${p.source} · ${p.timestamp} — ${p.description}`,
      ),
      ``,
      ...(Object.keys(record.errors).length > 0
        ? [
            `## Recorded validation issues`,
            ``,
            ...Object.entries(record.errors).map(([k, v]) => `- \`${k}\`: ${v}`),
            ``,
          ]
        : []),
      ...(record.limitations.length > 0
        ? [`## Limitations`, ``, ...record.limitations.map((l) => `- ${l}`), ``]
        : []),
      `---`,
      ``,
    ].join("\n");

    return new Response(`${header}${report.full_text}\n`, {
      headers: {
        "content-type": "text/markdown; charset=utf-8",
        "content-disposition": `attachment; filename="${investigationId}-report.md"`,
      },
    });
  }

  return new Response(
    `Unsupported export format: ${format}. Supported: report.json, report.md. PDF generation is not implemented in the backend.`,
    { status: 400 },
  );
}
