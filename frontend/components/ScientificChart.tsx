"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { SIGNAL_STYLE } from "@/lib/signals";

/**
 * ScientificChart — one signal against the shared cycle axis (UX.md §26).
 *
 * Rules enforced:
 *  · named axes, cycle_number as the x-axis;
 *  · independent y-scale per signal (the 8 signals are not comparable);
 *  · null gaps are BREAKS, never interpolated (`connectNulls={false}`);
 *  · exact tooltip values — no rounding of the backend number;
 *  · anomaly markers use a distinct SHAPE, not only a hue;
 *  · no trend line, no fit, no confidence band, no change-point marker — the
 *    backend provides none of those (design.md §20.2, §20.3, UX.md §26).
 *
 * This component computes nothing. It plots the arrays it is given.
 */
export interface ChartPoint {
  cycle: number;
  value: number | null;
}

export function ScientificChart({
  signal,
  points,
  anomalyMarkers = [],
  height = 148,
  referenceMean,
}: {
  signal: string;
  points: readonly ChartPoint[];
  /** Cycle numbers where `is_anomaly` is true, with the signal value there. */
  anomalyMarkers?: readonly { cycle: number; value: number | null }[];
  height?: number;
  /** Declared healthy-reference mean, when the artifact supplied one. */
  referenceMean?: number | null;
}) {
  const style = SIGNAL_STYLE[signal] ?? {
    colorVar: "--ss-chart-axis",
    dash: undefined,
    label: signal,
  };
  const stroke = `var(${style.colorVar})`;

  return (
    <div className="w-full" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points as ChartPoint[]} margin={{ top: 6, right: 12, bottom: 4, left: 4 }}>
          <CartesianGrid stroke="var(--ss-chart-grid)" strokeDasharray="2 4" />
          <XAxis
            dataKey="cycle"
            type="number"
            domain={["dataMin", "dataMax"]}
            stroke="var(--ss-chart-axis)"
            tick={{ fill: "var(--ss-text-muted)", fontSize: 10 }}
            tickLine={false}
            name="cycle_number"
          />
          <YAxis
            stroke="var(--ss-chart-axis)"
            tick={{ fill: "var(--ss-text-muted)", fontSize: 10 }}
            tickLine={false}
            width={68}
            // Independent per-signal scale; never forced through zero, since the
            // signals have incomparable magnitudes and offsets.
            domain={["auto", "auto"]}
            name={signal}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "var(--ss-bg-raised)",
              border: "1px solid var(--ss-border-strong)",
              borderRadius: "var(--ss-radius-sm)",
              fontFamily: "var(--ss-font-mono)",
              fontSize: 12,
            }}
            labelStyle={{ color: "var(--ss-text-muted)" }}
            itemStyle={{ color: "var(--ss-text-primary)" }}
            // Exact value, unrounded (design.md acceptance 19).
            formatter={(v: unknown) => [String(v), signal]}
            labelFormatter={(l: unknown) => `cycle_number ${String(l)}`}
          />
          {typeof referenceMean === "number" && (
            <Line
              type="monotone"
              dataKey={() => referenceMean}
              stroke="var(--ss-reference-band)"
              strokeDasharray="4 4"
              strokeWidth={1}
              dot={false}
              isAnimationActive={false}
              name="healthy reference mean"
              legendType="none"
            />
          )}
          <Line
            type="linear"
            dataKey="value"
            stroke={stroke}
            strokeWidth={1.25}
            strokeDasharray={style.dash}
            dot={false}
            // Null gaps must break the line, not interpolate across it.
            connectNulls={false}
            isAnimationActive={false}
            name={signal}
          />
          {anomalyMarkers.map((m) =>
            m.value === null ? null : (
              <ReferenceDot
                key={m.cycle}
                x={m.cycle}
                y={m.value}
                // A hollow SQUARE, distinct in shape from the round default, so the
                // marker survives greyscale and colour-blind rendering
                // (UX.md §34, §44.8). Not colour-only.
                shape={(props: { cx?: number; cy?: number }) => (
                  <rect
                    x={(props.cx ?? 0) - 3}
                    y={(props.cy ?? 0) - 3}
                    width={6}
                    height={6}
                    fill="none"
                    stroke="var(--ss-marker-anomaly)"
                    strokeWidth={1.25}
                  />
                )}
              />
            ),
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
