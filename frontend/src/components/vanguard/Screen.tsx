import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Vanguard screen wrapper: max-width container, Geist as the screen font,
 * and bottom breathing room. Page-level horizontal padding comes from
 * AppShell (px-6 md:px-8); on < md we keep it to px-4-equivalent spacing.
 *
 * Section rhythm: separate major sections with `space-y-24 md:space-y-32`
 * (the default here). Working surfaces (kanban, editor, composer) stay dense
 * inside their section.
 */
export function Screen({ children, className, width = "wide" }: { children: ReactNode; className?: string; width?: "wide" | "narrow" }) {
  return (
    <div
      className={cn(
        "vanguard-screen relative mx-auto w-full font-geist antialiased",
        width === "narrow" ? "max-w-5xl" : "max-w-[1400px]",
        "space-y-20 pb-24 md:space-y-28 md:pb-40",
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
    <section id={id} aria-label={ariaLabel} className={cn("space-y-8 md:space-y-10", className)}>
      {children}
    </section>
  );
}
