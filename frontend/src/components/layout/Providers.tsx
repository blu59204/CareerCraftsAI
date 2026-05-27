"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense, useState } from "react";
import { Toaster } from "sonner";

const ReactQueryDevtools =
  process.env.NODE_ENV === "development"
    ? lazy(() =>
        import("@tanstack/react-query-devtools").then((m) => ({
          default: m.ReactQueryDevtools,
        }))
      )
    : () => null;

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5 * 60_000,
            gcTime: 10 * 60_000,
            retry: (failureCount, error: any) => {
              // Don't retry on auth errors
              if (error?.response?.status === 401 || error?.response?.status === 403) return false;
              return failureCount < 1;
            },
            refetchOnWindowFocus: false,
            refetchOnReconnect: true,
            throwOnError: false,
          },
          mutations: {
            retry: 0,
          },
        },
      })
  );
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster position="top-right" richColors closeButton />
      <Suspense>
        <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-left" />
      </Suspense>
    </QueryClientProvider>
  );
}
