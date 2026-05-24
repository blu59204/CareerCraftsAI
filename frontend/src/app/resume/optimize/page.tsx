"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { AgentStatusStream } from "@/components/agents/AgentStatusStream";
import { apiClient } from "@/lib/api";
import { useAgentStore } from "@/store/agentSlice";
import { toast } from "sonner";

export default function ResumeOptimizePage() {
  const [jd, setJd] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const { initRun } = useAgentStore();

  const { mutate, isPending } = useMutation({
    mutationFn: () =>
      apiClient.post("/api/v1/agents/run", {
        task_type: "resume_optimize",
        context: { jd_text: jd },
      }),
    onSuccess: (res) => {
      const id = (res.data as { run_id: string }).run_id;
      initRun(id);
      setRunId(id);
    },
    onError: () => toast.error("Failed to start"),
  });

  return (
    <main className="p-8 max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold">Optimize Resume</h1>
      <Textarea
        value={jd}
        onChange={(e) => setJd(e.target.value)}
        placeholder="Paste job description..."
        rows={10}
      />
      <Button onClick={() => mutate()} disabled={isPending || !jd.trim()}>
        {isPending ? "Starting..." : "Optimize with AI"}
      </Button>
      {runId && (
        <AgentStatusStream
          runId={runId}
          onApprove={() => toast.success("Resume ready")}
          onCancel={() => setRunId(null)}
        />
      )}
    </main>
  );
}
