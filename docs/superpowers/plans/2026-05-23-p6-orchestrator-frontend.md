# P6: Orchestrator + SSE Streaming + Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire LangGraph supervisor orchestrator, SSE real-time streaming, human-in-loop approval flow, and full Next.js frontend (Dashboard, Resume, Jobs kanban, LinkedIn, Email pages).

**Architecture:** LangGraph `StateGraph` supervisor routes between all agents. FastAPI SSE endpoint streams agent events via asyncio.Queue. Frontend `useAgentStream` hook wraps `EventSource`. `ApprovalModal` pauses on `checkpoint` events and calls `/approve`. All pages use TanStack Query for server state, Zustand for UI state.

**Tech Stack:** LangGraph 0.2+ StateGraph, FastAPI StreamingResponse, asyncio.Queue, Next.js 14 App Router, shadcn/ui, Zustand, TanStack Query v5

---

## File Map

**Backend:**
| File | Responsibility |
|---|---|
| `backend/app/agents/orchestrator.py` | LangGraph StateGraph supervisor |
| `backend/app/api/v1/agents.py` | Run, stream (SSE), approve, cancel endpoints |
| `backend/app/core/event_bus.py` | asyncio.Queue registry per run_id |
| `backend/tests/unit/test_orchestrator.py` | Unit tests — routing logic |

**Frontend:**
| File | Responsibility |
|---|---|
| `frontend/src/lib/sse.ts` | `useAgentStream(runId)` hook |
| `frontend/src/store/agentSlice.ts` | Zustand: active runs, events |
| `frontend/src/store/userSlice.ts` | Zustand: user profile, model settings |
| `frontend/src/components/agents/AgentStatusStream.tsx` | Live SSE log renderer |
| `frontend/src/components/agents/ApprovalModal.tsx` | Human-in-loop gate UI |
| `frontend/src/app/dashboard/page.tsx` | Stats + pipeline overview |
| `frontend/src/app/resume/optimize/page.tsx` | Resume optimizer page |
| `frontend/src/app/jobs/search/page.tsx` | Job search + results |
| `frontend/src/app/applications/page.tsx` | Kanban board |
| `frontend/src/app/linkedin/optimize/page.tsx` | LinkedIn optimizer |
| `frontend/src/app/settings/models/page.tsx` | Model API key settings |

---

## Task 1: Event Bus (asyncio.Queue registry)

**Files:**
- Create: `backend/app/core/event_bus.py`

- [ ] **Step 1: Implement event_bus.py**

```python
# backend/app/core/event_bus.py
import asyncio
import json
import time
from typing import AsyncIterator

_queues: dict[str, asyncio.Queue] = {}


def get_queue(run_id: str) -> asyncio.Queue:
    if run_id not in _queues:
        _queues[run_id] = asyncio.Queue(maxsize=100)
    return _queues[run_id]


def remove_queue(run_id: str) -> None:
    _queues.pop(run_id, None)


def emit(run_id: str, event_type: str, data: str | dict) -> None:
    """Emit event from sync context (agent thread)."""
    q = _queues.get(run_id)
    if q is None:
        return
    try:
        payload = data if isinstance(data, str) else json.dumps(data)
        q.put_nowait({"type": event_type, "data": payload, "ts": int(time.time())})
    except asyncio.QueueFull:
        pass  # drop event if consumer is slow


async def stream_events(run_id: str) -> AsyncIterator[str]:
    """Async generator for SSE — yields formatted event strings."""
    q = get_queue(run_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=30.0)
                yield f"data: {json.dumps(event)}\n\n"
                if event["type"] in ("complete", "error"):
                    break
            except asyncio.TimeoutError:
                yield "data: {\"type\":\"ping\"}\n\n"  # keep-alive
    finally:
        remove_queue(run_id)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/core/event_bus.py
git commit -m "feat(core): asyncio event bus — per-run SSE queue with emit, stream, keep-alive ping"
```

---

## Task 2: Orchestrator (LangGraph Supervisor)

