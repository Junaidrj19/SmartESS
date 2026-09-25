import type { ReactNode } from "react";

/**
 * AccessibleDataTable — dense analytical table (UX.md §25, §34).
 *
 * Every chart is accompanied by, or backed by, a tabular view of the same series
 * so the data is reachable without the visualisation (UX.md §34). Numerics are
 * monospace with tabular numerals; a caption is always present for screen
 * readers.
 */
export interface Column<Row> {
  readonly key: string;
  readonly header: string;
  readonly render: (row: Row) => ReactNode;
  /** Monospace + tabular numerals. Default true, since most cells are values. */
  readonly mono?: boolean;
  readonly align?: "left" | "right";
}

export function AccessibleDataTable<Row>({
  caption,
  columns,
  rows,
  rowKey,
  /** Cap the rendered rows and state the cap, rather than silently truncating. */
  maxRows,
}: {
  caption: string;
  columns: readonly Column<Row>[];
  rows: readonly Row[];
  rowKey: (row: Row, index: number) => string;
  maxRows?: number;
}) {
  const visible = maxRows === undefined ? rows : rows.slice(0, maxRows);
  const truncated = visible.length < rows.length;

  return (
    <div className="flex flex-col gap-[var(--ss-space-2)]">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <caption className="ss-sr-only">{caption}</caption>
          <thead>
            <tr className="border-b border-[var(--ss-border-strong)]">
              {columns.map((c) => (
                <th
                  key={c.key}
                  scope="col"
                  className="ss-field-label py-[var(--ss-space-2)] pr-[var(--ss-space-4)] whitespace-nowrap"
                  style={{ textAlign: c.align ?? "left" }}
                >
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((row, i) => (
              <tr key={rowKey(row, i)} className="border-b border-[var(--ss-border-subtle)]">
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className={`py-[var(--ss-space-2)] pr-[var(--ss-space-4)] align-top ${
                      c.mono === false ? "" : "ss-mono"
                    } text-[var(--ss-text-secondary)]`}
                    style={{ textAlign: c.align ?? "left" }}
                  >
                    {c.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {truncated && (
        <p className="text-[var(--ss-text-muted)]" style={{ fontSize: "var(--ss-text-label-size)" }}>
          Showing {visible.length} of {rows.length} rows.
        </p>
      )}
    </div>
  );
}
