import logging

from langgraph.graph import END, StateGraph

from app.agents.email_agent import email_agent_node
from app.agents.interview_prep_agent import interview_prep_agent_node
from app.agents.job_search import job_search_agent_node
from app.agents.linkedin_agent import linkedin_agent_node
from app.agents.resume_agent import resume_agent_node
from app.agents.cover_letter_agent import cover_letter_node
from app.agents.interview_coach_agent import start_session_node
from app.agents.salary_agent import salary_report_node
from app.agents.company_research_agent import company_research_node as _async_company_research_node
from app.agents.nl_search_agent import nl_search_node
from app.agents.state import AgentState
from app.core.event_bus import emit

logger = logging.getLogger(__name__)


def company_research_node(state: AgentState) -> AgentState:
    """Sync wrapper for the async company_research_node."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(1) as pool:
                return pool.submit(asyncio.run, _async_company_research_node(state)).result()
        return loop.run_until_complete(_async_company_research_node(state))
    except RuntimeError:
        return asyncio.run(_async_company_research_node(state))

_TASK_ROUTES: dict[str, str] = {
    "resume_optimize": "resume",
    "job_search": "job_search",
    "linkedin_optimize": "linkedin",
    "email": "email",
    "interview_prep": "interview_prep",
    "cover_letter": "cover_letter",
    "interview_coach": "interview_coach",
    "evaluate_answer": "interview_coach",
    "salary_intelligence": "salary",
    "company_research": "company_research",
    "nl_job_search": "nl_search",
    "linkedin_outreach": "linkedin",
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
    graph.add_node("interview_prep", _wrap_with_events(interview_prep_agent_node, "InterviewPrepAgent"))
    graph.add_node("cover_letter", _wrap_with_events(cover_letter_node, "CoverLetterAgent"))
    graph.add_node("interview_coach", _wrap_with_events(start_session_node, "InterviewCoachAgent"))
    graph.add_node("salary", _wrap_with_events(salary_report_node, "SalaryAgent"))
    graph.add_node("company_research", _wrap_with_events(company_research_node, "CompanyResearchAgent"))
    graph.add_node("nl_search", _wrap_with_events(nl_search_node, "NLSearchAgent"))
    graph.set_conditional_entry_point(
        route_task,
        {
            "resume": "resume",
            "job_search": "job_search",
            "linkedin": "linkedin",
            "email": "email",
            "interview_prep": "interview_prep",
            "cover_letter": "cover_letter",
            "interview_coach": "interview_coach",
            "salary": "salary",
            "company_research": "company_research",
            "nl_search": "nl_search",
            "__end__": END,
        },
    )
    for node in ("resume", "job_search", "linkedin", "email", "interview_prep",
                 "cover_letter", "interview_coach", "salary", "company_research", "nl_search"):
        graph.add_edge(node, END)
    return graph.compile()


orchestrator = build_graph()
