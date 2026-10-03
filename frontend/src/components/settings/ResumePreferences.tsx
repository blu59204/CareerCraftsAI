"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Bezel, IslandButton, PanelTitle, Select } from "@/components/vanguard";
import { Switch } from "@/components/ui/switch";
import { apiClient } from "@/lib/api";
import type { AutoApplyPreferences } from "@/lib/applications-api";
import type { ResumeTemplateId } from "@/lib/resume-types";

export type ResumePrefs = {
  resume_template: ResumeTemplateId;
  resume_page_target: 1 | 2;
  resume_tailor_per_job: boolean;
  resume_tone: string;
};

const TEMPLATES: { id: ResumeTemplateId; label: string }[] = [
  { id: "modern", label: "Modern" },
  { id: "classic", label: "Classic" },
  { id: "technical", label: "Technical" },
];
const TONES = ["professional", "friendly", "concise"];

/** Preferences as the backend returns them, with the same defaults the backend applies. */
export function toResumePrefs(p: AutoApplyPreferences | undefined): ResumePrefs {
  const template = TEMPLATES.some((t) => t.id === p?.resume_template) ? p?.resume_template : "modern";
  return {
    resume_template: template as ResumeTemplateId,
    resume_page_target: p?.resume_page_target === 1 ? 1 : 2,
    resume_tailor_per_job: p?.resume_tailor_per_job ?? true,
    resume_tone: p?.resume_tone ?? "professional",
  };
}

/** GET + PATCH /users/me/preferences for the auto-apply rule and resume preferences. */
export function useAutoApplyPrefs() {
  const qc = useQueryClient();
  const query = useQuery<AutoApplyPreferences>({
    queryKey: ["preferences"],
    queryFn: async () => (await apiClient.get("/users/me/preferences")).data ?? {},
  });
  const patch = useMutation({
    mutationFn: async (payload: AutoApplyPreferences) => apiClient.patch("/users/me/preferences", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["preferences"] }),
    onError: () => toast.error("Couldn't save your preferences"),
  });
  return { prefs: query.data, isLoading: query.isLoading, patch };
}

const labelClass = "text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground";

export function ResumePrefsFields({
  value,
  onChange,
  showLength = true,
}: {
  value: ResumePrefs;
  onChange: (next: ResumePrefs) => void;
  /** Off where the page already has its own single/multi-page control. */
  showLength?: boolean;
}) {
  const set = <K extends keyof ResumePrefs>(key: K, v: ResumePrefs[K]) => onChange({ ...value, [key]: v });
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <label className="space-y-1.5">
        <span className={labelClass}>Template</span>
        <Select
          value={value.resume_template}
          onChange={(e) => set("resume_template", e.target.value as ResumeTemplateId)}
        >
          {TEMPLATES.map((t) => (
            <option key={t.id} value={t.id}>
              {t.label}
            </option>
          ))}
        </Select>
      </label>
      {showLength && (
      <label className="space-y-1.5">
        <span className={labelClass}>Length</span>
        <Select
          value={String(value.resume_page_target)}
          onChange={(e) => set("resume_page_target", e.target.value === "1" ? 1 : 2)}
        >
          <option value="1">Single page</option>
          <option value="2">Multi page</option>
        </Select>
      </label>
      )}
      <label className="space-y-1.5">
        <span className={labelClass}>Tone</span>
        <Select value={value.resume_tone} onChange={(e) => set("resume_tone", e.target.value)}>
          {TONES.map((t) => (
            <option key={t} value={t}>
              {t[0].toUpperCase() + t.slice(1)}
            </option>
          ))}
        </Select>
      </label>
      <div className="flex items-center justify-between gap-3 self-end rounded-2xl px-1 py-2">
        <span id="tailor-per-job" className="text-sm text-foreground">
          Tailor a resume per job
        </span>
        <Switch
          aria-labelledby="tailor-per-job"
          checked={value.resume_tailor_per_job}
          onCheckedChange={(v) => set("resume_tailor_per_job", v)}
        />
      </div>
    </div>
  );
}

/** Card editing the resume preferences auto-apply uses (shown on the Resume page). */
export function ResumePreferencesCard({ showLength = true }: { showLength?: boolean }) {
  const { prefs, isLoading, patch } = useAutoApplyPrefs();
  const [draft, setDraft] = useState<ResumePrefs | null>(null);
  const value = draft ?? toResumePrefs(prefs);
  return (
    <Bezel coreClassName="p-5 md:p-6">
      <PanelTitle title="Auto-apply resume" />
      <p className="mt-2 text-xs leading-5 text-muted-foreground">
        How auto-apply tailors your resume for each job. Turn tailoring off to send your active resume as is.
      </p>
      <div className="mt-4">
        <ResumePrefsFields value={value} onChange={setDraft} showLength={showLength} />
      </div>
      <div className="mt-5 flex justify-end">
        <IslandButton
          tone="primary"
          size="sm"
          disabled={isLoading || !draft || patch.isPending}
          onClick={() =>
            patch.mutate(
              { ...value, resume_prefs_set_at: prefs?.resume_prefs_set_at ?? new Date().toISOString() },
              {
                onSuccess: () => {
                  setDraft(null);
                  toast.success("Resume preferences saved");
                },
              },
            )
          }
        >
          {patch.isPending ? "Saving…" : "Save"}
        </IslandButton>
      </div>
    </Bezel>
  );
}
