"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Sparkles } from "lucide-react";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { OnboardingStepper } from "@/components/onboarding/OnboardingStepper";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { apiClient } from "@/lib/api";

interface FormData {
  goal: string;
  targetRoles: string;
  preferredLocations: string;
  experienceLevel: string;
  yearsExperience: string;
  jobTypes: string[];
  workModes: string[];
  provider: "anthropic" | "openai" | "google" | "ollama" | "nvidia_nim";
  apiKey: string;
  modelName: string;
}

const MODEL_DEFAULTS: Record<string, string> = {
  anthropic: "claude-3-5-sonnet-20241022",
  openai: "gpt-4o",
  google: "gemini-1.5-pro",
  ollama: "llama3.2",
  nvidia_nim: "meta/llama-3.1-70b-instruct",
};

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

function toggleSelection(values: string[], value: string) {
  if (values.includes(value)) {
    return values.length > 1 ? values.filter((item) => item !== value) : values;
  }
  return [...values, value];
}

function splitCsv(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function toggleCsvValue(value: string, item: string) {
  const values = splitCsv(value);
  if (values.includes(item)) {
    return values.filter((role) => role !== item).join(", ");
  }
  return [...values, item].join(", ");
}

function StepWrapper({
  children,
  onNext,
  onPrev,
  canPrev,
  isLast,
  loading,
}: {
  children: React.ReactNode;
  onNext: () => void;
  onPrev: () => void;
  canPrev: boolean;
  isLast: boolean;
  loading?: boolean;
}) {
  return (
    <div className="space-y-6">
      <div className="rounded-3xl border border-border bg-card/60 p-6">{children}</div>
      <div className="flex items-center justify-between">
        <LiquidGlassButton tone="ghost" size="sm" onClick={onPrev} disabled={!canPrev || loading}>
          Back
        </LiquidGlassButton>
        <LiquidGlassButton tone="primary" size="sm" onClick={onNext} disabled={loading}>
          {loading ? (
            <span className="flex items-center gap-2">
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />
              {isLast ? "Saving…" : "Loading…"}
            </span>
          ) : isLast ? (
            "Finish"
          ) : (
            "Continue"
          )}
        </LiquidGlassButton>
      </div>
    </div>
  );
}

export default function OnboardingPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [i, setI] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [uploadedDocId, setUploadedDocId] = useState<string | null>(null);
  const [suggestingRoles, setSuggestingRoles] = useState(false);
  const [suggestedRoles, setSuggestedRoles] = useState<string[]>([]);

  const [formData, setFormData] = useState<FormData>({
    goal: "Switch roles",
    targetRoles: "",
    preferredLocations: "",
    experienceLevel: "mid",
    yearsExperience: "",
    jobTypes: ["full-time"],
    workModes: ["remote"],
    provider: "anthropic",
    apiKey: "",
    modelName: "claude-3-5-sonnet-20241022",
  });

  const TOTAL_STEPS = 6;
  const isLast = i === TOTAL_STEPS - 1;
  const selectedRoles = splitCsv(formData.targetRoles);

  const advance = () => setI((n) => Math.min(n + 1, TOTAL_STEPS - 1));
  const prev = () => setI((n) => Math.max(n - 1, 0));

  const handleResumeUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("doc_type", "resume");
      fd.append("is_primary", "true");
      const { data } = await apiClient.post("/rag/upload", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setUploadedDocId(data.id);
      toast.success(`Resume uploaded: ${file.name}`);
    } catch {
      toast.error("Upload failed — try again");
    } finally {
      setUploading(false);
    }
  };

  const markOnboardingDone = () => {
    queryClient.setQueryData(["me"], (old: Record<string, unknown> | undefined) =>
      old ? { ...old, onboarding_completed: true } : { onboarding_completed: true }
    );
  };

  const handleFinish = async () => {
    setSaving(true);
    try {
      const locations = formData.preferredLocations
        .split(",")
        .map((l) => l.trim())
        .filter(Boolean);

      await apiClient.patch("/users/me/preferences", {
        experience_level: formData.experienceLevel,
        years_experience: formData.yearsExperience ? parseInt(formData.yearsExperience, 10) : undefined,
        job_type: formData.jobTypes.join(","),
        work_mode: formData.workModes.join(","),
        target_roles: selectedRoles,
        preferred_locations: locations,
      });

      if (formData.apiKey) {
        await apiClient.post("/users/me/models", {
          provider: formData.provider,
          api_key: formData.apiKey,
          model_name: formData.modelName || MODEL_DEFAULTS[formData.provider] || "default",
        });
      }

      await apiClient.patch("/users/me", { onboarding_completed: true });
      toast.success("Setup complete! Welcome to CareerCraft AI.");
      markOnboardingDone();
      router.push("/dashboard");
    } catch {
      toast.error("Setup failed — check your details and try again");
    } finally {
      setSaving(false);
    }
  };

  const handleSkip = async () => {
    setSaving(true);
    try {
      await apiClient.patch("/users/me", { onboarding_completed: true });
      markOnboardingDone();
      router.push("/dashboard");
    } catch {
      toast.error("Could not skip setup — try again");
    } finally {
      setSaving(false);
    }
  };

  const handleSuggestRoles = async () => {
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
    } catch {
      setSuggestedRoles(POPULAR_ROLES.slice(0, 5));
    } finally {
      setSuggestingRoles(false);
    }
  };

  const handleNext = () => {
    if (isLast) {
      handleFinish();
    } else {
      advance();
    }
  };

  const wrap = (node: React.ReactNode, stepLoading = false) => (
    <StepWrapper
      onNext={handleNext}
      onPrev={prev}
      canPrev={i > 0}
      isLast={isLast}
      loading={stepLoading || saving}
    >
      {node}
    </StepWrapper>
  );

  const steps = [
    {
      id: "welcome",
      title: "Welcome to CareerCraft AI.",
      content: wrap(
        <p className="text-sm text-muted-foreground">
          Let&apos;s set up your job search in under two minutes.
        </p>,
      ),
    },
    {
      id: "goal",
      title: "What's your goal?",
      content: wrap(
        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium">Career goal</label>
            <select
              value={formData.goal}
              onChange={(e) => setFormData((p) => ({ ...p, goal: e.target.value }))}
              className="w-full rounded-2xl border border-border bg-background p-3 text-sm"
            >
              <option>First job after college</option>
              <option>Switch roles</option>
              <option>Internship</option>
              <option>Promotion / senior move</option>
              <option>Freelance / contract</option>
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium">Experience level</label>
            <select
              value={formData.experienceLevel}
              onChange={(e) =>
                setFormData((p) => ({
                  ...p,
                  experienceLevel: e.target.value,
                  yearsExperience: e.target.value === "fresher" ? "0" : p.yearsExperience,
                }))
              }
              className="w-full rounded-2xl border border-border bg-background p-3 text-sm"
            >
              <option value="fresher">Fresher (0–1 yr)</option>
              <option value="junior">Junior (1–3 yrs)</option>
              <option value="mid">Mid-level (3–6 yrs)</option>
              <option value="senior">Senior (6–10 yrs)</option>
              <option value="lead">Lead / Staff (10+ yrs)</option>
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium">Exact years of experience</label>
            <input
              type="number"
              min={0}
              max={60}
              value={formData.yearsExperience}
              onChange={(e) => setFormData((p) => ({ ...p, yearsExperience: e.target.value }))}
              placeholder={formData.experienceLevel === "fresher" ? "0" : "e.g. 2"}
              className="w-full rounded-2xl border border-border bg-background p-3 text-sm"
            />
            <p className="mt-1.5 text-xs text-muted-foreground">
              Helps agents avoid senior jobs for freshers and junior profiles.
            </p>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium">Job type</label>
            <div className="flex flex-wrap gap-2">
              {["full-time", "part-time", "contract", "internship"].map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() =>
                    setFormData((p) => ({ ...p, jobTypes: toggleSelection(p.jobTypes, t) }))
                  }
                  aria-pressed={formData.jobTypes.includes(t)}
                  className={`rounded-full border px-3 py-1 text-xs capitalize transition-colors ${
                    formData.jobTypes.includes(t)
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border text-muted-foreground"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium">Work mode</label>
            <div className="flex flex-wrap gap-2">
              {["remote", "hybrid", "onsite"].map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() =>
                    setFormData((p) => ({ ...p, workModes: toggleSelection(p.workModes, m) }))
                  }
                  aria-pressed={formData.workModes.includes(m)}
                  className={`min-w-24 flex-1 rounded-2xl border px-3 py-2 text-xs capitalize transition-colors ${
                    formData.workModes.includes(m)
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border text-muted-foreground"
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>
        </div>,
      ),
    },
    {
      id: "resume",
      title: "Upload your resume",
      content: wrap(
        <div className="space-y-3">
          <input
            type="file"
            accept=".pdf,.docx"
            onChange={handleResumeUpload}
            disabled={uploading}
            className="w-full rounded-2xl border border-dashed border-border bg-background p-4 text-sm disabled:opacity-50"
          />
          {uploading && (
            <p className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
              Uploading…
            </p>
          )}
          {uploadedDocId && !uploading && (
            <p className="text-xs text-success">Resume uploaded successfully.</p>
          )}
          <p className="text-xs text-muted-foreground">PDF or DOCX, max 10 MB. You can change this later.</p>
        </div>,
        uploading,
      ),
    },
    {
      id: "role",
      title: "Target roles",
      content: wrap(
        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium">Role titles</label>
            <input
              value={formData.targetRoles}
              onChange={(e) => setFormData((p) => ({ ...p, targetRoles: e.target.value }))}
              placeholder="Frontend Engineer, React Developer, Full Stack Developer"
              className="w-full rounded-2xl border border-border bg-background p-3 text-sm"
            />
            <p className="mt-1.5 text-xs text-muted-foreground">
              Add multiple custom roles with commas, or click chips below.
            </p>
            {selectedRoles.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {selectedRoles.map((role) => (
                  <button
                    key={role}
                    type="button"
                    onClick={() =>
                      setFormData((p) => ({
                        ...p,
                        targetRoles: splitCsv(p.targetRoles)
                          .filter((item) => item !== role)
                          .join(", "),
                      }))
                    }
                    className="rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium text-primary transition-colors hover:bg-primary/15"
                  >
                    {role} ×
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleSuggestRoles}
              disabled={suggestingRoles || !uploadedDocId}
              className="flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/5 px-3 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-primary/10 disabled:opacity-50"
            >
              {suggestingRoles ? (
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
              ) : (
                <Sparkles className="h-3 w-3" />
              )}
              {suggestingRoles ? "Analyzing resume…" : "Suggest from resume"}
            </button>
            {!uploadedDocId && (
              <span className="text-xs text-muted-foreground">Upload resume first</span>
            )}
          </div>
          {suggestedRoles.length > 0 && (
            <div>
              <div className="mb-2 text-xs font-medium text-primary">AI suggestions</div>
              <div className="flex flex-wrap gap-2">
                {suggestedRoles.map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() =>
                      setFormData((p) => ({ ...p, targetRoles: toggleCsvValue(p.targetRoles, r) }))
                    }
                    aria-pressed={selectedRoles.includes(r)}
                    className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                      selectedRoles.includes(r)
                        ? "border-primary bg-primary/10 text-primary font-medium"
                        : "border-primary/40 bg-primary/5 text-primary hover:bg-primary/10"
                    }`}
                  >
                    {r}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div>
            <div className="mb-2 text-xs text-muted-foreground">Popular roles — click to add</div>
            <div className="flex flex-wrap gap-2">
              {POPULAR_ROLES.map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() =>
                    setFormData((p) => ({ ...p, targetRoles: toggleCsvValue(p.targetRoles, r) }))
                  }
                  aria-pressed={selectedRoles.includes(r)}
                  className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                    selectedRoles.includes(r)
                      ? "border-primary bg-primary/10 text-primary font-medium"
                      : "border-border text-muted-foreground hover:border-primary/50 hover:text-foreground"
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>
        </div>,
      ),
    },
    {
      id: "locations",
      title: "Preferred locations",
      content: wrap(
        <div className="space-y-2">
          <label className="mb-1.5 block text-sm font-medium">Locations (comma-separated)</label>
          <input
            value={formData.preferredLocations}
            onChange={(e) => setFormData((p) => ({ ...p, preferredLocations: e.target.value }))}
            placeholder="Bangalore, Remote, Hyderabad"
            className="w-full rounded-2xl border border-border bg-background p-3 text-sm"
          />
          <p className="text-xs text-muted-foreground">Separate multiple locations with commas.</p>
        </div>,
      ),
    },
    {
      id: "model",
      title: "Bring your own model",
      content: wrap(
        <div className="space-y-4 text-sm">
          <div>
            <label className="mb-1.5 block font-medium">Provider</label>
            <select
              value={formData.provider}
              onChange={(e) => {
                const p = e.target.value as FormData["provider"];
                setFormData((prev) => ({
                  ...prev,
                  provider: p,
                  modelName: MODEL_DEFAULTS[p] ?? "",
                }));
              }}
              className="w-full rounded-2xl border border-border bg-background p-3"
            >
              <option value="anthropic">Anthropic</option>
              <option value="openai">OpenAI</option>
              <option value="google">Google</option>
              <option value="ollama">Ollama (local)</option>
              <option value="nvidia_nim">NVIDIA NIM</option>
            </select>
          </div>
          <div>
            <label className="mb-1.5 block font-medium">Model name</label>
            <input
              value={formData.modelName}
              onChange={(e) => setFormData((p) => ({ ...p, modelName: e.target.value }))}
              placeholder={MODEL_DEFAULTS[formData.provider]}
              className="w-full rounded-2xl border border-border bg-background p-3"
            />
          </div>
          <div>
            <label className="mb-1.5 block font-medium">
              API key{" "}
              <span className="font-normal text-muted-foreground">(optional — skip to use free tier)</span>
            </label>
            <input
              type="password"
              value={formData.apiKey}
              onChange={(e) => setFormData((p) => ({ ...p, apiKey: e.target.value }))}
              placeholder="sk-…"
              className="w-full rounded-2xl border border-border bg-background p-3"
            />
          </div>
        </div>,
      ),
    },
  ];

  return (
    <ThemeProvider zoneDefault="light">
      <div className="min-h-screen bg-[radial-gradient(circle_at_50%_0%,hsl(var(--primary)/0.10),transparent_34%),linear-gradient(180deg,hsl(var(--background)),hsl(var(--muted)/0.45))] px-6 py-16">
        <div className="mx-auto mb-8 max-w-3xl text-center">
          <div className="inline-flex rounded-full border border-border bg-card/70 px-3 py-1 text-xs uppercase tracking-[0.22em] text-muted-foreground shadow-sm backdrop-blur">
            Aurora Onboard
          </div>
          <h1 className="mt-5 font-display text-5xl leading-none text-foreground md:text-7xl">
            Set your job search orbit.
          </h1>
        </div>
        <OnboardingStepper steps={steps} currentIndex={i} onChange={setI} />
        <div className="mt-6 text-center">
          <button
            type="button"
            onClick={handleSkip}
            disabled={saving}
            className="text-xs text-muted-foreground hover:text-foreground underline-offset-2 hover:underline transition-colors disabled:opacity-60"
          >
            Skip setup — go to dashboard →
          </button>
        </div>
      </div>
    </ThemeProvider>
  );
}
