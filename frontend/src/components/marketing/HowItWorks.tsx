"use client";

import { motion } from "motion/react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { Upload, Target, Bot, CheckCheck } from "lucide-react";

const STEPS = [
  {
    n: "01",
    icon: <Upload className="h-5 w-5" />,
    title: "Upload your resume",
    body: "Drop a PDF or DOCX. We parse skills, projects, and experience.",
  },
  {
    n: "02",
    icon: <Target className="h-5 w-5" />,
    title: "Add a target role",
    body: "Tell us the role, locations, and seniority. We build a job search plan.",
  },
  {
    n: "03",
    icon: <Bot className="h-5 w-5" />,
    title: "Agents go to work",
    body: "Resume tailoring, job search, application drafts — all in parallel.",
  },
  {
    n: "04",
    icon: <CheckCheck className="h-5 w-5" />,
    title: "Approve and send",
    body: "You stay in the loop. Every email and apply goes through your approval.",
  },
];

export function HowItWorks() {
  return (
    <section id="how" className="relative overflow-hidden bg-background py-28">
      <div className="absolute inset-x-0 top-1/2 h-px bg-gradient-to-r from-transparent via-primary/25 to-transparent" />
      <div className="mx-auto max-w-6xl px-6">
        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: "-80px" }}
          variants={stagger}
          className="mb-14 max-w-2xl"
        >
          <motion.div
            variants={fadeUp}
            className="inline-flex rounded-full border border-border bg-card/70 px-3 py-1 text-xs font-medium uppercase tracking-[0.22em] text-primary"
          >
            AI Workflow
          </motion.div>
          <motion.h2
            variants={fadeUp}
            className="mt-2 text-4xl font-medium text-foreground md:text-5xl"
          >
            From resume to interview in one controlled flow.
          </motion.h2>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: "-60px" }}
          variants={stagger}
          className="relative grid gap-4 md:grid-cols-2 lg:grid-cols-4"
        >
          {STEPS.map((s) => (
            <motion.div
              key={s.n}
              variants={fadeUp}
              className="group relative overflow-hidden rounded-[2rem] border border-border/80 bg-card/70 p-7 shadow-[0_24px_90px_hsl(var(--background)/0.28)] backdrop-blur-xl transition hover:-translate-y-1 hover:border-primary/30"
            >
              <div className="absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-primary/55 to-transparent opacity-0 transition group-hover:opacity-100" />
              <div className="mb-4 flex items-center gap-2">
                <span className="rounded-full border border-primary/20 bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                  {s.n}
                </span>
              </div>
              <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                {s.icon}
              </div>
              <div className="text-lg font-medium text-foreground">{s.title}</div>
              <p className="mt-2 text-sm text-muted-foreground">{s.body}</p>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
