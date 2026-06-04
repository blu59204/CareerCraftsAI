"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

function SSOCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleCallback = async () => {
      const code = searchParams.get("code");
      const errorParam = searchParams.get("error");

      if (errorParam) {
        setError(decodeURIComponent(errorParam));
        return;
      }

      if (!code) {
        setError("No authorization code received");
        return;
      }

      // Backend already handled the OAuth flow and created the user
      // Just redirect to dashboard
      router.push("/dashboard");
    };

    handleCallback();
  }, [searchParams, router]);

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
    <main className="flex min-h-screen items-center justify-center bg-background">
      <div className="space-y-3 text-center">
        <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        <p className="text-sm font-medium text-foreground">Completing sign in...</p>
      </div>
    </main>
  );
}

export default function SSOCallbackPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center bg-background">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </main>
      }
    >
      <SSOCallbackContent />
    </Suspense>
  );
}
