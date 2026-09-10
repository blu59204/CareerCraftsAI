"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import {
  Bot,
  Building2,
  CheckCircle2,
  Clock3,
  DollarSign,
  FileText,
  Mail,
  MessageSquare,
  MonitorCheck,
  Play,
  Search,
  Sparkles,
  TriangleAlert,
  Users,
} from "lucide-react";
import { BrandLinkedin } from "@/components/icons/BrandIcons";
import { toast } from "sonner";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { AgentStatusCard } from "@/components/agents/AgentStatusCard";
import { AgentStatusStream } from "@/components/agents/AgentStatusStream";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { CommandHeader } from "@/components/immersive/CommandHeader";
import { apiClient } from "@/lib/api";
import { useAgentStore } from "@/store/agentStore";

const AGENTS = [
  { key: "auto_apply", label: "Auto Apply", icon: Bot, accent: "from-cyan-500/20 to-violet-500/5", note: "Isolated browser + two reviews" },
  { key: "resume_optimize", label: "Resume", icon: FileText, accent: "from-cyan-500/20 to-blue-500/5", note: "Tailored resume draft" },
  { key: "job_search", label: "Job Search", icon: Search, accent: "from-emerald-500/20 to-cyan-500/5", note: "Fresh matching roles" },
  { key: "nl_job_search", label: "NL Search", icon: Search, accent: "from-teal-500/20 to-emerald-500/5", note: "Plain-English query parser" },
  { key: "linkedin_optimize", label: "LinkedIn", icon: BrandLinkedin, accent: "from-sky-500/20 to-indigo-500/5", note: "Profile rewrite" },
  { key: "linkedin_outreach", label: "Outreach", icon: Users, accent: "from-blue-500/20 to-cyan-500/5", note: "Recruiter drafts" },
  { key: "email", label: "Email", icon: Mail, accent: "from-amber-500/20 to-orange-500/5", note: "Reviewable draft" },
  { key: "email_monitor", label: "Monitor", icon: MonitorCheck, accent: "from-lime-500/20 to-emerald-500/5", note: "Inbox status scan" },
  { key: "interview_prep", label: "Interview Prep", icon: Sparkles, accent: "from-fuchsia-500/20 to-violet-500/5", note: "Question set" },
  { key: "interview_coach", label: "Coach", icon: MessageSquare, accent: "from-rose-500/20 to-pink-500/5", note: "Mock interview session" },
  { key: "cover_letter", label: "Cover Letter", icon: FileText, accent: "from-purple-500/20 to-fuchsia-500/5", note: "Role-specific letter" },
  { key: "salary_intelligence", label: "Salary", icon: DollarSign, accent: "from-green-500/20 to-lime-500/5", note: "Market benchmark" },
  { key: "company_research", label: "Company", icon: Building2, accent: "from-indigo-500/20 to-blue-500/5", note: "Interview intel brief" },
];

const DEFAULT_CONTEXT: Record<string, Record<string, unknown>> = {
  auto_apply: { search_query: "software engineer", location: "Remote", max_applications: 1 },
  resume_optimize: { jd_text: "Software Engineer role focused on product delivery, reliability, and measurable impact." },
  job_search: { search_query: "software engineer", location: "Remote", max_results: 10 },
  nl_job_search: { query: "remote senior backend role at a product company using Python or TypeScript" },
  linkedin_optimize: { target_role: "Software Engineer" },
  linkedin_outreach: { company_name: "Target Company", role_context: "Software Engineer" },
  email: { company: "Target Company", role: "Software Engineer", recipient_email: "recruiter@example.com" },
  email_monitor: {},
  interview_prep: { role: "Software Engineer", company: "Target Company" },
  interview_coach: { role: "Software Engineer", company: "Target Company" },
  cover_letter: { tone: "formal", jd_text: "Software Engineer role focused on product delivery, reliability, and measurable impact." },
  salary_intelligence: { role: "Software Engineer", company: "Target Company", location: "Remote" },
  company_research: { company_name: "Target Company" },
};

// BUG 6: interface matches backend AgentRunResponse (started_at, not created_at)
interface AgentRun {
  id: string;
  agent_type: string;
  status: string;
  started_at: string;
  output: { error?: string } | null;
  duration_ms: number | null;
}

interface RagDocument {
  filename: string;
  doc_type: string;
  is_primary: boolean;
}

function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function runMessage(run: AgentRun): string {
  if (run.status === "queued") return "Queued for a worker";
  if (run.status === "awaiting_approval") return "Waiting for approval";
  if (run.status === "running") return "In progress...";
  if (run.status === "failed") return run.output?.error ?? "Failed";
  if (run.duration_ms !== null) return `Completed in ${(run.duration_ms / 1000).toFixed(1)}s`;
  return run.status === "awaiting_approval" ? "Waiting for approval" : "Completed";
}

