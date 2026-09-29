"use client";

import { useState, type DragEvent } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Download, ExternalLink, Inbox, Search, Share2, X } from "lucide-react";
import { toast } from "sonner";
import { fadeUp, stagger } from "@/lib/motion-variants";
import type { ApplicationItem, AppStage } from "@/components/apps/ApplicationKanban";
import { ApplicationDrawer } from "@/components/apps/ApplicationDrawer";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { CommandHeader } from "@/components/immersive/CommandHeader";
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
};

const STAGES: AppStage[] = ["saved", "applied", "viewed", "interview", "offer", "rejected"];
const STAGE_LABELS: Record<AppStage, string> = {
  saved: "Saved",
  applied: "Applied",
  viewed: "Viewed",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
};

function nextFollowUp(application: ApplicationRecord): string | undefined {
  const next = [application.followup_day5, application.followup_day12]
    .filter((date): date is string => !!date && new Date(date).getTime() > Date.now())
    .sort()[0];
  return next ? new Date(next).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : undefined;
}

function sourceLabel(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    if (!["http:", "https:"].includes(parsed.protocol)) return null;
    return parsed.hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

export default function ApplicationsPage() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [dragOverStage, setDragOverStage] = useState<AppStage | null>(null);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [search, setSearch] = useState("");

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

  const handleDragStart = (event: DragEvent<HTMLButtonElement>, id: string) => {
    setDraggedId(id);
    event.dataTransfer.effectAllowed = "move";
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>, targetStage: AppStage) => {
    event.preventDefault();
    if (draggedId) {
      const item = items.find((candidate) => candidate.id === draggedId);
      if (item && item.stage !== targetStage) {
        statusMutation.mutate({ id: draggedId, newStage: targetStage });
      }
    }
    setDraggedId(null);
    setDragOverStage(null);
  };

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

  return (
    <motion.main initial="hidden" animate="show" variants={stagger} className="space-y-7">
      <motion.div variants={fadeUp}>
        <CommandHeader
          eyebrow="Your job search"
          title="Application tracker"
          description="Keep each role, its original posting, and your next step in one place."
          actions={
            <div className="flex w-full flex-wrap items-center gap-2 lg:w-auto">
              <label className="flex h-10 min-w-[15rem] flex-1 items-center gap-2 rounded-xl border border-border bg-card/70 px-3 text-muted-foreground focus-within:border-primary lg:flex-none">
                <Search className="h-4 w-4 shrink-0" />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search roles or companies"
                  aria-label="Search applications"
                  className="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                />
                {search && (
                  <button type="button" onClick={() => setSearch("")} aria-label="Clear search" className="rounded p-1 hover:text-foreground">
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </label>
              <div className="relative">
                <LiquidGlassButton tone="ghost" size="sm" onClick={() => setShowExportMenu((open) => !open)}>
                  <Share2 className="h-4 w-4" /> Export
                </LiquidGlassButton>
                {showExportMenu && (
                  <div className="absolute right-0 z-20 mt-2 w-44 overflow-hidden rounded-xl border border-border bg-card shadow-xl">
                    <button type="button" onClick={exportToCSV} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted">
                      <Download className="h-4 w-4" /> Download CSV
                    </button>
                    <button type="button" onClick={() => { window.open("https://sheets.new", "_blank", "noopener,noreferrer"); setShowExportMenu(false); }} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted">
                      <ExternalLink className="h-4 w-4" /> Open Sheets
                    </button>
                  </div>
                )}
              </div>
            </div>
          }
        />
      </motion.div>

      <motion.section variants={fadeUp} aria-label="Application overview" className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-border bg-border sm:grid-cols-4">
        {[
          { label: "All roles", value: items.length },
          { label: "In progress", value: activeCount },
          { label: "Interviews", value: interviewCount },
          { label: "Offers", value: offerCount },
        ].map((stat) => (
          <div key={stat.label} className="bg-card/80 px-5 py-4">
            <p className="text-xs text-muted-foreground">{stat.label}</p>
            <p className="mt-1 font-command text-3xl font-semibold tabular-nums text-foreground">{stat.value}</p>
          </div>
        ))}
      </motion.section>

      <motion.section variants={fadeUp} aria-label="Applications by stage">
        {isLoading ? (
          <div className="flex gap-4 overflow-hidden">
            {STAGES.map((stage) => (
              <div key={stage} className="min-w-[15rem] flex-1 space-y-3">
                <div className="h-5 w-24 animate-pulse rounded bg-muted" />
                <div className="h-32 animate-pulse rounded-xl bg-muted/60" />
              </div>
            ))}
          </div>
        ) : isError ? (
          <div className="rounded-2xl border border-border bg-card p-8 text-center">
            <p className="font-medium">Could not load your applications.</p>
            <button type="button" onClick={() => refetch()} className="mt-3 text-sm font-medium text-primary underline underline-offset-4">Try again</button>
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center rounded-2xl border border-dashed border-border bg-card/50 px-6 py-14 text-center">
            <Inbox className="h-7 w-7 text-muted-foreground" />
            <h2 className="mt-4 text-lg font-semibold">Your tracker is ready</h2>
            <p className="mt-2 max-w-sm text-sm text-muted-foreground">Save a job from the Jobs page to keep its posting and description here.</p>
            <Link href="/jobs" className="mt-5 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">Explore jobs</Link>
          </div>
        ) : (
          <>
            {search && <p className="mb-3 text-sm text-muted-foreground">{filteredItems.length} matching {filteredItems.length === 1 ? "role" : "roles"}</p>}
            <div className="flex snap-x gap-3 overflow-x-auto pb-4">
              {STAGES.map((stage) => {
                const columnItems = filteredItems.filter((item) => item.stage === stage);
                return (
                  <div
                    key={stage}
                    onDragOver={(event) => { event.preventDefault(); event.dataTransfer.dropEffect = "move"; setDragOverStage(stage); }}
                    onDragLeave={() => setDragOverStage((current) => current === stage ? null : current)}
                    onDrop={(event) => handleDrop(event, stage)}
                    className={`min-h-[17rem] min-w-[15.5rem] flex-1 snap-start rounded-2xl border p-3.5 transition-colors ${dragOverStage === stage ? "border-primary bg-primary/5" : "border-border bg-card/35"}`}
                  >
                    <div className="mb-4 flex items-center justify-between px-1">
                      <h2 className="text-sm font-semibold">{STAGE_LABELS[stage]}</h2>
                      <span className="rounded-md bg-muted px-2 py-0.5 text-xs font-medium tabular-nums text-muted-foreground">{columnItems.length}</span>
                    </div>
                    <div className="space-y-2.5">
                      {columnItems.length === 0 ? (
                        <p className="rounded-xl border border-dashed border-border/70 px-3 py-8 text-center text-xs text-muted-foreground">
                          {search ? "No matching roles" : "No roles yet"}
                        </p>
                      ) : columnItems.map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          draggable
                          onDragStart={(event) => handleDragStart(event, item.id)}
                          onDragEnd={() => { setDraggedId(null); setDragOverStage(null); }}
                          onClick={() => setSelectedId(item.id)}
                          className={`w-full cursor-grab rounded-xl border border-border/80 bg-card p-4 text-left transition-all hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary active:cursor-grabbing ${draggedId === item.id ? "opacity-50" : ""}`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <span className="min-w-0 text-xs font-medium text-muted-foreground">{item.company}</span>
                            {item.matchPercent != null && (
                              <span className="shrink-0 text-xs font-semibold tabular-nums text-primary">{item.matchPercent}%</span>
                            )}
                          </div>
                          <p className="mt-1.5 line-clamp-2 text-sm font-semibold leading-snug text-foreground">{item.role}</p>
                          {(item.location || sourceLabel(item.jobUrl)) && (
                            <p className="mt-3 truncate text-xs text-muted-foreground">
                              {[item.location, sourceLabel(item.jobUrl)].filter(Boolean).join(" · ")}
                            </p>
                          )}
                          {item.nextFollowUp && <p className="mt-2 text-xs font-medium text-primary">Follow up {item.nextFollowUp}</p>}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </motion.section>

      <ApplicationDrawer
        application={selected}
        open={selected !== null}
        onClose={() => setSelectedId(null)}
        onStageChange={(stage) => selected && statusMutation.mutate({ id: selected.id, newStage: stage })}
        activityRuns={activityRuns}
      />
    </motion.main>
  );
}
