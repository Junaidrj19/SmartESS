import { notFound } from "next/navigation";
import Link from "next/link";
import type { ReactNode } from "react";
import { ContextRail } from "@/components/ContextRail";
import { ErrorState } from "@/components/ErrorState";
import { StatusChip } from "@/components/StatusChip";
import { getModule } from "@/lib/api/endpoints";
import { asString } from "@/lib/investigation";

/**
 * Module layout — owns the persistent context rail for module-scoped routes.
 *
 * Mirrors the investigation layout: the rail is rendered outside the page content
 * so it survives navigation between context / signals / anomaly / evaluation and
 * is unaffected by a panel-level failure (UX.md §4, §31).
 *
 * Unlike the investigation rail, `feature_version` and `detector_version` ARE
 * available here, because `GET /modules/{id}` includes the model record.
 */

const TABS: readonly { href: string; label: string }[] = [
  { href: "", label: "Context" },
  { href: "/signals", label: "Signal Analysis" },
  { href: "/anomaly", label: "M7 Anomaly" },
  { href: "/evaluation", label: "M8 Evaluation" },
];

export default async function ModuleLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ moduleId: string }>;
}) {
  const { moduleId } = await params;
  const result = await getModule(moduleId);

  // A module that is genuinely not in the scored population is a 404, matching
  // the investigation layout. Transport failures keep their own error state so
  // "does not exist" is never confused with "could not be reached".
  if (result.kind === "not-found") notFound();

  if (result.kind !== "ok") {
    return (
      <div className="p-[var(--ss-space-4)]">
        <ErrorState result={result} />
      </div>
    );
  }

  const detail = result.data;
  const summary = detail.module_summary;
  const latest = detail.investigations.at(-1);

  return (
    <div className="flex min-h-full flex-col lg:h-full lg:flex-row lg:overflow-hidden">
      <ContextRail
        context={{
          moduleId: summary.module_id,
          testId: summary.test_id,
          lotId: summary.lot_id,
          datasetId: summary.dataset_id,
          dataOrigin: detail.data_origin.toUpperCase(),
          modelId: detail.model.model_id,
          featureVersion: detail.model.feature_version,
          detectorVersion: detail.model.detector_version,
          moduleStatus: asString(summary.module_anomaly_status),
          investigationId: latest?.investigation_id ?? null,
          investigationStatus: latest?.status ?? null,
        }}
      />

      <div className="flex min-w-0 flex-1 flex-col lg:overflow-y-auto">
        <nav
          className="flex flex-wrap items-center gap-[var(--ss-space-1)] border-b border-[var(--ss-border-subtle)] px-[var(--ss-space-4)] py-[var(--ss-space-3)] lg:px-[var(--ss-space-6)]"
          aria-label="Module"
        >
          {TABS.map((tab) => (
            <Link
              key={tab.label}
              href={`/modules/${moduleId}${tab.href}`}
              className="ss-field-label border border-[var(--ss-border-subtle)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] text-[var(--ss-text-secondary)] hover:border-[var(--ss-accent)] hover:text-[var(--ss-text-primary)]"
              style={{ borderRadius: "var(--ss-radius-sm)" }}
            >
              {tab.label}
            </Link>
          ))}
          <span className="ml-auto flex items-center gap-[var(--ss-space-2)]">
            <StatusChip status={asString(summary.module_anomaly_status)} />
            <Link
              href={`/investigations/new?module_id=${encodeURIComponent(moduleId)}`}
              className="ss-field-label border border-[var(--ss-accent)] px-[var(--ss-space-3)] py-[var(--ss-space-1)] text-[var(--ss-text-primary)]"
              style={{
                borderRadius: "var(--ss-radius-sm)",
                backgroundColor: "var(--ss-accent-muted)",
              }}
            >
              Start Investigation
            </Link>
          </span>
        </nav>

        <div className="flex flex-col gap-[var(--ss-space-4)] p-[var(--ss-space-4)] lg:p-[var(--ss-space-6)]">
          {children}
        </div>
      </div>
    </div>
  );
}
