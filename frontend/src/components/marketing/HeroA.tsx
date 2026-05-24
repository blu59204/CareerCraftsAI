"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";

const HEADLINE_WORDS = ["Apply", "smarter.", "Tailor", "faster."];
const HIGHLIGHT = "Get noticed.";

export function HeroA() {
  return (
    <section className="relative isolate overflow-hidden gradient-mesh-light noise-overlay pt-16">
      <div className="relative mx-auto max-w-6xl px-6 pb-32 pt-20 text-center">
        <motion.span
          initial="hidden"
          animate="show"
          variants={fadeUp}
          className="inline-flex items-center gap-2 rounded-full border border-border bg-card/70 px-4 py-1.5 text-xs font-medium text-muted-foreground"
        >
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary" />
          AI job-search copilot for students and freshers
        </motion.span>

        <motion.h1
          initial="hidden"
          animate="show"
          variants={stagger}
          className="mx-auto mt-8 max-w-4xl text-balance text-5xl font-medium leading-tight tracking-tight md:text-7xl"
        >
          {HEADLINE_WORDS.map((w, i) => (
            <motion.span key={i} variants={fadeUp} className="inline-block">
              {w}&nbsp;
            </motion.span>
          ))}
          <motion.span variants={fadeUp} className="font-display text-primary">
            {HIGHLIGHT}
          </motion.span>
        </motion.h1>

        <motion.p
          initial="hidden"
          animate="show"
          variants={fadeUp}
          className="mx-auto mt-6 max-w-2xl text-base text-muted-foreground md:text-lg"
        >
          Resume tailoring, job matching, auto-apply, and follow-up — all powered by your own API keys.
        </motion.p>

        <motion.div
          initial="hidden"
          animate="show"
          variants={fadeUp}
          className="mt-10 flex items-center justify-center gap-3"
        >
          <Link href="/register">
            <LiquidGlassButton tone="primary" size="lg">
              Start free
            </LiquidGlassButton>
          </Link>
          <Link href="/#demo">
            <LiquidGlassButton tone="ghost" size="lg">
              Watch demo
            </LiquidGlassButton>
          </Link>
        </motion.div>

        <motion.div
          initial="hidden"
          animate="show"
          variants={fadeUp}
          className="relative mx-auto mt-20 aspect-[16/9] max-w-5xl overflow-hidden rounded-3xl border border-border bg-card shadow-2xl"
        >
          <div className="flex h-full items-center justify-center text-muted-foreground">
            Product preview
          </div>
        </motion.div>
      </div>
    </section>
  );
}
