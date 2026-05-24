"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { Upload, Download } from "lucide-react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { AtsScoreRing } from "@/components/resume/AtsScoreRing";
import { KeywordCoverage } from "@/components/resume/KeywordCoverage";
import { SuggestionsList, type Suggestion } from "@/components/resume/SuggestionsList";
import { EmptyState } from "@/components/ui/EmptyState";

// TODO Phase 4 wiring: pull from apiClient.resume.getCurrent() once endpoint is wired.
const MOCK_SUGGESTIONS: Suggestion[] = [
  {
    id: "1",
    original: "Worked on the backend team building REST APIs.",
    suggestion: "Designed and shipped 12 REST endpoints handling 4k+ daily requests; cut p95 latency from 320ms to 110ms.",
  },
  {
    id: "2",
    original: "Built a React dashboard.",
    suggestion: "Built a real-time React dashboard with TanStack Query and WebSockets, used daily by 200+ internal operators.",
  },
];

export default function ResumePage() {
  const [suggestions, setSuggestions] = useState<Suggestion[]>(MOCK_SUGGESTIONS);
  const accept = (id: string) => setSuggestions((s) => s.filter((x) => x.id !== id));
  const reject = (id: string) => setSuggestions((s) => s.filter((x) => x.id !== id));

  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
      <motion.div variants={fadeUp} className="flex items-center justify-between">
        <div>
          <div className="text-sm text-muted-foreground">Resume Workspace</div>
          <h1 className="mt-1 text-3xl font-medium">Tailor your resume.</h1>
        </div>
        <div className="flex gap-2">
          <LiquidGlassButton tone="ghost" size="sm">
            <Upload className="h-4 w-4" /> Upload
          </LiquidGlassButton>
          <LiquidGlassButton tone="primary" size="sm">
            <Download className="h-4 w-4" /> Export
          </LiquidGlassButton>
        </div>
      </motion.div>

      <motion.div variants={fadeUp} className="grid gap-6 lg:grid-cols-[300px_1fr_320px]">
        <aside className="space-y-6">
          <div className="rounded-3xl border border-border bg-card/60 p-6 text-center">
            <AtsScoreRing score={78} />
          </div>
          <KeywordCoverage
            matched={["React", "TypeScript", "Python", "FastAPI"]}
            missing={["AWS", "Docker", "CI/CD", "PostgreSQL"]}
          />
        </aside>

        <section className="rounded-3xl border border-border bg-card/40 p-6">
          <div className="text-sm text-muted-foreground">Preview</div>
          <div className="mt-3 aspect-[8.5/11] w-full overflow-hidden rounded-2xl border border-border bg-background p-8 text-sm">
            <div className="text-2xl font-medium">Your Name</div>
            <div className="mt-1 text-muted-foreground">Frontend Engineer · email@you.com · github.com/you</div>
            <div className="mt-6 text-xs uppercase tracking-wide text-muted-foreground">Experience</div>
            <p className="mt-2">Resume preview pane — bullets you accept appear here. Connect parser to populate.</p>
          </div>
        </section>

        <aside className="space-y-3">
          <div className="text-sm text-muted-foreground">AI suggestions</div>
          {suggestions.length === 0 ? (
            <EmptyState title="All suggestions reviewed" description="Re-run the Resume Agent to get more tailored bullets." />
          ) : (
            <SuggestionsList suggestions={suggestions} onAccept={accept} onReject={reject} />
          )}
        </aside>
      </motion.div>
    </motion.div>
  );
}
