"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "motion/react";
import {
  Search,
  Filter,
  MapPin,
  Clock,
  Bookmark,
  ExternalLink,
  Zap,
  TrendingUp,
  RefreshCw,
  Globe,
  Copy,
  ChevronDown,
  Loader2,
} from "lucide-react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiClient } from "@/lib/api";

const XRAY_TEMPLATES = [
  `site:linkedin.com/jobs "Frontend Engineer" "React" "Remote"`,
  `site:greenhouse.io OR site:lever.co "Software Engineer" "Python" "India"`,
  `"careers.stripe.com" OR "jobs.notion.so" "Software Engineer" -intern`,
];

const FILTER_CHIPS = ["Remote", "Full-time", "Entry-level", "Bangalore", "Hyderabad", "Mumbai"];

interface SavedJob {
  id: string;
  company: string;
  role: string;
  job_url: string | null;
  match_score: number | null;
  status: string;
  applied_at: string | null;
}

function relativeTime(iso: string | null): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3600000);
  if (h < 1) return "Just now";
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return d === 1 ? "Yesterday" : `${d}d ago`;
}

function XraySearchPanel({
  query,
  setQuery,
}: {
  query: string;
  setQuery: (q: string) => void;
}) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(query);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="rounded-3xl border border-border bg-card/60 p-6 space-y-4">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-primary/10">
          <Globe className="h-5 w-5 text-primary" />
        </div>
        <div>
          <p className="text-sm font-semibold text-foreground">X-ray Search</p>
          <p className="text-xs text-muted-foreground">
            Build Boolean search queries to find jobs directly via Google
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {XRAY_TEMPLATES.map((tpl) => (
          <button
            key={tpl}
            onClick={() => setQuery(tpl)}
            className={`rounded-full border px-3 py-1 text-xs transition-colors ${
              query === tpl
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-card/40 text-muted-foreground hover:bg-card/70"
            }`}
          >
            {tpl.length > 52 ? tpl.slice(0, 52) + "…" : tpl}
          </button>
        ))}
      </div>

      <textarea
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        rows={3}
        className="w-full resize-none rounded-2xl border border-border bg-background/60 px-4 py-3 font-mono text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
      />

      <div className="flex items-center gap-2">
        <LiquidGlassButton
          tone="primary"
          size="sm"
          onClick={() =>
            window.open(
              `https://www.google.com/search?q=${encodeURIComponent(query)}`,
              "_blank",
            )
          }
        >
          <ExternalLink className="h-3.5 w-3.5" />
          Search on Google ↗
        </LiquidGlassButton>
        <LiquidGlassButton tone="ghost" size="sm" onClick={handleCopy}>
          <Copy className="h-3.5 w-3.5" />
          {copied ? "Copied!" : "Copy query"}
        </LiquidGlassButton>
      </div>

      <p className="text-xs text-muted-foreground">
        X-ray searches bypass job board algorithms and find hidden openings
      </p>
    </div>
  );
}

function MatchBar({ percent }: { percent: number | null }) {
  const p = percent ?? 0;
  const fillColor = p >= 80 ? "bg-primary" : p >= 60 ? "bg-yellow-500" : "bg-red-400";

  return (
    <div className="mt-4">
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-muted-foreground">Match</span>
        <span className="font-medium">{p > 0 ? `${p}%` : "—"}</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-primary/20">
        <div
          className={`h-1.5 rounded-full ${fillColor} transition-all`}
          style={{ width: `${p}%` }}
        />
      </div>
    </div>
  );
}

