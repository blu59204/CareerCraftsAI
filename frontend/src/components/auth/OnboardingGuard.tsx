"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { usePathname, useRouter } from "next/navigation";
import { apiClient } from "@/lib/api";

interface UserProfile {
  onboarding_completed: boolean;
}

export function OnboardingGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoaded) return;
    let cancelled = false;

    async function checkAccess() {
      setReady(false);
      setError(null);

      if (!isSignedIn) {
        const next = `${window.location.pathname}${window.location.search}`;
        router.replace(`/login?redirect_url=${encodeURIComponent(next)}`);
        return;
      }

      try {
        const token = await getToken();
        if (!token) {
          const next = `${window.location.pathname}${window.location.search}`;
          router.replace(`/login?redirect_url=${encodeURIComponent(next)}`);
          return;
        }

        const { data } = await apiClient.get<UserProfile>("/users/me", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (cancelled) return;

        if (!data.onboarding_completed && pathname !== "/onboarding") {
          router.replace("/onboarding");
          return;
        }
      } catch (err) {
        if (cancelled) return;
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 401 || status === 403) {
          const next = `${window.location.pathname}${window.location.search}`;
          router.replace(`/login?redirect_url=${encodeURIComponent(next)}`);
          return;
        }
        setError("Unable to verify your session. Check the backend connection and retry.");
        return;
      }

      setReady(true);
    }

    checkAccess();

    return () => {
      cancelled = true;
    };
  }, [getToken, isLoaded, isSignedIn, pathname, router]);

  // Keep protected app content hidden until auth and onboarding state are known.
  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6">
        {error ? (
          <div className="max-w-sm rounded-2xl border border-destructive/30 bg-card p-5 text-center">
            <p className="text-sm font-medium text-foreground">{error}</p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="mt-4 rounded-full border border-border px-4 py-2 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              Retry
            </button>
          </div>
        ) : (
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        )}
      </div>
    );
  }

  return <>{children}</>;
}
