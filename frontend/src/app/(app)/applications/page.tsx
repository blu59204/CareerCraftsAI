"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { ApplicationKanban, type ApplicationItem, type AppStage } from "@/components/apps/ApplicationKanban";
import { ApplicationDrawer } from "@/components/apps/ApplicationDrawer";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { Download, FileText, ExternalLink, Share2 } from "lucide-react";
import { apiClient } from "@/lib/api";

export default function ApplicationsPage() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: items = [], isLoading } = useQuery<ApplicationItem[]>({
    queryKey: ["applications"],
    queryFn: async () => {
      const { data } = await apiClient.get("/jobs/applications");
      return (data as any[]).map((a) => ({
        id: String(a.id),
        company: a.company,
        role: a.role,
        matchPercent: a.match_score ?? 0,
        stage: a.status as ApplicationItem["stage"],
        nextFollowUp: undefined,
      }));
    },
  });

  const statusMutation = useMutation({
    mutationFn: async ({ id, newStage }: { id: string; newStage: string }) => {
      await apiClient.patch(`/jobs/applications/${id}/status`, { status: newStage });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
  });
  const [showExportMenu, setShowExportMenu] = useState(false);
  const selected = items.find((i) => i.id === selectedId) ?? null;

  const exportToCSV = () => {
    const headers = ["Company", "Role", "Match %", "Stage", "Next Follow-up"];
    const rows = items.map((i) => [
      i.company,
      i.role,
      `${i.matchPercent}%`,
      i.stage,
      i.nextFollowUp ?? "—",
    ]);
    const csv = [headers, ...rows].map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "applications.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const openSheetsExport = () => {
    window.open("https://sheets.new", "_blank");
  };

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
            <LiquidGlassButton
              tone="ghost"
              size="sm"
              onClick={() => setShowExportMenu((v) => !v)}
            >
              <Download className="h-4 w-4" /> Export
            </LiquidGlassButton>
            {showExportMenu && (
              <div className="absolute right-0 top-12 z-10 rounded-2xl border border-border bg-card shadow-lg p-2 text-sm min-w-[180px]">
                <button
                  className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left hover:bg-muted"
                  onClick={() => { exportToCSV(); setShowExportMenu(false); }}
                >
                  <FileText className="h-4 w-4 text-muted-foreground" /> Download CSV
                </button>
                <button
                  className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left hover:bg-muted"
                  onClick={() => { openSheetsExport(); setShowExportMenu(false); }}
                >
                  <ExternalLink className="h-4 w-4 text-muted-foreground" /> Open in Google Sheets
                </button>
                <button
                  className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left hover:bg-muted"
                  onClick={() => setShowExportMenu(false)}
                >
                  <Share2 className="h-4 w-4 text-muted-foreground" /> Export to Notion
                </button>
              </div>
            )}
          </div>
        </div>
      </motion.div>

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
          <ApplicationKanban
            items={items}
            onSelect={setSelectedId}
            onStageChange={(id: string, newStage: AppStage) =>
              statusMutation.mutate({ id, newStage })
            }
          />
        )}
      </motion.div>

      <ApplicationDrawer
        application={selected}
        open={selected !== null}
        onClose={() => setSelectedId(null)}
      />
    </motion.div>
  );
}
