"use client";

import { motion } from "motion/react";
import { Check } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { Bezel } from "@/components/vanguard/Bezel";
import { IslandButton } from "@/components/vanguard/IslandButton";
import { SectionHeading } from "@/components/vanguard/PageHero";
import { listItem, listStagger } from "@/components/vanguard/motion";

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
    accent: "bg-success",
  },
  {
    id: "minimal",
    name: "Minimal Compact",
    description: "Clean single-page design for senior candidates with focused content.",
    atsScore: 94,
    sections: ["Contact", "Skills", "Experience", "Education"],
    accent: "bg-muted-foreground",
  },
];

type Props = {
  selected: string;
  onSelect: (id: string) => void;
};

function TemplateMiniPreview({ accent }: { accent: string }) {
  return (
    <div aria-hidden="true" className="h-48 w-full overflow-hidden rounded-[1rem] bg-background p-4 ring-1 ring-foreground/[0.06] dark:ring-white/10">
      <div className="space-y-1">
        <div className="h-3 w-2/3 rounded bg-foreground/80" />
        <div className="h-2 w-1/2 rounded bg-muted-foreground/40" />
      </div>
      <div className={cn("my-3 h-0.5 w-full rounded", accent)} />
      <div className="mb-3 space-y-1">
        <div className="h-1.5 w-16 rounded bg-muted-foreground/50" />
        <div className="h-2 w-full rounded bg-muted/80" />
        <div className="h-2 w-4/5 rounded bg-muted/60" />
      </div>
      <div className="mb-3 space-y-1">
        <div className="h-1.5 w-20 rounded bg-muted-foreground/50" />
        <div className="h-2 w-full rounded bg-primary/30" />
        <div className="h-2 w-3/4 rounded bg-primary/20" />
        <div className="h-2 w-5/6 rounded bg-primary/20" />
      </div>
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
    <div className="space-y-8">
      <SectionHeading
        eyebrow="Templates"
        title="Choose a template."
        description="All templates are single-column and optimised for Applicant Tracking Systems."
      />

      <motion.ul initial="hidden" animate="show" variants={listStagger} className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
        {TEMPLATES.map((tpl) => {
          const isSelected = selected === tpl.id;
          return (
            <motion.li key={tpl.id} variants={listItem}>
              <Bezel tone={isSelected ? "primary" : "default"} coreClassName="flex h-full flex-col p-5">
                <TemplateMiniPreview accent={tpl.accent} />

                <div className="mt-5 flex items-start justify-between gap-3">
                  <h3 className="font-geist text-[15px] font-semibold tracking-[-0.015em] text-foreground">{tpl.name}</h3>
                  <span className="shrink-0 rounded-full bg-success/10 px-2 py-0.5 text-[11px] font-medium tabular-nums text-success ring-1 ring-success/20">
                    ATS: {tpl.atsScore}%
                  </span>
                </div>

                <p className="mt-2 text-sm leading-6 text-muted-foreground">{tpl.description}</p>

                <ul className="mt-4 flex flex-wrap gap-1">
                  {tpl.sections.map((sec) => (
                    <li
                      key={sec}
                      className="rounded-full bg-foreground/[0.03] px-2 py-0.5 text-[11px] text-muted-foreground ring-1 ring-foreground/[0.06] dark:bg-white/[0.04] dark:ring-white/10"
                    >
                      {sec}
                    </li>
                  ))}
                </ul>

                <div className="mt-auto flex items-center justify-between pt-5">
                  <span className="text-xs tabular-nums text-muted-foreground">{tpl.sections.length} sections</span>
                  <IslandButton
                    tone={isSelected ? "ghost" : "primary"}
                    size="sm"
                    onClick={() => onSelect(tpl.id)}
                    aria-pressed={isSelected}
                    icon={isSelected ? <Check size={14} weight="light" /> : undefined}
                  >
                    {isSelected ? "Selected ✓" : "Select"}
                  </IslandButton>
                </div>
              </Bezel>
            </motion.li>
          );
        })}
      </motion.ul>
    </div>
  );
}
