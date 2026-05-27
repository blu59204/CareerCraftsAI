"use client";
import { useEffect, useRef } from "react";
import { createClient } from "@/lib/supabase/client";
import { useAgentStore } from "@/store/agentSlice";

// BUG 5: fetch-based SSE so we can send Authorization header
// BUG 10: retryRef resets to 0 on each successful message
export function useAgentStream(runId: string | null) {
  const { addEvent, setRunStatus } = useAgentStore();
  const abortRef = useRef<AbortController | null>(null);
  const retryRef = useRef(0);

  useEffect(() => {
    if (!runId) return;
    const id = runId;

    async function connect() {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const supabase = createClient();
        const { data: { session } } = await supabase.auth.getSession();
        const token = session?.access_token ?? "";

        const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
        const res = await fetch(`${apiUrl}/agents/${id}/stream`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        });

        if (!res.ok || !res.body) {
          throw new Error(`SSE ${res.status}`);
        }

        // BUG 10: reset retry counter on successful connection
        retryRef.current = 0;

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split("\n");
          buf = lines.pop() ?? "";
          for (const line of lines) {
            if (!line.startsWith("data:")) continue;
            const raw = line.slice(5).trim();
            if (!raw) continue;
            try {
              const event = JSON.parse(raw) as { type: string; data: unknown; ts: number };
              addEvent(id, event);
              if (event.type === "complete" || event.type === "error") {
                setRunStatus(id, event.type === "complete" ? "completed" : "failed");
                return;
              }
            } catch {
              /* malformed — ignore */
            }
          }
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        if (retryRef.current < 3) {
          retryRef.current += 1;
          setTimeout(connect, Math.pow(2, retryRef.current) * 1000);
        }
      }
    }

    connect();
    return () => abortRef.current?.abort();
  }, [runId, addEvent, setRunStatus]);
}
