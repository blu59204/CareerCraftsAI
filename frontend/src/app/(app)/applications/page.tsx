"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  ArrowSquareOut,
  ArrowsLeftRight,
  Briefcase,
  CaretDown,
  Export,
  FileCsv,
  MagnifyingGlass,
  Rows,
  SquaresFour,
  Table,
  Tray,
  WarningCircle,
  X,
} from "@phosphor-icons/react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { APP_STAGES, ApplicationKanban, ApplicationList, type ApplicationItem, type AppStage } from "@/components/apps/ApplicationKanban";
import { ApplicationDrawer } from "@/components/apps/ApplicationDrawer";
import {
  Bezel,
  EmptyPanel,
  IconButton,
  IslandButton,
  IslandLink,
  Input,
  PageHero,
  Reveal,
  SPRING_SOFT,
  Screen,
  Segmented,
  Section,
  Skeleton,
  StatStrip,
} from "@/components/vanguard";
import { apiClient } from "@/lib/api";

type AgentRun = {
  id: string;
  agent_type: string;
  status: string;
  started_at: string;
  output_summary?: string;
};

type ApplicationRecord = {
  id: string;
  company: string;
  role: string;
  location: string | null;
  job_url: string | null;
  jd_text: string | null;
  match_score: number | null;
  status: AppStage;
  applied_at: string | null;
  followup_day5: string | null;
  followup_day12: string | null;
  notes: string | null;
  source: string | null;
  resume_label: string | null;
  outreach_status: string | null;
  outreach_to: string | null;
};

function nextFollowUp(application: ApplicationRecord): string | undefined {
  const next = [application.followup_day5, application.followup_day12]
    .filter((date): date is string => !!date && new Date(date).getTime() > Date.now())
    .sort()[0];
  return next ? new Date(next).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : undefined;
}

