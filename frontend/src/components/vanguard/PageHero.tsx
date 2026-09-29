"use client";

import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { EASE_OUT_EXPO } from "./motion";

/** Microscopic pill badge placed above H1/H2s. */
export function Eyebrow({ children, className, tone = "default" }: { children: ReactNode; className?: string; tone?: "default" | "primary" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[10px] font-medium uppercase tracking-[0.2em]",
        tone === "primary"
          ? "bg-primary/10 text-primary ring-1 ring-primary/20"
          : "bg-foreground/[0.04] text-muted-foreground ring-1 ring-foreground/[0.07] dark:bg-white/[0.04] dark:ring-white/10",
        className,
      )}
    >
      {children}
    </span>
  );
}

interface PageHeroProps {
  eyebrow: string;
  /** The screen's H1. Keep the words the e2e manifest expects (see backend/tests/e2e/screen_manifest.py). */
  title: ReactNode;
  /** Optional muted second line rendered inside the H1 after the title. */
  accent?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  /** Slot rendered to the right on lg+ (stats, status, meta). Stacks below on mobile. */
  aside?: ReactNode;
  className?: string;
}

/**
 * Editorial page header: eyebrow → massive tight-tracked Geist headline →
 * measured description, with an optional right-hand aside. Provides the
 * macro-whitespace above the working area (pt-8 md:pt-16 pb-12 md:pb-20).
 */
export function PageHero({ eyebrow, title, accent, description, actions, aside, className }: PageHeroProps) {
  const reduce = useReducedMotion();
  const enter = (delay: number) =>
    reduce
      ? { initial: { opacity: 0 }, animate: { opacity: 1 }, transition: { duration: 0.2 } }
      : {
          initial: { opacity: 0, y: 28, filter: "blur(10px)" },
          animate: { opacity: 1, y: 0, filter: "blur(0px)" },
          transition: { duration: 0.9, ease: EASE_OUT_EXPO, delay },
        };

  return (
    <header className={cn("grid gap-10 pb-12 pt-6 md:pb-20 md:pt-14 lg:grid-cols-12 lg:items-end", className)}>
      <div className="min-w-0 lg:col-span-7 xl:col-span-8">
        <motion.div {...enter(0)}>
          <Eyebrow>{eyebrow}</Eyebrow>
        </motion.div>
        <motion.h1
          {...enter(0.06)}
          className="mt-6 max-w-[18ch] text-balance font-geist text-[2.6rem] font-semibold leading-[0.95] tracking-[-0.045em] text-foreground sm:text-6xl xl:text-7xl"
        >
          {title}
          {accent ? <span className="block text-muted-foreground/70">{accent}</span> : null}
        </motion.h1>
        {description ? (
          <motion.p {...enter(0.12)} className="mt-6 max-w-[58ch] text-pretty text-[15px] leading-7 text-muted-foreground md:text-base">
            {description}
          </motion.p>
        ) : null}
        {actions ? (
          <motion.div {...enter(0.18)} className="mt-8 flex flex-wrap items-center gap-3">
            {actions}
          </motion.div>
        ) : null}
      </div>
      {aside ? (
        <motion.div {...enter(0.22)} className="min-w-0 lg:col-span-5 xl:col-span-4">
          {aside}
        </motion.div>
      ) : null}
    </header>
  );
}

/** Section header used between major blocks inside a screen. */
export function SectionHeading({
  eyebrow,
  title,
  description,
  actions,
  className,
  as: Tag = "h2",
}: {
  eyebrow?: string;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
  as?: "h2" | "h3";
}) {
  return (
    <div className={cn("flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div className="min-w-0">
        {eyebrow ? <Eyebrow className="mb-4">{eyebrow}</Eyebrow> : null}
        <Tag className="font-geist text-2xl font-semibold tracking-[-0.03em] text-foreground md:text-3xl">{title}</Tag>
        {description ? <p className="mt-2 max-w-[60ch] text-sm leading-6 text-muted-foreground">{description}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

/** Card-level title row (inside a Bezel core). */
export function PanelTitle({ title, meta, icon, className }: { title: ReactNode; meta?: ReactNode; icon?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-center justify-between gap-3", className)}>
      <div className="flex min-w-0 items-center gap-2.5">
        {icon ? <span aria-hidden className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-foreground/[0.04] text-foreground/80 ring-1 ring-foreground/[0.06] dark:bg-white/[0.05] dark:ring-white/10">{icon}</span> : null}
        <h3 className="truncate font-geist text-[15px] font-semibold tracking-[-0.015em] text-foreground">{title}</h3>
      </div>
      {meta ? <div className="shrink-0 text-xs text-muted-foreground">{meta}</div> : null}
    </div>
  );
}
