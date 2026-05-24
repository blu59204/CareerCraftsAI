"use client";
import { useEffect, useRef } from "react";
import { useAgentStore } from "@/store/agentSlice";

export function useAgentStream(runId: string | null) {
  const { addEvent, setRunStatus } = useAgentStore();
  const sourceRef = useRef<EventSource | null>(null);
  const retryRef = useRef(0);

  useEffect(() => {
    if (!runId) return;
    const id: string = runId;
    function connect() {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const src = new EventSource(`${apiUrl}/api/v1/agents/${id}/stream`);
      sourceRef.current = src;
      src.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data as string) as {
            type: string;
            data: unknown;
            ts: number;
          };
          addEvent(id, event);
          if (event.type === "complete" || event.type === "error") {
            setRunStatus(id, event.type === "complete" ? "completed" : "failed");
            src.close();
          }
        } catch {
          /* malformed — ignore */
        }
      };
      src.onerror = () => {
        src.close();
        if (retryRef.current < 3) {
          retryRef.current += 1;
          setTimeout(connect, Math.pow(2, retryRef.current) * 1000);
        }
      };
    }
    connect();
    return () => sourceRef.current?.close();
  }, [runId, addEvent, setRunStatus]);
}
