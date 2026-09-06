"use client";

import { useState, useEffect } from "react";
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
  X,
  Brain,
  Save,
  AlertCircle,
  Briefcase,
} from "lucide-react";
import { toast } from "sonner";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { EmptyState } from "@/components/ui/EmptyState";
import { CommandHeader } from "@/components/immersive/CommandHeader";
import { apiClient } from "@/lib/api";
import { AgentStatusStream } from "@/components/agents/AgentStatusStream";
import { useAgentStore } from "@/store/agentStore";

const XRAY_TEMPLATES = [
  `site:linkedin.com/jobs "Frontend Engineer" "React" "Remote"`,
  `site:greenhouse.io OR site:lever.co "Software Engineer" "Python" "India"`,
  `"careers.stripe.com" OR "jobs.notion.so" "Software Engineer" -intern`,
];

const FILTER_CHIPS = ["Remote", "Hybrid", "Onsite", "Full-time", "Entry-level", "Bangalore", "Hyderabad", "Mumbai"];
const MODE_FILTERS = ["Remote", "Hybrid", "Onsite"];
const LOCATION_FILTERS = ["Bangalore", "Hyderabad", "Mumbai"];

const JOB_TYPE_FILTERS = ["Full-time", "Part-time", "Contract", "Internship"];
const EXPERIENCE_FILTERS = ["Entry-level", "Mid-level", "Senior", "Lead"];
const DATE_FILTERS = ["Today", "Past week", "Past month"];
const EXPERIENCE_LEVELS = ["fresher", "junior", "mid", "senior", "lead", "principal"];
const WORK_MODES = ["remote", "hybrid", "onsite"];
const JOB_TYPES = ["full-time", "part-time", "contract", "internship"];

interface SavedJob {
  id: string;
  company: string;
  role: string;
  location: string | null;
  job_url: string | null;
  match_score: number | null;
  status: string;
  applied_at: string | null;
}

interface JobSearchPrefs {
  target_roles?: string[];
  preferred_locations?: string[];
  work_mode?: string;
  job_type?: string;
  experience_level?: string;
  years_experience?: number | null;
  current_title?: string;
  bio?: string | null;
}

interface JobSearchProfile {
  resume_found: boolean;
  resume_filename?: string | null;
  role_suggestions: string[];
  skills: string[];
  inferred_years_experience?: number | null;
  inferred_experience_level?: string | null;
  saved_preferences: JobSearchPrefs;
  search_query_preview: string;
  location_preview: string;
  work_mode_preview?: string | null;
  missing_fields: string[];
  analysis_notes: string[];
}

interface SearchProfileForm {
  target_roles: string;
  preferred_locations: string;
  experience_level: string;
  years_experience: string;
  job_type: string;
  work_mode: string;
  current_title: string;
}

