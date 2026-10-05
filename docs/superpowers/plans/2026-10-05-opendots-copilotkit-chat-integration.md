# OpenDots-Style Career Copilot (CopilotKit / AG-UI Integration)

Date: 2026-10-05
Branch: `sprint/applications-autoapply`

## Goal

Bring the OpenDots pattern — a persistent conversational agent that orchestrates
job search, applications, and every other CareerCraft agent through one chat
interface — into CareerCraft AI.

OpenDots itself (github.com/CopilotKit/OpenDots) is a Node.js/Hono/Vite template
and cannot be embedded as a library in our Python backend. What we integrate is
its architecture, over the same open protocol it is built on (AG-UI, served by
CopilotKit):

- A chat agent ("Career Copilot") that users talk to in natural language.
- The copilot's tools start and monitor the existing LangGraph agent runs
  (job search, auto-apply, resume tailoring, cover letters, interview prep,
  company research, salary intelligence, email outreach).
- Human-in-the-loop stays exactly where it is today: approvals only via
  `POST /agents/{run_id}/approve`, clicked by the user. The copilot can surface
  pending approvals as cards but never approves anything itself.
- All heavy work still runs through Temporal workflows with the existing
  concurrency caps, `agent_runs` logging, and per-user BYOK model routing.

## Why this design

- Reuses 100% of the proven execution machinery (Temporal HITL, SSE, Redis
  event bus, approval validation, extension-based form submission).
- No new HITL path is created, so the mandatory approval gates cannot be
  bypassed by the chat agent.
- The chat layer is orchestration + monitoring only, which keeps the security
  surface small.

## Components

### Backend

1. **LLM gateway tool-calling support** (`app/core/llm_gateway.py`)
   - New opt-in flag on gateway sessions: `allow_tools` (stored in the Redis
     session record, default false — existing agent behavior unchanged).
   - When `allow_tools` is true the proxy accepts an OpenAI `tools` array
     (validated: bounded count/size, JSON-schema parameters) and `tool` role
     messages, binds them via `llm.bind_tools(...)`, and serializes
     `tool_calls` back into the OpenAI-shaped response. Redaction callbacks
     stay attached. Streaming stays disabled.
   - New helper `get_chat_gateway_llm(user_id, db)` that creates an
     `allow_tools` session and returns the key-free ChatOpenAI client.

2. **Chat orchestrator graph** (`app/agents/chat_orchestrator.py`)
   - Hand-rolled LangGraph message loop (agent node → tool node → repeat) so
     the model is resolved per-request through the gateway.
   - Tools: `start_agent_run` (whitelisted task types only), `get_run_status`,
     `list_recent_runs`, `list_applications`, `search_jobs_now`.
   - The model never sees real API keys (gateway session token only).
   - Each chat turn is logged as an `agent_runs` row (`agent_type="chat"`).

3. **Request context** (`app/core/request_context.py`)
   - `current_user_id` ContextVar set by the JWT middleware; the chat graph
     reads it to scope every tool call to the authenticated user.

4. **AG-UI endpoint** (`app/api/v1/copilot_chat.py` + `main.py`)
   - `add_langgraph_fastapi_endpoint(app, chat_graph, "/api/v1/agents/chat")`
     from `ag-ui-langgraph[fastapi]`.
   - Path is not public, so Clerk JWT middleware guards it.
   - In-process MemorySaver checkpointer keyed by AG-UI `thread_id` (v1;
     Postgres checkpointer is a follow-up).

5. **Dependencies**: add `ag-ui-langgraph[fastapi]` (≥0.0.46) following the
   requirements.txt / constraints.txt / requirements.lock pattern.

### Frontend

1. **Copilot page** (`frontend/src/app/(app)/copilot/page.tsx`)
   - `CopilotKitProvider` from `@copilotkit/react-core` (root import) with
     `runtimeUrl = ${API_BASE_URL}/api/v1/agents/chat` and async `headers`
     that return a fresh Clerk bearer token per request.
   - v2 hooks (`@copilotkit/react-core/v2`): `useAgent` for the
     `career-copilot` agent, thread id persisted in localStorage.
   - Custom chat transcript matching the vanguard design system, tool-call
     cards, and suggestion chips ("Find me jobs", "Tailor my resume",
     "Auto-apply this week").
   - Approval cards rendered from `get_run_status` tool results; Approve /
     Reject buttons call the existing approve endpoint from the browser.

2. **Navigation**: Copilot entry in the AppShell sidebar.

## Constraints honored

- No model names hardcoded; everything resolves through the gateway/router.
- API keys never leave the encrypted store except inside the gateway.
- HITL gates untouched: chat can pause runs for approval but never approve.
- Every agent action logged to `agent_runs`.

## Verification

- Backend: pytest for gateway tools passthrough and chat graph tools
  (user isolation, whitelist enforcement, no approve capability).
- Frontend: typecheck + production build.
- Manual: dev servers up, chat turn starts a job_search run, approval card
  appears when the run awaits approval, approve releases the run.

## Out of scope (follow-ups)

- Streaming token-by-token through the gateway.
- Postgres-backed chat thread persistence.
- Voice, Slack channels, agent "computers" (OpenDots extras) — the browser
  extension already fills the computer role for form submission.
