"""AG-UI endpoint for the Career Copilot chat graph.

Serves the chat orchestrator over the AG-UI protocol so the CopilotKit React
SDK can talk to it directly. Mounted at /api/v1/agents/chat — a non-public
path, so the app-level Clerk JWT middleware authenticates every request and
records the subject into request_context for the graph's tools.

The database stores owner-scoped messages and restores them into the graph
after restarts; thread ids live in the browser localStorage.
"""

from __future__ import annotations

import hashlib
import logging
from app.services import copilot_history as history

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.request_context import current_user_id

logger = logging.getLogger(__name__)

COPILOT_CHAT_PATH = "/api/v1/agents/chat"
COPILOT_AGENT_NAME = "career-copilot"


def scoped_thread_id(user_id: str, thread_id: str) -> str:
    """Checkpoint keys belong to an authenticated user, never a bare client id."""
    return hashlib.sha256(f"{len(user_id)}:{user_id}{thread_id}".encode()).hexdigest()


def mount_copilot_chat(app: FastAPI) -> None:
    """Wire the chat graph as an AG-UI FastAPI endpoint."""
    try:
        from ag_ui.core import RunAgentInput
        from ag_ui.encoder import EventEncoder
        from ag_ui_langgraph import LangGraphAgent
    except ImportError:  # pragma: no cover - depends on optional dependency
        logger.warning("ag-ui-langgraph not installed — /agents/chat disabled")
        return

    from app.agents.chat_orchestrator import chat_graph

    # Define the route here so identity and checkpoint ownership are enforced
    # before the adapter reads any history. Keep the public thread id on wire.
    async def chat_endpoint(input_data: RunAgentInput, request: Request):
        user_id = current_user_id.get()
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")
        if not input_data.thread_id or len(input_data.thread_id) > 200:
            raise HTTPException(status_code=422, detail="Invalid thread id")
        if not input_data.run_id or len(input_data.run_id) > 200:
            raise HTTPException(status_code=422, detail="Invalid run id")
        db_user_id, messages = await history.start_turn(user_id, input_data.thread_id, input_data.run_id,
            [m.model_dump(mode="json", by_alias=True, exclude_none=True) for m in input_data.messages])
        from pydantic import TypeAdapter
        from ag_ui.core import Message
        scoped_input = input_data.model_copy(
            update={
                "thread_id": scoped_thread_id(user_id, input_data.thread_id),
                # Chat has no client tools or graph-control surface. In particular,
                # commands must never jump straight to a graph's tools node.
                "messages": TypeAdapter(list[Message]).validate_python(messages),
                "state": {},
                "tools": [],
                "forwarded_props": {},
            }
        )
        encoder = EventEncoder(accept=request.headers.get("accept"))
        request_agent = LangGraphAgent(
            name=COPILOT_AGENT_NAME,
            graph=chat_graph,
            emit_raw_events=False,
            config={"recursion_limit": 20},
        )

        async def events():
            snapshot = None
            saved = False
            try:
                async for event in request_agent.run(scoped_input):
                    if event.type == "MESSAGES_SNAPSHOT":
                        snapshot = [m.model_dump(mode="json", by_alias=True, exclude_none=True) for m in event.messages]
                    if event.type in {"RUN_FINISHED", "RUN_ERROR"}:
                        await history.finish_turn(db_user_id, input_data.thread_id, input_data.run_id, snapshot)
                        saved = True
                    if hasattr(event, "thread_id"):
                        event = event.model_copy(update={"thread_id": input_data.thread_id})
                    yield encoder.encode(event)
            finally:
                if not saved:
                    await history.finish_turn(db_user_id, input_data.thread_id, input_data.run_id, snapshot)

        return StreamingResponse(events(), media_type=encoder.get_content_type())

    # RunAgentInput is an optional dependency imported above; resolve the local
    # annotation explicitly for FastAPI (this module uses future annotations).
    chat_endpoint.__annotations__["input_data"] = RunAgentInput
    app.post(COPILOT_CHAT_PATH)(chat_endpoint)

    @app.get(f"{COPILOT_CHAT_PATH}/threads")
    async def threads():
        user_id = current_user_id.get()
        if not user_id:
            raise HTTPException(401, "Authentication required")
        return await history.list_threads(user_id)

    @app.get(f"{COPILOT_CHAT_PATH}/threads/{{thread_id}}")
    async def thread(thread_id: str):
        user_id = current_user_id.get()
        if not user_id:
            raise HTTPException(401, "Authentication required")
        return await history.get_thread(user_id, thread_id)

    @app.get(f"{COPILOT_CHAT_PATH}/health")
    def health():
        return {"status": "ok", "agent": {"name": COPILOT_AGENT_NAME}}

    logger.info("Copilot chat endpoint mounted at %s", COPILOT_CHAT_PATH)
