"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";

interface UserProfile {
  onboarding_completed: boolean;
}

export function OnboardingGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  const { data: user } = useQuery<UserProfile>({
    queryKey: ["me"],
    queryFn: async () => {
      const { data } = await apiClient.get<UserProfile>("/users/me");
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (pathname === "/onboarding") return;
    if (user && user.onboarding_completed === false) {
      router.replace("/onboarding");
    }
  }, [user, router, pathname]);

  return <>{children}</>;
}
