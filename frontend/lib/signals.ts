import type { BaselineSignal } from "@/lib/types/backend";

/**
 * Per-signal chart styling — UX.md §44.8.
 *
 * Every series is distinguishable by DASH PATTERN as well as hue, so identity
 * survives greyscale and colour-blind rendering (UX.md §34, §44.8).
 *
 * `unit` is deliberately absent for most signals: no engineering unit is carried
 * in the M6/M7 artifacts (design.md §20.4). The two documented exceptions are
 * marked `unitSource: "documentation"` so the UI can label them as
 * documentation-derived rather than measured.
 */
export interface SignalStyle {
  readonly colorVar: string;
  readonly dash?: string;
  readonly label: string;
  readonly unit?: string;
  readonly unitSource?: "documentation";
}

export const SIGNAL_STYLE: Record<string, SignalStyle> = {
  RDS_on: {
    colorVar: "--ss-signal-rds-on",
    label: "RDS(on)",
    unit: "mOhm",
    unitSource: "documentation",
  },
  VTH: { colorVar: "--ss-signal-vth", dash: "4 2", label: "VTH" },
  IGSS: { colorVar: "--ss-signal-igss", dash: "2 2", label: "IGSS" },
  IDSS: { colorVar: "--ss-signal-idss", dash: "6 2", label: "IDSS" },
  VDS_on: { colorVar: "--ss-signal-vds-on", dash: "1 3", label: "VDS(on)" },
  electrical_power: {
    colorVar: "--ss-signal-electrical-power",
    dash: "8 3",
    label: "electrical_power",
  },
  Tj: {
    colorVar: "--ss-signal-tj",
    dash: "3 1 1 1",
    label: "Tj",
    unit: "°C",
    unitSource: "documentation",
  },
  Tc: {
    colorVar: "--ss-signal-tc",
    dash: "5 2 1 2",
    label: "Tc",
    unit: "°C",
    unitSource: "documentation",
  },
};

/** Display order for the eight baseline signals. */
export const SIGNAL_ORDER: readonly BaselineSignal[] = [
  "RDS_on",
  "VTH",
  "IGSS",
  "IDSS",
  "VDS_on",
  "electrical_power",
  "Tj",
  "Tc",
];