**Files:**
- Create: `backend/app/agents/orchestrator.py`
- Create: `backend/tests/unit/test_orchestrator.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_orchestrator.py
import uuid
import pytest
from unittest.mock import MagicMock, patch
from app.agents.state import AgentState


def make_state(task_type: str) -> AgentState:
    return AgentState(
        user_id="usr_test",
        run_id=str(uuid.uuid4()),
        task_type=task_type,
        messages=[],
        context={},
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )


def test_orchestrator_routes_resume_task():
    from app.agents.orchestrator import route_task
    state = make_state("resume_optimize")
    assert route_task(state) == "resume"


def test_orchestrator_routes_job_search_task():
    from app.agents.orchestrator import route_task
    state = make_state("job_search")
    assert route_task(state) == "job_search"


def test_orchestrator_routes_linkedin_task():
    from app.agents.orchestrator import route_task
    state = make_state("linkedin_optimize")
    assert route_task(state) == "linkedin"


def test_orchestrator_routes_email_task():
    from app.agents.orchestrator import route_task
    state = make_state("email")
    assert route_task(state) == "email"


def test_orchestrator_routes_unknown_to_end():
    from app.agents.orchestrator import route_task
    state = make_state("unknown_task")
    assert route_task(state) == "__end__"


def test_orchestrator_routes_completed_to_end():
    from app.agents.orchestrator import route_task
    state = make_state("resume_optimize")
    state["status"] = "completed"
    assert route_task(state) == "__end__"
```

- [ ] **Step 2: Run — verify fails**

```bash
pytest tests/unit/test_orchestrator.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement orchestrator.py**

```python
# backend/app/agents/orchestrator.py
from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.resume_agent import resume_agent_node
from app.agents.linkedin_agent import linkedin_agent_node
from app.agents.job_search import job_search_agent_node
from app.agents.email_agent import email_agent_node
from app.core.event_bus import emit

TASK_ROUTES = {
    "resume_optimize": "resume",
    "job_search": "job_search",
    "linkedin_optimize": "linkedin",
    "email": "email",
}


def route_task(state: AgentState) -> str:
    if state["status"] in ("completed", "failed", "awaiting_approval"):
        return "__end__"
    return TASK_ROUTES.get(state["task_type"], "__end__")


def _wrap_with_events(agent_fn, agent_name: str):
    def _wrapped(state: AgentState) -> AgentState:
        emit(state["run_id"], "log", f"[{agent_name}] starting...")
        result = agent_fn(state)
        if result["status"] == "awaiting_approval":
            emit(state["run_id"], "checkpoint", result.get("pending_action", {}))
        elif result["status"] == "failed":
            emit(state["run_id"], "error", result.get("error", "Unknown error"))
        elif result["status"] == "completed":
            emit(state["run_id"], "complete", result.get("result", {}))
        return result
    return _wrapped


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("resume", _wrap_with_events(resume_agent_node, "ResumeAgent"))
    graph.add_node("job_search", _wrap_with_events(job_search_agent_node, "JobSearchAgent"))
    graph.add_node("linkedin", _wrap_with_events(linkedin_agent_node, "LinkedInAgent"))
    graph.add_node("email", _wrap_with_events(email_agent_node, "EmailAgent"))

    graph.set_conditional_entry_point(route_task, {
        "resume": "resume",
        "job_search": "job_search",
        "linkedin": "linkedin",
        "email": "email",
        "__end__": END,
    })

    for node in ("resume", "job_search", "linkedin", "email"):
        graph.add_edge(node, END)

    return graph.compile()


orchestrator = build_graph()
```

- [ ] **Step 4: Run tests — verify pass**

```bash
pytest tests/unit/test_orchestrator.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/orchestrator.py backend/tests/unit/test_orchestrator.py
git commit -m "feat(agents): LangGraph supervisor orchestrator — conditional routing, SSE event emission wrappers"
```

---

## Task 3: Agents API (Run + SSE Stream + Approve)

**Files:**
- Create: `backend/app/api/v1/agents.py`

- [ ] **Step 1: Implement agents.py**

```python
# backend/app/api/v1/agents.py
import asyncio
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.api.v1.deps import get_current_user, get_db
from app.models.db import User, AgentRun
from app.agents.orchestrator import orchestrator
from app.agents.state import AgentState
from app.core.event_bus import get_queue, stream_events, emit
from langchain_core.messages import HumanMessage

router = APIRouter(prefix="/agents", tags=["agents"])


class RunRequest(BaseModel):
    task_type: str
    context: dict = {}


class RunResponse(BaseModel):
    run_id: str
    status: str


