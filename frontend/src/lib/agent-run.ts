import { apiClient } from "@/lib/api";

/**
 * Shared client for long-running agent work (Company Research, Salary,
 * Interview Coach, LinkedIn Outreach, etc). These agents can run up to 120s
 * server-side, well past the 30s Axios timeout used for ordinary requests —
 * so instead of holding one long HTTP request open, we start the run with a
 * fast POST and poll a short GET until it reaches a terminal status.
 */
export type AgentRunDetail = {
  id: string;
  status: "queued" | "running" | "awaiting_approval" | "completed" | "failed" | "expired";
  output: Record<string, unknown> | null;
  error: string | null;
};

const TERMINAL_STATUSES: ReadonlyArray<AgentRunDetail["status"]> = [
  "completed",
  "failed",
  "awaiting_approval",
  "expired",
];

export async function startAgentRun(taskType: string, context: Record<string, unknown>): Promise<string> {
  const { data } = await apiClient.post<{ run_id: string }>("/agents/run", { task_type: taskType, context });
  return data.run_id;
}

export async function waitForAgentRun(runId: string, timeoutMs = 300_000): Promise<AgentRunDetail> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const { data } = await apiClient.get<AgentRunDetail>(`/agents/runs/${runId}`);
    if (TERMINAL_STATUSES.includes(data.status)) return data;
    await new Promise((resolve) => window.setTimeout(resolve, 1_500));
  }
  throw new Error(`Agent run did not finish within ${timeoutMs / 1000} seconds`);
}
