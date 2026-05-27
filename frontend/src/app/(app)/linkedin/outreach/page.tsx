"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Users, Send, Check, X, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { apiClient } from "@/lib/api";

interface OutreachRun {
  id: string;
  status: string;
  input: { company_name?: string } | null;
  output: { contacts?: Array<{ name: string; title: string; linkedin_url: string }>; messages?: Array<{ contact_name: string; message: string }> } | null;
  started_at: string | null;
}

export default function LinkedInOutreachPage() {
  const qc = useQueryClient();
  const [company, setCompany] = useState("");
  const [roleContext, setRoleContext] = useState("");

  const identifyMutation = useMutation({
    mutationFn: () => apiClient.post("/linkedin/outreach/identify", { company_name: company, role_context: roleContext || undefined }),
    onSuccess: () => {
      toast.success("Finding contacts — results will appear shortly");
      setTimeout(() => qc.invalidateQueries({ queryKey: ["outreach-queue"] }), 5000);
    },
    onError: () => toast.error("Failed to start outreach — check backend"),
  });

  const { data: queue = [], isLoading } = useQuery<OutreachRun[]>({
    queryKey: ["outreach-queue"],
    queryFn: async () => {
      const { data } = await apiClient.get("/linkedin/outreach/queue");
      return data;
    },
    refetchInterval: 10000,
  });

  const approveMutation = useMutation({
    mutationFn: ({ runId, approved }: { runId: string; approved: boolean }) =>
      apiClient.post(`/linkedin/outreach/${runId}/approve`, { approved }),
    onSuccess: (_, { approved }) => {
      toast.success(approved ? "Message approved for sending" : "Message discarded");
      qc.invalidateQueries({ queryKey: ["outreach-queue"] });
    },
  });

  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
      <motion.div variants={fadeUp}>
        <div className="text-sm text-muted-foreground">LinkedIn Outreach</div>
        <h1 className="mt-1 text-3xl font-medium">Connect with decision-makers.</h1>
      </motion.div>

      <motion.div variants={fadeUp} className="rounded-3xl border border-border bg-card/60 p-6 space-y-4">
        <div className="flex items-center gap-2">
          <Users className="h-4 w-4 text-primary" />
          <span className="text-sm font-medium">Find Contacts</span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <input value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Company name" className="rounded-2xl border border-border bg-background/60 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
          <input value={roleContext} onChange={(e) => setRoleContext(e.target.value)} placeholder="Role context (optional)" className="rounded-2xl border border-border bg-background/60 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
        </div>
        <LiquidGlassButton tone="primary" size="sm" onClick={() => identifyMutation.mutate()} disabled={!company.trim() || identifyMutation.isPending}>
          {identifyMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Users className="h-4 w-4" />}
          {identifyMutation.isPending ? "Searching…" : "Find Contacts"}
        </LiquidGlassButton>
      </motion.div>

      <motion.div variants={fadeUp} className="space-y-4">
        <div className="text-sm text-muted-foreground">Outreach Queue</div>
        {isLoading ? (
          <div className="h-32 shimmer rounded-3xl" />
        ) : queue.length === 0 ? (
          <div className="rounded-3xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
            No outreach runs yet. Find contacts to get started.
          </div>
        ) : (
          queue.map((run) => (
            <div key={run.id} className="rounded-3xl border border-border bg-card/60 p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">{run.input?.company_name ?? "Unknown"}</span>
                <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${run.status === "completed" ? "bg-green-100 text-green-700" : run.status === "awaiting_approval" ? "bg-amber-100 text-amber-700" : "bg-primary/10 text-primary"}`}>
                  {run.status.replace("_", " ")}
                </span>
              </div>
              {run.output?.contacts && (
                <div className="space-y-2">
                  {run.output.contacts.slice(0, 5).map((c, i) => (
                    <div key={i} className="flex items-center justify-between text-xs">
                      <span className="font-medium">{c.name}</span>
                      <span className="text-muted-foreground">{c.title}</span>
                    </div>
                  ))}
                </div>
              )}
              {run.status === "awaiting_approval" && (
                <div className="flex gap-2 pt-2">
                  <LiquidGlassButton tone="primary" size="sm" onClick={() => approveMutation.mutate({ runId: run.id, approved: true })}>
                    <Check className="h-3.5 w-3.5" /> Approve & Send
                  </LiquidGlassButton>
                  <LiquidGlassButton tone="ghost" size="sm" onClick={() => approveMutation.mutate({ runId: run.id, approved: false })}>
                    <X className="h-3.5 w-3.5" /> Discard
                  </LiquidGlassButton>
                </div>
              )}
            </div>
          ))
        )}
      </motion.div>

      <motion.div variants={fadeUp}>
        <div className="flex items-center gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4">
          <Send className="h-4 w-4 shrink-0 text-amber-600" />
          <p className="text-sm text-amber-800">Every outreach message requires your approval before sending.</p>
        </div>
      </motion.div>
    </motion.div>
  );
}
