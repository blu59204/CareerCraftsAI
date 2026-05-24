"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { Bot, FileText, Search, Linkedin, Mail, Bell, Sparkles } from "lucide-react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { AgentStatusCard } from "@/components/agents/AgentStatusCard";
import { ApprovalCard } from "@/components/agents/ApprovalCard";
import { EmptyState } from "@/components/ui/EmptyState";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";

const AGENTS = [
  { key: "orchestrator", label: "Orchestrator", icon: Sparkles },
  { key: "resume", label: "Resume", icon: FileText },
  { key: "job", label: "Job Search", icon: Search },
  { key: "linkedin", label: "LinkedIn", icon: Linkedin },
  { key: "email", label: "Email", icon: Mail },
  { key: "followup", label: "Follow-up", icon: Bell },
];

export default function AgentsPage() {
  const [active, setActive] = useState("orchestrator");
  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="grid gap-6 lg:grid-cols-[220px_1fr_320px]">
      <motion.aside variants={fadeUp} className="rounded-3xl border border-border bg-card/40 p-3">
        <div className="px-2 py-2 text-xs uppercase tracking-wide text-muted-foreground">Agents</div>
        <nav className="space-y-1">
          {AGENTS.map((a) => {
            const Icon = a.icon;
            const isActive = active === a.key;
            return (
              <button
                key={a.key}
                onClick={() => setActive(a.key)}
                className={`flex w-full items-center gap-2 rounded-2xl px-3 py-2 text-sm ${
                  isActive ? "bg-primary/15 text-foreground" : "text-muted-foreground hover:bg-card"
                }`}
              >
                <Icon className="h-4 w-4" />
                {a.label}
              </button>
            );
          })}
        </nav>
      </motion.aside>

      <motion.section variants={fadeUp} className="rounded-3xl border border-border bg-card/40 p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-primary" />
            <div className="font-medium">{AGENTS.find((a) => a.key === active)?.label} Agent</div>
          </div>
          <LiquidGlassButton tone="primary" size="sm">Run</LiquidGlassButton>
        </div>
        <div className="mt-6 min-h-[400px] rounded-2xl border border-border bg-background/40 p-4">
          <EmptyState
            icon={<Sparkles className="h-6 w-6" />}
            title="Automate repetitive applications."
            description="Tell the orchestrator what role you're after. It'll route work across the resume, job, email, and follow-up agents."
            action={<LiquidGlassButton tone="primary">Start run</LiquidGlassButton>}
          />
        </div>
      </motion.section>

      <motion.aside variants={fadeUp} className="space-y-3">
        <div className="text-sm text-muted-foreground">Context</div>
        <div className="rounded-3xl border border-border bg-card/40 p-4 text-sm">
          <div className="text-xs text-muted-foreground">Resume</div>
          <div className="mt-1">resume-v3.pdf</div>
          <div className="mt-3 text-xs text-muted-foreground">Target role</div>
          <div className="mt-1">Frontend Engineer</div>
          <div className="mt-3 text-xs text-muted-foreground">Model</div>
          <div className="mt-1">Anthropic · claude-sonnet-4-6</div>
        </div>
        <div className="text-sm text-muted-foreground">Run history</div>
        <AgentStatusCard agentName="Resume Agent" status="succeeded" latestMessage="Tailored for BetaCorp." startedAt="3 min ago" />
        <ApprovalCard
          title="Apply to Acme Frontend Engineer"
          summary="Application draft ready. Click approve to submit through the browser agent."
          onApprove={() => {}}
          onReject={() => {}}
        />
      </motion.aside>
    </motion.div>
  );
}
