import axios from "axios";
import { createClient } from "@/lib/supabase/client";

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
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (session?.access_token) {
        config.headers.Authorization = `Bearer ${session.access_token}`;
      }
    } catch {
      // not authenticated — request will get 401, guard handles redirect
    }
  }
  return config;
});

// Response interceptor — redirect to login on 401 only once per page load
let redirectingToLogin = false;
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error?.response?.status === 401 &&
      typeof window !== "undefined" &&
      !window.location.pathname.startsWith("/login") &&
      !redirectingToLogin
    ) {
      redirectingToLogin = true;
      window.location.href = `/login?redirect_url=${encodeURIComponent(window.location.pathname)}`;
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
