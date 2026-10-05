"use client";

/**
 * Copilot (AG-UI) wiring for the Career Copilot chat page.
 *
 * The backend exposes a bare AG-UI agent endpoint (ag-ui-langgraph), not a
 * full CopilotKit runtime — so the provider must NOT get a `runtimeUrl`:
 * the v2 client probes `${runtimeUrl}` with its own `{method: "info"}`
 * protocol and the AG-UI endpoint answers 422 ("Runtime info request
 * failed"). Instead we hand the provider a self-managed `HttpAgent` that
 * speaks AG-UI directly to `/api/v1/agents/chat`.
 *
 * Clerk session tokens rotate about every minute and `HttpAgent.headers` is
 * a plain record (no async support), so the token is cached in this module,
 * refreshed on a short interval, and pushed onto the live agent instance —
 * a request never sees a token older than ~30s.
 */

import { HttpAgent } from "@ag-ui/client";

import { API_BASE_URL } from "@/lib/api";
import { getClerkAuthToken } from "@/lib/clerk-token";

const THREAD_STORAGE_KEY = "cc-copilot-thread-id";
const TOKEN_REFRESH_INTERVAL_MS = 30_000;

export const COPILOT_AGENT_ID = "career-copilot";

let cachedToken: string | null = null;
let refreshTimer: ReturnType<typeof setInterval> | null = null;
let agent: HttpAgent | null = null;

export function getCopilotAgentUrl(): string {
  return `${API_BASE_URL}/agents/chat`;
}

/** Lazily creates the process-wide chat agent; headers refresh with the token. */
export function getOrCreateCopilotAgent(): HttpAgent {
  if (!agent) {
    agent = new HttpAgent({
      agentId: COPILOT_AGENT_ID,
      url: getCopilotAgentUrl(),
      headers: getCopilotHeaders(),
    });
  }
  return agent;
}

export function getOrCreateCopilotThreadId(): string {
  if (typeof window === "undefined") return "";
  let threadId = window.localStorage.getItem(THREAD_STORAGE_KEY);
  if (!threadId) {
    threadId = newThreadId();
  }
  return threadId;
}

export function resetCopilotThreadId(): string {
  const threadId = newThreadId();
  if (typeof window !== "undefined") {
    window.localStorage.setItem(THREAD_STORAGE_KEY, threadId);
  }
  return threadId;
}

function newThreadId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `thread-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

async function refreshCopilotToken(): Promise<void> {
  cachedToken = await getClerkAuthToken();
  if (agent) {
    agent.headers = getCopilotHeaders();
  }
}

export function startCopilotTokenRefresh(): void {
  void refreshCopilotToken();
  if (refreshTimer === null) {
    refreshTimer = setInterval(() => void refreshCopilotToken(), TOKEN_REFRESH_INTERVAL_MS);
  }
}

export function stopCopilotTokenRefresh(): void {
  if (refreshTimer !== null) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

function getCopilotHeaders(): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (cachedToken) {
    headers.Authorization = `Bearer ${cachedToken}`;
  }
  return headers;
}