function splitCsv(value: string | null | undefined): string[] {
  return (value ?? "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function toggleCsvValue(value: string, item: string) {
  const values = splitCsv(value);
  if (values.includes(item)) {
    return values.length > 1 ? values.filter((v) => v !== item).join(", ") : value;
  }
  return [...values, item].join(", ");
}

function primaryCsvValue(value: string | null | undefined, fallback = "") {
  return splitCsv(value)[0] ?? fallback;
}

function titleToValue(value: string) {
  return value.toLowerCase().replace(/\s+/g, "-");
}

function modeValueToChip(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function jobTypeValueToChip(value: string) {
  const labels: Record<string, string> = {
    "full-time": "Full-time",
    "part-time": "Part-time",
    contract: "Contract",
    internship: "Internship",
  };
  return labels[value] ?? labelize(value);
}

function labelize(value: string | null | undefined): string {
  if (!value) return "Not set";
  return value.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
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

function FilterPanel({
  activeFilters,
  onToggle,
  onClear,
}: {
  activeFilters: Set<string>;
  onToggle: (chip: string) => void;
  onClear: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.25 }}
      className="overflow-hidden"
    >
      <div className="rounded-3xl border border-border bg-card/60 p-5 space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold">Filters</span>
          {activeFilters.size > 0 && (
            <button onClick={onClear} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
              <X className="h-3 w-3" /> Clear all
            </button>
          )}
        </div>

        <div>
          <p className="mb-2 text-xs font-medium text-muted-foreground">Location / Mode</p>
          <div className="flex flex-wrap gap-2">
            {["Remote", "Hybrid", "Onsite", "Bangalore", "Hyderabad", "Mumbai"].map((chip) => (
              <button
                key={chip}
                onClick={() => onToggle(chip)}
                className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                  activeFilters.has(chip)
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-card/40 text-muted-foreground hover:bg-card/70"
                }`}
              >
                {chip}
              </button>
            ))}
          </div>
        </div>

        <div>
          <p className="mb-2 text-xs font-medium text-muted-foreground">Job type</p>
          <div className="flex flex-wrap gap-2">
            {JOB_TYPE_FILTERS.map((chip) => (
              <button
                key={chip}
                onClick={() => onToggle(chip)}
                className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                  activeFilters.has(chip)
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-card/40 text-muted-foreground hover:bg-card/70"
                }`}
              >
                {chip}
              </button>
            ))}
          </div>
        </div>

        <div>
          <p className="mb-2 text-xs font-medium text-muted-foreground">Experience level</p>
          <div className="flex flex-wrap gap-2">
            {EXPERIENCE_FILTERS.map((chip) => (
              <button
                key={chip}
                onClick={() => onToggle(chip)}
                className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                  activeFilters.has(chip)
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-card/40 text-muted-foreground hover:bg-card/70"
                }`}
              >
                {chip}
              </button>
            ))}
          </div>
        </div>

        <div>
          <p className="mb-2 text-xs font-medium text-muted-foreground">Date posted</p>
          <div className="flex flex-wrap gap-2">
            {DATE_FILTERS.map((chip) => (
              <button
                key={chip}
                onClick={() => onToggle(chip)}
                className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                  activeFilters.has(chip)
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-card/40 text-muted-foreground hover:bg-card/70"
                }`}
              >
                {chip}
              </button>
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function ProfileSearchPanel({
  profile,
  form,
  saving,
  onChange,
  onSave,
  onRun,
}: {
  profile: JobSearchProfile | undefined;
  form: SearchProfileForm;
  saving: boolean;
  onChange: (key: keyof SearchProfileForm, value: string) => void;
  onSave: () => void;
  onRun: () => void;
}) {
  const suggestions = profile?.role_suggestions ?? [];
  const skills = profile?.skills ?? [];
  const missing = profile?.missing_fields ?? [];

  return (
    <motion.div variants={fadeUp} className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
      <div className="glass-panel rounded-3xl p-6">
        <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <Brain className="h-4 w-4 text-primary" />
              Resume-first search profile
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Agents analyze resume, then you confirm fresher/years, role, location, and work mode.
            </p>
          </div>
          <span className="rounded-full border border-border bg-card/40 px-3 py-1 text-xs text-muted-foreground">
            {profile?.resume_found ? profile.resume_filename ?? "Resume found" : "No resume yet"}
          </span>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <label className="space-y-1.5 text-xs font-medium text-muted-foreground">
            Target roles
            <input
              value={form.target_roles}
              onChange={(e) => onChange("target_roles", e.target.value)}
              placeholder="Frontend Engineer, React Developer"
              className="w-full rounded-2xl border border-border bg-card/40 px-4 py-2.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </label>
          <label className="space-y-1.5 text-xs font-medium text-muted-foreground">
            Preferred locations
            <input
              value={form.preferred_locations}
              onChange={(e) => onChange("preferred_locations", e.target.value)}
              placeholder="Remote, Bangalore, Hyderabad"
              className="w-full rounded-2xl border border-border bg-card/40 px-4 py-2.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </label>
          <label className="space-y-1.5 text-xs font-medium text-muted-foreground">
            Are you fresher or experienced?
            <select
              value={form.experience_level}
              onChange={(e) =>
                onChange("experience_level", e.target.value)
              }
              className="w-full rounded-2xl border border-border bg-card/40 px-4 py-2.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            >
              {EXPERIENCE_LEVELS.map((level) => (
                <option key={level} value={level}>
                  {labelize(level)}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1.5 text-xs font-medium text-muted-foreground">
            Exact years
            <input
              type="number"
              min={0}
              max={60}
              value={form.years_experience}
              onChange={(e) => onChange("years_experience", e.target.value)}
              placeholder="0 for fresher"
              className="w-full rounded-2xl border border-border bg-card/40 px-4 py-2.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </label>
          <div className="space-y-2">
            <div className="text-xs font-medium text-muted-foreground">Job type</div>
            <div className="flex flex-wrap gap-2">
              {JOB_TYPES.map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => onChange("job_type", toggleCsvValue(form.job_type, type))}
                  aria-pressed={splitCsv(form.job_type).includes(type)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium capitalize transition-colors ${
                    splitCsv(form.job_type).includes(type)
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-card/40 text-muted-foreground hover:bg-card/70"
                  }`}
                >
                  {labelize(type)}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-2">
            <div className="text-xs font-medium text-muted-foreground">Work mode</div>
            <div className="flex flex-wrap gap-2">
              {WORK_MODES.map((mode) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => onChange("work_mode", toggleCsvValue(form.work_mode, mode))}
                  aria-pressed={splitCsv(form.work_mode).includes(mode)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium capitalize transition-colors ${
                    splitCsv(form.work_mode).includes(mode)
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-card/40 text-muted-foreground hover:bg-card/70"
                  }`}
                >
                  {labelize(mode)}
                </button>
              ))}
            </div>
          </div>
        </div>

        {suggestions.length > 0 && (
          <div className="mt-4">
            <div className="mb-2 text-xs font-medium text-muted-foreground">Resume role suggestions</div>
            <div className="flex flex-wrap gap-2">
              {suggestions.map((role) => (
                <button
                  key={role}
                  type="button"
                  onClick={() => onChange("target_roles", role)}
                  className="rounded-full border border-primary/35 bg-primary/10 px-3 py-1 text-xs font-medium text-primary transition-colors hover:bg-primary/15"
                >
                  {role}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="mt-5 flex flex-wrap gap-2">
          <LiquidGlassButton tone="primary" size="sm" onClick={onRun}>
            <Search className="h-4 w-4" />
            Search with this profile
          </LiquidGlassButton>
          <LiquidGlassButton tone="ghost" size="sm" onClick={onSave} disabled={saving}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save preferences
          </LiquidGlassButton>
        </div>
      </div>

      <div className="glass-panel rounded-3xl p-6">
        <div className="mb-4 flex items-center gap-2 text-sm font-semibold">
          <Briefcase className="h-4 w-4 text-primary" />
          Search plan
        </div>
        <div className="space-y-3 text-sm">
          <div className="rounded-2xl border border-border bg-card/35 p-3">
            <p className="text-xs text-muted-foreground">Query preview</p>
            <p className="mt-1 font-medium text-foreground">{profile?.search_query_preview || "Set target role"}</p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-2xl border border-border bg-card/35 p-3">
              <p className="text-xs text-muted-foreground">Location</p>
              <p className="mt-1 font-medium">{profile?.location_preview || form.preferred_locations || "Any"}</p>
            </div>
            <div className="rounded-2xl border border-border bg-card/35 p-3">
              <p className="text-xs text-muted-foreground">Experience</p>
              <p className="mt-1 font-medium">
                {form.years_experience ? `${form.years_experience} yr` : "Confirm"} · {labelize(form.experience_level)}
              </p>
            </div>
          </div>

          {skills.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-medium text-muted-foreground">Skills found in resume</p>
              <div className="flex flex-wrap gap-2">
                {skills.map((skill) => (
                  <span key={skill} className="rounded-full border border-border bg-card/35 px-2.5 py-1 text-xs">
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )}

          {missing.length > 0 && (
            <div className="rounded-2xl border border-warning/30 bg-warning/10 p-3 text-warning">
              <div className="mb-1 flex items-center gap-2 text-xs font-semibold">
                <AlertCircle className="h-3.5 w-3.5" />
                Needs confirmation
              </div>
              <p className="text-xs">{missing.join(", ")}</p>
            </div>
          )}

          {(profile?.analysis_notes ?? []).map((note) => (
            <p key={note} className="text-xs text-muted-foreground">
              {note}
            </p>
          ))}
        </div>
      </div>
    </motion.div>
  );
}

function MatchBar({ percent }: { percent: number | null }) {
  const p = percent ?? 0;
  const fillColor = p >= 80 ? "bg-primary" : p >= 60 ? "bg-warning" : "bg-danger";

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

function JobCard({ job, onPrepareApply }: { job: SavedJob; onPrepareApply: (job: SavedJob) => void }) {
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
        {job.location && (
          <span className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground">
            <MapPin className="h-3 w-3" />
            {job.location}
          </span>
        )}
        {domain && (
          <span className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground">
            <ExternalLink className="h-3 w-3" />
            {domain}
          </span>
        )}
        <span className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground">
          <Clock className="h-3 w-3" />
          {relativeTime(job.applied_at)}
        </span>
        <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
          job.status === "applied" ? "bg-success/15 text-success"
          : job.status === "saved" ? "bg-primary/15 text-primary"
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
            onClick={() => {
              // Open the real job posting so the user can apply directly...
              if (job.job_url) window.open(job.job_url, "_blank", "noopener,noreferrer");
              // ...and kick off the human-in-the-loop auto-apply prep.
              onPrepareApply(job);
            }}
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
    new Set(["Full-time"]),
  );
  const [showFilters, setShowFilters] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [xrayQuery, setXrayQuery] = useState(XRAY_TEMPLATES[0]);
  const [searchQuery, setSearchQuery] = useState("");
  const [agentRunning, setAgentRunning] = useState(false);
  const [liveBrowser, setLiveBrowser] = useState(true);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [profileForm, setProfileForm] = useState<SearchProfileForm>({
    target_roles: "",
    preferred_locations: "",
    experience_level: "fresher",
    years_experience: "0",
    job_type: "full-time",
    work_mode: "remote",
    current_title: "",
  });
  const [profileInitialized, setProfileInitialized] = useState(false);
  const initRun = useAgentStore((s) => s.initRun);
  const addEvent = useAgentStore((s) => s.addEvent);
  const setCheckpoint = useAgentStore((s) => s.setCheckpoint);
  const setRunStatus = useAgentStore((s) => s.setRunStatus);
  const storeActiveRunId = useAgentStore((s) => s.activeRunId);
  const setActiveRun = useAgentStore((s) => s.setActiveRun);
  // Persisted run survives navigation + reload, so the live view reappears on return.
  const displayRunId = activeRunId ?? storeActiveRunId;
  const activeRunStatus = useAgentStore((s) =>
    activeRunId ? s.runs[activeRunId]?.status : undefined,
  );

  const { data: jobs = [], isLoading } = useQuery<SavedJob[]>({
    queryKey: ["jobs-saved", Array.from(activeFilters).sort().join(",")],
    queryFn: async () => {
      const params = new URLSearchParams({ status: "saved" });
      // Pass active filters to backend
      const locations = Array.from(activeFilters).filter((f) =>
        ["Remote", "Hybrid", "Onsite", "Bangalore", "Hyderabad", "Mumbai"].includes(f)
      );
      const jobTypes = Array.from(activeFilters).filter((f) =>
        ["Full-time", "Part-time", "Contract", "Internship"].includes(f)
      );
      const expLevels = Array.from(activeFilters).filter((f) =>
        ["Entry-level", "Mid-level", "Senior", "Lead"].includes(f)
      );
      if (locations.length > 0) params.set("location", locations.join(","));
      if (jobTypes.length > 0) params.set("job_type", jobTypes.join(","));
      if (expLevels.length > 0) params.set("experience_level", expLevels.join(","));
      const { data } = await apiClient.get(`/jobs/applications?${params.toString()}`);
      return data;
    },
  });

  const { data: prefs } = useQuery({
    queryKey: ["preferences"],
    queryFn: async () => {
      const { data } = await apiClient.get("/users/me/preferences");
      return data as {
        target_roles?: string[];
        preferred_locations?: string[];
        work_mode?: string;
        job_type?: string;
        experience_level?: string;
        years_experience?: number | null;
        current_title?: string;
      } | null;
    },
  });

  const { data: searchProfile } = useQuery<JobSearchProfile>({
    queryKey: ["job-search-profile"],
    queryFn: async () => {
      const { data } = await apiClient.get("/users/me/job-search-profile");
      return data;
    },
  });

  useEffect(() => {
    if (!searchProfile || profileInitialized) return;
    const saved = searchProfile.saved_preferences ?? {};
    const inferredYears = saved.years_experience ?? searchProfile.inferred_years_experience;
    setProfileForm({
      target_roles: (saved.target_roles?.length ? saved.target_roles : searchProfile.role_suggestions).join(", "),
      preferred_locations: (saved.preferred_locations ?? []).join(", "),
      experience_level: saved.experience_level ?? searchProfile.inferred_experience_level ?? "fresher",
      years_experience: inferredYears != null ? String(inferredYears) : "",
      job_type: saved.job_type ?? "full-time",
      work_mode: saved.work_mode ?? searchProfile.work_mode_preview ?? "remote",
      current_title: saved.current_title ?? "",
    });
    setProfileInitialized(true);
  }, [searchProfile, profileInitialized]);

  // Prefill search form and filters from saved preferences on first load
  useEffect(() => {
    if (!prefs) return;
    setActiveFilters((prev) => {
      const next = new Set(prev);
      splitCsv(prefs.work_mode).forEach((mode) => {
        const chip = modeValueToChip(mode);
        if (MODE_FILTERS.includes(chip)) next.add(chip);
      });
      splitCsv(prefs.job_type).forEach((type) => {
        const chip = jobTypeValueToChip(type);
        if (JOB_TYPE_FILTERS.includes(chip)) next.add(chip);
      });
      if (
        (prefs.experience_level === "fresher" || prefs.experience_level === "junior") &&
        !next.has("Entry-level")
      ) {
        next.add("Entry-level");
      }
      return next;
    });
  }, [prefs]);

  const searchMutation = useMutation({
    mutationFn: (payload: {
      search_query: string;
      location: string;
      max_results: number;
      live_browser: boolean;
      work_mode: string;
      experience_level?: string;
      years_experience?: number;
      job_type?: string;
      target_roles?: string[];
      preferred_locations?: string[];
    }) =>
      apiClient.post("/jobs/search", payload),
    onSuccess: (res) => {
      setAgentRunning(true);
      const runId = res.data?.run_id as string | undefined;
      if (runId) {
        initRun(runId);
        setActiveRunId(runId);
      }
      toast.success("Job Agent started — scanning boards for matching roles");
    },
    onError: () => {
      toast.error("Job Agent unavailable — backend not connected");
    },
  });

  const saveProfileMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        current_title: profileForm.current_title || undefined,
        experience_level: profileForm.experience_level || undefined,
        years_experience: profileForm.years_experience ? parseInt(profileForm.years_experience, 10) : undefined,
        job_type: profileForm.job_type || undefined,
        work_mode: profileForm.work_mode || undefined,
        target_roles: splitCsv(profileForm.target_roles),
        preferred_locations: splitCsv(profileForm.preferred_locations),
      };
      const { data } = await apiClient.patch("/users/me/preferences", payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["preferences"] });
      qc.invalidateQueries({ queryKey: ["job-search-profile"] });
      toast.success("Search preferences saved");
    },
    onError: () => toast.error("Could not save search preferences"),
  });

  useEffect(() => {
    if (!activeRunId || !activeRunStatus) return;
    if (activeRunStatus === "completed" || activeRunStatus === "failed") {
      setAgentRunning(false);
      qc.invalidateQueries({ queryKey: ["jobs-saved"] });
    }
  }, [activeRunId, activeRunStatus, qc]);

  useEffect(() => {
    if (!activeRunId || activeRunStatus !== "running") return;
    let stopped = false;
    const interval = window.setInterval(async () => {
      try {
        const { data } = await apiClient.get("/agents/runs?limit=20");
        const run = (data as Array<{
          id: string;
          status: "completed" | "failed" | "running" | "awaiting_approval";
          output?: Record<string, unknown> | null;
        }>)
          .find((item) => item.id === activeRunId);
        if (
          !stopped &&
          run &&
          (run.status === "completed" ||
            run.status === "failed" ||
            run.status === "awaiting_approval")
        ) {
          if (run.status === "awaiting_approval") {
            addEvent(activeRunId, "checkpoint", run.output ?? {});
            setCheckpoint(activeRunId, (run.output ?? {}) as Record<string, unknown>);
          } else {
            setRunStatus(activeRunId, run.status);
          }
        }
      } catch {
        // SSE remains primary; polling only protects against missed terminal events.
      }
    }, 5000);
    return () => {
      stopped = true;
      window.clearInterval(interval);
    };
  }, [activeRunId, activeRunStatus, addEvent, setCheckpoint, setRunStatus]);

  const prepareApplyMutation = useMutation({
    mutationFn: (job: SavedJob) =>
      apiClient.post(`/jobs/applications/${job.id}/prepare-apply`, { live_browser: liveBrowser }),
    onSuccess: (res) => {
      const runId = res.data?.run_id as string | undefined;
      if (runId) {
        initRun(runId);
        setActiveRunId(runId);
      }
      toast.success("Live apply prep started — review before submitting");
    },
    onError: () => toast.error("Could not start live apply prep"),
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
      if (next.has(chip)) {
        next.delete(chip);
      } else {
        if (LOCATION_FILTERS.includes(chip)) {
          next.delete("Remote");
        }
        next.add(chip);
      }
      return next;
    });
  }

  function updateProfileForm(key: keyof SearchProfileForm, value: string) {
    setProfileForm((prev) => ({
      ...prev,
      [key]: value,
      ...(key === "experience_level" && value === "fresher" && !prev.years_experience
        ? { years_experience: "0" }
        : {}),
    }));
  }

  function handleRunAgent() {
    const query = searchQuery.trim();
    const manualRoles = splitCsv(profileForm.target_roles);
    const manualLocations = splitCsv(profileForm.preferred_locations);
    const selectedLocation = Array.from(activeFilters).find((f) =>
      LOCATION_FILTERS.includes(f)
    );
    const selectedModes = Array.from(activeFilters)
      .filter((f) => MODE_FILTERS.includes(f))
      .map(titleToValue);
    const workMode = selectedModes.length > 0
      ? selectedModes.join(",")
      : profileForm.work_mode || (selectedLocation ? "" : prefs?.work_mode ?? "");
    const locationFromProfile = manualLocations[0] ?? "";
    const primaryWorkMode = primaryCsvValue(workMode);
    searchMutation.mutate({
      search_query: query,
      location: primaryWorkMode === "remote" ? "Remote" : (selectedLocation ?? locationFromProfile) || "Any",
      max_results: 10,
      live_browser: liveBrowser,
      work_mode: workMode,
      experience_level: profileForm.experience_level,
      years_experience: profileForm.years_experience ? parseInt(profileForm.years_experience, 10) : undefined,
      job_type: profileForm.job_type,
      target_roles: manualRoles,
      preferred_locations: manualLocations,
    });
  }

  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
      <CommandHeader
        eyebrow="Grow AI Talent Platform"
        title="Find your next role."
        description="Resume is analyzed first. Confirm fresher/years, target roles, location, and work mode before agents search."
        actions={
        <div className="flex shrink-0 flex-wrap gap-2">
          <LiquidGlassButton
            tone={showFilters ? "primary" : "ghost"}
            size="sm"
            onClick={() => setShowFilters((v) => !v)}
          >
            <Filter className="h-4 w-4" />
            Filters
            {activeFilters.size > 0 && (
              <span className="ml-1 rounded-full bg-current/20 px-1.5 py-0.5 text-[10px] font-semibold">
                {activeFilters.size}
              </span>
            )}
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
        }
      />

      <ProfileSearchPanel
        profile={searchProfile}
        form={profileForm}
        saving={saveProfileMutation.isPending}
        onChange={updateProfileForm}
        onSave={() => saveProfileMutation.mutate()}
        onRun={handleRunAgent}
      />

      {/* Search + active filter chips */}
      <motion.div variants={fadeUp} className="space-y-3">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleRunAgent()}
            placeholder="Leave blank to use resume + saved preferences, or type custom role…"
            className="h-11 w-full rounded-full border border-border bg-card/40 pl-11 pr-4 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-border bg-card/40 px-3 py-1 text-xs text-muted-foreground">
            {searchQuery.trim()
              ? "Custom search"
              : splitCsv(profileForm.target_roles)[0]
                ? `Using profile: ${splitCsv(profileForm.target_roles)[0]}`
                : searchProfile?.search_query_preview
                  ? `Resume plan: ${searchProfile.search_query_preview}`
                  : "Using resume/profile"}
          </span>
          <button
            type="button"
            onClick={() => setLiveBrowser((v) => !v)}
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs transition-colors ${
              liveBrowser
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-card/40 text-muted-foreground hover:bg-card/70"
            }`}
          >
            <span className="relative flex h-2 w-2">
              {liveBrowser && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-60" />}
              <span className="relative inline-flex h-2 w-2 rounded-full bg-current" />
            </span>
            Watch browser
          </button>
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

      {/* Filter panel */}
      <AnimatePresence>
        {showFilters && (
          <FilterPanel
            activeFilters={activeFilters}
            onToggle={toggleFilter}
            onClear={() => setActiveFilters(new Set())}
          />
        )}
      </AnimatePresence>

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

      {displayRunId && (
        <motion.div variants={fadeUp}>
          <AgentStatusStream
            runId={displayRunId}
            onApprove={() => {
              qc.invalidateQueries({ queryKey: ["jobs-saved"] });
              setActiveRunId(null);
              setActiveRun(null);
            }}
            onCancel={() => {
              setActiveRunId(null);
              setActiveRun(null);
            }}
          />
        </motion.div>
      )}

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
            <JobCard key={job.id} job={job} onPrepareApply={(selected) => prepareApplyMutation.mutate(selected)} />
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
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-success" />
            </span>
            Job Search Agent ready — {jobs.length > 0 ? `${jobs.length} roles saved` : "run agent to discover roles"}
          </>
        )}
      </motion.div>
    </motion.div>
  );
}
