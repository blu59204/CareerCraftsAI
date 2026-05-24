import axios from "axios";

export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use(async (config) => {
  if (typeof window !== "undefined") {
    try {
      const token = await (
        window as Window & { Clerk?: { session?: { getToken: () => Promise<string | null> } } }
      ).Clerk?.session?.getToken();
      if (token) config.headers.Authorization = `Bearer ${token}`;
    } catch {
      // clerk not loaded or SSR
    }
  }
  return config;
});
