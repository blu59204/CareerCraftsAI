"""AG-UI endpoint for the Career Copilot chat graph.

Serves the chat orchestrator over the AG-UI protocol so the CopilotKit React
SDK can talk to it directly. Mounted at /api/v1/agents/chat — a non-public
path, so the app-level Clerk JWT middleware authenticates every request and
records the subject into request_context for the graph's tools.

The in-process MemorySaver keeps thread state per AG-UI thread id; restarts
drop chat history (thread ids live in the browser's localStorage), which is
acceptable for v1 — durable chat threads are a planned follow-up.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

logger = logging.getLogger(__name__)

COPILOT_CHAT_PATH = "/api/v1/agents/chat"
COPILOT_AGENT_NAME = "career-copilot"


def mount_copilot_chat(app: FastAPI) -> None:
    """Wire the chat graph as an AG-UI FastAPI endpoint."""
    try:
        from ag_ui_langgraph import LangGraphAgent, add_langgraph_fastapi_endpoint
    except ImportError:  # pragma: no cover - depends on optional dependency
        logger.warning("ag-ui-langgraph not installed — /agents/chat disabled")
        return

    from app.agents.chat_orchestrator import chat_graph

    # Raw events are dropped: they duplicate every other event on the wire and
    # can carry large state dumps. The structured AG-UI events are enough.
    agent = LangGraphAgent(
        name=COPILOT_AGENT_NAME,
        graph=chat_graph,
        emit_raw_events=False,
    )
    add_langgraph_fastapi_endpoint(app, agent, COPILOT_CHAT_PATH)
    logger.info("Copilot chat endpoint mounted at %s", COPILOT_CHAT_PATH)
