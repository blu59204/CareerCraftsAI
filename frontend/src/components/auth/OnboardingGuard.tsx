"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

export function OnboardingGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    setMounted(true);
    const supabase = createClient();
    supabase.auth.getUser().then(({ data: { user } }) => {
      if (!user) {
        router.replace("/login");
      } else {
        setAuthenticated(true);
      }
    });
  }, [router]);

  // Return null on both server and initial client render to avoid hydration mismatch.
  // Server renders with mounted=false, client hydrates with mounted=false — consistent.
  if (!mounted || !authenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return <>{children}</>;
}
