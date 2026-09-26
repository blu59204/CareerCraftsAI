"use client";

import { useState, type DragEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import type { ApplicationItem, AppStage } from "@/components/apps/ApplicationKanban";
import { ApplicationDrawer } from "@/components/apps/ApplicationDrawer";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { CommandHeader } from "@/components/immersive/CommandHeader";
import { Download, ExternalLink, Share2, Inbox } from "lucide-react";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";

type AgentRun = {
  id: string;
  agent_type: string;
  status: string;
  started_at: string;
  output_summary?: string;
};

const STAGES: AppStage[] = ["saved", "applied", "viewed", "interview", "offer", "rejected"];

export default function ApplicationsPage() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [dragOverStage, setDragOverStage] = useState<AppStage | null>(null);
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
      return (Array.isArray(data) ? data : data.runs ?? []) as AgentRun[];
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
    setDragOverStage(null);
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
      <motion.div variants={fadeUp}>
        <CommandHeader
          eyebrow="Application Pipeline"
          title="Application Tracker"
          description="Track saved, applied, interview, offer, and rejected roles with a clean dashboard workflow."
          actions={
            <div className="flex gap-2">
              <input
                placeholder="Filter by company or role..."
                className="h-10 rounded-full border border-border bg-card/55 px-4 text-sm placeholder:text-muted-foreground"
              />
              <div className="relative">
                <LiquidGlassButton tone="ghost" size="sm" onClick={() => setShowExportMenu((v) => !v)}>
                  <Share2 className="h-4 w-4" />
                  Export
                </LiquidGlassButton>
                {showExportMenu && (
                  <div className="absolute right-0 z-20 mt-2 w-44 overflow-hidden rounded-xl border border-border bg-card shadow-xl">
                    <button onClick={exportToCSV} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted">
                      <Download className="h-4 w-4" /> CSV
                    </button>
                    <button onClick={openSheetsExport} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted">
                      <ExternalLink className="h-4 w-4" /> Google Sheets
                    </button>
                  </div>
                )}
              </div>
            </div>
          }
        />
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
                  onDragOver={(e) => {
                    handleDragOver(e);
                    setDragOverStage(stage);
                  }}
                  onDragLeave={() => setDragOverStage((s) => (s === stage ? null : s))}
                  onDrop={(e) => handleDrop(e, stage)}
                  className={`rounded-3xl border p-4 transition-colors ${
                    dragOverStage === stage ? "border-primary bg-primary/5" : "border-border bg-card/40"
                  }`}
                >
                  <div className="mb-3 flex items-center justify-between text-xs text-muted-foreground">
                    <span>{label}</span>
                    <span>{colItems.length}</span>
                  </div>
                  {colItems.length === 0 ? (
                    <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-border/60 py-8 text-center">
                      <Inbox className="h-4 w-4 text-muted-foreground/50" />
                      <p className="text-[11px] text-muted-foreground/70">
                        {stage === "saved" ? "Save a role from Jobs to see it here" : "Drag a card here"}
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {colItems.map((it) => (
                        <motion.div
                          key={it.id}
                          draggable
                          onDragStart={(e) => handleDragStart(e as unknown as DragEvent, it.id)}
                          onClick={() => setSelectedId(it.id)}
                          className={`w-full cursor-grab rounded-2xl border border-border bg-card p-3 text-left active:cursor-grabbing ${draggedId === it.id ? "opacity-50" : ""}`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="min-w-0 truncate text-sm font-medium">{it.company}</span>
                            <span className="shrink-0 rounded-full bg-primary/15 px-2 py-0.5 text-[10px] text-primary">{it.matchPercent}%</span>
                          </div>
                          <div className="mt-1 truncate text-xs text-muted-foreground">{it.role}</div>
                          {it.nextFollowUp && (
                            <div className="mt-2 text-[10px] text-warning">Follow up {it.nextFollowUp}</div>
                          )}
                        </motion.div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </motion.div>

      <ApplicationDrawer
        application={selected}
        open={selected !== null}
        onClose={() => setSelectedId(null)}
        activityRuns={activityRuns}
      />
    </motion.div>
  );
}
