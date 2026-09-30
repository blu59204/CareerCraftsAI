"use client";

import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";
import {
  ArrowClockwise,
  ArrowDown,
  ArrowLineDown,
  ArrowLineUp,
  ArrowUp,
  ArrowElbowDownLeft,
  Backspace,
  Browser,
  CursorClick,
  KeyReturn,
  Lock,
  SelectionAll,
  Timer,
  WarningCircle,
} from "@phosphor-icons/react";
import { apiClient } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Bezel, Input, IslandButton, Notice, StatusPill } from "@/components/vanguard";

interface Frame {
  image: string;
  url: string;
  width: number;
  height: number;
  interactive: boolean;
  expires_at: string;
}

type KeyName = "Tab" | "Backspace" | "ArrowDown" | "ArrowUp" | "ControlOrMeta+A";

const KEY_ICON: Record<KeyName, ReactNode> = {
  Tab: <ArrowElbowDownLeft size={14} weight="light" className="-scale-x-100" />,
  Backspace: <Backspace size={14} weight="light" />,
  ArrowDown: <ArrowDown size={14} weight="light" />,
  ArrowUp: <ArrowUp size={14} weight="light" />,
  "ControlOrMeta+A": <SelectionAll size={14} weight="light" />,
};

/** Compact key-cap button for the remote keyboard strip. */
function KeyCap({ children, icon, disabled, onClick }: { children: ReactNode; icon: ReactNode; disabled?: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "inline-flex h-9 items-center gap-2 rounded-xl bg-card px-3 text-[12px] font-medium text-foreground",
        "ring-1 ring-foreground/[0.08] shadow-bezel-core dark:bg-white/[0.04] dark:ring-white/10 dark:shadow-bezel-core-dark",
        "transition-[background-color,transform,box-shadow] duration-500 ease-vanguard hover:bg-muted/60 active:scale-[0.96]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50",
      )}
    >
      <span aria-hidden className="grid place-items-center text-muted-foreground">{icon}</span>
      {children}
    </button>
  );
}