@router.post("/run", response_model=RunResponse)
async def start_agent_run(
    payload: RunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    valid_tasks = {"resume_optimize", "job_search", "linkedin_optimize", "email"}
    if payload.task_type not in valid_tasks:
        raise HTTPException(status_code=400, detail=f"task_type must be one of: {valid_tasks}")

    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type=payload.task_type,
        status="running",
        input={"task_type": payload.task_type, "context_keys": list(payload.context.keys())},
    )
    db.add(agent_run)
    await db.flush()

    get_queue(run_id)  # initialize queue before background task

    state = AgentState(
        user_id=str(current_user.id),
        run_id=run_id,
        task_type=payload.task_type,
        messages=[HumanMessage(content=str(payload.context))],
        context=payload.context,
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )

    async def _run_agent():
        try:
            loop = asyncio.get_event_loop()
            result_state = await loop.run_in_executor(None, orchestrator.invoke, state)
            from app.core.database import AsyncSessionLocal
            async with AsyncSessionLocal() as fresh_db:
                res = await fresh_db.execute(select(AgentRun).where(AgentRun.id == uuid.UUID(run_id)))
                run = res.scalar_one_or_none()
                if run:
                    run.status = result_state["status"]
                    run.output = result_state.get("result") or result_state.get("pending_action")
                    run.completed_at = datetime.now(timezone.utc)
                await fresh_db.commit()
        except Exception as exc:
            emit(run_id, "error", str(exc))

    asyncio.create_task(_run_agent())
    return RunResponse(run_id=run_id, status="running")


@router.get("/{run_id}/stream")
async def stream_agent(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentRun).where(AgentRun.id == uuid.UUID(run_id), AgentRun.user_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Run not found")

    return StreamingResponse(
        stream_events(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


class ApproveRequest(BaseModel):
    approved: bool


@router.post("/{run_id}/approve", response_model=dict)
async def approve_or_cancel(
    run_id: str,
    payload: ApproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AgentRun).where(AgentRun.id == uuid.UUID(run_id), AgentRun.user_id == current_user.id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != "awaiting_approval":
        raise HTTPException(status_code=400, detail=f"Run is {run.status}, not awaiting_approval")

    if not payload.approved:
        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        emit(run_id, "complete", {"cancelled": True})
        return {"status": "cancelled"}

    # Dispatch approved action to the appropriate service
    pending = run.output or {}
    action_type = pending.get("type", "")
    user_id = str(current_user.id)

    if action_type == "send_email":
        from app.services.gmail_service import GmailMCPClient
        gmail = GmailMCPClient(user_id)
        gmail.send_message(pending["recipient"], pending["subject"], pending["body"])
        run.status = "completed"
    elif action_type in ("resume_ready", "linkedin_edits"):
        run.status = "completed"
    else:
        run.status = "completed"

    run.completed_at = datetime.now(timezone.utc)
    emit(run_id, "complete", {"approved": True, "action": action_type})
    return {"status": "completed", "action": action_type}
```

- [ ] **Step 2: Register in main.py**

```python
# backend/app/main.py
from app.api.v1 import users, rag, resume, jobs, email, agents
app.include_router(agents.router, prefix="/api/v1")
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/v1/agents.py backend/app/main.py
git commit -m "feat(api): agent run, SSE stream, and approve/cancel endpoints with asyncio background task"
```

---

## Task 4: Frontend — SSE Hook + Zustand Store

**Files:**
- Create: `frontend/src/lib/sse.ts`
- Create: `frontend/src/store/agentSlice.ts`
- Create: `frontend/src/store/userSlice.ts`

- [ ] **Step 1: Create sse.ts hook**

```typescript
// frontend/src/lib/sse.ts
"use client";
import { useEffect, useRef } from "react";
import { useAgentStore } from "@/store/agentSlice";

export function useAgentStream(runId: string | null) {
  const { addEvent, setRunStatus } = useAgentStore();
  const sourceRef = useRef<EventSource | null>(null);
  const retryRef = useRef(0);

  useEffect(() => {
    if (!runId) return;

    function connect() {
      const src = new EventSource(`/api/agents/${runId}/stream`);
      sourceRef.current = src;

      src.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data);
          addEvent(runId, event);
          if (event.type === "complete" || event.type === "error") {
            setRunStatus(runId, event.type === "complete" ? "completed" : "failed");
            src.close();
          }
        } catch {
          // malformed event — ignore
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
    return () => {
      sourceRef.current?.close();
    };
  }, [runId, addEvent, setRunStatus]);
}
```

- [ ] **Step 2: Create agentSlice.ts**

```typescript
// frontend/src/store/agentSlice.ts
import { create } from "zustand";

interface AgentEvent {
  type: string;
  data: string | object;
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
  addEvent: (runId: string, event: AgentEvent) => void;
  setRunStatus: (runId: string, status: AgentRun["status"]) => void;
  initRun: (runId: string) => void;
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
      const run = s.runs[runId] ?? { runId, status: "running", events: [], pendingAction: null };
      const updates: Partial<AgentRun> = { events: [...run.events, event] };
      if (event.type === "checkpoint") {
        updates.status = "awaiting_approval";
        updates.pendingAction = typeof event.data === "string" ? JSON.parse(event.data) : event.data;
      }
      return { runs: { ...s.runs, [runId]: { ...run, ...updates } } };
    }),
  setRunStatus: (runId, status) =>
    set((s) => ({
      runs: { ...s.runs, [runId]: { ...s.runs[runId], status } },
    })),
  clearRun: (runId) =>
    set((s) => {
      const { [runId]: _, ...rest } = s.runs;
      return { runs: rest };
    }),
}));
```

- [ ] **Step 3: Create userSlice.ts**

```typescript
// frontend/src/store/userSlice.ts
import { create } from "zustand";

