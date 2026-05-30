"use client";
import { useAgentStore } from "@/store/agentSlice";
import { useAgentStream } from "@/lib/sse";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { CheckCircle2, Clock3, Loader2, Terminal, TriangleAlert } from "lucide-react";
import { ApprovalModal } from "./ApprovalModal";

const STATUS_COLOR: Record<string, string> = {
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
  useAgentStream(runId);
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
