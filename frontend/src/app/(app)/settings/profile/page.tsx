"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  ArrowLeft,
  Briefcase,
  Browser,
  Check,
  CalendarCheck,
  CircleNotch,
  EnvelopeSimple,
  CurrencyDollar,
  FloppyDisk,
  MapPin,
  Plus,
  Sparkle,
  SuitcaseSimple,
  Target,
  TextAlignLeft,
  X,
} from "@phosphor-icons/react";
import { apiClient } from "@/lib/api";
import { cn } from "@/lib/utils";
import { SettingsNav } from "@/components/settings/SettingsNav";
import {
  Bezel,
  Chip,
  Field,
  Hairline,
  Input,
  IslandButton,
  IslandLink,
  PageHero,
  PanelTitle,
  Reveal,
  Screen,
  Skeleton,
  StatusPill,
  Textarea,
  Toggle,
} from "@/components/vanguard";

interface UserPreferences {
  experience_level: string | null;
  years_experience: number | null;
  job_type: string | null;
  work_mode: string | null;
  salary_min: number | null;
  salary_max: number | null;
  target_roles: string[];
  preferred_locations: string[];
  current_title: string | null;
  bio: string | null;
  // When true, autonomous job search + apply open a visible Chromium and
  // stream browser_frame SSE events to the UI.  Default false (headless).
  prefer_live_browser: boolean;
  // Opt-in: the scheduled morning search runs only for members who turn it on.
  daily_search_enabled: boolean;
  // Opt-in: scan the connected Gmail for replies and move applications forward.
  inbox_tracking_enabled: boolean;
  // Recruiter emails per rolling 24 hours, and whether approved-before senders go out unattended.
  outreach_daily_cap: number;
  outreach_auto_send: boolean;
  outreach_track_opens: boolean;
  // Opt-in: tailor a resume and queue applications for saved jobs above the match threshold.
  auto_apply_enabled: boolean;
}

interface FormState {
  current_title: string;
  experience_level: string;
  years_experience: string;
  job_type: string;
  work_mode: string;
  salary_min: string;
  salary_max: string;
  target_roles: string;
  preferred_locations: string;
  bio: string;
  prefer_live_browser: boolean;
  daily_search_enabled: boolean;
  inbox_tracking_enabled: boolean;
  outreach_daily_cap: string;
  outreach_auto_send: boolean;
  outreach_track_opens: boolean;
  auto_apply_enabled: boolean;
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

const DEFAULT_FORM: FormState = {
  current_title: "",
  experience_level: "mid",
  years_experience: "",
  job_type: "full-time",
  work_mode: "remote",
  salary_min: "",
  salary_max: "",
  target_roles: "",
  preferred_locations: "",
  bio: "",
  prefer_live_browser: false,
  daily_search_enabled: false,
  inbox_tracking_enabled: false,
  outreach_daily_cap: "25",
  outreach_auto_send: false,
  outreach_track_opens: false,
  auto_apply_enabled: false,
};

function prefsToForm(prefs: UserPreferences): FormState {
  return {
    current_title: prefs.current_title ?? "",
    experience_level: prefs.experience_level ?? "mid",
    years_experience: prefs.years_experience != null ? String(prefs.years_experience) : "",
    job_type: prefs.job_type ?? "full-time",
    work_mode: prefs.work_mode ?? "remote",
    salary_min: prefs.salary_min != null ? String(prefs.salary_min) : "",
    salary_max: prefs.salary_max != null ? String(prefs.salary_max) : "",
    target_roles: (prefs.target_roles ?? []).join(", "),
    preferred_locations: (prefs.preferred_locations ?? []).join(", "),
    bio: prefs.bio ?? "",
    prefer_live_browser: Boolean(prefs.prefer_live_browser),
    daily_search_enabled: Boolean(prefs.daily_search_enabled),
    inbox_tracking_enabled: Boolean(prefs.inbox_tracking_enabled),
    outreach_daily_cap: String(prefs.outreach_daily_cap ?? 25),
    outreach_auto_send: Boolean(prefs.outreach_auto_send),
    outreach_track_opens: Boolean(prefs.outreach_track_opens),
    auto_apply_enabled: Boolean(prefs.auto_apply_enabled),
  };
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

const compactUsd = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});

