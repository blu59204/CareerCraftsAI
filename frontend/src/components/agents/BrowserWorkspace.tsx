"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";

interface Frame {
  image: string;
  url: string;
  width: number;
  height: number;
  interactive: boolean;
  expires_at: string;
}

export function BrowserWorkspace({ runId }: { runId: string }) {
  const [frame, setFrame] = useState<Frame | null>(null);
  const [error, setError] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const fetching = useRef(false);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    if (fetching.current) return;
    fetching.current = true;
    try {
      const response = await apiClient.get<Frame>(`/browser/${runId}/frame`, { signal });
      setFrame(response.data);
      setError("");
    } catch {
      if (!signal?.aborted) setError("Browser unavailable, busy, or expired. Refresh to try again.");
    } finally {
      fetching.current = false;
    }
  }, [runId]);

  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal);
    const timer = setInterval(() => void refresh(controller.signal), 3000);
    return () => { controller.abort(); clearInterval(timer); };
  }, [refresh]);

  const input = async (payload: Record<string, unknown>) => {
    if (busy || !frame?.interactive) return;
    setBusy(true);
    try {
      await apiClient.post(`/browser/${runId}/input`, payload);
      setText("");
      await refresh();
    } catch {
      setError("Action could not be performed. Final submission requires form approval below.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="space-y-3 rounded-xl border border-border p-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">Isolated browser {frame?.interactive ? "· Your control" : "· Read-only review"}</h3>
        <Button size="sm" variant="outline" onClick={() => void refresh()}>Refresh</Button>
      </div>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {frame && <>
        <p className="break-all text-xs text-muted-foreground">{frame.url}</p>
        <button type="button" className="block w-full overflow-hidden rounded-lg border border-border"
          aria-label="Click a field or control in the remote browser" disabled={busy || !frame.interactive}
          onClick={(event) => {
            const rect = event.currentTarget.getBoundingClientRect();
            void input({ action: "click", x: Math.round((event.clientX - rect.left) * frame.width / rect.width),
              y: Math.round((event.clientY - rect.top) * frame.height / rect.height) });
          }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={`data:image/jpeg;base64,${frame.image}`} alt="Current application browser screen" className="w-full" draggable={false} />
        </button>
        {frame.interactive && <>
          <p className="text-xs text-muted-foreground">Click a field above, then enter its value here. Passwords and codes go directly to your browser. Click the site’s login button to sign in.</p>
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); void input({ action: "text", text }); }}>
            <input aria-label="Text to enter in the selected browser field" type="password" autoComplete="off"
              value={text} onChange={(e) => setText(e.target.value)} className="min-w-0 flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm" />
            <Button type="submit" disabled={busy || !text}>Type</Button>
          </form>
          <div className="flex flex-wrap gap-2">
            {(["Tab", "Backspace", "ArrowDown", "ArrowUp", "ControlOrMeta+A"] as const).map(key =>
              <Button key={key} size="sm" variant="outline" disabled={busy} onClick={() => void input({ action: "key", key })}>{key === "ControlOrMeta+A" ? "Select all" : key}</Button>)}
            <Button size="sm" variant="outline" disabled={busy} onClick={() => void input({ action: "scroll", delta: 600 })}>Scroll down</Button>
            <Button size="sm" variant="outline" disabled={busy} onClick={() => void input({ action: "scroll", delta: -600 })}>Scroll up</Button>
          </div>
        </>}
        <p className="text-xs text-muted-foreground">Session expires {new Date(frame.expires_at).toLocaleTimeString()}.</p>
      </>}
    </section>
  );
}
