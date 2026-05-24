"use client";

import { motion } from "motion/react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";

type ResumeTemplate = {
  id: string;
  name: string;
  description: string;
  atsScore: number;
  sections: string[];
  accent: string;
};

const TEMPLATES: ResumeTemplate[] = [
  {
    id: "modern",
    name: "Clean Modern",
    description: "Balanced layout with a skills-first approach. Ideal for tech roles.",
    atsScore: 96,
    sections: ["Contact", "Summary", "Skills", "Experience", "Education", "Projects"],
    accent: "bg-primary",
  },
  {
    id: "classic",
    name: "Classic Chronological",
    description: "Traditional reverse-chronological format trusted by all ATS systems.",
    atsScore: 99,
    sections: ["Contact", "Summary", "Experience", "Education", "Skills"],
    accent: "bg-emerald-500",
  },
  {
    id: "minimal",
    name: "Minimal Compact",
    description: "Clean single-page design for senior candidates with focused content.",
    atsScore: 94,
    sections: ["Contact", "Skills", "Experience", "Education"],
    accent: "bg-slate-600",
  },
];

type Props = {
  selected: string;
  onSelect: (id: string) => void;
};

function TemplateMiniPreview({ accent }: { accent: string }) {
  return (
    <div className="h-48 w-full overflow-hidden rounded-2xl border border-border bg-background p-4">
      {/* Header area */}
      <div className="space-y-1">
        <div className="h-3 w-2/3 rounded bg-foreground/80" />
        <div className="h-2 w-1/2 rounded bg-muted-foreground/40" />
      </div>
      {/* Accent divider */}
      <div className={`my-3 h-0.5 w-full rounded ${accent}`} />
      {/* Section 1 */}
      <div className="mb-3 space-y-1">
        <div className="h-1.5 w-16 rounded bg-muted-foreground/50" />
        <div className="h-2 w-full rounded bg-muted/80" />
        <div className="h-2 w-4/5 rounded bg-muted/60" />
      </div>
      {/* Section 2 */}
      <div className="mb-3 space-y-1">
        <div className="h-1.5 w-20 rounded bg-muted-foreground/50" />
        <div className="h-2 w-full rounded bg-primary/30" />
        <div className="h-2 w-3/4 rounded bg-primary/20" />
        <div className="h-2 w-5/6 rounded bg-primary/20" />
      </div>
      {/* Section 3 */}
      <div className="space-y-1">
        <div className="h-1.5 w-14 rounded bg-muted-foreground/50" />
        <div className="h-2 w-full rounded bg-muted/70" />
        <div className="h-2 w-2/3 rounded bg-muted/50" />
      </div>
    </div>
  );
}

export function ResumeTemplates({ selected, onSelect }: Props) {
  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-4">
      <motion.div variants={fadeUp}>
        <div className="text-sm text-muted-foreground">Resume Workspace · Templates</div>
        <h2 className="mt-1 text-xl font-medium">Choose a template.</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          All templates are single-column and optimised for Applicant Tracking Systems.
        </p>
      </motion.div>

      <motion.div variants={fadeUp} className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {TEMPLATES.map((tpl) => {
          const isSelected = selected === tpl.id;
          return (
            <motion.div
              key={tpl.id}
              variants={fadeUp}
              className={`rounded-3xl border p-6 transition-colors ${
                isSelected
                  ? "border-primary bg-primary/5"
                  : "border-border bg-card/60"
              }`}
            >
              <TemplateMiniPreview accent={tpl.accent} />

              <div className="mt-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{tpl.name}</span>
                  <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-600">
                    ATS: {tpl.atsScore}%
                  </span>
                </div>

                <p className="text-sm text-muted-foreground">{tpl.description}</p>

                <div className="flex flex-wrap gap-1">
                  {tpl.sections.map((sec) => (
                    <span
                      key={sec}
                      className="rounded-full border border-border bg-muted/40 px-2 py-0.5 text-xs text-muted-foreground"
                    >
                      {sec}
                    </span>
                  ))}
                </div>

                <div className="flex items-center justify-between pt-1">
                  <span className="text-xs text-muted-foreground">
                    {tpl.sections.length} sections
                  </span>
                  <LiquidGlassButton
                    tone={isSelected ? "ghost" : "primary"}
                    size="sm"
                    onClick={() => onSelect(tpl.id)}
                    aria-pressed={isSelected}
                  >
                    {isSelected ? "Selected ✓" : "Select"}
                  </LiquidGlassButton>
                </div>
              </div>
            </motion.div>
          );
        })}
      </motion.div>
    </motion.div>
  );
}
