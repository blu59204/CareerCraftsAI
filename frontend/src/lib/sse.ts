"use client";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { useAuth } from "@clerk/nextjs";
import { useEffect, useRef } from "react";
import { useAgentStore } from "@/store/agentSlice";

export function useAgentStream(runId: string | null) {
  const { getToken } = useAuth();
  const { addEvent, setRunStatus } = useAgentStore();
  const sourceRef = useRef<AbortController | null>(null);
  const retryRef = useRef(0);

  useEffect(() => {
    if (!runId) return;
    const id: string = runId;
    const ctrl = new AbortController();
    sourceRef.current = ctrl;

    async function connect() {
      const token = await getToken();
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      await fetchEventSource(`${apiUrl}/api/v1/agents/${id}/stream`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: ctrl.signal,
        onmessage(ev) {
          try {
            const event = JSON.parse(ev.data) as {
              type: string;
              data: unknown;
              ts: number;
            };
            addEvent(id, event);
            if (event.type === "complete" || event.type === "error") {
              setRunStatus(id, event.type === "complete" ? "completed" : "failed");
              ctrl.abort();
            }
          } catch {
            /* malformed — ignore */
          }
        },
        onerror(err) {
          if (retryRef.current < 3) {
            retryRef.current += 1;
            const delay = Math.pow(2, retryRef.current) * 1000;
            setTimeout(connect, delay);
          }
          throw err;
        },
      });
    }

    connect().catch(() => {/* aborted or max retries */});
    return () => ctrl.abort();
  }, [runId, getToken, addEvent, setRunStatus]);
}
