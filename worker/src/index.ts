import { Worker, ConnectionOptions } from "bullmq";
import { processJobSearch } from "./processors/job-search.processor";
import { processFollowupEmail } from "./processors/followup.processor";

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

console.log("[worker] BullMQ worker started, listening on agent-queue");
