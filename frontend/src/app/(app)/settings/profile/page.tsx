"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Briefcase, MapPin, DollarSign, Target, Loader2, X, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { apiClient } from "@/lib/api";
import { cn } from "@/lib/utils";

interface UserPreferences {
  experience_level: string | null;
  job_type: string | null;
  work_mode: string | null;
  salary_min: number | null;
  salary_max: number | null;
  target_roles: string[];
  preferred_locations: string[];
  current_title: string | null;
  bio: string | null;
}

interface FormState {
  current_title: string;
  experience_level: string;
  job_type: string;
  work_mode: string;
  salary_min: string;
  salary_max: string;
  target_roles: string;
  preferred_locations: string;
  bio: string;
}

const EXPERIENCE_LEVELS = ["fresher", "junior", "mid", "senior", "lead", "principal"];
const JOB_TYPES = ["full-time", "part-time", "contract", "freelance", "internship"];
const WORK_MODES = ["remote", "hybrid", "onsite"];

const POPULAR_ROLES = [
  "Software Engineer",
  "Frontend Engineer",
  "Backend Engineer",
  "Full Stack Developer",
  "DevOps Engineer",
  "Site Reliability Engineer",
  "Data Engineer",
  "Data Scientist",
  "ML Engineer",
  "AI Engineer",
  "Product Manager",
  "UX Designer",
  "Android Developer",
  "iOS Developer",
  "Cloud Architect",
  "QA Engineer",
  "Python Developer",
  "React Developer",
  "Node.js Developer",
  "Security Engineer",
];

function PillButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "rounded-full border px-3 py-1 text-xs font-medium capitalize transition-colors",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-card/40 text-muted-foreground hover:bg-card/70",
      )}
    >
      {label}
    </button>
  );
}

