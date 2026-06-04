import axios from "axios";
import { getSupabaseAuthToken } from "@/lib/supabase-token";

export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1",
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
});

// Deduplicate concurrent identical GET requests
const pendingRequests = new Map<string, Promise<unknown>>();

apiClient.interceptors.request.use(async (config) => {
  if (typeof window !== "undefined") {
    try {
      const token = await getSupabaseAuthToken();
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
    if (typeof window !== "undefined" && error?.response) {
      const { config, response } = error;
      console.error(
        `API ${config?.method?.toUpperCase?.() ?? "?"} ${config?.url ?? "?"} -> ${response.status}`,
        response.data?.detail ?? response.data,
      );
    }
    return Promise.reject(error);
  }
);

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
