import { Job } from "bullmq";
import axios from "axios";

const BACKEND_URL =
  process.env.BACKEND_INTERNAL_URL ?? process.env.BACKEND_URL ?? "http://backend:8000";
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
      {
        headers: { "x-internal-secret": INTERNAL_SECRET },
        timeout: 130_000, // 130s — just above backend 120s server timeout
      }
    );
  } catch (err: unknown) {
    if (axios.isAxiosError(err)) {
      console.error(
        `[job-search] POST ${BACKEND_URL}/internal/agents/run-job-search run=${run_id} failed: status=${err.response?.status ?? "NO_RESPONSE"} body=${JSON.stringify(err.response?.data) ?? err.message}`
      );
    }
    const rawDetail = axios.isAxiosError(err) ? err.response?.data?.detail : undefined;
    const message =
      typeof rawDetail === "string" ? rawDetail : rawDetail ? JSON.stringify(rawDetail) : (axios.isAxiosError(err) ? err.message : String(err));
    const status = axios.isAxiosError(err) ? (err.response?.status ?? "NO_RESPONSE") : "unknown";
    throw new Error(`Job search failed for run ${run_id}: status=${status} ${message}`);
  }
}
