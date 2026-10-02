// Minimal stub; the full assisted-apply flow (extension prefill) lands from another branch.
import { setApplyState } from "@/lib/applications-api";

/** Open the job in the member's own browser and record "opened". Call synchronously from a click handler. */
export function startAssistedApply(app: { id: string; job_url: string | null }): void {
  if (!app.job_url) return;
  window.open(app.job_url, "_blank", "noopener,noreferrer");
  void setApplyState(app.id, "opened").catch(() => undefined);
}
