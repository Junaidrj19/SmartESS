import Link from "next/link";
import { AccessibleDataTable } from "@/components/AccessibleDataTable";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { MetricValue } from "@/components/MetricValue";
import { MonoId } from "@/components/MonoId";
import { Panel, SectionHeader } from "@/components/Panel";
import { StatusChip } from "@/components/StatusChip";
import { getModulePopulation, listModules } from "@/lib/api/endpoints";
import { ANOMALY_QUALIFICATION } from "@/lib/copy/states";
import { MODULE_ANOMALY_STATUS } from "@/lib/types/backend";

export const metadata = { title: "Module Explorer — SmartESS" };

const PAGE_SIZE = 50;

/**
 * Module Explorer (UX.md §5 module table).
 *
 * Every row is a real `module-summary.parquet` row served by `GET /modules`.
 * Filtering and pagination happen on the server; the client computes nothing.
 */
export default async function ModulesPage({
  searchParams,
}: {
  searchParams: Promise<{
    lot_id?: string;
    anomaly_status?: string;
    search?: string;
    offset?: string;
  }>;
}) {
  const sp = await searchParams;
  const offset = Number.parseInt(sp.offset ?? "0", 10) || 0;

  const [pageResult, populationResult] = await Promise.all([
    listModules({
      lot_id: sp.lot_id,
      anomaly_status: sp.anomaly_status,
      search: sp.search,
      limit: PAGE_SIZE,
      offset,
    }),
    getModulePopulation(),
  ]);

  if (pageResult.kind !== "ok") {
    return (
      <Panel>
        <SectionHeader
          level={1} title="Module Explorer" />
        <div className="p-[var(--ss-space-4)]">
          <ErrorState result={pageResult} />
        </div>
      </Panel>
    );
  }

  const page = pageResult.data;
  const population = populationResult.kind === "ok" ? populationResult.data : null;
  const lots = population ? Object.keys(population.by_lot).sort() : [];

  function href(next: Record<string, string | number | undefined>) {
    const params = new URLSearchParams();
    const merged = {
      lot_id: sp.lot_id,
      anomaly_status: sp.anomaly_status,
      search: sp.search,
      offset: offset || undefined,
      ...next,
    };
    for (const [k, v] of Object.entries(merged)) {
      if (v !== undefined && v !== "" && v !== 0) params.set(k, String(v));
    }
    const q = params.toString();
    return q ? `/modules?${q}` : "/modules";
  }

  return (
    <>
      {/* ── population context ───────────────────────────────────────── */}
      <Panel>
        <SectionHeader
          level={1}
          title="Module Explorer"
          subtitle={`${page.total} module${page.total === 1 ? "" : "s"} scored by this detector. ${ANOMALY_QUALIFICATION}`}
        />
        <div className="flex flex-col gap-[var(--ss-space-4)] p-[var(--ss-space-4)]">
          {population ? (
            <>
              <div className="grid grid-cols-2 gap-[var(--ss-space-4)] lg:grid-cols-4">
                <MetricValue label="Modules" value={population.n_modules} register="DATA" />
                {MODULE_ANOMALY_STATUS.map((s) => (
                  <MetricValue
                    key={s}
                    label={s}
                    value={population.by_anomaly_status[s] ?? 0}
                    register="CALCULATION"
                  />
                ))}
              </div>

              {/* lot × status, as a dense table rather than KPI tiles */}
              <AccessibleDataTable
                caption="Module count by lot and anomaly status."
                rows={lots}
                rowKey={(lot) => lot}
                columns={[
                  {
                    key: "lot",
                    header: "lot_id",
                    render: (lot) => (
                      <Link href={href({ lot_id: lot, offset: undefined })} className="text-[var(--ss-accent)]">
                        {lot}
                      </Link>
                    ),
                  },
                  {
                    key: "total",
                    header: "modules",
                    render: (lot) => population.by_lot[lot] ?? 0,
                  },
                  ...MODULE_ANOMALY_STATUS.map((s) => ({
                    key: s,
                    header: s,
                    render: (lot: string) => population.by_lot_and_status[lot]?.[s] ?? 0,
                  })),
                ]}
              />
            </>
          ) : (
            <ErrorState result={populationResult} />
          )}
        </div>
      </Panel>

      {/* ── filters ──────────────────────────────────────────────────── */}
      <Panel>
        <SectionHeader title="Filter" level={3} />
        <div className="flex flex-col gap-[var(--ss-space-3)] p-[var(--ss-space-4)]">
          <div className="flex flex-wrap items-center gap-[var(--ss-space-2)]">
            <span className="ss-field-label">Anomaly status</span>
            <Link
              href={href({ anomaly_status: undefined, offset: undefined })}
              className="ss-field-label border px-[var(--ss-space-2)] py-[var(--ss-space-1)]"
              style={{
                borderRadius: "var(--ss-radius-sm)",
                borderColor: sp.anomaly_status ? "var(--ss-border-subtle)" : "var(--ss-accent)",
                color: sp.anomaly_status ? "var(--ss-text-muted)" : "var(--ss-text-primary)",
              }}
            >
              ALL
            </Link>
            {MODULE_ANOMALY_STATUS.map((s) => (
              <Link key={s} href={href({ anomaly_status: s, offset: undefined })}>
                <StatusChip
                  status={s}
                  suffix={population ? String(population.by_anomaly_status[s] ?? 0) : undefined}
                />
              </Link>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-[var(--ss-space-2)]">
            <span className="ss-field-label">Lot</span>
            <Link
              href={href({ lot_id: undefined, offset: undefined })}
              className="ss-field-label border px-[var(--ss-space-2)] py-[var(--ss-space-1)]"
              style={{
                borderRadius: "var(--ss-radius-sm)",
                borderColor: sp.lot_id ? "var(--ss-border-subtle)" : "var(--ss-accent)",
                color: sp.lot_id ? "var(--ss-text-muted)" : "var(--ss-text-primary)",
              }}
            >
              ALL
            </Link>
            {lots.map((lot) => (
              <Link
                key={lot}
                href={href({ lot_id: lot, offset: undefined })}
                className="ss-mono border px-[var(--ss-space-2)] py-[var(--ss-space-1)]"
                style={{
                  borderRadius: "var(--ss-radius-sm)",
                  borderColor: sp.lot_id === lot ? "var(--ss-accent)" : "var(--ss-border-subtle)",
                  color: sp.lot_id === lot ? "var(--ss-text-primary)" : "var(--ss-text-secondary)",
                }}
              >
                {lot}
              </Link>
            ))}
          </div>

          <form action="/modules" method="get" className="flex flex-wrap items-end gap-[var(--ss-space-2)]">
            {sp.lot_id && <input type="hidden" name="lot_id" value={sp.lot_id} />}
            {sp.anomaly_status && (
              <input type="hidden" name="anomaly_status" value={sp.anomaly_status} />
            )}
            <div className="flex flex-col gap-[var(--ss-space-1)]">
              <label htmlFor="search" className="ss-field-label">
                Module id contains
              </label>
              <input
                id="search"
                name="search"
                defaultValue={sp.search ?? ""}
                placeholder="syn-mod-00"
                className="ss-mono border border-[var(--ss-border-strong)] bg-[var(--ss-bg-inset)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] text-[var(--ss-text-primary)]"
                style={{ borderRadius: "var(--ss-radius-sm)" }}
              />
            </div>
            <button
              type="submit"
              className="ss-field-label border border-[var(--ss-border-strong)] px-[var(--ss-space-3)] py-[var(--ss-space-1)] hover:border-[var(--ss-accent)]"
              style={{ borderRadius: "var(--ss-radius-sm)" }}
            >
              Select
            </button>
          </form>
        </div>
      </Panel>

      {/* ── the modules ──────────────────────────────────────────────── */}
      <Panel>
        <SectionHeader
          title="Modules"
          subtitle={`Showing ${page.returned} of ${page.total} matching, from offset ${page.offset}.`}
          level={3}
        />
        <div className="flex flex-col gap-[var(--ss-space-3)] p-[var(--ss-space-4)]">
          {page.items.length === 0 ? (
            <EmptyState
              state="NO_DATA"
              body="No module matches this filter."
              detail={`lot_id=${sp.lot_id ?? "any"} anomaly_status=${sp.anomaly_status ?? "any"} search=${sp.search ?? "none"}`}
            />
          ) : (
            <>
              <AccessibleDataTable
                caption="Scored modules with their M7 anomaly summary."
                rows={page.items}
                rowKey={(m) => m.module_id}
                columns={[
                  {
                    key: "module",
                    header: "module_id",
                    render: (m) => (
                      <Link
                        href={`/modules/${m.module_id}`}
                        className="text-[var(--ss-accent)] hover:text-[var(--ss-accent-hover)]"
                      >
                        {m.module_id}
                      </Link>
                    ),
                  },
                  { key: "lot", header: "lot_id", render: (m) => m.lot_id ?? "—" },
                  { key: "test", header: "test_id", render: (m) => m.test_id ?? "—" },
                  {
                    key: "status",
                    header: "anomaly status",
                    render: (m) => <StatusChip status={m.module_anomaly_status} />,
                    mono: false,
                  },
                  { key: "nobs", header: "n_obs", render: (m) => m.n_observations ?? "—", align: "right" },
                  {
                    key: "nflag",
                    header: "flagged",
                    render: (m) => m.n_anomalous_observations ?? "—",
                    align: "right",
                  },
                  {
                    key: "rate",
                    header: "anomaly_rate",
                    render: (m) => m.anomaly_rate ?? "—",
                    align: "right",
                  },
                  {
                    key: "max",
                    header: "max_anomaly_score",
                    render: (m) => m.max_anomaly_score ?? "—",
                    align: "right",
                  },
                  {
                    key: "base",
                    header: "statistical_baseline_max",
                    render: (m) => m.statistical_baseline_max ?? "—",
                    align: "right",
                  },
                ]}
              />

              <div className="flex items-center gap-[var(--ss-space-2)]">
                {offset > 0 && (
                  <Link
                    href={href({ offset: Math.max(0, offset - PAGE_SIZE) })}
                    className="ss-field-label border border-[var(--ss-border-strong)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] hover:border-[var(--ss-accent)]"
                    style={{ borderRadius: "var(--ss-radius-sm)" }}
                  >
                    ← Previous
                  </Link>
                )}
                {offset + PAGE_SIZE < page.total && (
                  <Link
                    href={href({ offset: offset + PAGE_SIZE })}
                    className="ss-field-label border border-[var(--ss-border-strong)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] hover:border-[var(--ss-accent)]"
                    style={{ borderRadius: "var(--ss-radius-sm)" }}
                  >
                    Next →
                  </Link>
                )}
                <span className="ss-field-label text-[var(--ss-text-muted)]">
                  offset <span className="ss-mono normal-case">{page.offset}</span> · limit{" "}
                  <span className="ss-mono normal-case">{page.limit}</span>
                </span>
              </div>
            </>
          )}
        </div>
      </Panel>

      {/* ── canonical case shortcut ─────────────────────────────────── */}
      <Panel>
        <SectionHeader
          title="Canonical case"
          subtitle="The module used for the reference investigation. Ground truth is healthy, the detector does not flag it at module level, and the statistical baseline does — which is the point."
          level={3}
        />
        <div className="flex flex-wrap items-center gap-[var(--ss-space-3)] p-[var(--ss-space-4)]">
          <MonoId value="syn-mod-0042" />
          <Link
            href="/modules/syn-mod-0042"
            className="ss-field-label border border-[var(--ss-accent)] px-[var(--ss-space-3)] py-[var(--ss-space-1)]"
            style={{
              borderRadius: "var(--ss-radius-sm)",
              backgroundColor: "var(--ss-accent-muted)",
            }}
          >
            Open module context
          </Link>
        </div>
      </Panel>
    </>
  );
}
