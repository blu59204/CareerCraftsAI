"use client";

import { useEffect, useMemo, useState } from "react";
import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

function safeNextPath(next: string | null) {
  if (!next || !next.startsWith("/") || next.startsWith("//")) {
    return "/dashboard";
  }
  return next;
}

function ClientAuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const code = searchParams.get("code");
  const next = useMemo(() => safeNextPath(searchParams.get("next")), [searchParams]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function exchangeCode() {
      if (!code) {
        router.replace("/login?error=missing_code");
        return;
      }

      const supabase = createClient();
      const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);
      if (cancelled) return;

      if (exchangeError) {
        setError(exchangeError.message);
        router.replace(`/login?error=${encodeURIComponent(exchangeError.message)}`);
        return;
      }

      router.replace(next);
      router.refresh();
    }

    exchangeCode();

    return () => {
      cancelled = true;
    };
  }, [code, next, router]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 text-center">
      <div className="space-y-2">
        <p className="text-sm font-medium text-foreground">
          {error ? "Authentication failed" : "Completing sign in..."}
        </p>
        {error && <p className="max-w-md text-xs text-muted-foreground">{error}</p>}
      </div>
    </main>
  );
}

export default function ClientAuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center bg-background px-6 text-center">
          <p className="text-sm font-medium text-foreground">Completing sign in...</p>
        </main>
      }
    >
      <ClientAuthCallbackContent />
    </Suspense>
  );
}
