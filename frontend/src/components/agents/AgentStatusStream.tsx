"use client";
import { useAgentStore } from "@/store/agentSlice";
import { useAgentStream } from "@/lib/sse";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ApprovalModal } from "./ApprovalModal";

const STATUS_COLOR: Record<string, string> = {
  running: "bg-blue-500",
  awaiting_approval: "bg-yellow-500",
  completed: "bg-green-500",
  failed: "bg-red-500",
};

interface Props {
  runId: string;
  onApprove?: () => void;
  onCancel?: () => void;
}

export function AgentStatusStream({ runId, onApprove, onCancel }: Props) {
  useAgentStream(runId);
  const run = useAgentStore((s) => s.runs[runId]);
  if (!run) return null;

  return (
    <div className="border rounded-lg p-4 space-y-3">
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${STATUS_COLOR[run.status] ?? "bg-gray-400"}`} />
        <Badge variant="outline">{run.status.replace("_", " ")}</Badge>
        <span className="text-xs text-slate-400 font-mono">{runId.slice(0, 8)}</span>
      </div>
      <ScrollArea className="h-48 font-mono text-xs bg-slate-950 text-slate-200 rounded p-3">
        {run.events.map((e, i) => (
          <div key={i} className="mb-1">
            <span className="text-slate-500">[{e.type}]</span>{" "}
            {typeof e.data === "string" ? e.data : JSON.stringify(e.data)}
          </div>
        ))}
        {run.status === "running" && (
          <div className="animate-pulse text-slate-400">&#9610;</div>
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
