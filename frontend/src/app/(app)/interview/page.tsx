"use client";

import { Suspense, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { ClockCounterClockwise, ListChecks, Microphone } from "@phosphor-icons/react";
import { Bezel, PageHero, Screen, Segmented, panelSwap } from "@/components/vanguard";
import { cn } from "@/lib/utils";
import { MockInterviewPanel } from "@/components/interview/MockInterviewPanel";
import { InterviewHistoryPanel } from "@/components/interview/InterviewHistoryPanel";
import { PrepPlanPanel } from "@/components/interview/PrepPlanPanel";
import { InterviewBodySkeleton } from "@/components/interview/InterviewSkeleton";

type InterviewTab = "prep" | "coach" | "history";

function parseTab(value: string | null): InterviewTab {
  return value === "coach" || value === "history" ? value : "prep";
}

const TAB_OPTIONS: ReadonlyArray<{ value: InterviewTab; label: string; icon: React.ReactNode }> = [
  { value: "prep", label: "Prep plan", icon: <ListChecks size={15} weight="light" /> },
  { value: "coach", label: "Mock interview", icon: <Microphone size={15} weight="light" /> },
  { value: "history", label: "History", icon: <ClockCounterClockwise size={15} weight="light" /> },
];

const RHYTHM: ReadonlyArray<{ step: string; title: string; body: string; tab: InterviewTab }> = [
  { step: "01", title: "Plan", body: "Build a role-specific question bank", tab: "prep" },
  { step: "02", title: "Rehearse", body: "Shape answers with STAR stories", tab: "prep" },
  { step: "03", title: "Perform", body: "Run a scored live session", tab: "coach" },
];

/** Hero aside: the three-beat prep rhythm, highlighting the active mode. */
function RhythmAside({ tab }: { tab?: InterviewTab }) {
  return (
    <Bezel size="md" className="hidden lg:block" coreClassName="p-2">
      <ol className="space-y-1">
        {RHYTHM.map((item) => {
          const active = tab === item.tab;
          return (
            <li
              key={item.step}
              className={cn(
                "flex items-center gap-4 rounded-[1rem] px-4 py-3 transition-colors duration-500 ease-vanguard",
                active ? "bg-primary/[0.07]" : "bg-transparent",
              )}
            >
              <span className={cn("font-geist-mono text-[11px] tabular-nums", active ? "text-primary" : "text-muted-foreground/70")}>{item.step}</span>
              <div className="min-w-0">
                <p className="text-sm font-semibold tracking-[-0.01em] text-foreground">{item.title}</p>
                <p className="truncate text-xs text-muted-foreground">{item.body}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </Bezel>
  );
}

function InterviewHero({ actions, tab }: { actions?: React.ReactNode; tab?: InterviewTab }) {
  return (
    <PageHero
      eyebrow="Interview studio"
      title="Interview Coach"
      accent="Practice makes perfect."
      description="Generate a role-specific prep plan, rehearse with STAR stories, then run a live session with score-backed feedback."
      actions={actions}
      aside={<RhythmAside tab={tab} />}
      className="pb-8 md:pb-10"
    />
  );
}

/**
 * Reads ?tab=prep|coach (default prep). Local state gives an instant swap;
 * the URL is kept in sync with router.replace (no scroll) and external URL
 * changes (back/forward, links) are adopted during render.
 */
function InterviewWorkspace() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const urlTab = parseTab(searchParams.get("tab"));
  const [tab, setTab] = useState<InterviewTab>(urlTab);
  const [syncedUrlTab, setSyncedUrlTab] = useState<InterviewTab>(urlTab);
  if (urlTab !== syncedUrlTab) {
    setSyncedUrlTab(urlTab);
    setTab(urlTab);
  }

  const selectTab = (next: InterviewTab) => {
    if (next === tab) return;
    setTab(next);
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", next);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  };

  return (
    <div>
      <InterviewHero
        tab={tab}
        actions={
          <Segmented<InterviewTab>
            ariaLabel="Interview mode"
            value={tab}
            onChange={selectTab}
            options={TAB_OPTIONS}
          />
        }
      />
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={tab}
          role="tabpanel"
          aria-label={tab === "prep" ? "Prep plan" : tab === "coach" ? "Mock interview" : "History"}
          variants={panelSwap}
          initial="hidden"
          animate="show"
          exit="exit"
        >
          {tab === "prep" ? <PrepPlanPanel /> : tab === "coach" ? <MockInterviewPanel /> : <InterviewHistoryPanel />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

export default function InterviewPage() {
  return (
    <Screen>
      <Suspense
        fallback={
          <div>
            <InterviewHero />
            <InterviewBodySkeleton />
          </div>
        }
      >
        <InterviewWorkspace />
      </Suspense>
    </Screen>
  );
}
