import axios from "axios";
import { getClerkAuthToken } from "@/lib/clerk-token";

const configuredUrl = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const API_BASE_URL = configuredUrl.endsWith("/api/v1") ? configuredUrl : `${configuredUrl}/api/v1`;
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
});

// Deduplicate concurrent identical GET requests
const pendingRequests = new Map<string, Promise<unknown>>();

apiClient.interceptors.request.use(async (config) => {
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
  return config;
});

// Response interceptor — log the failure and reject. We do NOT auto-redirect or
// loop on 401 here; the auth guard surfaces a single error page and lets the user
// choose to log in again. This avoids the dashboard⇄login redirect loop.
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
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
    }
    return Promise.reject(error);
  }
);

/**
 * Pulls the backend's `detail` message out of an axios error, falling back to
 * a generic message only when the backend gave nothing usable (e.g. the
 * request never reached it). Use this in onError handlers instead of a
 * hardcoded string, so a 409 "no model configured" doesn't get reported to
 * the user as "backend not connected".
 */
export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
  }
  return fallback;
}

/**
 * Deduplicated GET — prevents duplicate concurrent requests for the same URL.
 * Use for data that multiple components might request simultaneously.
 */
export async function deduplicatedGet<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const key = `${url}?${JSON.stringify(params ?? {})}`;
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
