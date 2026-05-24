import logging

from langgraph.graph import END, StateGraph

from app.agents.email_agent import email_agent_node
from app.agents.job_search import job_search_agent_node
from app.agents.linkedin_agent import linkedin_agent_node
from app.agents.resume_agent import resume_agent_node
from app.agents.state import AgentState
from app.core.event_bus import emit

logger = logging.getLogger(__name__)

_TASK_ROUTES: dict[str, str] = {
    "resume_optimize": "resume",
    "job_search": "job_search",
    "linkedin_optimize": "linkedin",
    "email": "email",
}

_TERMINAL_STATUSES = {"completed", "failed", "awaiting_approval"}


def route_task(state: AgentState) -> str:
    if state["status"] in _TERMINAL_STATUSES:
        return "__end__"
    return _TASK_ROUTES.get(state["task_type"], "__end__")


def _wrap_with_events(agent_fn, agent_name: str):
    def _wrapped(state: AgentState) -> AgentState:
        emit(state["run_id"], "log", f"[{agent_name}] starting...")
        result = agent_fn(state)
        if result["status"] == "awaiting_approval":
            emit(state["run_id"], "checkpoint", result.get("pending_action") or {})
        elif result["status"] == "failed":
            emit(state["run_id"], "error", result.get("error", "Unknown error"))
        elif result["status"] == "completed":
            emit(state["run_id"], "complete", result.get("result") or {})
        return result

    return _wrapped


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("resume", _wrap_with_events(resume_agent_node, "ResumeAgent"))
    graph.add_node("job_search", _wrap_with_events(job_search_agent_node, "JobSearchAgent"))
    graph.add_node("linkedin", _wrap_with_events(linkedin_agent_node, "LinkedInAgent"))
    graph.add_node("email", _wrap_with_events(email_agent_node, "EmailAgent"))
    graph.set_conditional_entry_point(
        route_task,
        {
            "resume": "resume",
            "job_search": "job_search",
            "linkedin": "linkedin",
            "email": "email",
            "__end__": END,
        },
    )
    for node in ("resume", "job_search", "linkedin", "email"):
        graph.add_edge(node, END)
    return graph.compile()


orchestrator = build_graph()
