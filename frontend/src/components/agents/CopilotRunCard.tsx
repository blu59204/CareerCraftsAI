"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { z } from "zod";
import { apiClient, getApiErrorMessage } from "@/lib/api";
import { ApprovalModal } from "./ApprovalModal";

interface RunDetail {
  status: string;
  agent_type: string;
  output: Record<string, unknown> | null;
}

export function CopilotRunCard({ runId, showChildren = true }: { runId: string; showChildren?: boolean }) {
  const [reviewing, setReviewing] = useState(false);
  const query = useQuery<RunDetail>({
    queryKey: ["copilot-run", runId],
    queryFn: async () => (await apiClient.get(`/agents/runs/${runId}`)).data,
    refetchInterval: (query) =>
      ["completed", "failed", "cancelled", "expired"].includes(query.state.data?.status ?? "")
        ? false : 3000,
  });
  const run = query.data;
  const closeReview = () => {
    setReviewing(false);
    void query.refetch();
  };

  return (
    <div className="my-3 rounded-2xl border border-border bg-card p-4 text-sm">
      <p className="font-semibold">{run?.agent_type.replaceAll("_", " ") ?? "Agent run"}</p>
      <p role="status" className="mt-1 text-muted-foreground">
        {query.error ? getApiErrorMessage(query.error, "Could not load run status.") :
          run?.status.replaceAll("_", " ") ?? "Loading progress…"}
      </p>
      {run?.agent_type === "computer_task" && typeof run.output?.message === "string" &&
        <p className="mt-2 whitespace-pre-wrap">{run.output.message}</p>}
      {run?.agent_type === "computer_task" && run.status === "failed" && typeof run.output?.error === "string" &&
        <p role="alert" className="mt-2 text-destructive">{run.output.error}</p>}
      <div className="mt-3 flex flex-wrap items-center gap-4">
        <Link className="text-primary underline" href={`/agents?run=${encodeURIComponent(runId)}`}>
          View full run
        </Link>
        {run?.status === "awaiting_approval" && run.output && (
          <button type="button" className="rounded-full bg-primary px-4 py-2 text-primary-foreground focus-visible:ring-2 focus-visible:ring-ring"
            onClick={() => setReviewing(true)}>
            Review approval
          </button>
        )}
      </div>
      {reviewing && run?.status === "awaiting_approval" && run.output && (
        <ApprovalModal runId={runId} action={run.output} onApprove={closeReview} onCancel={closeReview} />
      )}
      {showChildren && Array.isArray(run?.output?.child_run_ids) &&
        [...new Set(run.output.child_run_ids)].slice(0, 5).map((id) =>
          z.string().uuid().safeParse(id).success && id !== runId
            ? <CopilotRunCard key={String(id)} runId={String(id)} showChildren={false} /> : null
        )}
    </div>
  );
}
