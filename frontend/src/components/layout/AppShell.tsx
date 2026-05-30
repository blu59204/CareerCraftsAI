"use client";

import { usePathname } from "next/navigation";
import { AppSidebar } from "./AppSidebar";
import { AppTopbar } from "./AppTopbar";
import { ConstellationBackground } from "./ConstellationBackground";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  if (pathname === "/onboarding") {
    return <>{children}</>;
  }

  return (
    <div className="premium-command-bg relative min-h-screen overflow-x-hidden bg-background text-foreground">
      <ConstellationBackground />
      <div className="app-surface flex min-h-screen">
        <AppSidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <AppTopbar />
          <main className="min-w-0 flex-1 overflow-x-hidden px-6 pb-8 pt-7 md:px-8">{children}</main>
        </div>
      </div>
    </div>
  );
}
