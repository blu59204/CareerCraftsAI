"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";

/**
 * Keeps unauthenticated users out of the application route group while Clerk
 * resolves a client session. The backend remains the authorization boundary
 * for all user data and mutations.
 */
export function AuthGateClient({ children }: { children: React.ReactNode }) {
  const { isLoaded, isSignedIn } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoaded || isSignedIn) {
      return;
    }

    const target = `${window.location.pathname}${window.location.search}`;
    router.replace(`/login?redirect_url=${encodeURIComponent(target)}`);
  }, [isLoaded, isSignedIn, router]);

  if (!isLoaded || !isSignedIn) {
    return null;
  }

  return <>{children}</>;
}
