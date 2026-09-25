import type { ReactNode } from "react";

/**
 * Panel — the base analytical container.
 *
 * Structure comes from 1 px borders and the technical grid. No shadows, no
 * gradients, minimal rounding (UX.md §23, §44.7).
 */
export function Panel({
  children,
  className = "",
  as: Tag = "section",
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "div" | "article" | "aside";
}) {
  return (
    <Tag
      className={`border border-[var(--ss-border-subtle)] bg-[var(--ss-bg-surface)] ${className}`}
      style={{ borderRadius: "var(--ss-radius-md)" }}
    >
      {children}
    </Tag>
  );
}

/**
 * SectionHeader — compact hierarchy. The label is low-emphasis; the content
 * below carries the emphasis (UX.md §23).
 */
export function SectionHeader({
  title,
  subtitle,
  actions,
  level = 2,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  /** 1 for the page's primary heading; 2 and 3 for nested panels. */
  level?: 1 | 2 | 3;
}) {
  const Heading = level === 1 ? "h1" : level === 2 ? "h2" : "h3";
  return (
    <header className="flex items-start justify-between gap-[var(--ss-space-4)] border-b border-[var(--ss-border-subtle)] px-[var(--ss-space-4)] py-[var(--ss-space-3)]">
      <div className="flex flex-col gap-[var(--ss-space-1)]">
        <Heading
          className="font-medium text-[var(--ss-text-primary)]"
          style={{
            fontSize:
              level === 1
                ? "var(--ss-text-title-size)"
                : level === 2
                  ? "var(--ss-text-section-size)"
                  : "var(--ss-text-body-size)",
            lineHeight: "var(--ss-leading-tight)",
          }}
        >
          {title}
        </Heading>
        {subtitle && (
          <p
            className="text-[var(--ss-text-muted)]"
            style={{ maxWidth: "var(--ss-measure-prose)" }}
          >
            {subtitle}
          </p>
        )}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-[var(--ss-space-2)]">{actions}</div>}
    </header>
  );
}

/**
 * SplitPanel — two-column analytical split. Collapses to stacked panels below
 * 1024 px, where the workspace becomes read-only (UX.md §25).
 */
export function SplitPanel({
  left,
  right,
  ratio = "balanced",
}: {
  left: ReactNode;
  right: ReactNode;
  ratio?: "balanced" | "wide-left" | "wide-right";
}) {
  const cols =
    ratio === "wide-left"
      ? "lg:grid-cols-[2fr_1fr]"
      : ratio === "wide-right"
        ? "lg:grid-cols-[1fr_2fr]"
        : "lg:grid-cols-2";
  return (
    <div className={`grid grid-cols-1 gap-[var(--ss-space-4)] ${cols}`}>
      {left}
      {right}
    </div>
  );
}
