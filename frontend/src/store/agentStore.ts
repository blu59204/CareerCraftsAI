import { create } from "zustand";

interface AgentEvent {
  type: string;
  data: unknown;
  ts?: number;
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
  status: "queued" | "running" | "awaiting_approval" | "completed" | "failed";
  events: AgentEvent[];
  pendingAction: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  error: string | null;
  lastFrame?: BrowserFrame;
}

interface AgentStore {
  runs: Record<string, AgentRun>;
  activeRunId: string | null;

  setActiveRun: (runId: string | null) => void;
  initRun: (runId: string) => void;
  addEvent: (runId: string, eventType: string, data: unknown) => void;
  setCheckpoint: (runId: string, pendingAction: Record<string, unknown>) => void;
  clearCheckpoint: (runId: string) => void;
  setComplete: (runId: string, result: Record<string, unknown>) => void;
  setError: (runId: string, message: string) => void;
  setRunStatus: (runId: string, status: AgentRun["status"]) => void;
  clearRun: (runId: string) => void;
}

const ACTIVE_RUN_KEY = "cc_active_run_id";

function persistActiveRun(runId: string | null) {
  if (typeof window === "undefined") return;
  if (runId) localStorage.setItem(ACTIVE_RUN_KEY, runId);
  else localStorage.removeItem(ACTIVE_RUN_KEY);
}

const getInitialActiveRun = () => {
  if (typeof window !== "undefined") {
    return localStorage.getItem(ACTIVE_RUN_KEY);
  }
  return null;
};

export const useAgentStore = create<AgentStore>((set) => ({
  runs: {},
  activeRunId: getInitialActiveRun(),

  setActiveRun: (runId) => {
    persistActiveRun(runId);
    set({ activeRunId: runId });
  },

  initRun: (runId) => {
    persistActiveRun(runId);
    set((s) => ({
      activeRunId: runId,
      runs: {
        ...s.runs,
        [runId]: {
          runId,
          status: "running",
          events: [],
          pendingAction: null,
          result: null,
          error: null,
        },
      },
    }));
  },

  addEvent: (runId, eventType, data) =>
    set((s) => {
      const run = s.runs[runId] ?? {
        runId,
        status: "running",
        events: [],
        pendingAction: null,
        result: null,
        error: null,
      };
      if (eventType === "browser_frame") {
        return {
          runs: { ...s.runs, [runId]: { ...run, lastFrame: data as BrowserFrame } },
        };
      }
      return {
        runs: {
          ...s.runs,
          [runId]: {
            ...run,
            events: [...run.events.slice(-499), { type: eventType, data, ts: Date.now() }],
          },
        },
      };
    }),

  setCheckpoint: (runId, pendingAction) =>
    set((s) => ({
      runs: {
        ...s.runs,
        [runId]: {
          ...s.runs[runId],
          status: "awaiting_approval",
          pendingAction: pendingAction || null,
        },
      },
    })),

  clearCheckpoint: (runId) =>
    set((s) => ({
      runs: {
        ...s.runs,
        [runId]: {
          ...s.runs[runId],
          status: "running",
          pendingAction: null,
        },
      },
    })),

  setComplete: (runId, result) => {
    persistActiveRun(null);
    set((s) => ({
      runs: {
        ...s.runs,
        [runId]: {
          ...s.runs[runId],
          status: "completed",
          result,
        },
      },
    }));
  },

  setError: (runId, message) => {
    persistActiveRun(null);
    set((s) => ({
      runs: {
        ...s.runs,
        [runId]: {
          ...s.runs[runId],
          status: "failed",
          error: message,
        },
      },
    }));
  },

  setRunStatus: (runId, status) =>
    set((s) => ({
      runs: { ...s.runs, [runId]: { ...s.runs[runId], status } },
    })),

  clearRun: (runId) =>
    set((s) => {
      const rest = { ...s.runs };
      delete rest[runId];
      return { runs: rest };
    }),
}));
