"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth, useClerk } from "@clerk/nextjs";
import { apiClient } from "@/lib/api";

interface UserProfile {
  onboarding_completed: boolean;
  policy_accepted_at: string | null;
}

interface GuardError {
  message: string;
  isAuth: boolean;
}

export function OnboardingGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const { signOut } = useClerk();
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<GuardError | null>(null);
  const [needsConsent, setNeedsConsent] = useState(false);
  const [agreeChecked, setAgreeChecked] = useState(false);
  const [consenting, setConsenting] = useState(false);
  const [consentError, setConsentError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function checkAccess() {
      if (!isLoaded) return;

      setReady(false);
      setError(null);

      // No Clerk session at all → genuinely logged out → go to login.
      if (!isSignedIn) {
        const next = `${window.location.pathname}${window.location.search}`;
        router.replace(`/login?redirect_url=${encodeURIComponent(next)}`);
        return;
      }

      const token = await getToken();
      if (cancelled) return;

      if (!token) {
        const next = `${window.location.pathname}${window.location.search}`;
        router.replace(`/login?redirect_url=${encodeURIComponent(next)}`);
        return;
      }

      try {
        const { data } = await apiClient.get<UserProfile>("/users/me", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (cancelled) return;

        // Agreeing to the Terms/Privacy Policy comes before anything else —
        // the backend blocks every other endpoint until this is recorded, so
        // check it first rather than letting onboarding fail underneath it.
        if (!data.policy_accepted_at) {
          setNeedsConsent(true);
          setReady(true);
          return;
        }
        setNeedsConsent(false);

        if (!data.onboarding_completed && pathname !== "/onboarding") {
          router.replace("/onboarding");
          return;
        }
      } catch (err) {
        if (cancelled) return;
        const status = (err as { response?: { status?: number } })?.response?.status;

        // Show the error page ONCE — never loop or auto-redirect.
        // 401/403 = authentication error → offer a "Log in again" action.
        // Anything else (backend down, 5xx) → offer a plain "Retry".
        if (status === 401 || status === 403) {
          setError({
            message: "Your session is no longer valid. Please log in again.",
            isAuth: true,
          });
        } else {
          setError({
            message: "Unable to verify your session. Check the backend connection and retry.",
            isAuth: false,
          });
        }
        return;
      }

      setReady(true);
    }

    checkAccess();

    return () => {
      cancelled = true;
    };
  }, [pathname, router, isLoaded, isSignedIn, getToken, refreshKey]);

  async function handleLoginAgain() {
    try {
      await signOut();
    } catch {
      // ignore — redirect regardless
    }
    router.replace("/login");
  }

  async function handleAgree() {
    if (!agreeChecked || consenting) return;
    setConsenting(true);
    setConsentError(null);
    try {
      await apiClient.post("/users/me/consent");
      setRefreshKey((k) => k + 1);
    } catch {
      setConsentError("Couldn't record your agreement. Please try again.");
    } finally {
      setConsenting(false);
    }
  }

  // Keep protected app content hidden until auth and onboarding state are known.
  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6">
        {error ? (
          <div className="max-w-sm rounded-2xl border border-danger/30 bg-card p-5 text-center">
            <p className="text-sm font-medium text-foreground">{error.message}</p>
            {error.isAuth ? (
              <button
                type="button"
                onClick={handleLoginAgain}
                className="mt-4 rounded-full bg-primary px-4 py-2 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90"
              >
                Log in again
              </button>
            ) : (
              <button
                type="button"
                onClick={() => window.location.reload()}
                className="mt-4 rounded-full border border-border px-4 py-2 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                Retry
              </button>
            )}
          </div>
        ) : (
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        )}
      </div>
    );
  }

  if (needsConsent) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6">
        <div className="w-full max-w-md rounded-2xl border border-border bg-card p-6">
          <h1 className="text-lg font-medium text-foreground">One more thing</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Before you continue, please agree to our Terms of Service and Privacy Policy.
          </p>
          <label className="mt-5 flex items-start gap-2.5 text-sm text-muted-foreground">
            <input
              type="checkbox"
              checked={agreeChecked}
              onChange={(e) => setAgreeChecked(e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-border"
            />
            <span>
              I agree to the{" "}
              <a href="/terms" target="_blank" className="text-primary hover:underline">
                Terms of Service
              </a>{" "}
              and{" "}
              <a href="/privacy" target="_blank" className="text-primary hover:underline">
                Privacy Policy
              </a>
              .
            </span>
          </label>
          {consentError ? <p className="mt-3 text-sm text-danger">{consentError}</p> : null}
          <div className="mt-5 flex items-center justify-between gap-3">
            <button
              type="button"
              onClick={handleLoginAgain}
              className="text-xs font-medium text-muted-foreground hover:text-foreground"
            >
              Sign out
            </button>
            <button
              type="button"
              disabled={!agreeChecked || consenting}
              onClick={handleAgree}
              className="rounded-full bg-primary px-5 py-2 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {consenting ? "Saving…" : "Agree & continue"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
