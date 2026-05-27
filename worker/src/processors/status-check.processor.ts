import { Job } from "bullmq";
import axios from "axios";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://backend:8000";
const INTERNAL_SECRET = process.env.APP_SECRET_KEY ?? "";

/**
 * Checks application status on job platforms every 6 hours.
 * Calls the backend internal endpoint which uses browser-use to
 * login to platforms and check for status updates (viewed, shortlisted, etc.)
 */
export async function processStatusCheck(job: Job): Promise<void> {
  const { user_id } = job.data as { user_id: string };

  try {
    const response = await axios.post(
      `${BACKEND_URL}/internal/applications/check-status`,
      { user_id },
      {
        headers: { "x-internal-secret": INTERNAL_SECRET },
        timeout: 120_000, // 2 min — browser automation is slow
      }
    );

    const { updated_count } = response.data;
    if (updated_count > 0) {
      console.log(
        `[status-check] Updated ${updated_count} application(s) for user ${user_id}`
      );
    }
  } catch (err: unknown) {
    const message = axios.isAxiosError(err)
      ? err.response?.data?.detail ?? err.message
      : String(err);
    throw new Error(
      `Status check failed for user ${user_id}: ${message}`
    );
  }
}
