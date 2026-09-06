import { create } from "zustand";

interface AgentEvent {
  type: string;
  data: unknown;
  ts: number;
}

interface BrowserFrame {
  step: number;
  url: string;
  title: string;
  screenshot_b64: string;
  mime?: string;
}

interface AgentRun {
  runId: string;
  status: "running" | "awaiting_approval" | "completed" | "failed";
  events: AgentEvent[];
  pendingAction: Record<string, unknown> | null;
  lastFrame?: BrowserFrame;
}

interface AgentStore {
  runs: Record<string, AgentRun>;
  activeRunId: string | null;
  initRun: (runId: string) => void;
  setActiveRun: (runId: string | null) => void;
  addEvent: (runId: string, event: AgentEvent) => void;
  setRunStatus: (runId: string, status: AgentRun["status"]) => void;
  clearRun: (runId: string) => void;
}

const ACTIVE_RUN_KEY = "cc_active_run_id";

function persistActiveRun(runId: string | null) {
  if (typeof window === "undefined") return;
  if (runId) localStorage.setItem(ACTIVE_RUN_KEY, runId);
  else localStorage.removeItem(ACTIVE_RUN_KEY);
}

export const useAgentStore = create<AgentStore>((set) => ({
  runs: {},
  activeRunId: typeof window !== "undefined" ? localStorage.getItem(ACTIVE_RUN_KEY) : null,
  setActiveRun: (runId) => {
    persistActiveRun(runId);
    set({ activeRunId: runId });
  },
  initRun: (runId) => {
    persistActiveRun(runId);
    return set((s) => ({
      activeRunId: runId,
      runs: {
        ...s.runs,
        [runId]: { runId, status: "running", events: [], pendingAction: null },
      },
    }));
  },
  addEvent: (runId, event) =>
    set((s) => {
      const run = s.runs[runId] ?? {
        runId,
        status: "running" as const,
        events: [],
        pendingAction: null,
      };
      // Live browser screenshots are kept as the latest frame only (not in the
      // event log, which would bloat with base64 images).
      if (event.type === "browser_frame") {
        return { runs: { ...s.runs, [runId]: { ...run, lastFrame: event.data as BrowserFrame } } };
      }
      const updates: Partial<AgentRun> = { events: [...run.events, event] };
      if (event.type === "checkpoint") {
        updates.status = "awaiting_approval";
        updates.pendingAction =
          typeof event.data === "string"
            ? (JSON.parse(event.data) as Record<string, unknown>)
            : (event.data as Record<string, unknown>);
      }
      return { runs: { ...s.runs, [runId]: { ...run, ...updates } } };
    }),
  setRunStatus: (runId, status) =>
    set((s) => {
      if (status === "completed" || status === "failed") persistActiveRun(null);
      return { runs: { ...s.runs, [runId]: { ...s.runs[runId], status } } };
    }),
  clearRun: (runId) =>
    set((s) => {
      const rest = { ...s.runs };
      delete rest[runId];
      return { runs: rest };
    }),
}));
