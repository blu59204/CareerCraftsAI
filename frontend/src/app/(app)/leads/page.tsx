"use client";

import { motion } from "motion/react";
import { Plus, Download, Mail, Calendar, ChevronRight } from "lucide-react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { cn } from "@/lib/utils";

interface Lead {
  id: string;
  name: string;
  company: string;
  role: string;
  lastContact: string;
  status: "New" | "Contacted" | "Replied" | "Cold";
}

const LEADS: Lead[] = [
  { id: "1", name: "Sarah Chen", company: "Acme Corp", role: "HR Manager", lastContact: "2h ago", status: "New" },
  { id: "2", name: "Raj Patel", company: "BetaCorp", role: "Technical Recruiter", lastContact: "Yesterday", status: "Contacted" },
  { id: "3", name: "Priya Sharma", company: "Gamma", role: "Engineering Manager", lastContact: "2d ago", status: "Replied" },
  { id: "4", name: "Tom Wilson", company: "Delta Tech", role: "Recruiter", lastContact: "3d ago", status: "Contacted" },
  { id: "5", name: "Anita Roy", company: "Epsilon", role: "HR Lead", lastContact: "1w ago", status: "Cold" },
  { id: "6", name: "James Liu", company: "Zeta Analytics", role: "Hiring Manager", lastContact: "1w ago", status: "Cold" },
  { id: "7", name: "Maya Singh", company: "Alpha AI", role: "Recruiter", lastContact: "2w ago", status: "Replied" },
  { id: "8", name: "Dev Kumar", company: "Beta Systems", role: "CTO", lastContact: "Never", status: "Cold" },
];

const STATUS_STYLES: Record<Lead["status"], string> = {
  New: "bg-blue-500/15 text-blue-600",
  Contacted: "bg-yellow-500/15 text-yellow-600",
  Replied: "bg-green-500/15 text-green-600",
  Cold: "bg-muted text-muted-foreground",
};

const ACTION_LABEL: Record<Lead["status"], string> = {
  New: "Reply",
  Contacted: "Follow up",
  Replied: "Schedule",
  Cold: "Reach out",
};

function getInitials(name: string): string {
  return name.split(" ").map((p) => p[0]).join("").toUpperCase().slice(0, 2);
}

export default function LeadsPage() {
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
          <div className="mt-2 text-3xl font-semibold">18</div>
        </div>
        <div className="rounded-3xl border border-border bg-card/60 p-6">
          <div className="text-sm text-muted-foreground">Contacted</div>
          <div className="mt-2 text-3xl font-semibold">7</div>
        </div>
        <div className="rounded-3xl border border-border bg-card/60 p-6">
          <div className="text-sm text-muted-foreground">Replied</div>
          <div className="mt-2 flex items-baseline gap-3">
            <span className="text-3xl font-semibold">3</span>
            <span className="text-sm text-green-600">16.7% rate</span>
          </div>
        </div>
      </motion.div>

      {/* Lead list */}
      <motion.div variants={fadeUp} className="space-y-3">
        <div className="text-sm text-muted-foreground">All contacts</div>
        {LEADS.map((lead) => (
          <div
            key={lead.id}
            className="rounded-3xl border border-border bg-card/60 p-4 flex items-center gap-4"
          >
            {/* Avatar */}
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/15 text-sm font-semibold text-primary">
              {getInitials(lead.name)}
            </div>

            {/* Name / company / role */}
            <div className="min-w-0 flex-1">
              <div className="font-medium leading-none">{lead.name}</div>
              <div className="mt-1 truncate text-sm text-muted-foreground">
                {lead.role} · {lead.company}
              </div>
            </div>

            {/* Last contact */}
            <div className="hidden shrink-0 text-sm text-muted-foreground md:block w-24 text-right">
              {lead.lastContact}
            </div>

            {/* Status badge */}
            <span
              className={cn(
                "hidden shrink-0 rounded-full px-3 py-1 text-xs font-medium sm:inline-flex",
                STATUS_STYLES[lead.status],
              )}
            >
              {lead.status}
            </span>

            {/* Action */}
            <LiquidGlassButton tone="ghost" size="sm" className="shrink-0 gap-1.5">
              {lead.status === "Replied" ? (
                <Calendar className="h-3.5 w-3.5" />
              ) : (
                <Mail className="h-3.5 w-3.5" />
              )}
              {ACTION_LABEL[lead.status]}
              <ChevronRight className="h-3.5 w-3.5 opacity-50" />
            </LiquidGlassButton>
          </div>
        ))}
      </motion.div>

      {/* Empty state notice */}
      <motion.div variants={fadeUp}>
        <div className="rounded-3xl border border-dashed border-border bg-card/40 p-6 text-center text-sm text-muted-foreground">
          Import LinkedIn connections to find recruiters at target companies.
        </div>
      </motion.div>
    </motion.div>
  );
}
