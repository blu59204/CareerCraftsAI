"use client";

import { useEffect, useRef, useState } from "react";
import { useClerk } from "@clerk/nextjs";

/**
 * OAuth landing page for `signIn.authenticateWithRedirect({ redirectUrl: "/sso-callback" })`.
 *
 * Uses the headless `handleRedirectCallback()` from `useClerk()` rather than
 * Clerk's `<AuthenticateWithRedirectCallback />` component, so nothing
 * Clerk-branded is ever mounted.
 */
export default function SSOCallbackPage() {
  const { handleRedirectCallback } = useClerk();
  const [error, setError] = useState<string | null>(null);
  const startedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    handleRedirectCallback({
      signInFallbackRedirectUrl: "/dashboard",
      signUpFallbackRedirectUrl: "/dashboard",
      // A brand-new OAuth identity is transferred into a sign-up attempt here.
      continueSignUpUrl: "/login?mode=sign-up",
    }).catch((err: unknown) => {
      const clerkErrors = (err as { errors?: { longMessage?: string; message?: string }[] })?.errors;
      const first = clerkErrors?.[0];
      setError(
        first?.longMessage ||
          first?.message ||
          (err instanceof Error ? err.message : "Authentication failed"),
      );
    });
  }, [handleRedirectCallback]);

  if (error) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background">
        <div className="max-w-md space-y-4 text-center">
          <div className="text-destructive text-lg font-semibold">Authentication Error</div>
          <p className="text-sm text-muted-foreground">{error}</p>
          <a
            href="/login"
            className="inline-block rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            Back to Login
          </a>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 text-center">
      <div className="space-y-2">
        <p className="text-sm font-medium text-foreground">Completing sign in...</p>
      </div>
    </main>
  );
}
