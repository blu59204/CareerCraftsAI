import axios from "axios";

export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use(async (config) => {
  if (typeof window !== "undefined") {
    try {
      const { useAuth } = await import("@clerk/nextjs");
      const { getToken } = useAuth();
      const token = await getToken();
      if (token) config.headers.Authorization = `Bearer ${token}`;
    } catch {
      // not in clerk context or SSR
    }
  }
  return config;
});
