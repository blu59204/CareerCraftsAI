import { Job } from "bullmq";
import axios from "axios";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://backend:8000";
const INTERNAL_SECRET = process.env.INTERNAL_SECRET ?? process.env.APP_SECRET_KEY ?? "";

export async function processJobSearch(job: Job): Promise<void> {
  const { user_id, run_id, search_query, location, max_results, live_browser, work_mode } =
    job.data as {
      user_id: string;
      run_id: string;
      search_query: string;
      location: string;
      max_results: number;
      live_browser?: boolean;
      work_mode?: string;
    };

  try {
    await axios.post(
      `${BACKEND_URL}/internal/agents/run-job-search`,
      { user_id, run_id, search_query, location, max_results, live_browser: live_browser ?? false, work_mode: work_mode ?? "" },
      { headers: { "x-internal-secret": INTERNAL_SECRET } }
    );
  } catch (err: unknown) {
    const message = axios.isAxiosError(err)
      ? err.response?.data?.detail ?? err.message
      : String(err);
    throw new Error(`Job search failed for run ${run_id}: ${message}`);
  }
}
