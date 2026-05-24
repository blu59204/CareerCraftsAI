import { create } from "zustand";

interface AgentEvent {
  type: string;
  data: unknown;
  ts: number;
}

interface AgentRun {
  runId: string;
  status: "running" | "awaiting_approval" | "completed" | "failed";
  events: AgentEvent[];
  pendingAction: Record<string, unknown> | null;
}

interface AgentStore {
  runs: Record<string, AgentRun>;
  initRun: (runId: string) => void;
  addEvent: (runId: string, event: AgentEvent) => void;
  setRunStatus: (runId: string, status: AgentRun["status"]) => void;
  clearRun: (runId: string) => void;
}

export const useAgentStore = create<AgentStore>((set) => ({
  runs: {},
  initRun: (runId) =>
    set((s) => ({
      runs: {
        ...s.runs,
        [runId]: { runId, status: "running", events: [], pendingAction: null },
      },
    })),
  addEvent: (runId, event) =>
    set((s) => {
      const run = s.runs[runId] ?? {
        runId,
        status: "running" as const,
        events: [],
        pendingAction: null,
      };
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
    set((s) => ({
      runs: { ...s.runs, [runId]: { ...s.runs[runId], status } },
    })),
  clearRun: (runId) =>
    set((s) => {
      const { [runId]: _removed, ...rest } = s.runs;
      return { runs: rest };
    }),
}));