function formatSalary(value: string): string | null {
  const n = parseInt(value, 10);
  return Number.isFinite(n) ? compactUsd.format(n) : null;
}

/** Removable tag for parsed target roles / locations. */
function TagPill({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-foreground/[0.04] py-1 pl-3 pr-1 text-xs font-medium text-foreground ring-1 ring-foreground/[0.08] dark:bg-white/[0.05] dark:ring-white/10">
      {label}
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Remove ${label}`}
        className="grid h-5 w-5 place-items-center rounded-full text-muted-foreground transition-[background-color,color] duration-500 ease-vanguard hover:bg-foreground/[0.08] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:hover:bg-white/10"
      >
        <X aria-hidden size={11} weight="light" />
      </button>
    </span>
  );
}

/** Small uppercase group label used above chip rows. */
function GroupLabel({ id, children }: { id: string; children: ReactNode }) {
  return (
    <p id={id} className="pl-1 text-[12px] font-medium tracking-[-0.005em] text-muted-foreground">
      {children}
    </p>
  );
}

/** One bento cell: a Reveal wrapper carrying the grid span, holding a full-height Bezel. */
function PrefCard({
  className,
  icon,
  title,
  meta,
  tone = "default",
  delay = 0,
  children,
}: {
  className?: string;
  icon: ReactNode;
  title: ReactNode;
  meta?: ReactNode;
  tone?: "default" | "muted" | "primary";
  delay?: number;
  children: ReactNode;
}) {
  return (
    <Reveal delay={delay} className={cn("min-w-0", className)}>
      <Bezel tone={tone} className="h-full" coreClassName="flex flex-col p-6 md:p-7">
        <PanelTitle icon={icon} title={title} meta={meta} />
        <div className="mt-6 flex-1 space-y-5">{children}</div>
      </Bezel>
    </Reveal>
  );
}

function ProfileSkeleton() {
  const cells = [
    "lg:col-span-7 h-72",
    "lg:col-span-5 h-72",
    "lg:col-span-8 lg:row-span-2 h-[26rem] lg:h-auto",
    "lg:col-span-4 h-60",
    "lg:col-span-4 h-52",
    "lg:col-span-7 h-56",
    "lg:col-span-5 h-56",
    "lg:col-span-12 h-44",
    "lg:col-span-12 h-44",
  ];
  return (
    <div role="status" aria-live="polite" className="grid grid-cols-1 gap-6 lg:grid-cols-12">
      <span className="sr-only">Loading preferences…</span>
      {cells.map((cls, i) => (
        <Bezel key={i} className={cn("min-w-0", cls)} coreClassName="p-6 md:p-7">
          <div className="flex items-center gap-2.5">
            <Skeleton className="h-8 w-8 rounded-full" />
            <Skeleton className="h-4 w-32 rounded-full" />
          </div>
          <Skeleton className="mt-6 h-11 w-full rounded-2xl" />
          <div className="mt-5 flex flex-wrap gap-2">
            <Skeleton className="h-7 w-16 rounded-full" />
            <Skeleton className="h-7 w-20 rounded-full" />
            <Skeleton className="h-7 w-14 rounded-full" />
          </div>
        </Bezel>
      ))}
    </div>
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

  const [form, setForm] = useState<FormState>(DEFAULT_FORM);

  const [suggestingRoles, setSuggestingRoles] = useState(false);
  const [suggestedRoles, setSuggestedRoles] = useState<string[]>([]);

  useEffect(() => {
    if (prefs) {
      setForm(prefsToForm(prefs));
    }
  }, [prefs]);

  // Single set helper: strings for text/number fields, booleans for the
  // prefer_live_browser toggle.  Keeps call sites uniform.
  function set(key: keyof FormState, value: string | boolean) {
    setForm((prev) => ({ ...prev, [key]: value }) as FormState);
  }

  const parsedRoles = form.target_roles
    .split(",")
    .map((r) => r.trim())
    .filter(Boolean);

  const parsedLocations = form.preferred_locations
    .split(",")
    .map((l) => l.trim())
    .filter(Boolean);
  const selectedJobTypes = splitCsv(form.job_type);
  const selectedWorkModes = splitCsv(form.work_mode);

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
        // null clears a stored value; undefined would be dropped and the old one kept.
        current_title: form.current_title || null,
        experience_level: form.experience_level || null,
        years_experience: form.years_experience !== "" ? parseInt(form.years_experience, 10) : null,
        job_type: form.job_type || null,
        work_mode: form.work_mode || null,
        salary_min: form.salary_min !== "" ? parseInt(form.salary_min, 10) : null,
        salary_max: form.salary_max !== "" ? parseInt(form.salary_max, 10) : null,
        target_roles: parsedRoles,
        preferred_locations: parsedLocations,
        bio: form.bio || null,
        prefer_live_browser: form.prefer_live_browser,
        daily_search_enabled: form.daily_search_enabled,
        inbox_tracking_enabled: form.inbox_tracking_enabled,
        outreach_daily_cap: Math.min(100, Math.max(1, parseInt(form.outreach_daily_cap, 10) || 25)),
        outreach_auto_send: form.outreach_auto_send,
        outreach_track_opens: form.outreach_track_opens,
        auto_apply_enabled: form.auto_apply_enabled,
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

  const baseline = prefs ? prefsToForm(prefs) : DEFAULT_FORM;
  const isDirty = JSON.stringify(form) !== JSON.stringify(baseline);
  const salaryMinLabel = formatSalary(form.salary_min);
  const salaryMaxLabel = formatSalary(form.salary_max);

  return (
    <Screen>
      <div className="space-y-6 md:space-y-8">
        <PageHero
          className="pb-4 md:pb-6"
          eyebrow="Agent brief"
          title="Job Preferences"
          accent="What every agent works from."
          description="Tell agents what you want. Search, resume tailoring, and outreach use these preferences first."
          actions={
            <div role="status" aria-live="polite">
              {isLoading ? (
                <StatusPill tone="neutral" live>
                  Loading preferences…
                </StatusPill>
              ) : (
                <StatusPill tone={parsedRoles.length > 0 ? "primary" : "warning"}>
                  <span className="tabular-nums">{parsedRoles.length}</span>
                  {parsedRoles.length === 1 ? "target role" : "target roles"}
                  <span aria-hidden className="opacity-50">·</span>
                  <span className="tabular-nums">{parsedLocations.length}</span>
                  {parsedLocations.length === 1 ? "location" : "locations"}
                </StatusPill>
              )}
            </div>
          }
        />

        <Reveal subtle>
          <SettingsNav />
        </Reveal>

        {isLoading ? (
          <ProfileSkeleton />
        ) : (
          <div className="space-y-8">
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
              {/* A — role & seniority */}
              <PrefCard
                className="lg:col-span-7"
                icon={<Briefcase size={16} weight="light" />}
                title="Role & seniority"
              >
                <Field label="Current title">
                  {(id) => (
                    <Input
                      id={id}
                      name="current_title"
                      type="text"
                      value={form.current_title}
                      onChange={(e) => set("current_title", e.target.value)}
                      placeholder="e.g. Software Engineer, Product Manager…"
                    />
                  )}
                </Field>

                <div className="space-y-2.5">
                  <GroupLabel id="pref-experience-level">Experience level</GroupLabel>
                  <div role="group" aria-labelledby="pref-experience-level" className="flex flex-wrap gap-2">
                    {EXPERIENCE_LEVELS.map((lvl) => (
                      <Chip
                        key={lvl}
                        className="capitalize"
                        active={form.experience_level === lvl}
                        onClick={() => set("experience_level", lvl)}
                      >
                        {lvl}
                      </Chip>
                    ))}
                  </div>
                </div>

                <Field
                  label="Exact years of experience"
                  hint="Used by job search and application forms. Set 0 for fresher."
                >
                  {(id) => (
                    <Input
                      id={id}
                      name="years_experience"
                      type="number"
                      inputMode="numeric"
                      min={0}
                      max={60}
                      className="tabular-nums"
                      trayClassName="max-w-[12rem]"
                      value={form.years_experience}
                      onChange={(e) => set("years_experience", e.target.value)}
                      placeholder={form.experience_level === "fresher" ? "0" : "e.g. 3"}
                    />
                  )}
                </Field>
              </PrefCard>

              {/* B — salary */}
              <PrefCard
                className="lg:col-span-5"
                delay={0.05}
                icon={<CurrencyDollar size={16} weight="light" />}
                title="Salary range"
                meta="USD / year"
              >
                <p
                  aria-hidden
                  className="font-geist text-4xl font-semibold tabular-nums tracking-[-0.045em] text-foreground md:text-5xl"
                >
                  {salaryMinLabel ?? "—"}
                  <span className="mx-2 text-muted-foreground/50">–</span>
                  {salaryMaxLabel ?? "—"}
                </p>
                <Hairline />
                <div className="grid grid-cols-2 gap-4">
                  <Field label="Minimum (USD/yr)">
                    {(id) => (
                      <Input
                        id={id}
                        name="salary_min"
                        type="number"
                        inputMode="numeric"
                        min={0}
                        className="tabular-nums"
                        leading={<span className="text-sm">$</span>}
                        value={form.salary_min}
                        onChange={(e) => set("salary_min", e.target.value)}
                        placeholder="80000"
                      />
                    )}
                  </Field>
                  <Field label="Maximum (USD/yr)">
                    {(id) => (
                      <Input
                        id={id}
                        name="salary_max"
                        type="number"
                        inputMode="numeric"
                        min={0}
                        className="tabular-nums"
                        leading={<span className="text-sm">$</span>}
                        value={form.salary_max}
                        onChange={(e) => set("salary_max", e.target.value)}
                        placeholder="150000"
                      />
                    )}
                  </Field>
                </div>
              </PrefCard>

              {/* C — target roles (tall) */}
              <PrefCard
                className="lg:col-span-8 lg:row-span-2"
                delay={0.08}
                icon={<Target size={16} weight="light" />}
                title="Target roles"
                meta={
                  <IslandButton
                    tone="ghost"
                    size="sm"
                    onClick={handleSuggestRoles}
                    disabled={suggestingRoles}
                    aria-busy={suggestingRoles}
                    icon={
                      suggestingRoles ? (
                        <CircleNotch size={14} weight="light" className="animate-spin motion-reduce:animate-none" />
                      ) : (
                        <Sparkle size={14} weight="light" />
                      )
                    }
                  >
                    {suggestingRoles ? "Analyzing…" : "Suggest from resume"}
                  </IslandButton>
                }
              >
                <Field label="Roles you want" hint="Comma-separated. Click chips below to add.">
                  {(id) => (
                    <Input
                      id={id}
                      name="target_roles"
                      type="text"
                      value={form.target_roles}
                      onChange={(e) => set("target_roles", e.target.value)}
                      placeholder="Frontend Engineer, Full Stack Developer, React Developer"
                    />
                  )}
                </Field>

                {parsedRoles.length > 0 && (
                  <ul aria-label="Selected target roles" className="flex flex-wrap gap-2">
                    {parsedRoles.map((role) => (
                      <li key={role}>
                        <TagPill label={role} onRemove={() => removeRole(role)} />
                      </li>
                    ))}
                  </ul>
                )}

                {suggestedRoles.length > 0 && (
                  <div
                    aria-live="polite"
                    className="space-y-3 rounded-2xl bg-primary/[0.05] p-4 ring-1 ring-primary/15"
                  >
                    <p className="flex items-center gap-1.5 text-xs font-medium text-primary">
                      <Sparkle aria-hidden size={13} weight="light" />
                      AI suggestions — click to add
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {suggestedRoles.map((r) => {
                        const included = parsedRoles.includes(r);
                        return (
                          <Chip
                            key={r}
                            onClick={() => addRole(r)}
                            disabled={included}
                            active={included}
                            className={cn(!included && "text-primary ring-primary/30 hover:text-primary hover:ring-primary/50")}
                            icon={included ? <Check size={12} weight="light" /> : <Plus size={12} weight="light" />}
                          >
                            {r}
                          </Chip>
                        );
                      })}
                    </div>
                  </div>
                )}

                <div className="space-y-3">
                  <Hairline />
                  <GroupLabel id="pref-popular-roles">Popular roles — click to add</GroupLabel>
                  <div role="group" aria-labelledby="pref-popular-roles" className="flex flex-wrap gap-2">
                    {POPULAR_ROLES.map((r) => {
                      const included = parsedRoles.includes(r);
                      return (
                        <Chip
                          key={r}
                          onClick={() => addRole(r)}
                          disabled={included}
                          active={included}
                          icon={included ? <Check size={12} weight="light" /> : undefined}
                        >
                          {r}
                        </Chip>
                      );
                    })}
                  </div>
                </div>
              </PrefCard>

              {/* D — work type */}
              <PrefCard
                className="lg:col-span-4"
                delay={0.1}
                icon={<SuitcaseSimple size={16} weight="light" />}
                title="Work type"
              >
                <div className="space-y-2.5">
                  <GroupLabel id="pref-job-type">Job type</GroupLabel>
                  <div role="group" aria-labelledby="pref-job-type" className="flex flex-wrap gap-2">
                    {JOB_TYPES.map((jt) => (
                      <Chip
                        key={jt}
                        className="capitalize"
                        active={selectedJobTypes.includes(jt)}
                        onClick={() => set("job_type", toggleCsvValue(form.job_type, jt))}
                      >
                        {jt}
                      </Chip>
                    ))}
                  </div>
                </div>
                <div className="space-y-2.5">
                  <GroupLabel id="pref-work-mode">Work mode</GroupLabel>
                  <div role="group" aria-labelledby="pref-work-mode" className="flex flex-wrap gap-2">
                    {WORK_MODES.map((wm) => (
                      <Chip
                        key={wm}
                        className="capitalize"
                        active={selectedWorkModes.includes(wm)}
                        onClick={() => set("work_mode", toggleCsvValue(form.work_mode, wm))}
                      >
                        {wm}
                      </Chip>
                    ))}
                  </div>
                </div>
              </PrefCard>

              {/* E — locations */}
              <PrefCard
                className="lg:col-span-4"
                delay={0.12}
                icon={<MapPin size={16} weight="light" />}
                title="Preferred locations"
              >
                <Field label="Locations" hint="Comma-separated list of locations">
                  {(id) => (
                    <Input
                      id={id}
                      name="preferred_locations"
                      type="text"
                      value={form.preferred_locations}
                      onChange={(e) => set("preferred_locations", e.target.value)}
                      placeholder="Remote, Bangalore, San Francisco, New York"
                    />
                  )}
                </Field>
                {parsedLocations.length > 0 && (
                  <ul aria-label="Selected locations" className="flex flex-wrap gap-2">
                    {parsedLocations.map((loc) => (
                      <li key={loc}>
                        <TagPill label={loc} onRemove={() => removeLocation(loc)} />
                      </li>
                    ))}
                  </ul>
                )}
              </PrefCard>

              {/* F — bio */}
              <PrefCard
                className="lg:col-span-7"
                delay={0.06}
                icon={<TextAlignLeft size={16} weight="light" />}
                title="Bio"
                meta={<span className="font-geist-mono tabular-nums">{form.bio.length} chars</span>}
              >
                <Field label="About you" hint="Agents quote this when drafting outreach and cover letters.">
                  {(id) => (
                    <Textarea
                      id={id}
                      name="bio"
                      rows={4}
                      className="resize-none"
                      value={form.bio}
                      onChange={(e) => set("bio", e.target.value)}
                      placeholder="A short summary about yourself, your skills, and what you're looking for in your next role…"
                    />
                  )}
                </Field>
              </PrefCard>

              {/* G — live browser */}
              <PrefCard
                className="lg:col-span-5"
                delay={0.1}
                tone={form.prefer_live_browser ? "primary" : "muted"}
                icon={<Browser size={16} weight="light" />}
                title="Live browser"
                meta={
                  <Toggle
                    checked={form.prefer_live_browser}
                    onChange={(next) => set("prefer_live_browser", next)}
                    label="Open a visible browser for autonomous runs"
                  />
                }
              >
                <div>
                  <p className="text-sm font-medium tracking-[-0.01em] text-foreground">
                    Open a visible browser for autonomous runs
                  </p>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">
                    When on, the daily search and the &ldquo;Prepare Apply&rdquo; step open a real Chromium window that
                    streams to the page below. You&rsquo;ll see the agent click and type. When off (default),
                    CareerCraft uses the fast headless job-board APIs — invisible to you, but no CAPTCHAs and no extra
                    LLM tokens. You can always force the visible browser for a single run from the job card.
                  </p>
                </div>
                <StatusPill tone={form.prefer_live_browser ? "primary" : "neutral"}>
                  {form.prefer_live_browser ? "Visible Chromium" : "Headless (default)"}
                </StatusPill>
              </PrefCard>

              {/* H — daily search */}
              <PrefCard
                className="lg:col-span-12"
                delay={0.12}
                tone={form.daily_search_enabled ? "primary" : "muted"}
                icon={<CalendarCheck size={16} weight="light" />}
                title="Daily job search"
                meta={
                  <Toggle
                    checked={form.daily_search_enabled}
                    onChange={(next) => set("daily_search_enabled", next)}
                    label="Search for new jobs every morning"
                  />
                }
              >
                <div>
                  <p className="text-sm font-medium tracking-[-0.01em] text-foreground">
                    Search for new jobs every morning
                  </p>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">
                    When on, CareerCraft searches each morning for your target roles in your preferred locations,
                    using your own AI model and key. It needs at least one target role, and a location unless your
                    work mode is remote. Nothing is applied for without your approval.
                  </p>
                </div>
                <StatusPill tone={form.daily_search_enabled ? "primary" : "neutral"}>
                  {form.daily_search_enabled ? "Every morning" : "Off (default)"}
                </StatusPill>
              </PrefCard>

              {/* I — inbox tracking */}
              <PrefCard
                className="lg:col-span-12"
                delay={0.14}
                tone={form.inbox_tracking_enabled ? "primary" : "muted"}
                icon={<EnvelopeSimple size={16} weight="light" />}
                title="Track replies in Gmail"
                meta={
                  <Toggle
                    checked={form.inbox_tracking_enabled}
                    onChange={(next) => set("inbox_tracking_enabled", next)}
                    label="Update application status from your inbox"
                  />
                }
              >
                <div>
                  <p className="text-sm font-medium tracking-[-0.01em] text-foreground">
                    Update application status from your inbox
                  </p>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">
                    When on, CareerCraft checks your connected Gmail once a day for recruiter replies, such as an
                    interview invitation or a rejection, and moves the matching application forward. It reads sender,
                    subject and a short preview only, never changes or sends mail, and moves a status only when one
                    application clearly matches. Requires Gmail under Integrations and an AI model.
                  </p>
                </div>
                <StatusPill tone={form.inbox_tracking_enabled ? "primary" : "neutral"}>
                  {form.inbox_tracking_enabled ? "Checking daily" : "Off (default)"}
                </StatusPill>
              </PrefCard>

              {/* J0 — queue applications */}
              <PrefCard
                className="lg:col-span-12"
                delay={0.15}
                tone={form.auto_apply_enabled ? "primary" : "muted"}
                icon={<CalendarCheck size={16} weight="light" />}
                title="Queue applications for me"
                meta={
                  <Toggle
                    checked={form.auto_apply_enabled}
                    onChange={(next) => set("auto_apply_enabled", next)}
                    label="Prepare applications for strong matches"
                  />
                }
              >
                <div>
                  <p className="text-sm font-medium tracking-[-0.01em] text-foreground">
                    Prepare applications for strong matches
                  </p>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">
                    When on, CareerCraft takes saved jobs that match at 70% or more, tailors your resume using only
                    what is in your own documents, and queues each application in your browser extension, a few at a
                    time and within your daily limit. You still review every filled form in the extension before
                    anything is submitted. Needs a paired extension and an AI model.
                  </p>
                </div>
                <StatusPill tone={form.auto_apply_enabled ? "primary" : "neutral"}>
                  {form.auto_apply_enabled ? "Queuing strong matches" : "Off (default)"}
                </StatusPill>
              </PrefCard>

              {/* J — recruiter emails */}
              <PrefCard
                className="lg:col-span-12"
                delay={0.16}
                tone={form.outreach_auto_send ? "primary" : "muted"}
                icon={<EnvelopeSimple size={16} weight="light" />}
                title="Recruiter emails"
                meta={
                  <Toggle
                    checked={form.outreach_auto_send}
                    onChange={(next) => set("outreach_auto_send", next)}
                    label="Send verified emails without asking each time"
                  />
                }
              >
                <div>
                  <p className="text-sm font-medium tracking-[-0.01em] text-foreground">
                    Send verified emails without asking each time
                  </p>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">
                    Every recruiter email waits for your approval on the Outreach page. After you have approved three,
                    turning this on lets emails to verified addresses go out on their own. Unverified addresses are
                    always held for you. One follow-up is drafted after six days, and nothing more is sent once the
                    company replies.
                  </p>
                  <label className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
                    Emails per day, at most
                    <Input
                      name="outreach_daily_cap"
                      type="number"
                      inputMode="numeric"
                      min={1}
                      max={100}
                      className="tabular-nums"
                      trayClassName="w-24"
                      value={form.outreach_daily_cap}
                      onChange={(e) => set("outreach_daily_cap", e.target.value)}
                    />
                  </label>
                  <div className="mt-4 flex items-start justify-between gap-4 border-t border-border/60 pt-3">
                    <div>
                      <p className="text-sm font-medium tracking-[-0.01em] text-foreground">Show when emails are opened</p>
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">
                        Off by default. Adds a tiny invisible image to your emails so the Outreach page can show an
                        open. Some mail apps load images in advance, so treat it as a hint, and it can lower
                        deliverability with some providers.
                      </p>
                    </div>
                    <Toggle
                      checked={form.outreach_track_opens}
                      onChange={(next) => set("outreach_track_opens", next)}
                      label="Show when emails are opened"
                    />
                  </div>
                </div>
                <StatusPill tone={form.outreach_auto_send ? "primary" : "neutral"}>
                  {form.outreach_auto_send ? "Auto-send after 3 approvals" : "Approve each (default)"}
                </StatusPill>
              </PrefCard>
            </div>

            {/* Sticky save bar */}
            <div className="sticky bottom-4 z-20 md:bottom-6">
              <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 rounded-full bg-card/80 p-1.5 pl-5 shadow-ambient ring-1 ring-foreground/[0.08] backdrop-blur-xl dark:bg-background/70 dark:ring-white/10">
                <p role="status" aria-live="polite" className="flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
                  <span
                    aria-hidden
                    className={cn(
                      "h-1.5 w-1.5 shrink-0 rounded-full transition-colors duration-500 ease-vanguard",
                      isDirty ? "bg-warning" : "bg-success",
                    )}
                  />
                  <span className="truncate">{isDirty ? "Unsaved changes" : "Everything saved"}</span>
                </p>
                <div className="flex shrink-0 items-center gap-1.5">
                  <IslandLink
                    href="/settings/account"
                    tone="quiet"
                    size="sm"
                    className="hidden sm:inline-flex"
                    icon={<ArrowLeft size={14} weight="light" />}
                  >
                    Back to account
                  </IslandLink>
                  <IslandButton
                    tone="primary"
                    size="sm"
                    onClick={() => saveMutation.mutate()}
                    disabled={saveMutation.isPending}
                    aria-busy={saveMutation.isPending}
                    trailing={
                      saveMutation.isPending ? (
                        <CircleNotch size={14} weight="light" className="animate-spin motion-reduce:animate-none" />
                      ) : (
                        <FloppyDisk size={14} weight="light" />
                      )
                    }
                  >
                    {saveMutation.isPending ? "Saving…" : "Save preferences"}
                  </IslandButton>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </Screen>
  );
}
