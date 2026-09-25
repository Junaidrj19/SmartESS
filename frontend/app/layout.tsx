import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { AppShell } from "@/components/AppShell";

export const metadata: Metadata = {
  title: "SmartESS — Scientific Reliability Investigation",
  description:
    "Engineer-facing investigation platform over the SmartESS M1–M9 reliability-intelligence pipeline.",
};

/**
 * Root layout.
 *
 * The context rail is owned by the investigation layout, not by this one: per
 * UX.md §4 the rail is visible "while an investigation is open". Mission
 * Control, History and Readiness are not investigation-scoped, so they show no
 * rail rather than a rail full of `not recorded` placeholders.
 */
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
