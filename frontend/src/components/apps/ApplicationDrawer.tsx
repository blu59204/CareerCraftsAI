"use client";

import * as Dialog from "@radix-ui/react-dialog";
import Link from "next/link";
import { X, Sparkles, Clock, Mail } from "lucide-react";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import type { ApplicationItem, AppStage } from "./ApplicationKanban";

type AgentRun = {
  id: string;
  agent_type: string;
  status: string;
  started_at: string;
  output_summary?: string;
};

type Props = {
  application: ApplicationItem | null;
  open: boolean;
  onClose: () => void;
  activityRuns: AgentRun[];
};

const AI_SUGGESTIONS: Partial<Record<AppStage, { label: string; copy: string }>> = {
  interview: { label: "Prep with Interview Coach", copy: "Prepare for your interview with AI-powered mock sessions and feedback." },
  offer: { label: "Open Salary Agent", copy: "Negotiate your offer with data-driven salary insights and talking points." },
};

export function ApplicationDrawer({ application, open, onClose, activityRuns }: Props) {
  const suggestion = application ? AI_SUGGESTIONS[application.stage] : undefined;

  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-background/60 backdrop-blur-sm" />
        <Dialog.Content className="fixed right-0 top-0 z-50 h-full w-full max-w-md overflow-y-auto border-l border-border bg-card p-6">
          {application && (
            <>
              <div className="flex items-start justify-between">
                <div>
                  <Dialog.Title className="text-xl font-medium">{application.role}</Dialog.Title>
                  <Dialog.Description className="text-sm text-muted-foreground">
                    {application.company} · {application.matchPercent}% match
                  </Dialog.Description>
                </div>
                <button onClick={onClose} className="rounded-full p-2 hover:bg-muted" aria-label="Close">
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="mt-6 space-y-4">
                {suggestion && (
                  <div className="rounded-2xl border border-primary/20 bg-primary/5 p-4">
                    <div className="flex items-center gap-2 text-sm font-medium text-primary">
                      <Sparkles className="h-4 w-4" /> AI Suggestion
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">{suggestion.copy}</p>
                    <Link href={application.stage === "interview" ? "/interview-prep" : "/salary"}>
                      <LiquidGlassButton tone="primary" size="sm" className="mt-3">
                        <Sparkles className="h-3 w-3" /> {suggestion.label}
                      </LiquidGlassButton>
                    </Link>
                  </div>
                )}

                <div className="rounded-2xl border border-border p-4">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Clock className="h-4 w-4 text-muted-foreground" /> Activity Timeline
                  </div>
                  {activityRuns.length === 0 ? (
                    <p className="mt-3 text-xs text-muted-foreground">No agent activity yet for this application.</p>
                  ) : (
                    <div className="mt-3 space-y-3">
                      {activityRuns.map((run) => (
                        <div key={run.id} className="flex gap-3 text-xs">
                          <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-primary" />
                          <div>
                            <span className="font-medium capitalize">{run.agent_type.replace(/_/g, " ")}</span>
                            <span className="ml-2 text-muted-foreground">{run.status}</span>
                            {run.output_summary && <p className="mt-0.5 text-muted-foreground">{run.output_summary}</p>}
                            <p className="mt-0.5 text-muted-foreground/60">{new Date(run.started_at).toLocaleString()}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <Link href="/email">
                  <LiquidGlassButton tone="ghost" size="sm" className="w-full">
                    <Mail className="h-3.5 w-3.5" /> Draft a follow-up email
                  </LiquidGlassButton>
                </Link>
              </div>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
