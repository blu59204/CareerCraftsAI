import { Job } from "bullmq";
import axios from "axios";
import { BACKEND_URL, INTERNAL_SECRET } from "../config";

export async function processFollowupEmail(job: Job): Promise<void> {
  const { user_id, application_id, day } = job.data as {
    user_id: string;
    application_id: string;
    day: number;
  };

  try {
    await axios.post(
      `${BACKEND_URL}/internal/agents/run-followup`,
      { user_id, application_id, day },
      {
        headers: { "x-internal-secret": INTERNAL_SECRET },
        timeout: 60_000, // 60s — followup draft is fast, avoid hung slot
      }
    );
  } catch (err: unknown) {
    if (axios.isAxiosError(err)) {
      console.error(
        `[followup] POST ${BACKEND_URL}/internal/agents/run-followup app=${application_id} failed: status=${err.response?.status ?? "NO_RESPONSE"} body=${JSON.stringify(err.response?.data) ?? err.message}`
      );
    }
    const rawDetail = axios.isAxiosError(err) ? err.response?.data?.detail : undefined;
    const message =
      typeof rawDetail === "string" ? rawDetail : rawDetail ? JSON.stringify(rawDetail) : (axios.isAxiosError(err) ? err.message : String(err));
    const status = axios.isAxiosError(err) ? (err.response?.status ?? "NO_RESPONSE") : "unknown";
    throw new Error(
      `Follow-up email failed for app ${application_id}: status=${status} ${message}`
    );
  }
}
