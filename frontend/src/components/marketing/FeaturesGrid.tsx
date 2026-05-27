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
  },
  {
    icon: <Bot className="h-5 w-5" />,
    title: "AI Orchestrator",
    description: "A supervisor agent routes tasks across Resume, Job, Email, and Follow-up agents.",
  },
  {
    icon: <Target className="h-5 w-5" />,
    title: "Job Match",
    description: "Semantic search over LinkedIn, Naukri, and curated boards with match percentages.",
  },
  {
    icon: <KanbanSquare className="h-5 w-5" />,
    title: "Application Tracker",
    description: "Kanban board for every stage: Saved → Applied → Interview → Offer.",
  },
  {
    icon: <Mail className="h-5 w-5" />,
    title: "Email Drafts",
    description: "Gmail-connected agent drafts personalized follow-ups — you stay in control.",
  },
  {
    icon: <KeyRound className="h-5 w-5" />,
    title: "BYOK Models",
    description: "OpenAI, Anthropic, Gemini, Groq, Ollama. Your keys, your costs, your privacy.",
  },
];

export function FeaturesGrid() {
  return (
    <section id="features" className="bg-background py-28">
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
            Features
          </motion.div>
          <motion.h2
            variants={fadeUp}
            className="mt-2 text-4xl font-medium text-foreground md:text-5xl"
          >
            Everything you need to land your first role.
          </motion.h2>
          <motion.p
            variants={fadeUp}
            className="mt-4 text-base text-muted-foreground"
          >
            Purpose-built agents handle every step of your job search, from tailoring resumes to drafting follow-ups.
          </motion.p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: "-60px" }}
          variants={stagger}
          className="grid gap-6 md:grid-cols-2 lg:grid-cols-3"
        >
          {FEATURES.map((f) => (
            <FeatureCard key={f.title} {...f} />
          ))}
        </motion.div>
      </div>
    </section>
  );
}