function JobCard({ job }: { job: SavedJob }) {
  const domain = job.job_url
    ? (() => {
        try {
          return new URL(job.job_url).hostname.replace("www.", "");
        } catch {
          return null;
        }
      })()
    : null;

  return (
    <motion.div
      variants={fadeUp}
      className="rounded-3xl border border-border bg-card/60 p-6 hover:shadow-md transition-shadow flex flex-col gap-3"
    >
      <div>
        <div className="text-sm font-semibold text-muted-foreground">{job.company}</div>
        <div className="mt-0.5 text-xl font-medium leading-snug">{job.role}</div>
      </div>

      <div className="flex flex-wrap gap-2">
        {domain && (
          <span className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground">
            <MapPin className="h-3 w-3" />
            {domain}
          </span>
        )}
        <span className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground">
          <Clock className="h-3 w-3" />
          {relativeTime(job.applied_at)}
        </span>
        <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
          job.status === "applied" ? "bg-green-500/15 text-green-600"
          : job.status === "saved" ? "bg-blue-500/15 text-blue-600"
          : "bg-secondary text-secondary-foreground"
        }`}>
          {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
        </span>
      </div>

      <MatchBar percent={job.match_score} />

      <div className="mt-auto flex gap-2 pt-1">
        <LiquidGlassButton tone="ghost" size="sm" className="flex-1 gap-1.5">
          <Bookmark className="h-3.5 w-3.5" />
          Save
        </LiquidGlassButton>
        {job.job_url ? (
          <LiquidGlassButton
            tone="primary"
            size="sm"
            className="flex-1 gap-1.5"
            onClick={() => window.open(job.job_url!, "_blank")}
          >
            <ExternalLink className="h-3.5 w-3.5" />
            Apply
          </LiquidGlassButton>
        ) : (
          <LiquidGlassButton tone="primary" size="sm" className="flex-1 gap-1.5" disabled>
            <ExternalLink className="h-3.5 w-3.5" />
            Apply
          </LiquidGlassButton>
        )}
      </div>
    </motion.div>
  );
}

export default function JobsPage() {
  const qc = useQueryClient();
  const [activeFilters, setActiveFilters] = useState<Set<string>>(
    new Set(["Remote", "Full-time"]),
  );
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [xrayQuery, setXrayQuery] = useState(XRAY_TEMPLATES[0]);
  const [searchQuery, setSearchQuery] = useState("");
  const [agentRunning, setAgentRunning] = useState(false);

  const { data: jobs = [], isLoading } = useQuery<SavedJob[]>({
    queryKey: ["jobs-saved"],
    queryFn: async () => {
      const { data } = await apiClient.get("/jobs/applications?status=saved");
      return data;
    },
  });

  const searchMutation = useMutation({
    mutationFn: (payload: { search_query: string; location: string; max_results: number }) =>
      apiClient.post("/jobs/search", payload),
    onSuccess: () => {
      setAgentRunning(true);
      setTimeout(() => {
        setAgentRunning(false);
        qc.invalidateQueries({ queryKey: ["jobs-saved"] });
      }, 8000);
    },
  });

  const avgMatch =
    jobs.length > 0
      ? Math.round(jobs.reduce((s, j) => s + (j.match_score ?? 0), 0) / jobs.length)
      : 0;

  const oneDayAgo = Date.now() - 86400000;
  const newToday = jobs.filter(
    (j) => j.applied_at && new Date(j.applied_at).getTime() > oneDayAgo,
  ).length;

  function toggleFilter(chip: string) {
    setActiveFilters((prev) => {
      const next = new Set(prev);
      next.has(chip) ? next.delete(chip) : next.add(chip);
      return next;
    });
  }

  function handleRunAgent() {
    const query = searchQuery.trim() || "Software Engineer Remote";
    searchMutation.mutate({
      search_query: query,
      location: activeFilters.has("Remote") ? "Remote" : "Any",
      max_results: 10,
    });
  }

  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
      {/* Header */}
      <motion.div variants={fadeUp} className="flex items-start justify-between gap-4">
        <div>
          <div className="text-sm text-muted-foreground">Job Search</div>
          <h1 className="mt-1 text-3xl font-medium">Find your next role.</h1>
        </div>
        <div className="flex shrink-0 gap-2">
          <LiquidGlassButton tone="ghost" size="sm">
            <Filter className="h-4 w-4" />
            Filters
          </LiquidGlassButton>
          <LiquidGlassButton
            tone="ghost"
            size="sm"
            onClick={() => setShowAdvanced((v) => !v)}
          >
            <ChevronDown
              className={`h-4 w-4 transition-transform ${showAdvanced ? "rotate-180" : ""}`}
            />
            Advanced search ↓
          </LiquidGlassButton>
          <LiquidGlassButton
            tone="primary"
            size="sm"
            onClick={handleRunAgent}
            disabled={searchMutation.isPending || agentRunning}
          >
            {searchMutation.isPending || agentRunning ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Zap className="h-4 w-4" />
            )}
            {agentRunning ? "Searching…" : "Run Job Agent"}
          </LiquidGlassButton>
        </div>
      </motion.div>

      {/* Search + filter chips */}
      <motion.div variants={fadeUp} className="space-y-3">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleRunAgent()}
            placeholder="Search roles, companies, or skills…"
            className="h-11 w-full rounded-full border border-border bg-card/40 pl-11 pr-4 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {FILTER_CHIPS.map((chip) => (
            <button
              key={chip}
              onClick={() => toggleFilter(chip)}
              className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                activeFilters.has(chip)
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-card/40 text-muted-foreground hover:bg-card/70"
              }`}
            >
              {chip}
            </button>
          ))}
          {activeFilters.size > 0 && (
            <span className="rounded-full bg-secondary px-2.5 py-1 text-xs text-secondary-foreground">
              Active filters: {activeFilters.size}
            </span>
          )}
        </div>
      </motion.div>

      {/* Advanced Search (X-ray) */}
      <AnimatePresence>
        {showAdvanced && (
          <motion.div
            key="xray-panel"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
            className="overflow-hidden"
          >
            <XraySearchPanel query={xrayQuery} setQuery={setXrayQuery} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Metrics strip */}
      <motion.div variants={fadeUp} className="grid grid-cols-3 gap-4">
        <div className="rounded-3xl border border-border bg-card/60 p-6">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Roles found</span>
            <Search className="h-4 w-4 text-muted-foreground" />
          </div>
          {isLoading ? (
            <div className="mt-4 h-8 w-12 shimmer rounded-xl" />
          ) : (
            <div className="mt-4 text-3xl font-medium">{jobs.length}</div>
          )}
        </div>

        <div className="rounded-3xl border border-border bg-card/60 p-6">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Average match</span>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </div>
          {isLoading ? (
            <div className="mt-4 h-8 w-16 shimmer rounded-xl" />
          ) : (
            <div className="mt-4 text-3xl font-medium">{avgMatch > 0 ? `${avgMatch}%` : "—"}</div>
          )}
        </div>

        <div className="rounded-3xl border border-border bg-card/60 p-6">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">New since yesterday</span>
            <RefreshCw className="h-4 w-4 text-muted-foreground" />
          </div>
          {isLoading ? (
            <div className="mt-4 h-8 w-8 shimmer rounded-xl" />
          ) : (
            <div className="mt-4 text-3xl font-medium">{newToday}</div>
          )}
        </div>
      </motion.div>

      {/* Job cards grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-48 shimmer rounded-3xl" />
          ))}
        </div>
      ) : jobs.length === 0 ? (
        <motion.div variants={fadeUp}>
          <EmptyState
            icon={<Search className="h-6 w-6" />}
            title="No jobs found yet."
            description="Click Run Job Agent to start searching for roles matching your profile."
            action={
              <LiquidGlassButton tone="primary" onClick={handleRunAgent}>
                <Zap className="h-4 w-4" />
                Run Job Agent
              </LiquidGlassButton>
            }
          />
        </motion.div>
      ) : (
        <motion.div
          variants={stagger}
          className="grid grid-cols-1 gap-4 lg:grid-cols-2"
        >
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} />
          ))}
        </motion.div>
      )}

      {/* Agent status bar */}
      <motion.div
        variants={fadeUp}
        className="flex items-center gap-3 rounded-2xl border border-border bg-card/40 px-5 py-3 text-sm text-muted-foreground"
      >
        {agentRunning ? (
          <>
            <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
            Job Search Agent running — scanning boards for matching roles…
          </>
        ) : (
          <>
            <span className="relative flex h-2 w-2 shrink-0">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500" />
            </span>
            Job Search Agent ready — {jobs.length > 0 ? `${jobs.length} roles saved` : "run agent to discover roles"}
          </>
        )}
      </motion.div>
    </motion.div>
  );
}
