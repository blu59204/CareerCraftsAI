import { Worker, Queue, ConnectionOptions } from "bullmq";
import { processJobSearch } from "./processors/job-search.processor";
import { processFollowupEmail } from "./processors/followup.processor";
import { processStatusCheck } from "./processors/status-check.processor";
import { processDailySearch } from "./processors/daily-search.processor";

const REDIS_URL = process.env.REDIS_URL ?? "redis://redis:6379";
const url = new URL(REDIS_URL);

export const connection: ConnectionOptions = {
  host: url.hostname,
  port: parseInt(url.port ?? "6379"),
  password: url.password || undefined,
};

const worker = new Worker(
  "agent-queue",
  async (job) => {
    switch (job.name) {
      case "job-search":
        await processJobSearch(job);
        break;
      case "followup-email":
        await processFollowupEmail(job);
        break;
      case "status-check":
        await processStatusCheck(job);
        break;
      case "daily-search":
        await processDailySearch(job);
        break;
      default:
        throw new Error(`Unknown job type: ${job.name}`);
    }
  },
  {
    connection,
    concurrency: 2,
    limiter: { max: 10, duration: 60_000 },
  }
);

worker.on("completed", (job) =>
  console.log(`[worker] job ${job.id} (${job.name}) completed`)
);
worker.on("failed", (job, err) =>
  console.error(`[worker] job ${job?.id} failed:`, err.message)
);

// Schedule repeatable jobs
const queue = new Queue("agent-queue", { connection });

// Status check every 6 hours
queue
  .upsertJobScheduler(
    "status-check-scheduler",
    { every: 6 * 60 * 60 * 1000 },
    { name: "status-check", data: { user_id: "all" } }
  )
  .then(() => console.log("[worker] Status check scheduled every 6 hours"))
  .catch((err) => console.error("[worker] Failed to schedule status check:", err));

// Daily job search at 8 AM (every 24 hours)
queue
  .upsertJobScheduler(
    "daily-search-scheduler",
    { every: 24 * 60 * 60 * 1000 },
    { name: "daily-search", data: { user_id: "all" } }
  )
  .then(() => console.log("[worker] Daily search scheduled every 24 hours"))
  .catch((err) => console.error("[worker] Failed to schedule daily search:", err));

console.log("[worker] BullMQ worker started, listening on agent-queue");
