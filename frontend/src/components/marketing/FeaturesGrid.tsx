import { FileText, Bot, Target, KanbanSquare, Mail, KeyRound } from "lucide-react";
import { FeatureCard } from "@/components/ui/FeatureCard";

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
    <section id="features" className="bg-[#0a0a0a] py-28 text-white">
      <div className="mx-auto max-w-6xl px-6">
        <div className="mb-14 max-w-2xl">
          <div className="text-sm text-white/50">Features</div>
          <h2 className="mt-2 text-4xl font-medium md:text-5xl">
            Everything you need to land your first role.
          </h2>
        </div>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <FeatureCard key={f.title} {...f} />
          ))}
        </div>
      </div>
    </section>
  );
}