export function BrowserWorkspace({ runId }: { runId: string }) {
  const [frame, setFrame] = useState<Frame | null>(null);
  const [error, setError] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const fetching = useRef(false);
  const headingId = useId();

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
    <section aria-labelledby={headingId} className="space-y-4">
      <Bezel size="lg" coreClassName="overflow-hidden">
        {/* Window chrome: title, mode, refresh */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 pb-3 pt-4 md:px-5">
          <div className="flex min-w-0 items-center gap-3">
            <span aria-hidden className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-foreground/[0.04] text-foreground/80 ring-1 ring-foreground/[0.06] dark:bg-white/[0.05] dark:ring-white/10">
              <Browser size={17} weight="light" />
            </span>
            <h3 id={headingId} className="truncate font-geist text-[15px] font-semibold tracking-[-0.015em] text-foreground">
              Isolated browser {frame?.interactive ? "· Your control" : "· Read-only review"}
            </h3>
          </div>
          <div className="flex items-center gap-2">
            {frame ? (
              <StatusPill tone={frame.interactive ? "primary" : "neutral"} live={frame.interactive}>
                {frame.interactive ? "Interactive" : "View only"}
              </StatusPill>
            ) : null}
            <IslandButton
              tone="ghost"
              size="sm"
              icon={<ArrowClockwise size={14} weight="light" />}
              onClick={() => void refresh()}
            >
              Refresh
            </IslandButton>
          </div>
        </div>

        {/* Address bar */}
        {frame ? (
          <div className="px-4 pb-3 md:px-5">
            <div className="flex items-start gap-2 rounded-full bg-muted/60 px-4 py-2 ring-1 ring-foreground/[0.05] dark:bg-background/60 dark:ring-white/[0.06]">
              <Lock aria-hidden size={13} weight="light" className="mt-[3px] shrink-0 text-muted-foreground" />
              <p className="min-w-0 break-all font-geist-mono text-[11px] leading-5 text-muted-foreground">{frame.url}</p>
            </div>
          </div>
        ) : null}

        {/* Viewport */}
        <div className="px-1.5 pb-1.5">
          {frame ? (
            <button
              type="button"
              className={cn(
                "group relative block w-full overflow-hidden rounded-[calc(2rem-0.75rem)] bg-muted/40 ring-1 ring-foreground/[0.06] dark:ring-white/10",
                "transition-[box-shadow] duration-500 ease-vanguard focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                frame.interactive && !busy ? "cursor-crosshair hover:ring-primary/40" : "cursor-default",
                busy && "opacity-80",
              )}
              aria-label="Click a field or control in the remote browser"
              disabled={busy || !frame.interactive}
              onClick={(event) => {
                const rect = event.currentTarget.getBoundingClientRect();
                void input({ action: "click", x: Math.round((event.clientX - rect.left) * frame.width / rect.width),
                  y: Math.round((event.clientY - rect.top) * frame.height / rect.height) });
              }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`data:image/jpeg;base64,${frame.image}`} alt="Current application browser screen" className="block w-full" draggable={false} />
              {frame.interactive ? (
                <span
                  aria-hidden
                  className="pointer-events-none absolute bottom-3 left-3 inline-flex items-center gap-1.5 rounded-full bg-background/90 px-3 py-1.5 text-[11px] font-medium text-foreground opacity-0 ring-1 ring-foreground/[0.08] transition-opacity duration-500 ease-vanguard group-hover:opacity-100 dark:ring-white/10"
                >
                  <CursorClick size={13} weight="light" />
                  Click to focus a field
                </span>
              ) : null}
            </button>
          ) : (
            <div
              aria-hidden
              className="shimmer aspect-[16/10] w-full rounded-[calc(2rem-0.75rem)]"
            />
          )}
        </div>
      </Bezel>

      {error ? (
        <Notice tone="danger" icon={<WarningCircle size={16} weight="light" />}>
          {error}
        </Notice>
      ) : null}

      {frame ? (
        <div className="space-y-4">
          {frame.interactive ? (
            <Bezel size="md" tone="muted" coreClassName="space-y-4 p-4 md:p-5">
              <p className="max-w-[68ch] text-xs leading-5 text-muted-foreground">
                Click a field above, then enter its value here. Passwords and codes go directly to your browser. Click the site’s login button to sign in.
              </p>
              <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); void input({ action: "text", text }); }}>
                <Input
                  aria-label="Text to enter in the selected browser field"
                  type="password"
                  autoComplete="off"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  trayClassName="min-w-0 flex-1"
                  className="font-geist-mono"
                  leading={<KeyReturn size={15} weight="light" />}
                />
                <IslandButton type="submit" size="md" disabled={busy || !text}>
                  Type
                </IslandButton>
              </form>
              <div className="flex flex-wrap gap-2" role="group" aria-label="Remote keyboard and scrolling">
                {(["Tab", "Backspace", "ArrowDown", "ArrowUp", "ControlOrMeta+A"] as const).map(key =>
                  <KeyCap key={key} icon={KEY_ICON[key]} disabled={busy} onClick={() => void input({ action: "key", key })}>
                    {key === "ControlOrMeta+A" ? "Select all" : key}
                  </KeyCap>)}
                <KeyCap icon={<ArrowLineDown size={14} weight="light" />} disabled={busy} onClick={() => void input({ action: "scroll", delta: 600 })}>Scroll down</KeyCap>
                <KeyCap icon={<ArrowLineUp size={14} weight="light" />} disabled={busy} onClick={() => void input({ action: "scroll", delta: -600 })}>Scroll up</KeyCap>
              </div>
            </Bezel>
          ) : null}
          <p className="flex items-center gap-2 pl-1 text-xs text-muted-foreground">
            <Timer aria-hidden size={14} weight="light" />
            <span className="tabular-nums">Session expires {new Date(frame.expires_at).toLocaleTimeString()}.</span>
          </p>
        </div>
      ) : null}
    </section>
  );
}
