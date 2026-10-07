import axios, { type InternalAxiosRequestConfig } from "axios";
import { useAgentStore } from "../store/agentStore";
type OwnedRequest = InternalAxiosRequestConfig & { ownerGeneration?: number };
import { toast } from "sonner";
import { getClerkAuthToken } from "@/lib/clerk-token";

// Debounce the toast itself — a burst of concurrent requests hitting the same
// limit would otherwise stack a toast per request instead of showing one.
let lastRateLimitToastAt = 0;

const configuredUrl = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const API_BASE_URL = configuredUrl.endsWith("/api/v1") ? configuredUrl : `${configuredUrl}/api/v1`;
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
});

// Deduplicate concurrent identical GET requests
const pendingRequests = new Map<string, Promise<unknown>>();

apiClient.interceptors.request.use(async (config: OwnedRequest) => {
  config.ownerGeneration = useAgentStore.getState().generation;
  if (typeof window !== "undefined") {
    try {
      const token = await getClerkAuthToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    } catch {
      // not authenticated — request will get 401, guard handles redirect
    }
  }
  if (config.ownerGeneration !== useAgentStore.getState().generation) throw new axios.CanceledError("Account changed");
  return config;
});

// Response interceptor — log the failure and reject. We do NOT auto-redirect or
// loop on 401 here; the auth guard surfaces a single error page and lets the user
// choose to log in again. This avoids the dashboard⇄login redirect loop.
apiClient.interceptors.response.use(
  (response) => {
    if ((response.config as OwnedRequest).ownerGeneration !== useAgentStore.getState().generation) throw new axios.CanceledError("Account changed");
    return response;
  },
  async (error) => {
    if (error.config && (error.config as OwnedRequest).ownerGeneration !== useAgentStore.getState().generation) return Promise.reject(new axios.CanceledError("Account changed"));
    // Surface which request failed and the backend's reason (helps diagnose 400/422/500).
    // Only unexpected server failures are errors; a 4xx or a 503 ("feature
    // disabled", "workflow engine unavailable") is an answer the UI handles.
    if (typeof window !== "undefined" && error?.response) {
      const { config, response } = error;
      const log = response.status >= 500 && response.status !== 503 ? console.error : console.warn;
      log(
        `API ${config?.method?.toUpperCase?.() ?? "?"} ${config?.url ?? "?"} -> ${response.status}`,
        response.data?.detail ?? response.data,
      );

      // The backend rate-limits per user/IP but previously gave no visible
      // feedback at all — a 429 just failed silently. Surface it once per
      // 5s window rather than a stacked toast per request in the burst.
      if (response.status === 429) {
        const now = Date.now();
        if (now - lastRateLimitToastAt > 5_000) {
          lastRateLimitToastAt = now;
          const retryAfter = Number(response.headers?.["retry-after"]);
          const wait = Number.isFinite(retryAfter) && retryAfter > 0 ? ` Try again in ${retryAfter}s.` : "";
          toast.error(`You're doing that too much.${wait}`, {
            description: "Please slow down and try again shortly.",
          });
        }
      }
    }
    return Promise.reject(error);
  }
);

/**
 * An error whose message is written for the user (e.g. "Tailor your resume
 * first."). `getApiErrorMessage` shows only these messages; any other Error
 * (a timeout, a bug, a raw agent failure) gets the caller's fallback.
 */
export class UserFacingError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "UserFacingError";
  }
}

/**
 * Pulls the backend's `detail` message out of an axios error, falling back to
 * a generic message only when the backend gave nothing usable (e.g. the
 * request never reached it). Use this in onError handlers instead of a
 * hardcoded string, so a 409 "no model configured" doesn't get reported to
 * the user as "backend not connected". FastAPI validation errors (a `detail`
 * array) are joined into one message; a `UserFacingError` uses its own
 * message; any other error uses `fallback`.
 */
export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail: unknown = error.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (Array.isArray(detail)) {
      const message = detail
        .map((d: unknown) =>
          typeof d === "string" ? d : typeof (d as { msg?: unknown })?.msg === "string" ? (d as { msg: string }).msg : "",
        )
        .filter((m) => m.trim())
        .join("; ");
      if (message) return message;
    }
    return fallback;
  }
  if (error instanceof UserFacingError && error.message.trim()) return error.message;
  return fallback;
}

/**
 * Deduplicated GET — prevents duplicate concurrent requests for the same URL.
 * Use for data that multiple components might request simultaneously.
 */
export async function deduplicatedGet<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const key = `${useAgentStore.getState().generation}:${url}?${JSON.stringify(params ?? {})}`;
  const existing = pendingRequests.get(key);
  if (existing) return existing as Promise<T>;

  const promise = apiClient.get(url, { params }).then((r) => {
    pendingRequests.delete(key);
    return r.data as T;
  }).catch((err) => {
    pendingRequests.delete(key);
    throw err;
  });

  pendingRequests.set(key, promise);
  return promise;
}