interface ModelSettings {
  id: string;
  provider: string;
  modelName: string | null;
  isActive: boolean;
}

interface UserStore {
  models: ModelSettings[];
  setModels: (models: ModelSettings[]) => void;
}

export const useUserStore = create<UserStore>((set) => ({
  models: [],
  setModels: (models) => set({ models }),
}));
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/sse.ts frontend/src/store/
git commit -m "feat(frontend): useAgentStream SSE hook with auto-reconnect, Zustand agent + user stores"
```

---

## Task 5: Frontend — Agent Components

**Files:**
- Create: `frontend/src/components/agents/AgentStatusStream.tsx`
- Create: `frontend/src/components/agents/ApprovalModal.tsx`

- [ ] **Step 1: Create AgentStatusStream.tsx**

```tsx
// frontend/src/components/agents/AgentStatusStream.tsx
"use client";
import { useAgentStore } from "@/store/agentSlice";
import { useAgentStream } from "@/lib/sse";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ApprovalModal } from "./ApprovalModal";

interface Props {
  runId: string;
  onApprove?: (runId: string) => void;
  onCancel?: (runId: string) => void;
}

const STATUS_COLOR: Record<string, string> = {
  running: "bg-blue-500",
  awaiting_approval: "bg-yellow-500",
  completed: "bg-green-500",
  failed: "bg-red-500",
};

