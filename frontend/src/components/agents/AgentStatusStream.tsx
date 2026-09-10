"use client";
import { useEffect } from "react";
import { useAgentStore } from "@/store/agentStore";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { CheckCircle2, Clock3, Loader2, Terminal, TriangleAlert } from "lucide-react";
import { ApprovalModal } from "./ApprovalModal";

const STATUS_COLOR: Record<string, string> = {
  queued: "text-muted-foreground border-border bg-muted",
  running: "text-primary border-primary/30 bg-primary/10",
  awaiting_approval: "text-warning border-warning/30 bg-warning/10",
  completed: "text-success border-success/30 bg-success/10",
  failed: "text-danger border-danger/30 bg-danger/10",
};

const STATUS_ICON: Record<string, typeof Clock3> = {
  running: Loader2,
  awaiting_approval: Clock3,
  completed: CheckCircle2,
  failed: TriangleAlert,
};

interface Props {
  runId: string;
  onApprove?: () => void;
  onCancel?: () => void;
}

export function AgentStatusStream({ runId, onApprove, onCancel }: Props) {
  const setActiveRun = useAgentStore((s) => s.setActiveRun);
  // Register this run as active; the persistent stream in AppShell handles the
  // SSE connection so it survives page navigation.
  useEffect(() => {
    setActiveRun(runId);
  }, [runId, setActiveRun]);
  const run = useAgentStore((s) => s.runs[runId]);
  if (!run) {
    return (
      <div className="flex min-h-52 items-center justify-center rounded-xl border border-border bg-card/60 p-6 text-center">
        <div>
          <Loader2 className="mx-auto h-6 w-6 animate-spin text-primary" />
          <div className="mt-3 text-sm font-medium">Connecting to agent...</div>
          <div className="mt-1 font-mono text-xs text-muted-foreground">{runId.slice(0, 8)}</div>
        </div>
      </div>
    );
  }
  const StatusIcon = STATUS_ICON[run.status] ?? Clock3;

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <span className={`grid h-9 w-9 place-items-center rounded-lg border ${STATUS_COLOR[run.status] ?? "border-border bg-muted text-muted-foreground"}`}>
            <StatusIcon className={`h-4 w-4 ${run.status === "running" ? "animate-spin" : ""}`} />
          </span>
          <div>
            <Badge variant="outline" className={STATUS_COLOR[run.status] ?? ""}>{run.status.replace("_", " ")}</Badge>
            <div className="mt-1 font-mono text-xs text-muted-foreground">{runId.slice(0, 8)}</div>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Terminal className="h-4 w-4" />
          Live log
        </div>
      </div>
      {run.lastFrame?.screenshot_b64 && (
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          <div className="flex items-center justify-between border-b border-border px-3 py-1.5 text-xs text-muted-foreground">
            <span className="truncate">{run.lastFrame.title || run.lastFrame.url}</span>
            <span className="shrink-0 pl-2">live · step {run.lastFrame.step}</span>
          </div>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`data:${run.lastFrame.mime ?? "image/png"};base64,${run.lastFrame.screenshot_b64}`}
            alt="Live browser view"
            className="w-full"
          />
        </div>
      )}
      <ScrollArea className="h-64 rounded-xl border border-border bg-card p-3 font-mono text-xs text-card-foreground shadow-inner">
        {run.events.map((e, i) => (
          <div key={i} className="mb-2 break-words leading-relaxed">
            <span className="text-muted-foreground">[{e.type}]</span>{" "}
            {typeof e.data === "string" ? e.data : JSON.stringify(e.data)}
          </div>
        ))}
        {run.status === "running" && (
          <div className="animate-pulse text-muted-foreground">&#9610;</div>
        )}
      </ScrollArea>
      {Array.isArray(run.result?.child_run_ids) && (
        <div className="rounded-xl border border-border p-3 text-sm">
          <p className="mb-2 font-medium">Application workflows</p>
          {(run.result.child_run_ids as string[]).map(childId => (
            <a key={childId} href={`/agents?run=${encodeURIComponent(childId)}`} className="mr-3 inline-block text-primary underline">
              Open {childId.slice(0, 8)}
            </a>
          ))}
        </div>
      )}
      {run.status === "awaiting_approval" && run.pendingAction && (
        <ApprovalModal
          runId={runId}
          action={run.pendingAction}
          onApprove={onApprove ?? (() => {})}
          onCancel={onCancel ?? (() => {})}
        />
      )}
    </div>
  );
}
