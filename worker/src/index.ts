import { Worker, Queue, ConnectionOptions } from "bullmq";
import IORedis from "ioredis";
import { processJobSearch } from "./processors/job-search.processor";
import { processFollowupEmail } from "./processors/followup.processor";
import { processStatusCheck } from "./processors/status-check.processor";
import { processDailySearch } from "./processors/daily-search.processor";

const REDIS_URL = process.env.REDIS_URL ?? "redis://127.0.0.1:6379";
const url = new URL(REDIS_URL);
const redisConnection = {
  host: url.hostname,
  port: parseInt(url.port || "6379", 10),
  password: url.password || process.env.REDIS_PASSWORD || undefined,
  maxRetriesPerRequest: null,
  connectTimeout: 5_000,
};

export const connection: ConnectionOptions = redisConnection;

async function main(): Promise<void> {
  const probe = new IORedis(REDIS_URL, {
    connectTimeout: 5_000,
    maxRetriesPerRequest: 1,
    retryStrategy: () => null,
  });

  try {
    await probe.ping();
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(
      `[worker] Redis unavailable at ${url.hostname}:${url.port || "6379"} (${message})`
    );
    console.error(
      "[worker] Start Redis, or set REDIS_URL/REDIS_PASSWORD to a reachable instance."
    );
    process.exit(1);
  } finally {
    probe.disconnect();
  }

  const queue = new Queue("agent-queue", { connection });

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

  // Status check every 6 hours
  await queue.upsertJobScheduler(
    "status-check-scheduler",
    { every: 6 * 60 * 60 * 1000 },
    { name: "status-check", data: { user_id: "all" } }
  );
  console.log("[worker] Status check scheduled every 6 hours");

  // Daily job search every 24 hours
  await queue.upsertJobScheduler(
    "daily-search-scheduler",
    { every: 24 * 60 * 60 * 1000 },
    { name: "daily-search", data: { user_id: "all" } }
  );
  console.log("[worker] Daily search scheduled every 24 hours");

  console.log("[worker] BullMQ worker started, listening on agent-queue");
}

main().catch((err) => {
  console.error("[worker] fatal:", err);
  process.exit(1);
});
