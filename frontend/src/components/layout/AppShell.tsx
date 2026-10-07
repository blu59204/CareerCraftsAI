"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { AppSidebar } from "./AppSidebar";
import { AppTopbar } from "./AppTopbar";
import { ConstellationBackground } from "./ConstellationBackground";
import { PendingDeletionBanner } from "./PendingDeletionBanner";
import { useAgentStream } from "@/lib/sse";
import { useAgentStore } from "@/store/agentStore";
import { useUser } from "@clerk/nextjs";
import { CompanionProvider } from "@/components/companion/CompanionProvider";
import { FloatingCompanion } from "@/components/companion/FloatingCompanion";
import { CopilotSessionProvider } from "@/components/agents/CopilotSessionProvider";
import "@/components/companion/companion.css";

// Persistent SSE stream for the active run — lives in the shell so it keeps
// streaming (and updating the store) even when the user navigates between pages.
function ActiveRunStream() {
  const activeRunId = useAgentStore((s) => s.activeRunId);
  useAgentStream(activeRunId);
  return null;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user } = useUser();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  if (pathname === "/onboarding") {
    return <>{children}</>;
  }

  return (
    <CompanionProvider key={user?.id ?? "loading"} ownerId={user?.id ?? ""}>
    <CopilotSessionProvider ownerId={user?.id ?? ""}>
    <div className="premium-command-bg relative min-h-screen overflow-x-clip bg-background text-foreground">
      <ConstellationBackground />
      <ActiveRunStream />
      <div className="app-surface flex min-h-screen">
        <AppSidebar mobileOpen={mobileNavOpen} onMobileClose={() => setMobileNavOpen(false)} />
        <div className="flex min-w-0 flex-1 flex-col">
          <PendingDeletionBanner />
          <AppTopbar onMenuClick={() => setMobileNavOpen(true)} />
          {/* overflow-x-clip (not hidden) so sticky columns/save bars inside screens still stick. */}
          <main className="min-w-0 flex-1 overflow-x-clip px-3 pb-4 pt-5 sm:px-5 lg:px-6">{children}</main>
        </div>
      </div>
    </div>
    <FloatingCompanion />
    </CopilotSessionProvider>
    </CompanionProvider>
  );
}
