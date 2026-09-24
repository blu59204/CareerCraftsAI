"use client";

import { FileText, Bot, Target, KanbanSquare, Mail, KeyRound } from "lucide-react";
import { FeatureCard } from "@/components/ui/FeatureCard";
import { motion } from "motion/react";
import { fadeUp, stagger } from "@/lib/motion-variants";

const FEATURES = [
  {
    icon: <FileText className="h-5 w-5" />,
    title: "Resume Intelligence",
    description: "ATS scoring, keyword coverage, and bullet rewrites tailored to each job.",
    // Anchor tile: tall, spans two rows.
    span: "md:col-span-2 lg:col-span-2 lg:row-span-2",
  },
  {
    icon: <Bot className="h-5 w-5" />,
    title: "AI Orchestrator",
    description: "A supervisor agent routes tasks across Resume, Job, Email, and Follow-up agents.",
    span: "md:col-span-2 lg:col-span-2",
  },
  {
    icon: <Target className="h-5 w-5" />,
    title: "Job Match",
    description: "Semantic search over LinkedIn, Naukri, and curated boards with match percentages.",
    span: "lg:col-span-1",
  },
  {
    icon: <KanbanSquare className="h-5 w-5" />,
    title: "Application Tracker",
    description: "Kanban board for every stage: Saved → Applied → Interview → Offer.",
    span: "lg:col-span-1",
  },
  {
    icon: <Mail className="h-5 w-5" />,
    title: "Email Drafts",
    description: "Gmail-connected agent drafts personalized follow-ups — you stay in control.",
    span: "md:col-span-2 lg:col-span-2",
  },
  {
    icon: <KeyRound className="h-5 w-5" />,
    title: "BYOK Models",
    description: "OpenAI, Anthropic, Gemini, Groq, Ollama. Your keys, your costs, your privacy.",
    span: "md:col-span-2 lg:col-span-2",
  },
];

export function FeaturesGrid() {
  return (
    <section id="features" className="relative overflow-hidden bg-background py-28 text-foreground">
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
            className="inline-flex rounded-full border border-border bg-muted px-3 py-1 text-xs font-medium uppercase tracking-[0.22em] text-muted-foreground"
          >
            AI Automation
          </motion.div>
          <motion.h2
            variants={fadeUp}
            className="mt-5 max-w-3xl text-4xl font-medium leading-tight text-foreground md:text-6xl"
          >
            Everything you need to land your first role.
          </motion.h2>
          <motion.p
            variants={fadeUp}
            className="mt-5 max-w-xl text-base leading-8 text-muted-foreground"
          >
            Purpose-built agents handle every step of your job search, from tailoring resumes to drafting follow-ups.
          </motion.p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: "-60px" }}
          variants={stagger}
          className="grid gap-4 md:grid-cols-4 lg:grid-cols-4"
        >
          {FEATURES.map(({ span, ...f }) => (
            <motion.div key={f.title} variants={fadeUp} className={span}>
              <FeatureCard {...f} className="h-full" />
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
