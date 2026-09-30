import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Vanguard screen wrapper: max-width container, Geist as the screen font,
 * and bottom breathing room. Page-level horizontal padding comes from
 * AppShell. Keep working surfaces close to their headers.
 *
 * Section rhythm: separate major sections with `space-y-6 md:space-y-8`
 * (the default here). Working surfaces (kanban, editor, composer) stay dense
 * inside their section.
 */
export function Screen({ children, className, width = "wide" }: { children: ReactNode; className?: string; width?: "wide" | "narrow" }) {
  return (
    <div
      className={cn(
        "vanguard-screen relative mx-auto w-full min-w-0 break-words font-geist antialiased",
        width === "narrow" ? "max-w-5xl" : "max-w-[1400px]",
        "space-y-6 pb-8 md:space-y-8 md:pb-12",
        className,
      )}
    >
      {children}
    </div>
  );
}

/** A major section with top-level spacing handled by Screen. */
export function Section({ children, className, id, "aria-label": ariaLabel }: { children: ReactNode; className?: string; id?: string; "aria-label"?: string }) {
  return (
    <section id={id} aria-label={ariaLabel} className={cn("min-w-0 space-y-5 md:space-y-6", className)}>
      {children}
    </section>
  );
}
