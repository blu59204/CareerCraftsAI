"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { useAgentStore } from "@/store/agentStore";
import { Toaster } from "sonner";
import { CookieBanner } from "@/components/layout/CookieBanner";

const ReactQueryDevtools =
  process.env.NODE_ENV === "development"
    ? lazy(() =>
        import("@tanstack/react-query-devtools").then((m) => ({
          default: m.ReactQueryDevtools,
        }))
      )
    : () => null;

export function Providers({ children }: { children: React.ReactNode }) {
  const { isLoaded, userId } = useAuth();
  return <AccountProviders key={!isLoaded ? "loading" : userId ?? "signed-out"} owner={userId ?? null}>{children}</AccountProviders>;
}

function AccountProviders({ children, owner }: { children: React.ReactNode; owner: string | null }) {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    useAgentStore.getState().setOwner(owner);
    setReady(true);
  }, [owner]);
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

  useEffect(() => queryClient.getQueryCache().subscribe((event) => {
    if (event.type !== "updated" || event.action.type !== "invalidate") return;
    const key = String(event.query.queryKey[0]);
    const groups = [["models", "user-models"], ["resume-docs", "rag-documents", "dashboard-ats"], ["preferences", "user-preferences"]];
    const group = groups.find((keys) => keys.includes(key));
    if (group) void queryClient.invalidateQueries({ predicate: (query) => query !== event.query && group.includes(String(query.queryKey[0])) && !query.state.isInvalidated });
  }), [queryClient]);
  useEffect(() => () => {
    void queryClient.cancelQueries();
    queryClient.clear();
  }, [queryClient]);
  if (owner && !ready) return null;
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster position="top-right" richColors closeButton />
      <CookieBanner />
      <Suspense>
        <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-left" />
      </Suspense>
    </QueryClientProvider>
  );
}
