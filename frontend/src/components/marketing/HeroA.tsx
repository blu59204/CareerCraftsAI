"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";

const HEADLINE_WORDS = ["Apply", "smarter.", "Tailor", "faster."];
const HIGHLIGHT = "Get noticed.";

function DashboardMockup() {
  return (
    <div className="w-full overflow-hidden rounded-2xl border border-border bg-white shadow-2xl">
      {/* Top bar */}
      <div className="flex items-center gap-2 border-b border-border/60 bg-muted/40 px-4 py-3">
        <span className="h-2.5 w-2.5 rounded-full bg-red-400/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-yellow-400/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-green-400/70" />
        <span className="ml-3 text-xs font-medium text-foreground/60">CareerCraft AI — Dashboard</span>
      </div>

      <div className="p-5">
        {/* Metric cards row */}
        <div className="grid grid-cols-4 gap-3 text-left">
          {[
            { label: "Applications", value: "34", trend: "+8 this week", color: "text-primary" },
            { label: "Interviews", value: "6", trend: "+2 this week", color: "text-emerald-600" },
            { label: "Avg Match", value: "87%", trend: "↑ 4% vs last wk", color: "text-violet-600" },
            { label: "Follow-ups", value: "12", trend: "3 pending", color: "text-amber-600" },
          ].map((m) => (
            <div
              key={m.label}
              className="rounded-xl border border-border/70 bg-white px-3 py-3 shadow-sm"
            >
              <div className="text-[10px] font-medium text-muted-foreground">{m.label}</div>
              <div className={`mt-0.5 text-xl font-semibold ${m.color}`}>{m.value}</div>
              <div className="mt-0.5 text-[9px] text-muted-foreground/70">{m.trend}</div>
            </div>
          ))}
        </div>

        {/* Two panels */}
        <div className="mt-4 grid grid-cols-5 gap-3">
          {/* Left: ATS Score panel */}
          <div className="col-span-2 rounded-xl border border-border/70 bg-white p-4 shadow-sm">
            <div className="text-[11px] font-medium text-foreground/60">Resume ATS Score</div>
            <div className="mt-3 flex items-center justify-center">
              {/* SVG circle gauge */}
              <svg viewBox="0 0 80 80" className="h-20 w-20 -rotate-90">
                <circle
                  cx="40" cy="40" r="32"
                  fill="none"
                  strokeWidth="7"
                  stroke="hsl(214 32% 91%)"
                />
                <circle
                  cx="40" cy="40" r="32"
                  fill="none"
                  strokeWidth="7"
                  stroke="hsl(245 75% 59%)"
                  strokeLinecap="round"
                  strokeDasharray={`${2 * Math.PI * 32 * 0.82} ${2 * Math.PI * 32}`}
                />
              </svg>
              <div className="absolute text-center">
                <div className="text-lg font-bold text-foreground">82</div>
                <div className="text-[9px] text-muted-foreground">/ 100</div>
              </div>
            </div>
            <div className="mt-3 space-y-1.5">
              {[
                { label: "Keywords", pct: 88 },
                { label: "Formatting", pct: 91 },
                { label: "Relevance", pct: 75 },
              ].map((bar) => (
                <div key={bar.label} className="flex items-center gap-2">
                  <span className="w-16 text-[9px] text-muted-foreground">{bar.label}</span>
                  <div className="h-1 flex-1 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary/70"
                      style={{ width: `${bar.pct}%` }}
                    />
                  </div>
                  <span className="w-6 text-right text-[9px] font-medium text-foreground/60">
                    {bar.pct}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Right: Job match cards */}
          <div className="col-span-3 rounded-xl border border-border/70 bg-white p-4 shadow-sm">
            <div className="mb-3 text-[11px] font-medium text-foreground/60">Top Job Matches</div>
            <div className="space-y-2">
              {[
                { role: "Frontend Engineer", company: "Stripe", match: 94, tag: "Remote" },
                { role: "Software Engineer", company: "Notion", match: 89, tag: "SF / Remote" },
                { role: "Full-Stack Dev", company: "Linear", match: 81, tag: "Remote" },
              ].map((job) => (
                <div
                  key={job.role}
                  className="flex items-center justify-between rounded-lg border border-border/50 bg-muted/30 px-3 py-2"
                >
                  <div>
                    <div className="text-[11px] font-medium text-foreground">{job.role}</div>
                    <div className="text-[9px] text-muted-foreground">
                      {job.company} · {job.tag}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[9px] font-semibold text-primary">
                      {job.match}% match
                    </span>
                    <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[9px] font-medium text-emerald-700">
                      Apply
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function HeroA() {
  return (
    <section className="relative isolate overflow-hidden pt-16">
      {/* Video background */}
      <video
        autoPlay
        muted
        loop
        playsInline
        className="absolute inset-0 -z-20 h-full w-full object-cover opacity-[0.07]"
        src="/videos/hero.mp4"
      />
      {/* Gradient overlay keeps text readable */}
      <div className="absolute inset-0 -z-10 bg-gradient-to-b from-background/60 via-background/40 to-background" />
      <div className="absolute inset-0 -z-10 noise-overlay" />
      <div className="relative mx-auto max-w-6xl px-6 pb-32 pt-20 text-center">
        <motion.span
          initial="hidden"
          animate="show"
          variants={fadeUp}
          className="inline-flex items-center gap-2 rounded-full border border-border bg-card/70 px-4 py-1.5 text-xs font-medium text-muted-foreground"
        >
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary" />
          AI job-search copilot · 2024
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
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1], delay: 0.4 }}
          className="relative mx-auto mt-20 max-w-5xl"
        >
          {/* Subtle glow behind the mockup */}
          <div className="absolute -inset-4 -z-10 rounded-[2rem] bg-primary/5 blur-2xl" />
          <DashboardMockup />
        </motion.div>
      </div>
    </section>
  );
}
