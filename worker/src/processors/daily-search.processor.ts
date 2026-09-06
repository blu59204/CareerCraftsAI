import { Job } from "bullmq";
import axios from "axios";

const BACKEND_URL =
  process.env.BACKEND_INTERNAL_URL ?? process.env.BACKEND_URL ?? "http://backend:8000";
const INTERNAL_SECRET = process.env.INTERNAL_SECRET ?? process.env.APP_SECRET_KEY ?? "";

/**
 * Daily automated job search based on user preferences.
 * Fetches user preferences from memory, searches all platforms,
 * scores matches, and queues auto-apply for top results.
 *
 * The backend fanout endpoint filters per-user: only members with an
 * active LLM model + saved preferences (target_roles /
 * preferred_locations) are processed. Anonymous / unconfigured users
 * are silently skipped, so this is safe to run on a single schedule
 * shared by every member.
 */
export async function processDailySearch(job: Job): Promise<void> {
  // user_id is reserved for an explicit per-user trigger; "all" (or
  // anything truthy) tells the backend to fan out across eligible members.
  const { user_id } = job.data as { user_id?: string };
  const targetUser = user_id && user_id !== "all" ? user_id : "all";

  try {
    const response = await axios.post(
      `${BACKEND_URL}/internal/agents/daily-search`,
      { user_id: targetUser },
      {
        headers: { "x-internal-secret": INTERNAL_SECRET },
        timeout: 300_000, // 5 min — searches multiple platforms
      }
    );

    const { users_searched, jobs_found, applications_queued } = response.data as {
      users_searched?: number;
      jobs_found?: number;
      applications_queued?: number;
    };
    console.log(
      `[daily-search] users_searched=${users_searched ?? 0} jobs_found=${jobs_found ?? 0} applications_queued=${applications_queued ?? 0}`
    );
  } catch (err: unknown) {
    if (axios.isAxiosError(err)) {
      console.error(
        `[daily-search] POST ${BACKEND_URL}/internal/agents/daily-search failed: status=${err.response?.status ?? "NO_RESPONSE"} body=${JSON.stringify(err.response?.data) ?? err.message}`
      );
    }
    const rawDetail = axios.isAxiosError(err) ? err.response?.data?.detail : undefined;
    const message =
      typeof rawDetail === "string" ? rawDetail : rawDetail ? JSON.stringify(rawDetail) : (axios.isAxiosError(err) ? err.message : String(err));
    const status = axios.isAxiosError(err) ? (err.response?.status ?? "NO_RESPONSE") : "unknown";
    throw new Error(`Daily search failed: status=${status} ${message}`);
  }
}
