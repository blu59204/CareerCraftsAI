import { Job } from "bullmq";
import axios from "axios";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://backend:8000";
const INTERNAL_SECRET = process.env.APP_SECRET_KEY ?? "";

/**
 * Daily automated job search based on user preferences.
 * Fetches user preferences from memory, searches all platforms,
 * scores matches, and queues auto-apply for top results.
 *
 * Runs once per day per user (or for all users if user_id="all").
 */
export async function processDailySearch(job: Job): Promise<void> {
  const { user_id } = job.data as { user_id: string };

  try {
    const response = await axios.post(
      `${BACKEND_URL}/internal/agents/daily-search`,
      { user_id },
      {
        headers: { "x-internal-secret": INTERNAL_SECRET },
        timeout: 300_000, // 5 min — searches multiple platforms
      }
    );

    const { jobs_found, applications_queued } = response.data;
    console.log(
      `[daily-search] Found ${jobs_found} jobs, queued ${applications_queued} applications for user ${user_id}`
    );
  } catch (err: unknown) {
    const message = axios.isAxiosError(err)
      ? err.response?.data?.detail ?? err.message
      : String(err);
    throw new Error(`Daily search failed for user ${user_id}: ${message}`);
  }
}
