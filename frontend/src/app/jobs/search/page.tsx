"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AgentStatusStream } from "@/components/agents/AgentStatusStream";
import { apiClient } from "@/lib/api";
import { useAgentStore } from "@/store/agentSlice";
import { toast } from "sonner";

export default function JobSearchPage() {
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("Remote");
  const [runId, setRunId] = useState<string | null>(null);
  const { initRun } = useAgentStore();

  const { mutate, isPending } = useMutation({
    mutationFn: () =>
      apiClient.post("/api/v1/agents/run", {
        task_type: "job_search",
        context: { search_query: query, location, max_results: 10 },
      }),
    onSuccess: (res) => {
      const id = (res.data as { run_id: string }).run_id;
      initRun(id);
      setRunId(id);
    },
    onError: () => toast.error("Failed to start search"),
  });

  return (
    <main className="p-8 max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold">Job Search</h1>
      <div className="flex gap-3">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Job title or keywords"
          className="flex-1"
        />
        <Input
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="Location"
          className="w-40"
        />
        <Button onClick={() => mutate()} disabled={isPending || !query.trim()}>
          {isPending ? "Searching..." : "Search"}
        </Button>
      </div>
      {runId && (
        <AgentStatusStream
          runId={runId}
          onApprove={() => toast.success("Search complete")}
          onCancel={() => setRunId(null)}
        />
      )}
    </main>
  );
}
