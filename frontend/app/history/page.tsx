import { EmptyState } from "@/components/EmptyState";
import Link from "next/link";
import { ErrorState } from "@/components/ErrorState";
import { MonoId } from "@/components/MonoId";
import { Panel, SectionHeader } from "@/components/Panel";
import { StatusChip } from "@/components/StatusChip";
import { listInvestigations } from "@/lib/api/endpoints";

export const metadata = { title: "Investigation History — SmartESS" };
export const dynamic = "force-dynamic";

/**
 * Investigation History (UX.md §36 `/history`).
 *
 * M10-A renders only what `GET /investigations` actually returns:
 * investigation_id, module_id, model_id, status, created_at.
 *
 * Evidence count, candidate count, report status and the mocked-inference flag
 * are deliberately ABSENT: they live on the full record, which is ~217 KB each
 * (design.md §11.3, §19.4), so fetching 69 of them to render a table is
 * forbidden. The full history surface with those columns is M10-H, behind the
 * paginated list endpoint of design.md §10.2.
 */
export default async function HistoryPage() {
  const investigations = await listInvestigations();

  return (
    <Panel>
      <SectionHeader
          level={1}
        title="Investigation History"
        subtitle="Every stored investigation on this host. PARTIAL records are distinguished from COMPLETED: a partial investigation still has inspectable stages."
      />

      <div className="p-[var(--ss-space-4)]">
        {investigations.kind !== "ok" ? (
          <ErrorState result={investigations} />
        ) : investigations.data.length === 0 ? (
          <EmptyState
            state="NO_DATA"
            body="No investigations have been recorded in this environment."
            detail="ml/datasets/investigations/ — scripts/investigate.py"
          />
        ) : (
          <>
            <table className="w-full border-collapse text-left">
              <caption className="ss-sr-only">
                Stored SmartESS investigations with module, model, status and
                creation timestamp.
              </caption>
              <thead>
                <tr className="border-b border-[var(--ss-border-strong)]">
                  <th scope="col" className="ss-field-label py-[var(--ss-space-2)] pr-[var(--ss-space-4)]">
                    Investigation
                  </th>
                  <th scope="col" className="ss-field-label py-[var(--ss-space-2)] pr-[var(--ss-space-4)]">
                    Module
                  </th>
                  <th scope="col" className="ss-field-label py-[var(--ss-space-2)] pr-[var(--ss-space-4)]">
                    Model
                  </th>
                  <th scope="col" className="ss-field-label py-[var(--ss-space-2)] pr-[var(--ss-space-4)]">
                    Status
                  </th>
                  <th scope="col" className="ss-field-label py-[var(--ss-space-2)]">
                    Created
                  </th>
                </tr>
              </thead>
              <tbody>
                {investigations.data.map((item) => (
                  <tr
                    key={item.investigation_id}
                    className="border-b border-[var(--ss-border-subtle)]"
                  >
                    <th scope="row" className="py-[var(--ss-space-2)] pr-[var(--ss-space-4)] font-normal">
                      <Link
                        href={`/investigations/${item.investigation_id}`}
                        className="ss-mono break-all text-[var(--ss-accent)] hover:text-[var(--ss-accent-hover)]"
                      >
                        {item.investigation_id}
                      </Link>
                    </th>
                    <td className="py-[var(--ss-space-2)] pr-[var(--ss-space-4)]">
                      <MonoId value={item.module_id} />
                    </td>
                    <td className="py-[var(--ss-space-2)] pr-[var(--ss-space-4)]">
                      <MonoId value={item.model_id} truncate />
                    </td>
                    <td className="py-[var(--ss-space-2)] pr-[var(--ss-space-4)]">
                      <StatusChip status={item.status} />
                    </td>
                    <td className="ss-mono py-[var(--ss-space-2)] text-[var(--ss-text-secondary)]">
                      {item.created_at}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <p
              className="mt-[var(--ss-space-4)] text-[var(--ss-text-muted)]"
              style={{ fontSize: "var(--ss-text-label-size)" }}
            >
              Evidence count, candidate count, report status and inference mode
              are not shown: they are only on the full investigation record, which
              is too large to fetch per row. Those columns arrive in M10-H with
              the paginated list endpoint (design.md §10.2, §19.4).
            </p>
          </>
        )}
      </div>
    </Panel>
  );
}
