import Link from "next/link";
import type { ReactNode } from "react";

/**
 * Navigation — UX.md §3.
 *
 * The four agent stages and the two validation stages are first-class named
 * concepts. The navigation must never make the user guess where the agentic
 * workflow is, and the system is never labelled simply "AI".
 *
 * `available: false` entries are shown but not linked, because their backend
 * contracts do not exist yet (design.md §10.2). Hiding them would misrepresent
 * the product; linking them would produce a dead end.
 */
interface NavItem {
  readonly label: string;
  readonly href?: string;
  readonly available: boolean;
}

interface NavGroup {
  readonly heading: string;
  readonly items: readonly NavItem[];
}

const NAV: readonly NavGroup[] = [
  {
    heading: "Investigation",
    items: [
      { label: "Module Explorer", href: "/modules", available: true },
      { label: "Start Investigation", href: "/investigations/new", available: true },
    ],
  },
  {
    heading: "M9 Investigation",
    items: [
      { label: "Investigation History", href: "/history", available: true },
    ],
  },
  {
    heading: "System",
    items: [
      { label: "Pipeline Readiness", href: "/system/readiness", available: true },
    ],
  },
];

function NavLink({ item }: { item: NavItem }) {
  if (!item.available || !item.href) {
    return (
      <span
        className="flex items-center justify-between gap-[var(--ss-space-2)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] text-[var(--ss-text-muted)]"
        title="Backend contract not implemented (design.md §10.2)"
      >
        <span>{item.label}</span>
        <span className="ss-field-label shrink-0">N/I</span>
      </span>
    );
  }
  return (
    <Link
      href={item.href}
      className="block px-[var(--ss-space-2)] py-[var(--ss-space-1)] text-[var(--ss-text-secondary)] hover:bg-[var(--ss-bg-raised)] hover:text-[var(--ss-text-primary)]"
      style={{ borderRadius: "var(--ss-radius-sm)" }}
    >
      {item.label}
    </Link>
  );
}

/**
 * AppShell — persistent application shell (UX.md §3).
 *
 * Layout is navigation | content. The context rail is NOT rendered here: per
 * UX.md §4 it is visible "while an investigation is open", so it is owned by
 * `app/investigations/[investigationId]/layout.tsx`. That nested layout does not
 * remount across the investigation sub-routes, which is what makes the rail
 * survive route changes and panel-level API errors (UX.md §4, §31).
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col lg:h-screen lg:flex-row lg:overflow-hidden">
      <nav
        className="flex w-full shrink-0 flex-col gap-[var(--ss-space-5)] border-b border-[var(--ss-border-subtle)] bg-[var(--ss-bg-inset)] p-[var(--ss-space-4)] lg:h-full lg:w-[228px] lg:border-b-0 lg:border-r lg:overflow-y-auto"
        aria-label="Primary"
      >
        <Link href="/" className="flex flex-col gap-[var(--ss-space-1)]">
          <span
            className="ss-mono font-medium tracking-wide text-[var(--ss-text-primary)]"
            style={{ fontSize: "var(--ss-text-title-size)" }}
          >
            SMARTESS
          </span>
          <span className="ss-field-label">Scientific Reliability Investigation</span>
        </Link>

        <Link
          href="/"
          className="border border-[var(--ss-border-strong)] px-[var(--ss-space-2)] py-[var(--ss-space-1)] text-center text-[var(--ss-text-primary)] hover:border-[var(--ss-accent)]"
          style={{ borderRadius: "var(--ss-radius-sm)" }}
        >
          Mission Control
        </Link>

        {NAV.map((group) => (
          <div key={group.heading} className="flex flex-col gap-[var(--ss-space-1)]">
            <span className="ss-field-label px-[var(--ss-space-2)]">{group.heading}</span>
            {group.items.map((item) => (
              <NavLink key={item.label} item={item} />
            ))}
          </div>
        ))}

        <div className="mt-auto flex flex-col gap-[var(--ss-space-1)]">
          <span className="ss-field-label">Workflow</span>
          <p
            className="text-[var(--ss-text-muted)]"
            style={{ fontSize: "var(--ss-text-label-size)" }}
          >
            Signals, anomaly detection and detector evaluation are scoped to a module.
            Pipeline trace, evidence, hypotheses, report and provenance are scoped to an
            investigation. Open one to reach them.
          </p>
        </div>
      </nav>

      <main className="flex-1 lg:overflow-y-auto">
        <div className="flex flex-col gap-[var(--ss-space-4)] p-[var(--ss-space-4)] lg:p-[var(--ss-space-6)]">
          {children}
        </div>
      </main>
    </div>
  );
}