export default function ApplicationsPage() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [search, setSearch] = useState("");
  const [view, setView] = useState<"list" | "board">("list");

  const { data: items = [], isLoading, isError, refetch } = useQuery<ApplicationItem[]>({
    queryKey: ["applications"],
    queryFn: async () => {
      const { data } = await apiClient.get<ApplicationRecord[]>("/jobs/applications");
      return data.map((application) => ({
        id: String(application.id),
        company: application.company,
        role: application.role,
        location: application.location,
        jobUrl: application.job_url,
        jobDescription: application.jd_text,
        matchPercent: application.match_score,
        stage: application.status,
        appliedAt: application.applied_at,
        nextFollowUp: nextFollowUp(application),
        notes: application.notes,
        source: application.source,
        resumeLabel: application.resume_label,
        outreachStatus: application.outreach_status,
        outreachTo: application.outreach_to,
      }));
    },
  });

  const { data: activityRuns = [] } = useQuery<AgentRun[]>({
    queryKey: ["agent-runs", selectedId],
    enabled: !!selectedId,
    queryFn: async () => {
      const { data } = await apiClient.get("/agents/runs", { params: { application_id: selectedId, limit: 10 } });
      return (Array.isArray(data) ? data : data.runs ?? []) as AgentRun[];
    },
  });

  const statusMutation = useMutation({
    mutationFn: async ({ id, newStage }: { id: string; newStage: AppStage }) => {
      await apiClient.patch(`/jobs/applications/${id}/status`, { status: newStage });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["applications"] });
      toast.success("Status updated");
    },
    onError: () => toast.error("Could not update the application status"),
  });

  const selected = items.find((item) => item.id === selectedId) ?? null;
  const filteredItems = items.filter((item) =>
    `${item.company} ${item.role} ${item.location ?? ""}`.toLowerCase().includes(search.trim().toLowerCase())
  );
  const activeCount = items.filter((item) => ["applied", "viewed", "interview"].includes(item.stage)).length;
  const interviewCount = items.filter((item) => item.stage === "interview").length;
  const offerCount = items.filter((item) => item.stage === "offer").length;

  const exportToCSV = () => {
    const csvCell = (value: string | number | null | undefined) =>
      `"${String(value ?? "").replace(/"/g, '""')}"`;
    const headers = ["Company", "Role", "Location", "Source", "Match %", "Stage", "Next follow-up"];
    const rows = items.map((item) => [
      item.company, item.role, item.location, item.jobUrl, item.matchPercent, item.stage, item.nextFollowUp,
    ]);
    const csv = [headers, ...rows].map((row) => row.map(csvCell).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "applications.csv";
    anchor.click();
    URL.revokeObjectURL(url);
    setShowExportMenu(false);
  };

  const openSheets = () => {
    window.open("https://sheets.new", "_blank", "noopener,noreferrer");
    setShowExportMenu(false);
  };

  const boardStatus = isLoading
    ? "Loading your board…"
    : isError
      ? "Board unavailable"
      : search
        ? `${filteredItems.length} matching ${filteredItems.length === 1 ? "role" : "roles"}`
        : `${items.length} ${items.length === 1 ? "role" : "roles"} across ${APP_STAGES.length} stages`;

  return (
    <Screen>
      <PageHero
        eyebrow="Your job search"
        title="Application tracker"
        description="Your pipeline, from saved role to signed offer. Keep the next step in sight."
        className="pb-0 md:pb-0"
        actions={
          <>
            <IslandLink href="/jobs" tone="ghost" size="md" icon={<Briefcase size={16} weight="light" />} trailing>
              Find roles
            </IslandLink>
          </>
        }
      />

      <StatStrip
        items={[
          { label: "All roles", value: items.length },
          { label: "In progress", value: activeCount },
          { label: "Interviews", value: interviewCount },
          { label: "Offers", value: offerCount },
        ]}
      />

      <Section aria-label="Applications by stage" className="space-y-5 md:space-y-5">
        <h2 className="sr-only">Applications by stage</h2>

        <Bezel size="md" coreClassName="flex min-w-0 flex-wrap items-center gap-3 p-3">
          <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search company or role" aria-label="Search applications" trayClassName="w-full sm:flex-1 sm:min-w-[12rem]" leading={<MagnifyingGlass size={16} weight="light" />} trailing={search ? <IconButton size="sm" aria-label="Clear search" onClick={() => setSearch("")}><X size={13} weight="light" /></IconButton> : undefined} />
          <Segmented value={view} onChange={setView} asTabs={false} ariaLabel="Application view" size="sm" options={[{ value: "list", label: "List", icon: <Rows size={14} /> }, { value: "board", label: "Board", icon: <SquaresFour size={14} /> }]} />
          <ExportMenu open={showExportMenu} onOpenChange={setShowExportMenu} onDownloadCsv={exportToCSV} onOpenSheets={openSheets} />
        </Bezel>

        <Reveal subtle className="flex flex-wrap items-center justify-between gap-3">
          <p aria-live="polite" className="flex items-center gap-2 pl-1 text-[13px] text-muted-foreground">
            <ArrowsLeftRight size={15} weight="light" aria-hidden />
            <span className="tabular-nums">{boardStatus}</span>
          </p>
          <span className="text-xs text-muted-foreground">{view === "board" ? "Drag roles to update their stage" : "Select a role to view details"}</span>
        </Reveal>

        {isLoading && view === "list" ? (
          <Bezel size="md" aria-busy="true" aria-label="Loading applications" coreClassName="space-y-3 p-4">
            {Array.from({ length: 5 }).map((_, index) => <Skeleton key={index} className="h-16 w-full rounded-xl" />)}
          </Bezel>
        ) : isLoading ? (
          <div aria-busy="true" aria-label="Loading applications" className="flex gap-4 overflow-hidden p-1">
            {APP_STAGES.map((stage) => (
              <Bezel key={stage} size="md" tone="muted" className="w-[17.25rem] shrink-0 md:w-[18.5rem]" coreClassName="min-h-[24rem] space-y-2.5 p-2.5">
                <Skeleton className="mx-2 mb-3 mt-2 h-4 w-24 rounded-full" />
                <Skeleton className="h-28 rounded-[1.15rem]" />
                <Skeleton className="h-24 rounded-[1.15rem]" />
              </Bezel>
            ))}
          </div>
        ) : isError ? (
          <Reveal>
            <Bezel role="alert" coreClassName="px-4">
              <EmptyPanel
                icon={<WarningCircle size={24} weight="light" />}
                title="Could not load your applications."
                description="The board could not reach the server. Your saved roles are safe."
                action={
                  <IslandButton tone="ghost" size="sm" onClick={() => refetch()}>
                    Try again
                  </IslandButton>
                }
              />
            </Bezel>
          </Reveal>
        ) : items.length === 0 ? (
          <Reveal>
            <Bezel coreClassName="px-4">
              <EmptyPanel
                icon={<Tray size={24} weight="light" />}
                title="Your tracker is ready"
                description="Save a job from the Jobs page to keep its posting and description here."
                action={
                  <IslandLink href="/jobs" size="md" trailing>
                    Explore jobs
                  </IslandLink>
                }
              />
            </Bezel>
          </Reveal>
        ) : filteredItems.length === 0 ? (
          <Bezel><EmptyPanel compact title="No matching applications" description="Try another company or role." action={<IslandButton tone="ghost" size="sm" onClick={() => setSearch("")}>Clear search</IslandButton>} /></Bezel>
        ) : view === "list" ? (
          <ApplicationList items={filteredItems} onSelect={setSelectedId} onStageChange={(id, newStage) => statusMutation.mutate({ id, newStage })} />
        ) : (
          <ApplicationKanban
            items={filteredItems}
            onSelect={setSelectedId}
            onStageChange={(id, newStage) => statusMutation.mutate({ id, newStage })}
            emptyColumnLabel={search ? "No matching roles" : "No roles yet"}
          />
        )}
      </Section>

      <ApplicationDrawer
        application={selected}
        open={selected !== null}
        onClose={() => setSelectedId(null)}
        onStageChange={(stage) => selected && statusMutation.mutate({ id: selected.id, newStage: stage })}
        activityRuns={activityRuns}
      />
    </Screen>
  );
}

