"use client";

import { useEffect, useMemo, useState } from "react";

import {
  CopilotChat,
  CopilotKitProvider,
  useConfigureSuggestions,
} from "@copilotkit/react-core/v2";
import "./copilot-v2.css";

import {
  COPILOT_AGENT_ID,
  getOrCreateCopilotAgent,
  getOrCreateCopilotThreadId,
  resetCopilotThreadId,
  startCopilotTokenRefresh,
  stopCopilotTokenRefresh,
} from "@/lib/copilot";

const SUGGESTIONS = [
  {
    title: "Find me jobs",
    message: "Search for Python developer jobs in Remote and show me the top matches.",
  },
  {
    title: "Run auto-apply",
    message: "Start an auto-apply run for the jobs I saved this week.",
  },
  {
    title: "Tailor my resume",
    message: "Tailor my resume to a job description I'll paste.",
  },
  {
    title: "Interview prep",
    message: "Prep me for a senior backend interview at a product company.",
  },
];

function CopilotChatPanel({ threadId, onNewChat }: { threadId: string; onNewChat: () => void }) {
  const [error, setError] = useState<string | null>(null);

  // CopilotChat's onError overlaps the DOM onError in its prop type; a wide
  // parameter satisfies both members of the intersection.
  const handleChatError = (event: unknown) => {
    const message =
      typeof event === "object" && event !== null && "error" in event
        ? (event as { error: Error }).error?.message
        : undefined;
    setError(message || "The copilot hit an error. Try again.");
  };

  useConfigureSuggestions(
    {
      suggestions: SUGGESTIONS,
      available: "before-first-message",
      consumerAgentId: COPILOT_AGENT_ID,
    },
    [threadId],
  );

  return (
    <div className="glass-panel flex h-[calc(100vh-9rem)] min-h-[540px] flex-col overflow-hidden rounded-[32px]">
      <div className="flex items-center justify-between border-b border-white/40 px-6 py-4 dark:border-white/10">
        <div>
          <h1 className="font-command text-xl font-semibold leading-none">Career Copilot</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            Start runs, check progress, and review applications — approvals always stay with you.
          </p>
        </div>
        <button
          type="button"
          onClick={onNewChat}
          className="rounded-full border border-white/40 bg-white/[0.10] px-4 py-1.5 text-xs font-medium text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.35)] backdrop-blur-[18px] transition hover:bg-white/[0.16] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:border-white/10 dark:bg-black/[0.12]"
        >
          New chat
        </button>
      </div>
      {error && (
        <div className="mx-6 mt-4 rounded-2xl border border-destructive/40 bg-destructive/10 px-4 py-2 text-sm text-destructive">
          {error}
        </div>
      )}
      <div className="copilot-chat-host min-h-0 flex-1">
        <CopilotChat
          agentId={COPILOT_AGENT_ID}
          threadId={threadId}
          labels={{ chatInputPlaceholder: "Ask your copilot to start or check a run…" }}
          onError={handleChatError}
        />
      </div>
    </div>
  );
}

export default function CopilotPage() {
  const [threadId, setThreadId] = useState<string | null>(null);

  useEffect(() => {
    startCopilotTokenRefresh();
    setThreadId(getOrCreateCopilotThreadId());
    return () => stopCopilotTokenRefresh();
  }, []);

  // The backend serves a bare AG-UI agent (no CopilotKit runtime), so the
  // provider gets a self-managed HttpAgent and NO runtimeUrl — a runtimeUrl
  // would make the client probe it with its own protocol and 422.
  const agent = useMemo(() => getOrCreateCopilotAgent(), []);

  return (
    <div className="mx-auto w-full max-w-4xl">
      {threadId ? (
        <CopilotKitProvider
          key={threadId}
          agentId={COPILOT_AGENT_ID}
          selfManagedAgents={{ [COPILOT_AGENT_ID]: agent }}
        >
          <CopilotChatPanel threadId={threadId} onNewChat={() => setThreadId(resetCopilotThreadId())} />
        </CopilotKitProvider>
      ) : (
        <div className="glass-panel h-[calc(100vh-9rem)] animate-pulse rounded-[32px]" />
      )}
    </div>
  );
}
