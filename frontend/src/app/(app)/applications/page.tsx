"use client";

import { useState, type DragEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { ApplicationKanban, type ApplicationItem, type AppStage } from "@/components/apps/ApplicationKanban";
import { ApplicationDrawer } from "@/components/apps/ApplicationDrawer";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { Download, FileText, ExternalLink, Share2, Sparkles, Clock } from "lucide-react";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";

type AgentRun = {
  id: string;
  agent_type: string;
  status: string;
  created_at: string;
  output_summary?: string;
};

const STAGES: AppStage[] = ["saved", "applied", "viewed", "interview", "offer", "rejected"];

export default function ApplicationsPage() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [showExportMenu, setShowExportMenu] = useState(false);

  const { data: items = [], isLoading } = useQuery<ApplicationItem[]>({
    queryKey: ["applications"],
    queryFn: async () => {
      const { data } = await apiClient.get("/jobs/applications");
      return (data as any[]).map((a) => ({
        id: String(a.id),
        company: a.company,
        role: a.role,
        matchPercent: a.match_score ?? 0,
        stage: a.status as AppStage,
        nextFollowUp: undefined,
      }));
    },
  });

  const { data: activityRuns = [] } = useQuery<AgentRun[]>({
    queryKey: ["agent-runs", selectedId],
    enabled: !!selectedId,
    queryFn: async () => {
      const { data } = await apiClient.get(`/agents/runs`, { params: { application_id: selectedId, limit: 10 } });
      return data as AgentRun[];
    },
  });

  const statusMutation = useMutation({
    mutationFn: async ({ id, newStage }: { id: string; newStage: string }) => {
      await apiClient.patch(`/jobs/applications/${id}/status`, { status: newStage });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["applications"] });
      toast.success("Status updated");
    },
    onError: () => toast.error("Failed to update status"),
  });

  const selected = items.find((i) => i.id === selectedId) ?? null;

  // HTML5 drag-and-drop handlers
  const handleDragStart = (e: DragEvent, id: string) => {
    setDraggedId(id);
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  };

  const handleDrop = (e: DragEvent, targetStage: AppStage) => {
    e.preventDefault();
    if (draggedId) {
      const item = items.find((i) => i.id === draggedId);
      if (item && item.stage !== targetStage) {
        statusMutation.mutate({ id: draggedId, newStage: targetStage });
      }
    }
    setDraggedId(null);
  };

  const getAISuggestion = (stage: AppStage) => {
    if (stage === "interview") return { label: "Launch Interview Coach", agent: "interview_prep" };
    if (stage === "offer") return { label: "Launch Salary Agent", agent: "salary_negotiation" };
    return null;
  };

  const exportToCSV = () => {
    const headers = ["Company", "Role", "Match %", "Stage", "Next Follow-up"];
    const rows = items.map((i) => [i.company, i.role, `${i.matchPercent}%`, i.stage, i.nextFollowUp ?? "—"]);
    const csv = [headers, ...rows].map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "applications.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const openSheetsExport = () => window.open("https://sheets.new", "_blank");

  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-6">
      <motion.div variants={fadeUp} className="flex items-center justify-between">
        <div>
          <div className="text-sm text-muted-foreground">Pipeline</div>
          <h1 className="mt-1 text-3xl font-medium">Applications</h1>
        </div>
        <div className="flex gap-2">
          <input
            placeholder="Filter by company or role…"
            className="h-10 rounded-full border border-border bg-card/40 px-4 text-sm placeholder:text-muted-foreground"
          />
          <div className="relative">
            <LiquidGlassButton tone="ghost" size="sm" onClick={() => setShowExportMenu((v) => !v)}>
              <Download className="h-4 w-4" /> Export
            </LiquidGlassButton>
            {showExportMenu && (
              <div className="absolute right-0 top-12 z-10 rounded-2xl border border-border bg-card shadow-lg p-2 text-sm min-w-[180px]">
                <button className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left hover:bg-muted" onClick={() => { exportToCSV(); setShowExportMenu(false); }}>
                  <FileText className="h-4 w-4 text-muted-foreground" /> Download CSV
                </button>
                <button className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left hover:bg-muted" onClick={() => { openSheetsExport(); setShowExportMenu(false); }}>
                  <ExternalLink className="h-4 w-4 text-muted-foreground" /> Open in Google Sheets
                </button>
                <button className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left hover:bg-muted" onClick={() => setShowExportMenu(false)}>
                  <Share2 className="h-4 w-4 text-muted-foreground" /> Export to Notion
                </button>
              </div>
            )}
          </div>
        </div>
      </motion.div>

      {/* Kanban with HTML5 drag-and-drop columns */}
      <motion.div variants={fadeUp}>
        {isLoading ? (
          <div className="flex gap-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex-1 space-y-3">
                <div className="h-5 w-24 rounded-lg bg-muted animate-pulse" />
                <div className="h-28 rounded-2xl bg-muted animate-pulse" />
                <div className="h-28 rounded-2xl bg-muted/60 animate-pulse" />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
            {STAGES.map((stage) => {
              const colItems = items.filter((it) => it.stage === stage);
              const label = stage.charAt(0).toUpperCase() + stage.slice(1);
              return (
                <div
                  key={stage}
                  onDragOver={handleDragOver}
                  onDrop={(e) => handleDrop(e, stage)}
                  className="rounded-3xl border border-border bg-card/40 p-4 transition-colors data-[drag-over]:border-primary"
                >
                  <div className="mb-3 flex items-center justify-between text-xs text-muted-foreground">
                    <span>{label}</span>
                    <span>{colItems.length}</span>
                  </div>
                  <div className="space-y-3">
                    {colItems.map((it) => (
                      <motion.div
                        key={it.id}
                        draggable
                        onDragStart={(e) => handleDragStart(e as unknown as DragEvent, it.id)}
                        onClick={() => setSelectedId(it.id)}
                        className={`w-full cursor-grab rounded-2xl border border-border bg-card p-3 text-left active:cursor-grabbing ${draggedId === it.id ? "opacity-50" : ""}`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium">{it.company}</span>
                          <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[10px] text-primary">{it.matchPercent}%</span>
                        </div>
                        <div className="mt-1 text-xs text-muted-foreground">{it.role}</div>
                        {it.nextFollowUp && (
                          <div className="mt-2 text-[10px] text-warning">Follow up {it.nextFollowUp}</div>
                        )}
                      </motion.div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </motion.div>

      {/* Detail Panel */}
      {selected && (
        <motion.div variants={fadeUp} className="rounded-3xl border border-border bg-card/40 p-6">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-xl font-medium">{selected.role}</h2>
              <p className="text-sm text-muted-foreground">{selected.company} · {selected.matchPercent}% match</p>
            </div>
            <LiquidGlassButton tone="ghost" size="sm" onClick={() => setSelectedId(null)}>
              Close
            </LiquidGlassButton>
          </div>

          <div className="mt-6 grid gap-6 md:grid-cols-2">
            {/* AI Next-Action Suggestions */}
            {getAISuggestion(selected.stage) && (
              <div className="rounded-2xl border border-primary/20 bg-primary/5 p-4">
                <div className="flex items-center gap-2 text-sm font-medium text-primary">
                  <Sparkles className="h-4 w-4" /> AI Suggestion
                </div>
                <p className="mt-2 text-sm text-muted-foreground">
                  {selected.stage === "interview" && "Prepare for your interview with AI-powered mock sessions and feedback."}
                  {selected.stage === "offer" && "Negotiate your offer with data-driven salary insights and talking points."}
                </p>
                <LiquidGlassButton
                  tone="primary"
                  size="sm"
                  className="mt-3"
                  onClick={() => toast.info(`Launching ${getAISuggestion(selected.stage)!.label}…`)}
                >
                  <Sparkles className="h-3 w-3" /> {getAISuggestion(selected.stage)!.label}
                </LiquidGlassButton>
              </div>
            )}

            {/* Activity Timeline */}
            <div className="rounded-2xl border border-border p-4">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Clock className="h-4 w-4 text-muted-foreground" /> Activity Timeline
              </div>
              {activityRuns.length === 0 ? (
                <p className="mt-3 text-xs text-muted-foreground">No agent activity yet for this application.</p>
              ) : (
                <div className="mt-3 space-y-3">
                  {activityRuns.map((run) => (
                    <div key={run.id} className="flex gap-3 text-xs">
                      <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-primary" />
                      <div>
                        <span className="font-medium capitalize">{run.agent_type.replace("_", " ")}</span>
                        <span className="ml-2 text-muted-foreground">{run.status}</span>
                        {run.output_summary && <p className="mt-0.5 text-muted-foreground">{run.output_summary}</p>}
                        <p className="mt-0.5 text-muted-foreground/60">{new Date(run.created_at).toLocaleString()}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </motion.div>
      )}

      <ApplicationDrawer
        application={selected}
        open={selected !== null}
        onClose={() => setSelectedId(null)}
      />
    </motion.div>
  );
}
