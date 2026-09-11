"use client";
import { useEffect, useRef } from "react";
import { getSupabaseAuthToken } from "@/lib/supabase-token";
import { useAgentStore } from "@/store/agentStore";
import { apiClient, API_BASE_URL } from "@/lib/api";

export function useAgentStream(runId: string | null) {
  const { addEvent, setRunStatus, setCheckpoint, setComplete, setError } = useAgentStore();
  const abortRef = useRef<AbortController | null>(null);
  const retryRef = useRef(0);

  useEffect(() => {
    if (!runId) return;
    const id = runId;
    let disposed = false;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let polling = false;
    const pollController = new AbortController();
    if (!useAgentStore.getState().runs[id]) useAgentStore.getState().initRun(id);

    // DB state is authoritative: restore approvals/results after refresh or lost SSE.
    async function reconcile() {
      if (polling || disposed) return;
      polling = true;
      try {
        const { data } = await apiClient.get(`/agents/runs/${id}`, { signal: pollController.signal });
        if (disposed) return;
        if (data.status === "awaiting_approval") setCheckpoint(id, data.output || {});
        else if (data.status === "completed") setComplete(id, data.output || {});
        else if (data.status === "failed") setError(id, data.output?.error || data.output?.message || "Agent failed");
        else if (data.status === "queued" || data.status === "running") setRunStatus(id, data.status);
      } catch { /* transient transport failure is not a failed agent */ }
      finally { polling = false; }
    }
    void reconcile();
    const pollTimer = setInterval(() => void reconcile(), 3000);

    async function connect() {
      if (disposed) return;
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const token = await getSupabaseAuthToken();
        const apiUrl = API_BASE_URL;
        const res = await fetch(`${apiUrl}/agents/${id}/stream`, {
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
          signal: controller.signal,
        });

        if (!res.ok || !res.body) {
          throw new Error(`SSE ${res.status}`);
        }

        retryRef.current = 0;
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        let eventType = "";
        let dataBuffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split("\n");
          buf = lines.pop() ?? "";

          for (const line of lines) {
            if (line.startsWith("event:")) {
              eventType = line.slice(6).trim();
              continue;
            }
            if (line.startsWith("data:")) {
              const raw = line.slice(5).trim();
              dataBuffer += raw;
              continue;
            }
            if (line.trim() === "") {
              // End of an SSE frame
              if (eventType && dataBuffer) {
                try {
                  const data = JSON.parse(dataBuffer);
                  addEvent(id, eventType, data);
                  if (eventType === "checkpoint") {
                    setCheckpoint(id, data);
                  } else if (eventType === "complete") {
                    setComplete(id, data);
                    return;
                   } else if (eventType === "error") {
                    // A broken event bus is not evidence of workflow failure.
                    void reconcile();
                  } else if (eventType === "approved") {
                    useAgentStore.getState().clearCheckpoint(id);
                    setRunStatus(id, "queued");
                  }
                } catch { /* malformed JSON — skip */ }
              }
              eventType = "";
              dataBuffer = "";
            }
          }
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        if (retryRef.current < 3) {
          retryRef.current += 1;
           retryTimer = setTimeout(connect, Math.pow(2, retryRef.current) * 1000);
        }
      }
    }

    connect();
    return () => {
      disposed = true;
      pollController.abort();
      clearInterval(pollTimer);
      if (retryTimer) clearTimeout(retryTimer);
      abortRef.current?.abort();
    };
  }, [runId, addEvent, setRunStatus, setCheckpoint, setComplete, setError]);
}
