import { Job } from "bullmq";
import axios from "axios";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://backend:8000";
const INTERNAL_SECRET = process.env.APP_SECRET_KEY ?? "";

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
      { headers: { "x-internal-secret": INTERNAL_SECRET } }
    );
  } catch (err: unknown) {
    const message = axios.isAxiosError(err)
      ? err.response?.data?.detail ?? err.message
      : String(err);
    throw new Error(
      `Follow-up email failed for app ${application_id}: ${message}`
    );
  }
}