function runStatus(run?: AgentRun) {
  if (!run) return { label: "Ready", icon: Clock3, className: "text-muted-foreground" };
  if (run.status === "completed") return { label: "Last run succeeded", icon: CheckCircle2, className: "text-success" };
  if (run.status === "failed") return { label: "Last run failed", icon: TriangleAlert, className: "text-danger" };
  if (run.status === "awaiting_approval") return { label: "Review pending", icon: Clock3, className: "text-warning" };
  return { label: "Running", icon: Clock3, className: "text-primary" };
}

export default function AgentsPage() {
  const [active, setActive] = useState("resume_optimize");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [contextText, setContextText] = useState(JSON.stringify(DEFAULT_CONTEXT.resume_optimize, null, 2));
  const qc = useQueryClient();
  const initRun = useAgentStore((s) => s.initRun);
  const storeActiveRunId = useAgentStore((s) => s.activeRunId);
  const setActiveRun = useAgentStore((s) => s.setActiveRun);
  // Persisted run survives navigation + reload, so the panel reappears on return.
  const displayRunId = activeRunId ?? storeActiveRunId;
  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get("run");
    if (requested && /^[0-9a-f-]{36}$/i.test(requested)) setActiveRun(requested);
  }, [setActiveRun]);

  const runMutation = useMutation({
    mutationFn: async () => {
      const context = JSON.parse(contextText);
      if (!context || Array.isArray(context) || typeof context !== "object") throw new Error("Context must be a JSON object");
      return apiClient.post<{ run_id: string }>("/agents/run", {
        task_type: active,
        context,
      });
    },
    onSuccess: (res) => {
      toast.success(`${AGENTS.find((a) => a.key === active)?.label} Agent started`);
      initRun(res.data.run_id);
      setActiveRunId(res.data.run_id);
      setTimeout(() => qc.invalidateQueries({ queryKey: ["agent-runs"] }), 3000);
    },
    onError: () => toast.error("Could not queue the agent. Check your context, model settings, and active-run limit."),
  });

  const { data: runs = [], isLoading: runsLoading } = useQuery<AgentRun[]>({
    queryKey: ["agent-runs"],
    queryFn: async () => {
      const { data } = await apiClient.get("/agents/runs?limit=10");
      return Array.isArray(data) ? data : data.runs ?? [];
    },
    refetchInterval: 5000,
  });

  const { data: ragDocs = [] } = useQuery<RagDocument[]>({
    queryKey: ["rag-documents"],
    queryFn: async () => {
      const { data } = await apiClient.get("/rag/documents");
      return data;
    },
  });

  // BUG 19: fetch active model from /users/me/models
  const { data: userModels = [] } = useQuery<{ id: string; provider: string; model_name: string | null; is_active: boolean }[]>({
    queryKey: ["user-models"],
    queryFn: async () => {
      const { data } = await apiClient.get("/users/me/models");
      return data;
    },
  });

  const activeModel = userModels.find((m) => m.is_active);
  const primaryResume = ragDocs.find((d) => d.doc_type === "resume" && d.is_primary);
  const filteredRuns = runs.filter(
    (r) => r.agent_type === active
  );
  const activeAgent = AGENTS.find((a) => a.key === active) ?? AGENTS[0];
  const ActiveIcon = activeAgent.icon;
  const latestRun = filteredRuns[0];
  const latestStatus = runStatus(latestRun);
  const LatestStatusIcon = latestStatus.icon;

  // BUG 7: find the awaiting run to pass run_id to approval
  const awaitingRun = runs.find((r) => r.status === "awaiting_approval");

  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
      <motion.section variants={fadeUp} className="space-y-5">
        <CommandHeader
          eyebrow="Finlytic AI Agent"
          title="Run workspace agents."
          description="Coordinate resume, job search, LinkedIn, email, and interview agents from one approval-safe cockpit."
          actions={
            <div className={`hidden items-center gap-2 rounded-full border border-border bg-card/45 px-3 py-2 text-xs sm:flex ${latestStatus.className}`}>
              <LatestStatusIcon className="h-4 w-4" />
              {latestStatus.label}
            </div>
          }
        />
        <div className="rounded-2xl border border-border bg-card/50 p-3 shadow-sm">
          <nav className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
          {AGENTS.map((a) => {
            const Icon = a.icon;
            const isActive = active === a.key;
            return (
              <button
                key={a.key}
                onClick={() => { setActive(a.key); setContextText(JSON.stringify(DEFAULT_CONTEXT[a.key] ?? {}, null, 2)); }}
                className={`group min-h-[76px] rounded-xl border px-3 py-3 text-left transition ${
                  isActive
                    ? "border-primary/35 bg-primary/10 text-foreground shadow-[0_0_0_1px_rgba(255,255,255,0.04)_inset]"
                    : "border-transparent bg-background/30 text-muted-foreground hover:border-border hover:bg-card/70"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className={`grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br ${a.accent}`}>
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="text-sm font-medium">{a.label}</span>
                </div>
                <div className="mt-2 line-clamp-1 text-xs text-muted-foreground">{a.note}</div>
              </button>
            );
          })}
          </nav>
        </div>

        <div className="rounded-2xl border border-border bg-card/50 p-5 shadow-sm">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex items-start gap-3">
              <span className={`grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br ${activeAgent.accent}`}>
                <ActiveIcon className="h-5 w-5 text-foreground" />
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-semibold tracking-tight">{activeAgent.label} Agent</h2>
                  <Bot className="h-4 w-4 text-primary" />
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{activeAgent.note}</p>
              </div>
            </div>
            <LiquidGlassButton
              tone="primary"
              size="sm"
              disabled={runMutation.isPending}
              onClick={() => runMutation.mutate()}
              className="w-full sm:w-auto"
            >
              <Play className="h-4 w-4" />
              {runMutation.isPending ? "Running..." : "Run agent"}
            </LiquidGlassButton>
          </div>

          <label className="mt-4 block text-sm font-medium">
            Task context (JSON)
            <textarea value={contextText} onChange={event => setContextText(event.target.value)}
              className="mt-2 min-h-28 w-full rounded-lg border border-border bg-background p-3 font-mono text-xs"
              spellCheck={false} />
          </label>
          <div className="mt-5 min-h-[240px] rounded-xl border border-border bg-background/45 p-4">
          {/* BUG 12: mount AgentStatusStream when a run is active */}
          {displayRunId ? (
            <AgentStatusStream
              runId={displayRunId}
              onApprove={() => {
                qc.invalidateQueries({ queryKey: ["agent-runs"] });
              }}
              onCancel={() => {
                qc.invalidateQueries({ queryKey: ["agent-runs"] });
                setActiveRunId(null);
                setActiveRun(null);
              }}
            />
          ) : (
            <div className="flex min-h-[208px] items-center justify-center">
              <div className="w-full max-w-md text-center">
                <span className={`mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br ${activeAgent.accent}`}>
                  <Sparkles className="h-6 w-6 text-foreground" />
                </span>
                <h3 className="mt-4 text-xl font-semibold tracking-tight">{latestStatus.label}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{latestRun ? runMessage(latestRun) : activeAgent.note}</p>
              </div>
            </div>
          )}
          </div>
        </div>
      </motion.section>

      <motion.aside variants={fadeUp} className="space-y-4">
        {/* BUG 19: dynamic context sidebar */}
        <div className="rounded-2xl border border-border bg-card/50 p-4 text-sm shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Context</div>
          <div className="mt-4 space-y-3">
            <div className="rounded-xl bg-background/45 p-3">
              <div className="text-xs text-muted-foreground">Resume</div>
              <div className="mt-1 truncate font-medium">{primaryResume?.filename ?? "No resume uploaded"}</div>
            </div>
            <div className="rounded-xl bg-background/45 p-3">
              <div className="text-xs text-muted-foreground">Model</div>
              <div className="mt-1 truncate font-medium">{activeModel?.model_name ?? activeModel?.provider ?? "Not configured"}</div>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-card/50 p-4 shadow-sm">
          <div className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Run history</div>
          <div className="space-y-2">
            {runsLoading ? (
              <>
                <div className="h-16 shimmer rounded-xl" />
                <div className="h-16 shimmer rounded-xl" />
              </>
            ) : filteredRuns.length === 0 ? (
              <div className="rounded-xl border border-dashed border-border p-4 text-center text-sm text-muted-foreground">
                No runs yet.
              </div>
            ) : (
              filteredRuns.map((run) => (
                <button key={run.id} className="w-full text-left" onClick={() => { setActiveRunId(run.id); setActiveRun(run.id); }}>
                <AgentStatusCard
                  agentName={`${run.agent_type.charAt(0).toUpperCase() + run.agent_type.slice(1).replace(/_/g, " ")} Agent`}
                  status={
                    run.status === "completed"
                      ? "succeeded"
                      : run.status === "failed"
                        ? "failed"
                        : run.status === "awaiting_approval"
                          ? "awaiting_approval"
                          : "running"
                  }
                  latestMessage={runMessage(run)}
                  startedAt={relativeTime(run.started_at)}
                />
                </button>
              ))
            )}
          </div>
        </div>

        {/* BUG 7: wire approval callbacks with actual run_id — only show if NOT the same as activeRunId to avoid duplicates */}
        {awaitingRun && awaitingRun.id !== displayRunId && (
          <button className="w-full rounded-xl border border-border p-3 text-sm text-primary"
            onClick={() => { setActiveRunId(awaitingRun.id); setActiveRun(awaitingRun.id); }}>
            Open pending review · {awaitingRun.agent_type}
          </button>
        )}
      </motion.aside>
    </motion.div>
  );
}
