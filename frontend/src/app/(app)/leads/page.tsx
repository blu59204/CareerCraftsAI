"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Plus, Download, Mail, Calendar, ChevronRight } from "lucide-react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api";

interface Lead {
  id: string;
  name: string | null;
  email: string | null;
  company: string | null;
  linkedin_url: string | null;
  status: string;
  last_contact: string | null;
  notes: string | null;
}

type UIStatus = "New" | "Contacted" | "Replied" | "Cold";

const STATUS_MAP: Record<string, UIStatus> = {
  cold: "Cold",
  warm: "Contacted",
  hot: "Replied",
  contacted: "Contacted",
  replied: "Replied",
  closed: "Cold",
};

const STATUS_STYLES: Record<UIStatus, string> = {
  New: "bg-blue-500/15 text-blue-600",
  Contacted: "bg-yellow-500/15 text-yellow-600",
  Replied: "bg-green-500/15 text-green-600",
  Cold: "bg-muted text-muted-foreground",
};

const ACTION_LABEL: Record<UIStatus, string> = {
  New: "Reply",
  Contacted: "Follow up",
  Replied: "Schedule",
  Cold: "Reach out",
};

function getInitials(name: string | null): string {
  if (!name) return "?";
  return name.split(" ").map((p) => p[0]).join("").toUpperCase().slice(0, 2);
}

function relativeTime(iso: string | null): string {
  if (!iso) return "Never";
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3600000);
  if (h < 1) return "Just now";
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d === 1) return "Yesterday";
  if (d < 7) return `${d}d ago`;
  return `${Math.floor(d / 7)}w ago`;
}

// Fallback leads shown while unauthenticated or loading
const FALLBACK: Lead[] = [
  { id: "f1", name: "Sarah Chen", email: null, company: "Acme Corp", linkedin_url: null, status: "cold", last_contact: null, notes: null },
  { id: "f2", name: "Raj Patel", email: null, company: "BetaCorp", linkedin_url: null, status: "contacted", last_contact: new Date(Date.now() - 86400000).toISOString(), notes: null },
];

export default function LeadsPage() {
  const qc = useQueryClient();

  const { data: leads = FALLBACK, isLoading } = useQuery<Lead[]>({
    queryKey: ["leads"],
    queryFn: async () => {
      const { data } = await apiClient.get("/leads");
      return data;
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      apiClient.patch(`/leads/${id}/status`, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["leads"] }),
  });

  const contactedCount = leads.filter((l) => l.status === "contacted" || l.status === "warm").length;
  const repliedCount = leads.filter((l) => l.status === "replied" || l.status === "hot").length;
  const replyRate = leads.length > 0 ? ((repliedCount / leads.length) * 100).toFixed(1) : "0.0";

  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
      {/* Header */}
      <motion.div variants={fadeUp} className="flex items-end justify-between">
        <div>
          <div className="text-sm text-muted-foreground">Lead Pipeline</div>
          <h1 className="mt-1 text-3xl font-medium">Your recruiter contacts.</h1>
        </div>
        <div className="flex gap-3">
          <LiquidGlassButton tone="ghost" size="sm">
            <Download className="h-4 w-4" />
            Import from LinkedIn
          </LiquidGlassButton>
          <LiquidGlassButton tone="primary" size="sm">
            <Plus className="h-4 w-4" />
            Add lead
          </LiquidGlassButton>
        </div>
      </motion.div>

      {/* Stats row */}
      <motion.div variants={fadeUp} className="grid gap-4 md:grid-cols-3">
        <div className="rounded-3xl border border-border bg-card/60 p-6">
          <div className="text-sm text-muted-foreground">Total leads</div>
          {isLoading ? (
            <div className="mt-2 h-8 w-12 shimmer rounded-xl" />
          ) : (
            <div className="mt-2 text-3xl font-semibold">{leads.length}</div>
          )}
        </div>
        <div className="rounded-3xl border border-border bg-card/60 p-6">
          <div className="text-sm text-muted-foreground">Contacted</div>
          {isLoading ? (
            <div className="mt-2 h-8 w-8 shimmer rounded-xl" />
          ) : (
            <div className="mt-2 text-3xl font-semibold">{contactedCount}</div>
          )}
        </div>
        <div className="rounded-3xl border border-border bg-card/60 p-6">
          <div className="text-sm text-muted-foreground">Replied</div>
          {isLoading ? (
            <div className="mt-2 h-8 w-20 shimmer rounded-xl" />
          ) : (
            <div className="mt-2 flex items-baseline gap-3">
              <span className="text-3xl font-semibold">{repliedCount}</span>
              <span className="text-sm text-green-600">{replyRate}% rate</span>
            </div>
          )}
        </div>
      </motion.div>

      {/* Lead list */}
      <motion.div variants={fadeUp} className="space-y-3">
        <div className="text-sm text-muted-foreground">All contacts</div>
        {isLoading
          ? Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-16 shimmer rounded-3xl" />
            ))
          : leads.map((lead) => {
              const uiStatus: UIStatus = STATUS_MAP[lead.status] ?? "Cold";
              return (
                <div
                  key={lead.id}
                  className="rounded-3xl border border-border bg-card/60 p-4 flex items-center gap-4"
                >
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/15 text-sm font-semibold text-primary">
                    {getInitials(lead.name)}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="font-medium leading-none">{lead.name ?? "Unknown"}</div>
                    <div className="mt-1 truncate text-sm text-muted-foreground">
                      {lead.company ?? "No company"}
                    </div>
                  </div>

                  <div className="hidden shrink-0 text-sm text-muted-foreground md:block w-24 text-right">
                    {relativeTime(lead.last_contact)}
                  </div>

                  <span
                    className={cn(
                      "hidden shrink-0 rounded-full px-3 py-1 text-xs font-medium sm:inline-flex",
                      STATUS_STYLES[uiStatus]
                    )}
                  >
                    {uiStatus}
                  </span>

                  <LiquidGlassButton
                    tone="ghost"
                    size="sm"
                    className="shrink-0 gap-1.5"
                    onClick={() => statusMutation.mutate({
                      id: lead.id,
                      status: uiStatus === "Replied" ? "replied" : "contacted",
                    })}
                  >
                    {uiStatus === "Replied" ? (
                      <Calendar className="h-3.5 w-3.5" />
                    ) : (
                      <Mail className="h-3.5 w-3.5" />
                    )}
                    {ACTION_LABEL[uiStatus]}
                    <ChevronRight className="h-3.5 w-3.5 opacity-50" />
                  </LiquidGlassButton>
                </div>
              );
            })}
      </motion.div>

      {leads.length === 0 && !isLoading && (
        <motion.div variants={fadeUp}>
          <div className="rounded-3xl border border-dashed border-border bg-card/40 p-6 text-center text-sm text-muted-foreground">
            No leads yet. Add contacts manually or import from LinkedIn.
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}
