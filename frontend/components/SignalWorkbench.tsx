"use client";

import { useMemo, useState } from "react";
import { AccessibleDataTable } from "@/components/AccessibleDataTable";
import { RegisterBadge } from "@/components/RegisterValue";
import { ScientificChart, type ChartPoint } from "@/components/ScientificChart";
import { SIGNAL_ORDER, SIGNAL_STYLE } from "@/lib/signals";
import type { TelemetryPoint, TelemetrySeries } from "@/lib/types/m10";

/**
 * SignalWorkbench — interactive signal analysis (UX.md §7; design.md §A.6).
 *
 * Client-side behaviour is limited to VIEW control: which signals are shown and
 * which cycle window. It performs no fitting, no smoothing, no resampling and no
 * threshold derivation — every plotted value is the backend value for that
 * observation (UX.md §35 Rule 2).
 *
 * Zooming filters the already-fetched points; it never reinterpolates. The
 * accessible table below the charts always reflects the current window.
 */
export function SignalWorkbench({
  series,
  referenceMeans,
}: {
  series: TelemetrySeries;
  /** Declared healthy-reference means, when the artifact supplied them. */
  referenceMeans?: Record<string, number | null>;
}) {
  const available = SIGNAL_ORDER.filter((s) => series.signals.includes(s));
  const [selected, setSelected] = useState<string[]>([...available]);
  const [window, setWindow] = useState<{ from: number; to: number } | null>(null);

  const cycles = series.points.map((p) => p.cycle_number);
  const minCycle = cycles.length > 0 ? Math.min(...cycles) : 0;
  const maxCycle = cycles.length > 0 ? Math.max(...cycles) : 0;

  const visible: TelemetryPoint[] = useMemo(() => {
    if (!window) return series.points;
    return series.points.filter(
      (p) => p.cycle_number >= window.from && p.cycle_number <= window.to,
    );
  }, [series.points, window]);

  const flagged = visible.filter((p) => p.is_anomaly);
  const baselineFlagged = visible.filter((p) => p.statistical_baseline_flag);

  function toggle(signal: string) {
    setSelected((prev) =>
      prev.includes(signal) ? prev.filter((s) => s !== signal) : [...prev, signal],
    );
  }

  /** Zoom to the span that contains the flagged observations, if any. */
  function zoomToFlagged() {
    const f = series.points.filter((p) => p.is_anomaly).map((p) => p.cycle_number);
    if (f.length === 0) return;
    setWindow({ from: Math.min(...f), to: Math.max(...f) });
  }

  return (
    <div className="flex flex-col gap-[var(--ss-space-4)]">
      {/* ── controls ─────────────────────────────────────────────────── */}
      <div className="flex flex-col gap-[var(--ss-space-3)]">
        <fieldset className="flex flex-wrap items-center gap-[var(--ss-space-2)]">
          <legend className="ss-field-label">Signals</legend>
          {available.map((s) => {
            const on = selected.includes(s);
            const style = SIGNAL_STYLE[s];
            return (
              <button
                key={s}
                type="button"
                onClick={() => toggle(s)}
                aria-pressed={on}
                className="ss-field-label flex items-center gap-[var(--ss-space-1)] border px-[var(--ss-space-2)] py-[var(--ss-space-1)]"
                style={{
                  borderRadius: "var(--ss-radius-sm)",
                  borderColor: on ? `var(${style?.colorVar})` : "var(--ss-border-subtle)",
                  color: on ? "var(--ss-text-primary)" : "var(--ss-text-muted)",
                }}
              >
                <span
                  aria-hidden="true"
                  style={{
                    display: "inline-block",
                    width: 10,
                    height: 2,
                    backgroundColor: on ? `var(${style?.colorVar})` : "var(--ss-border-strong)",
                  }}
                />
                {style?.label ?? s}
                <span aria-hidden="true">{on ? "ON" : "OFF"}</span>
              </button>
            );
          })}
        </fieldset>

        <div className="flex flex-wrap items-center gap-[var(--ss-space-2)]">
          <span className="ss-field-label">Cycle window</span>
          <span className="ss-mono text-[var(--ss-text-secondary)]">
            {window ? `${window.from} – ${window.to}` : `${minCycle} – ${maxCycle} (full)`}
          </span>
          <button
            type="button"
            onClick={() => setWindow({ from: minCycle, to: Math.round(minCycle + (maxCycle - minCycle) / 4) })}
            className="ss-field-label border border-[var(--ss-border-strong)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] hover:border-[var(--ss-accent)]"
            style={{ borderRadius: "var(--ss-radius-sm)" }}
          >
            First quarter
          </button>
          <button
            type="button"
            onClick={() => setWindow({ from: Math.round(maxCycle - (maxCycle - minCycle) / 4), to: maxCycle })}
            className="ss-field-label border border-[var(--ss-border-strong)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] hover:border-[var(--ss-accent)]"
            style={{ borderRadius: "var(--ss-radius-sm)" }}
          >
            Last quarter
          </button>
          <button
            type="button"
            onClick={zoomToFlagged}
            disabled={!series.points.some((p) => p.is_anomaly)}
            className="ss-field-label border border-[var(--ss-border-strong)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] hover:border-[var(--ss-accent)] disabled:opacity-40"
            style={{ borderRadius: "var(--ss-radius-sm)" }}
          >
            Flagged span
          </button>
          <button
            type="button"
            onClick={() => setWindow(null)}
            className="ss-field-label border border-[var(--ss-border-strong)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] hover:border-[var(--ss-accent)]"
            style={{ borderRadius: "var(--ss-radius-sm)" }}
          >
            Reset
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-[var(--ss-space-4)]">
          <span className="ss-field-label">
            Observations shown{" "}
            <span className="ss-mono normal-case text-[var(--ss-text-primary)]">
              {visible.length}
            </span>{" "}
            of{" "}
            <span className="ss-mono normal-case text-[var(--ss-text-primary)]">
              {series.source_points}
            </span>
          </span>
          <span className="ss-field-label" style={{ color: "var(--ss-marker-anomaly)" }}>
            ▫ detector flagged{" "}
            <span className="ss-mono normal-case">{flagged.length}</span>
          </span>
          <span className="ss-field-label" style={{ color: "var(--ss-marker-baseline-flag)" }}>
            △ statistical baseline flagged{" "}
            <span className="ss-mono normal-case">{baselineFlagged.length}</span>
          </span>
          {series.downsampled && (
            <span className="ss-field-label" style={{ color: "var(--ss-state-attention)" }}>
              DOWNSAMPLED · {series.downsample_method}
            </span>
          )}
        </div>
      </div>

      {/* ── one pane per selected signal, shared cycle axis ──────────── */}
      {selected.length === 0 ? (
        <p className="text-[var(--ss-text-muted)]">
          No signal selected. Enable at least one signal above.
        </p>
      ) : (
        available
          .filter((s) => selected.includes(s))
          .map((signal) => {
            const style = SIGNAL_STYLE[signal];
            const points: ChartPoint[] = visible.map((p) => ({
              cycle: p.cycle_number,
              value: typeof p[signal] === "number" ? (p[signal] as number) : null,
            }));
            const markers = flagged.map((p) => ({
              cycle: p.cycle_number,
              value: typeof p[signal] === "number" ? (p[signal] as number) : null,
            }));
            return (
              <section
                key={signal}
                className="flex flex-col gap-[var(--ss-space-2)] border border-[var(--ss-border-subtle)] p-[var(--ss-space-3)]"
                style={{ borderRadius: "var(--ss-radius-sm)" }}
              >
                <header className="flex flex-wrap items-baseline justify-between gap-[var(--ss-space-2)]">
                  <h3 className="ss-mono text-[var(--ss-text-primary)]">
                    {style?.label ?? signal}
                  </h3>
                  <div className="flex items-center gap-[var(--ss-space-2)]">
                    {style?.unit ? (
                      <span className="ss-field-label text-[var(--ss-text-muted)]">
                        {style.unit} · documentation-derived
                      </span>
                    ) : (
                      <span className="ss-field-label text-[var(--ss-text-muted)]">
                        no unit in artifact
                      </span>
                    )}
                    <RegisterBadge register="DATA" />
                  </div>
                </header>
                <ScientificChart
                  signal={signal}
                  points={points}
                  anomalyMarkers={markers}
                  referenceMean={referenceMeans?.[signal] ?? null}
                />
                <p className="ss-sr-only">
                  {signal} against cycle_number. {points.length} observations from cycle{" "}
                  {points[0]?.cycle ?? "n/a"} to {points[points.length - 1]?.cycle ?? "n/a"}.
                  {markers.length} detector-flagged observations. Exact values are in the
                  observation table below.
                </p>
              </section>
            );
          })
      )}

      {/* ── accessible tabular representation of the same window ─────── */}
      <section className="flex flex-col gap-[var(--ss-space-2)]">
        <h3 className="ss-field-label">Observations (exact values)</h3>
        <AccessibleDataTable
          caption="Observation-level values for the current cycle window, including detector score and flags."
          rows={visible}
          rowKey={(p) => String(p.cycle_number)}
          maxRows={60}
          columns={[
            { key: "cycle", header: "cycle_number", render: (p) => p.cycle_number },
            {
              key: "score",
              header: "anomaly_score",
              render: (p) => (p.anomaly_score === null ? "—" : p.anomaly_score),
            },
            {
              key: "flag",
              header: "is_anomaly",
              render: (p) =>
                p.is_anomaly === null ? "—" : p.is_anomaly ? "true" : "false",
            },
            {
              key: "basescore",
              header: "statistical_baseline_score",
              render: (p) =>
                p.statistical_baseline_score === null ? "—" : p.statistical_baseline_score,
            },
            {
              key: "baseflag",
              header: "statistical_baseline_flag",
              render: (p) =>
                p.statistical_baseline_flag === null
                  ? "—"
                  : p.statistical_baseline_flag
                    ? "true"
                    : "false",
            },
            ...available
              .filter((s) => selected.includes(s))
              .map((s) => ({
                key: s,
                header: s,
                render: (p: TelemetryPoint) =>
                  typeof p[s] === "number" ? (p[s] as number) : "—",
              })),
          ]}
        />
      </section>
    </div>
  );
}