export function AgentStatusStream({ runId, onApprove, onCancel }: Props) {
  useAgentStream(runId);
  const run = useAgentStore((s) => s.runs[runId]);

  if (!run) return null;

  return (
    <div className="border rounded-lg p-4 space-y-3">
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${STATUS_COLOR[run.status] ?? "bg-gray-400"}`} />
        <Badge variant="outline">{run.status.replace("_", " ")}</Badge>
        <span className="text-xs text-slate-400 font-mono">{runId.slice(0, 8)}</span>
      </div>

      <ScrollArea className="h-48 font-mono text-xs bg-slate-950 text-slate-200 rounded p-3">
        {run.events.map((e, i) => (
          <div key={i} className="mb-1">
            <span className="text-slate-500">[{e.type}]</span>{" "}
            {typeof e.data === "string" ? e.data : JSON.stringify(e.data)}
          </div>
        ))}
        {run.status === "running" && (
          <div className="animate-pulse text-slate-400">▊</div>
        )}
      </ScrollArea>

      {run.status === "awaiting_approval" && run.pendingAction && (
        <ApprovalModal
          runId={runId}
          action={run.pendingAction}
          onApprove={() => onApprove?.(runId)}
          onCancel={() => onCancel?.(runId)}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create ApprovalModal.tsx**

```tsx
// frontend/src/components/agents/ApprovalModal.tsx
"use client";
import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";

interface Props {
  runId: string;
  action: Record<string, unknown>;
  onApprove: () => void;
  onCancel: () => void;
}

export function ApprovalModal({ runId, action, onApprove, onCancel }: Props) {
  const [loading, setLoading] = useState(false);

  const handleDecision = async (approved: boolean) => {
    setLoading(true);
    try {
      await apiClient.post(`/api/v1/agents/${runId}/approve`, { approved });
      if (approved) {
        toast.success("Action approved and executed");
        onApprove();
      } else {
        toast.info("Action cancelled");
        onCancel();
      }
    } catch {
      toast.error("Failed to process approval");
    } finally {
      setLoading(false);
    }
  };

  const actionType = action.type as string;

  return (
    <Dialog open>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            Review Required
            <Badge variant="secondary">{actionType?.replace(/_/g, " ")}</Badge>
          </DialogTitle>
          <DialogDescription>
            Review the agent's proposed action before it executes.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-2">
          {actionType === "send_email" && (
            <>
              <div><span className="font-medium text-sm">To:</span> <span className="text-slate-600">{action.recipient as string}</span></div>
              <div><span className="font-medium text-sm">Subject:</span> <span className="text-slate-600">{action.subject as string}</span></div>
              <div className="bg-slate-50 rounded p-3 text-sm whitespace-pre-wrap max-h-48 overflow-y-auto">{action.body as string}</div>
            </>
          )}
          {actionType === "resume_ready" && (
            <div className="bg-slate-50 rounded p-3 text-sm whitespace-pre-wrap max-h-64 overflow-y-auto">
              {action.resume_text as string}
            </div>
          )}
          {actionType === "linkedin_edits" && (
            <div className="space-y-2 text-sm">
              <div><span className="font-medium">Headline:</span> {action.headline as string}</div>
              <div><span className="font-medium">About:</span> <div className="text-slate-600 mt-1 whitespace-pre-wrap">{(action.about as string)?.slice(0, 200)}...</div></div>
            </div>
          )}
        </div>

        <div className="flex gap-2 pt-2">
          <Button onClick={() => handleDecision(true)} disabled={loading} className="flex-1">
            {loading ? "Processing..." : "Approve & Execute"}
          </Button>
          <Button variant="outline" onClick={() => handleDecision(false)} disabled={loading}>
            Cancel
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/agents/
git commit -m "feat(frontend): AgentStatusStream SSE renderer and ApprovalModal human-in-loop gate UI"
```

---

## Task 6: Frontend Pages

**Files:**
- Modify: `frontend/src/app/dashboard/page.tsx`
- Create: `frontend/src/app/resume/optimize/page.tsx`
- Create: `frontend/src/app/jobs/search/page.tsx`
- Create: `frontend/src/app/applications/page.tsx`
- Create: `frontend/src/app/settings/models/page.tsx`

- [ ] **Step 1: Dashboard page**

```tsx
// frontend/src/app/dashboard/page.tsx
import { currentUser } from "@clerk/nextjs/server";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

async function getStats() {
  // Server component — fetch directly from API using service key
  return { applied: 0, interviews: 0, offers: 0, pending: 0 };
}

export default async function DashboardPage() {
  const user = await currentUser();
  const stats = await getStats();

  return (
    <main className="p-8 space-y-6">
      <h1 className="text-2xl font-bold">Welcome back, {user?.firstName}</h1>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Applied", value: stats.applied },
          { label: "Interviews", value: stats.interviews },
          { label: "Offers", value: stats.offers },
          { label: "Pending", value: stats.pending },
        ].map(({ label, value }) => (
          <Card key={label}>
            <CardHeader className="pb-2"><CardTitle className="text-sm text-slate-500">{label}</CardTitle></CardHeader>
            <CardContent><span className="text-3xl font-bold">{value}</span></CardContent>
          </Card>
        ))}
      </div>
    </main>
  );
}
```

- [ ] **Step 2: Resume optimize page**

```tsx
// frontend/src/app/resume/optimize/page.tsx
"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { AgentStatusStream } from "@/components/agents/AgentStatusStream";
import { apiClient } from "@/lib/api";
import { useAgentStore } from "@/store/agentSlice";
import { toast } from "sonner";

export default function ResumOptimizePage() {
  const [jdText, setJdText] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const { initRun } = useAgentStore();

  const { mutate: optimize, isPending } = useMutation({
    mutationFn: () =>
      apiClient.post("/api/v1/agents/run", {
        task_type: "resume_optimize",
        context: { jd_text: jdText },
      }),
    onSuccess: (res) => {
      const id = res.data.run_id;
      initRun(id);
      setRunId(id);
    },
    onError: () => toast.error("Failed to start resume optimization"),
  });

  return (
    <main className="p-8 max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold">Optimize Resume</h1>
      <div className="space-y-2">
        <label className="text-sm font-medium">Paste Job Description</label>
        <Textarea
          value={jdText}
          onChange={(e) => setJdText(e.target.value)}
          placeholder="Paste the full job description here..."
          rows={10}
        />
      </div>
      <Button onClick={() => optimize()} disabled={isPending || !jdText.trim()}>
        {isPending ? "Starting..." : "Optimize with AI"}
      </Button>
      {runId && (
        <AgentStatusStream
          runId={runId}
          onApprove={() => toast.success("Resume ready — download from Versions")}
          onCancel={() => setRunId(null)}
        />
      )}
    </main>
  );
}
```

- [ ] **Step 3: Jobs search page**

```tsx
// frontend/src/app/jobs/search/page.tsx
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

  const { mutate: search, isPending } = useMutation({
    mutationFn: () =>
      apiClient.post("/api/v1/agents/run", {
        task_type: "job_search",
        context: { search_query: query, location, max_results: 10 },
      }),
    onSuccess: (res) => {
      const id = res.data.run_id;
      initRun(id);
      setRunId(id);
    },
    onError: () => toast.error("Failed to start job search"),
  });

  return (
    <main className="p-8 max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold">Job Search</h1>
      <div className="flex gap-3">
        <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Job title or keywords" className="flex-1" />
        <Input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Location" className="w-40" />
        <Button onClick={() => search()} disabled={isPending || !query.trim()}>
          {isPending ? "Searching..." : "Search"}
        </Button>
      </div>
      {runId && <AgentStatusStream runId={runId} onApprove={() => toast.success("Search complete")} onCancel={() => setRunId(null)} />}
    </main>
  );
}
```

- [ ] **Step 4: Applications kanban**

```tsx
// frontend/src/app/applications/page.tsx
"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";

const COLUMNS = ["saved", "applied", "viewed", "interview", "offer", "rejected"] as const;
type Status = typeof COLUMNS[number];

const COLUMN_LABELS: Record<Status, string> = {
  saved: "Saved", applied: "Applied", viewed: "Viewed",
  interview: "Interview", offer: "Offer", rejected: "Rejected",
};

interface Application {
  id: string; company: string; role: string;
  match_score: number | null; status: Status; applied_at: string | null;
}

export default function ApplicationsPage() {
  const qc = useQueryClient();
  const { data: apps = [] } = useQuery<Application[]>({
    queryKey: ["applications"],
    queryFn: () => apiClient.get("/api/v1/jobs/applications").then((r) => r.data),
  });

  const { mutate: updateStatus } = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      apiClient.patch(`/api/v1/jobs/applications/${id}/status`, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
    onError: () => toast.error("Failed to update status"),
  });

  return (
    <main className="p-8 space-y-4">
      <h1 className="text-2xl font-bold">Applications Pipeline</h1>
      <div className="flex gap-4 overflow-x-auto pb-4">
        {COLUMNS.map((col) => {
          const colApps = apps.filter((a) => a.status === col);
          return (
            <div key={col} className="min-w-[200px] space-y-2">
              <div className="flex items-center gap-2">
                <span className="font-medium text-sm">{COLUMN_LABELS[col]}</span>
                <Badge variant="secondary">{colApps.length}</Badge>
              </div>
              {colApps.map((app) => (
                <Card key={app.id} className="cursor-pointer hover:shadow-md transition-shadow">
                  <CardHeader className="pb-1 pt-3 px-3">
                    <CardTitle className="text-sm">{app.company}</CardTitle>
                  </CardHeader>
                  <CardContent className="px-3 pb-3 space-y-1">
                    <p className="text-xs text-slate-500">{app.role}</p>
                    {app.match_score != null && (
                      <Badge variant="outline" className="text-xs">{app.match_score}% match</Badge>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          );
        })}
      </div>
    </main>
  );
}
```

- [ ] **Step 5: Model settings page**

```tsx
// frontend/src/app/settings/models/page.tsx
"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";

const PROVIDERS = [
  { value: "anthropic", label: "Anthropic (Claude)", defaultModel: "claude-sonnet-4-6" },
  { value: "openai", label: "OpenAI (GPT)", defaultModel: "gpt-4o" },
  { value: "google", label: "Google (Gemini)", defaultModel: "gemini-2.0-flash" },
  { value: "ollama", label: "Ollama (Local)", defaultModel: "llama3.2" },
  { value: "nvidia_nim", label: "NVIDIA NIM", defaultModel: "meta/llama-3.1-70b-instruct" },
];

export default function ModelSettingsPage() {
  const qc = useQueryClient();
  const [provider, setProvider] = useState("anthropic");
  const [apiKey, setApiKey] = useState("");
  const [modelName, setModelName] = useState("claude-sonnet-4-6");
  const [ollamaUrl, setOllamaUrl] = useState("http://localhost:11434");

  const { data: models = [] } = useQuery({
    queryKey: ["models"],
    queryFn: () => apiClient.get("/api/v1/users/me/models").then((r) => r.data),
  });

  const { mutate: addModel, isPending } = useMutation({
    mutationFn: () =>
      apiClient.post("/api/v1/users/me/models", {
        provider, api_key: apiKey, model_name: modelName,
        ollama_url: provider === "ollama" ? ollamaUrl : null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["models"] });
      setApiKey("");
      toast.success("Model added successfully");
    },
    onError: () => toast.error("Failed to add model"),
  });

  return (
    <main className="p-8 max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold">AI Model Settings</h1>
      <Card>
        <CardHeader><CardTitle className="text-base">Add Model</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <Select value={provider} onValueChange={(v) => {
            setProvider(v);
            setModelName(PROVIDERS.find((p) => p.value === v)?.defaultModel ?? "");
          }}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {PROVIDERS.map((p) => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
            </SelectContent>
          </Select>
          <Input value={modelName} onChange={(e) => setModelName(e.target.value)} placeholder="Model name" />
          <Input
            value={apiKey} onChange={(e) => setApiKey(e.target.value)}
            placeholder={provider === "ollama" ? "No API key required" : "API Key"}
            type="password"
            disabled={provider === "ollama"}
          />
          {provider === "ollama" && (
            <Input value={ollamaUrl} onChange={(e) => setOllamaUrl(e.target.value)} placeholder="Ollama URL" />
          )}
          <Button onClick={() => addModel()} disabled={isPending || (!apiKey && provider !== "ollama")}>
            {isPending ? "Adding..." : "Add Model"}
          </Button>
        </CardContent>
      </Card>

      <div className="space-y-2">
        <h2 className="font-medium">Configured Models</h2>
        {(models as any[]).map((m: any) => (
          <div key={m.id} className="flex items-center justify-between border rounded p-3">
            <div>
              <span className="font-medium text-sm">{m.provider}</span>
              <span className="text-slate-500 text-sm ml-2">{m.model_name}</span>
            </div>
            {m.is_active && <Badge>Active</Badge>}
          </div>
        ))}
      </div>
    </main>
  );
}
```

- [ ] **Step 6: Build frontend and check for TS errors**

```bash
cd frontend && npm run build
```

Expected: Build succeeds, no TypeScript errors.

- [ ] **Step 7: Commit**

```bash
cd ..
git add frontend/src/app/ frontend/src/components/
git commit -m "feat(frontend): Dashboard, Resume optimize, Job search, Applications kanban, Model settings pages"
```

---

## Task 7: Full Integration Test Run

- [ ] **Step 1: Run all backend unit tests**

```bash
cd backend && source .venv/bin/activate
APP_SECRET_KEY="test-secret-key-32-chars-minimum!!" \
DATABASE_URL="postgresql+asyncpg://x:x@localhost/x" \
SUPABASE_URL="https://x.supabase.co" SUPABASE_SERVICE_KEY="x" \
CLERK_SECRET_KEY="sk_test_x" REDIS_URL="redis://localhost:6379" \
pytest tests/unit -v --tb=short
```

Expected: All tests pass.

- [ ] **Step 2: Final commit**

```bash
git commit -m "chore(p6): Phase 6 complete — Orchestrator + SSE + full frontend, all tests passing"
```

**P6 done. Proceed to P7 (Production Hardening).**
