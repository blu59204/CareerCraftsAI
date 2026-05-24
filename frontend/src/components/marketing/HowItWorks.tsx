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
    <section id="how" className="relative bg-muted/30 py-28">
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
            className="text-sm font-medium text-primary"
          >
            How it works
          </motion.div>
          <motion.h2
            variants={fadeUp}
            className="mt-2 text-4xl font-medium text-foreground md:text-5xl"
          >
            From resume to interview in 4 steps.
          </motion.h2>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: "-60px" }}
          variants={stagger}
          className="grid gap-6 md:grid-cols-2 lg:grid-cols-4"
        >
          {STEPS.map((s) => (
            <motion.div
              key={s.n}
              variants={fadeUp}
              className="rounded-3xl border border-border bg-card/60 p-8 hover:shadow-md transition-shadow"
            >
              <div className="mb-4 flex items-center gap-2">
                <span className="text-xs font-medium text-primary bg-primary/10 rounded-full px-2 py-0.5">
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
