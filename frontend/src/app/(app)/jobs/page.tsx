"use client";

import { useState } from "react";
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
} from "lucide-react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";

const XRAY_TEMPLATES = [
  `site:linkedin.com/jobs "Frontend Engineer" "React" "Remote"`,
  `site:greenhouse.io OR site:lever.co "Software Engineer" "Python" "India"`,
  `"careers.stripe.com" OR "jobs.notion.so" "Software Engineer" -intern`,
];

// ---------------------------------------------------------------------------
// X-ray Search Panel
// ---------------------------------------------------------------------------

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
      {/* Card header */}
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

      {/* Template chips */}
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

      {/* Editable query textarea */}
      <textarea
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        rows={3}
        className="w-full resize-none rounded-2xl border border-border bg-background/60 px-4 py-3 font-mono text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
      />

      {/* Actions */}
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

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Job {
  id: string;
  company: string;
  role: string;
  location: string;
  type: string;
  postedAgo: string;
  matchPercent: number;
  skills: [string, string, string];
}

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const JOBS: Job[] = [
  {
    id: "1",
    company: "Acme Corp",
    role: "Frontend Engineer",
    location: "Remote",
    type: "Full-time",
    postedAgo: "2 days ago",
    matchPercent: 92,
    skills: ["React", "TypeScript", "Next.js"],
  },
  {
    id: "2",
    company: "BetaCorp",
    role: "Full-stack Developer",
    location: "Bangalore",
    type: "Full-time",
    postedAgo: "2 days ago",
    matchPercent: 87,
    skills: ["Node.js", "Python", "PostgreSQL"],
  },
  {
    id: "3",
    company: "Gamma Systems",
    role: "Junior SDE",
    location: "Hyderabad",
    type: "Full-time",
    postedAgo: "2 days ago",
    matchPercent: 81,
    skills: ["Java", "Spring Boot", "MySQL"],
  },
  {
    id: "4",
    company: "Delta Tech",
    role: "React Developer",
    location: "Remote",
    type: "Full-time",
    postedAgo: "2 days ago",
    matchPercent: 78,
    skills: ["React", "Redux", "Jest"],
  },
  {
    id: "5",
    company: "Epsilon Labs",
    role: "Backend Engineer",
    location: "Pune",
    type: "Full-time",
    postedAgo: "2 days ago",
    matchPercent: 74,
    skills: ["Go", "Kubernetes", "Redis"],
  },
  {
    id: "6",
    company: "Zeta Analytics",
    role: "Data Engineer",
    location: "Bangalore",
    type: "Full-time",
    postedAgo: "2 days ago",
    matchPercent: 68,
    skills: ["Python", "Spark", "Airflow"],
  },
];

const FILTER_CHIPS = ["Remote", "Full-time", "Entry-level", "Bangalore", "Hyderabad", "Mumbai"];

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function MatchBar({ percent }: { percent: number }) {
  const fillColor =
    percent >= 80 ? "bg-primary" : percent >= 60 ? "bg-yellow-500" : "bg-red-400";

  return (
    <div className="mt-4">
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-muted-foreground">Match</span>
        <span className="font-medium">{percent}%</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-primary/20">
        <div
          className={`h-1.5 rounded-full ${fillColor} transition-all`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

function JobCard({ job }: { job: Job }) {
  return (
    <motion.div
      variants={fadeUp}
      className="rounded-3xl border border-border bg-card/60 p-6 hover:shadow-md transition-shadow flex flex-col gap-3"
    >
      {/* Company + role */}
      <div>
        <div className="text-sm font-semibold text-muted-foreground">{job.company}</div>
        <div className="mt-0.5 text-xl font-medium leading-snug">{job.role}</div>
      </div>

      {/* Badges */}
      <div className="flex flex-wrap gap-2">
        <span className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground">
          <MapPin className="h-3 w-3" />
          {job.location}
        </span>
        <span className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground">
          {job.type}
        </span>
        <span className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground">
          <Clock className="h-3 w-3" />
          {job.postedAgo}
        </span>
      </div>

      {/* Match bar */}
      <MatchBar percent={job.matchPercent} />

      {/* Skills */}
      <div className="flex flex-wrap gap-1.5">
        {job.skills.map((skill) => (
          <span
            key={skill}
            className="rounded-full bg-secondary px-2 py-0.5 text-xs text-secondary-foreground"
          >
            {skill}
          </span>
        ))}
      </div>

      {/* Actions */}
      <div className="mt-auto flex gap-2 pt-1">
        <LiquidGlassButton tone="ghost" size="sm" className="flex-1 gap-1.5">
          <Bookmark className="h-3.5 w-3.5" />
          Save
        </LiquidGlassButton>
        <LiquidGlassButton tone="primary" size="sm" className="flex-1 gap-1.5">
          <ExternalLink className="h-3.5 w-3.5" />
          Apply
        </LiquidGlassButton>
      </div>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function JobsPage() {
  const [activeFilters, setActiveFilters] = useState<Set<string>>(
    new Set(["Remote", "Full-time"]),
  );
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [xrayQuery, setXrayQuery] = useState(XRAY_TEMPLATES[0]);

  function toggleFilter(chip: string) {
    setActiveFilters((prev) => {
      const next = new Set(prev);
      next.has(chip) ? next.delete(chip) : next.add(chip);
      return next;
    });
  }

  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
      {/* ---- Header ---- */}
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
          <LiquidGlassButton tone="primary" size="sm">
            <Zap className="h-4 w-4" />
            Run Job Agent
          </LiquidGlassButton>
        </div>
      </motion.div>

      {/* ---- Search + filter chips ---- */}
      <motion.div variants={fadeUp} className="space-y-3">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
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

      {/* ---- Advanced Search (X-ray) ---- */}
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

      {/* ---- Metrics strip ---- */}
      <motion.div variants={fadeUp} className="grid grid-cols-3 gap-4">
        <div className="rounded-3xl border border-border bg-card/60 p-6">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Roles found</span>
            <Search className="h-4 w-4 text-muted-foreground" />
          </div>
          <div className="mt-4 text-3xl font-medium">47</div>
        </div>

        <div className="rounded-3xl border border-border bg-card/60 p-6">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Average match</span>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </div>
          <div className="mt-4 text-3xl font-medium">82%</div>
        </div>

        <div className="rounded-3xl border border-border bg-card/60 p-6">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">New since yesterday</span>
            <RefreshCw className="h-4 w-4 text-muted-foreground" />
          </div>
          <div className="mt-4 text-3xl font-medium">12</div>
        </div>
      </motion.div>

      {/* ---- Job cards grid ---- */}
      <motion.div
        variants={stagger}
        className="grid grid-cols-1 gap-4 lg:grid-cols-2"
      >
        {JOBS.map((job) => (
          <JobCard key={job.id} job={job} />
        ))}
      </motion.div>

      {/* ---- Agent status bar ---- */}
      <motion.div
        variants={fadeUp}
        className="flex items-center gap-3 rounded-2xl border border-border bg-card/40 px-5 py-3 text-sm text-muted-foreground"
      >
        <span className="relative flex h-2 w-2 shrink-0">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500" />
        </span>
        Job Search Agent is active — scanning 3 boards · 47 leads found · Last updated 2 min ago
      </motion.div>
    </motion.div>
  );
}