/** Export trigger with a floating Double-Bezel popover (CSV download / Google Sheets). */
function ExportMenu({
  open,
  onOpenChange,
  onDownloadCsv,
  onOpenSheets,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDownloadCsv: () => void;
  onOpenSheets: () => void;
}) {
  const rootRef = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const reduce = useReducedMotion();

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) onOpenChange(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onOpenChange(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onOpenChange]);

  const options = [
    { key: "csv", label: "Download CSV", hint: "Every role on the board as a file", icon: <FileCsv size={17} weight="light" />, onClick: onDownloadCsv, trailing: null },
    { key: "sheets", label: "Open Sheets", hint: "Start a blank Google Sheet", icon: <Table size={17} weight="light" />, onClick: onOpenSheets, trailing: <ArrowSquareOut size={13} weight="light" /> },
  ];

  return (
    <div ref={rootRef} className="relative">
      <IslandButton
        tone="ghost"
        size="sm"
        icon={<Export size={15} weight="light" />}
        trailing={
          <CaretDown
            size={12}
            weight="light"
            className={cn("transition-transform duration-500 ease-vanguard", open && "rotate-180")}
          />
        }
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => onOpenChange(!open)}
      >
        Export
      </IslandButton>

      <AnimatePresence>
        {open ? (
          <motion.div
            id={menuId}
            initial={reduce ? { opacity: 0 } : { opacity: 0, y: -6, scale: 0.97 }}
            animate={reduce ? { opacity: 1 } : { opacity: 1, y: 0, scale: 1 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, y: -4, scale: 0.98 }}
            transition={reduce ? { duration: 0.15 } : SPRING_SOFT}
            className="absolute right-0 top-full z-20 mt-3 w-[min(17rem,calc(100vw-3rem))] origin-top-right"
          >
            <Bezel size="md" lifted coreClassName="p-1.5">
              <ul className="space-y-0.5">
                {options.map((option) => (
                  <li key={option.key}>
                    <button
                      type="button"
                      onClick={option.onClick}
                      className="group flex w-full items-center gap-3 rounded-[1rem] px-3 py-2.5 text-left transition-colors duration-500 ease-vanguard hover:bg-foreground/[0.04] focus-visible:bg-foreground/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:hover:bg-white/[0.05] dark:focus-visible:bg-white/[0.05]"
                    >
                      <span aria-hidden className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-foreground/[0.04] text-foreground/80 ring-1 ring-foreground/[0.06] dark:bg-white/[0.05] dark:ring-white/10">
                        {option.icon}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-medium text-foreground">{option.label}</span>
                        <span className="block truncate text-xs text-muted-foreground">{option.hint}</span>
                      </span>
                      {option.trailing ? (
                        <span aria-hidden className="text-muted-foreground transition-transform duration-500 ease-vanguard group-hover:-translate-y-[1px] group-hover:translate-x-0.5">
                          {option.trailing}
                        </span>
                      ) : null}
                    </button>
                  </li>
                ))}
              </ul>
            </Bezel>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