function TagPill({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-border bg-secondary px-2.5 py-0.5 text-xs">
      {label}
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Remove ${label}`}
        className="ml-0.5 text-muted-foreground hover:text-foreground"
      >
        <X className="h-3 w-3" />
      </button>
    </span>
  );
}

export default function ProfilePreferencesPage() {
  const queryClient = useQueryClient();

  const { data: prefs, isLoading } = useQuery<UserPreferences | null>({
    queryKey: ["preferences"],
    queryFn: async () => {
      const { data } = await apiClient.get("/users/me/preferences");
      return data as UserPreferences | null;
    },
  });

  const [form, setForm] = useState<FormState>({
    current_title: "",
    experience_level: "mid",
    job_type: "full-time",
    work_mode: "remote",
    salary_min: "",
    salary_max: "",
    target_roles: "",
    preferred_locations: "",
    bio: "",
  });

  const [suggestingRoles, setSuggestingRoles] = useState(false);
  const [suggestedRoles, setSuggestedRoles] = useState<string[]>([]);

  useEffect(() => {
    if (prefs) {
      setForm({
        current_title: prefs.current_title ?? "",
        experience_level: prefs.experience_level ?? "mid",
        job_type: prefs.job_type ?? "full-time",
        work_mode: prefs.work_mode ?? "remote",
        salary_min: prefs.salary_min != null ? String(prefs.salary_min) : "",
        salary_max: prefs.salary_max != null ? String(prefs.salary_max) : "",
        target_roles: (prefs.target_roles ?? []).join(", "),
        preferred_locations: (prefs.preferred_locations ?? []).join(", "),
        bio: prefs.bio ?? "",
      });
    }
  }, [prefs]);

  function set(key: keyof FormState, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  const parsedRoles = form.target_roles
    .split(",")
    .map((r) => r.trim())
    .filter(Boolean);

  const parsedLocations = form.preferred_locations
    .split(",")
    .map((l) => l.trim())
    .filter(Boolean);

  function removeRole(role: string) {
    const updated = parsedRoles.filter((r) => r !== role).join(", ");
    set("target_roles", updated);
  }

  function addRole(role: string) {
    if (!parsedRoles.includes(role)) {
      set("target_roles", [...parsedRoles, role].join(", "));
    }
  }

  async function handleSuggestRoles() {
    setSuggestingRoles(true);
    try {
      const { data } = await apiClient.get("/rag/documents?doc_type=resume");
      const docs = data as { id: string; ats_data: { matched_keywords: string[] } | null }[];
      const keywords: string[] = docs?.[0]?.ats_data?.matched_keywords ?? [];
      const matched =
        keywords.length > 0
          ? POPULAR_ROLES.filter((role) =>
              keywords.some(
                (kw) =>
                  role.toLowerCase().includes(kw.toLowerCase()) ||
                  kw.toLowerCase().includes(role.toLowerCase().split(" ")[0].toLowerCase())
              )
            )
          : [];
      setSuggestedRoles(matched.length >= 3 ? matched.slice(0, 6) : POPULAR_ROLES.slice(0, 5));
      if (!matched.length) toast.info("Upload a resume to get AI-powered role suggestions");
    } catch {
      setSuggestedRoles(POPULAR_ROLES.slice(0, 5));
    } finally {
      setSuggestingRoles(false);
    }
  }

  function removeLocation(loc: string) {
    const updated = parsedLocations.filter((l) => l !== loc).join(", ");
    set("preferred_locations", updated);
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        current_title: form.current_title || undefined,
        experience_level: form.experience_level || undefined,
        job_type: form.job_type || undefined,
        work_mode: form.work_mode || undefined,
        salary_min: form.salary_min ? parseInt(form.salary_min, 10) : undefined,
        salary_max: form.salary_max ? parseInt(form.salary_max, 10) : undefined,
        target_roles: parsedRoles,
        preferred_locations: parsedLocations,
        bio: form.bio || undefined,
      };
      const { data } = await apiClient.patch("/users/me/preferences", payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["preferences"] });
      toast.success("Preferences saved");
    },
    onError: () => toast.error("Save failed"),
  });

  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
      {/* Header */}
      <motion.div variants={fadeUp}>
        <div className="text-sm text-muted-foreground">Settings / Job Preferences</div>
        <h1 className="mt-1 text-3xl font-medium">Job preferences</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Tell agents what you&apos;re looking for — they&apos;ll use this to tailor every search and application.
        </p>
      </motion.div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading preferences…
        </div>
      ) : (
        <div className="space-y-6">
          {/* Current title */}
          <motion.div variants={fadeUp} className="rounded-3xl border border-border bg-card/60 p-6">
            <div className="mb-4 flex items-center gap-2">
              <Briefcase className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">Current title</span>
            </div>
            <input
              type="text"
              value={form.current_title}
              onChange={(e) => set("current_title", e.target.value)}
              placeholder="e.g. Software Engineer, Product Manager…"
              className="w-full rounded-2xl border border-border bg-card/40 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </motion.div>

          {/* Experience, job type, work mode */}
          <motion.div variants={fadeUp} className="rounded-3xl border border-border bg-card/60 p-6 space-y-5">
            <div className="text-sm font-medium">Experience &amp; work type</div>

            <div>
              <label className="mb-2 block text-xs text-muted-foreground">Experience level</label>
              <div className="flex flex-wrap gap-2">
                {EXPERIENCE_LEVELS.map((lvl) => (
                  <PillButton
                    key={lvl}
                    label={lvl}
                    active={form.experience_level === lvl}
                    onClick={() => set("experience_level", lvl)}
                  />
                ))}
              </div>
            </div>

            <div>
              <label className="mb-2 block text-xs text-muted-foreground">Job type</label>
              <div className="flex flex-wrap gap-2">
                {JOB_TYPES.map((jt) => (
                  <PillButton
                    key={jt}
                    label={jt}
                    active={form.job_type === jt}
                    onClick={() => set("job_type", jt)}
                  />
                ))}
              </div>
            </div>

            <div>
              <label className="mb-2 block text-xs text-muted-foreground">Work mode</label>
              <div className="flex flex-wrap gap-2">
                {WORK_MODES.map((wm) => (
                  <PillButton
                    key={wm}
                    label={wm}
                    active={form.work_mode === wm}
                    onClick={() => set("work_mode", wm)}
                  />
                ))}
              </div>
            </div>
          </motion.div>

          {/* Salary range */}
          <motion.div variants={fadeUp} className="rounded-3xl border border-border bg-card/60 p-6">
            <div className="mb-4 flex items-center gap-2">
              <DollarSign className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">Salary range</span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1.5 block text-xs text-muted-foreground">Minimum (USD/yr)</label>
                <div className="relative">
                  <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">$</span>
                  <input
                    type="number"
                    min={0}
                    value={form.salary_min}
                    onChange={(e) => set("salary_min", e.target.value)}
                    placeholder="80000"
                    className="w-full rounded-2xl border border-border bg-card/40 pl-7 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
              </div>
              <div>
                <label className="mb-1.5 block text-xs text-muted-foreground">Maximum (USD/yr)</label>
                <div className="relative">
                  <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">$</span>
                  <input
                    type="number"
                    min={0}
                    value={form.salary_max}
                    onChange={(e) => set("salary_max", e.target.value)}
                    placeholder="150000"
                    className="w-full rounded-2xl border border-border bg-card/40 pl-7 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
              </div>
            </div>
          </motion.div>

          {/* Target roles */}
          <motion.div variants={fadeUp} className="rounded-3xl border border-border bg-card/60 p-6">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Target className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium">Target roles</span>
              </div>
              <button
                type="button"
                onClick={handleSuggestRoles}
                disabled={suggestingRoles}
                className="flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/5 px-3 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-primary/10 disabled:opacity-50"
              >
                {suggestingRoles ? (
                  <span className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
                ) : (
                  <Sparkles className="h-3 w-3" />
                )}
                {suggestingRoles ? "Analyzing…" : "Suggest from resume"}
              </button>
            </div>
            <input
              type="text"
              value={form.target_roles}
              onChange={(e) => set("target_roles", e.target.value)}
              placeholder="Frontend Engineer, Full Stack Developer, React Developer"
              className="w-full rounded-2xl border border-border bg-card/40 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <p className="mt-1.5 text-xs text-muted-foreground">Comma-separated. Click chips below to add.</p>
            {parsedRoles.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {parsedRoles.map((role) => (
                  <TagPill key={role} label={role} onRemove={() => removeRole(role)} />
                ))}
              </div>
            )}
            {suggestedRoles.length > 0 && (
              <div className="mt-4">
                <div className="mb-2 text-xs font-medium text-primary">AI suggestions — click to add</div>
                <div className="flex flex-wrap gap-2">
                  {suggestedRoles.map((r) => (
                    <button
                      key={r}
                      type="button"
                      onClick={() => addRole(r)}
                      disabled={parsedRoles.includes(r)}
                      className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                        parsedRoles.includes(r)
                          ? "border-primary/30 bg-primary/5 text-primary/50 cursor-default"
                          : "border-primary/40 bg-primary/5 text-primary hover:bg-primary/10"
                      }`}
                    >
                      {parsedRoles.includes(r) ? `✓ ${r}` : `+ ${r}`}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <div className="mt-4">
              <div className="mb-2 text-xs text-muted-foreground">Popular roles — click to add</div>
              <div className="flex flex-wrap gap-2">
                {POPULAR_ROLES.map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => addRole(r)}
                    disabled={parsedRoles.includes(r)}
                    className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                      parsedRoles.includes(r)
                        ? "border-primary/30 bg-primary/5 text-primary/50 cursor-default"
                        : "border-border text-muted-foreground hover:border-primary/50 hover:text-foreground"
                    }`}
                  >
                    {parsedRoles.includes(r) ? `✓ ${r}` : r}
                  </button>
                ))}
              </div>
            </div>
          </motion.div>

          {/* Preferred locations */}
          <motion.div variants={fadeUp} className="rounded-3xl border border-border bg-card/60 p-6">
            <div className="mb-4 flex items-center gap-2">
              <MapPin className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">Preferred locations</span>
            </div>
            <input
              type="text"
              value={form.preferred_locations}
              onChange={(e) => set("preferred_locations", e.target.value)}
              placeholder="Remote, Bangalore, San Francisco, New York"
              className="w-full rounded-2xl border border-border bg-card/40 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <p className="mt-1.5 text-xs text-muted-foreground">Comma-separated list of locations</p>
            {parsedLocations.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {parsedLocations.map((loc) => (
                  <TagPill key={loc} label={loc} onRemove={() => removeLocation(loc)} />
                ))}
              </div>
            )}
          </motion.div>

          {/* Bio */}
          <motion.div variants={fadeUp} className="rounded-3xl border border-border bg-card/60 p-6">
            <div className="mb-4 text-sm font-medium">Bio</div>
            <textarea
              rows={4}
              value={form.bio}
              onChange={(e) => set("bio", e.target.value)}
              placeholder="A short summary about yourself, your skills, and what you're looking for in your next role…"
              className="w-full resize-none rounded-2xl border border-border bg-card/40 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </motion.div>

          {/* Save */}
          <motion.div variants={fadeUp} className="flex items-center gap-3">
            <LiquidGlassButton
              tone="primary"
              size="md"
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending}
            >
              {saveMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Saving…
                </>
              ) : (
                "Save preferences"
              )}
            </LiquidGlassButton>
            <a href="/settings/account" className="text-sm text-muted-foreground hover:text-foreground">
              ← Back to account
            </a>
          </motion.div>
        </div>
      )}
    </motion.div>
  );
}
