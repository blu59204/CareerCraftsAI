"""
nl_search_agent.py — NL (Natural Language) Job Search Agent.

Parses plain-language job search queries into structured SearchParameters,
validates them, and returns a structured interpretation for user confirmation
before passing the query to the existing Job_Search_Agent via PinchTab.
"""

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.state import AgentState
from app.core.model_router import _build_llm
from app.core.sync_db import fetch_model_settings
from app.services.pinchtab_service import new_session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SearchParameters dataclass
# ---------------------------------------------------------------------------


@dataclass
class SearchParameters:
    """Structured representation of a natural language job search query."""

    role_title: str | None = None
    seniority: str | None = None
    location: str | None = None
    remote_preference: str | None = None
    industry: str | None = None
    salary_range: tuple[int, int] | None = None
    company_size: str | None = None
    tech_stack: list[str] = field(default_factory=list)
    additional_constraints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dictionary."""
        result = asdict(self)
        # tuple → list for JSON serialization
        if self.salary_range is not None:
            result["salary_range"] = list(self.salary_range)
        return result


# ---------------------------------------------------------------------------
# Parameter extraction via LLM
# ---------------------------------------------------------------------------

EXTRACT_PROMPT = """You are a job search query parser. Given a natural language job search query, extract structured parameters.

Return ONLY valid JSON with the following keys (use null for fields not mentioned):
{{
  "role_title": "string or null — the job title/role the user is searching for",
  "seniority": "string or null — e.g. junior, mid, senior, lead, principal, staff",
  "location": "string or null — city, state, country, or region",
  "remote_preference": "string or null — remote, hybrid, onsite, or null",
  "industry": "string or null — industry or company type",
  "salary_range": [min, max] or null — annual salary range as integers,
  "company_size": "string or null — startup, mid-size, enterprise, or null",
  "tech_stack": ["list of technologies mentioned"],
  "additional_constraints": ["any other preferences or constraints"]
}}

Query: {query}

JSON:"""


def _parse_llm_response(content: str) -> dict:
    """Parse LLM JSON response, handling markdown code fences."""
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()
    return json.loads(content)


def extract_parameters(llm: BaseChatModel, query: str) -> SearchParameters:
    """Use LLM to extract structured search parameters from a natural language query."""
    resp = llm.invoke([HumanMessage(content=EXTRACT_PROMPT.format(query=query))])
    parsed = _parse_llm_response(resp.content)

    salary_range = None
    if parsed.get("salary_range") and len(parsed["salary_range"]) == 2:
        try:
            salary_range = (int(parsed["salary_range"][0]), int(parsed["salary_range"][1]))
        except (ValueError, TypeError):
            salary_range = None

    return SearchParameters(
        role_title=parsed.get("role_title"),
        seniority=parsed.get("seniority"),
        location=parsed.get("location"),
        remote_preference=parsed.get("remote_preference"),
        industry=parsed.get("industry"),
        salary_range=salary_range,
        company_size=parsed.get("company_size"),
        tech_stack=parsed.get("tech_stack") or [],
        additional_constraints=parsed.get("additional_constraints") or [],
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_search_params(params: SearchParameters) -> bool:
    """
    Validate extracted search parameters.

    Returns True if the parameters are valid for executing a search.
    The minimum requirement is a non-empty role_title.
    """
    if not params.role_title or not params.role_title.strip():
        return False
    return True


# ---------------------------------------------------------------------------
# Build structured search query for Job_Search_Agent
# ---------------------------------------------------------------------------


def _build_search_query(params: SearchParameters) -> str:
    """Build a keyword search query string from structured parameters."""
    parts = []
    if params.role_title:
        parts.append(params.role_title)
    if params.seniority:
        parts.append(params.seniority)
    if params.tech_stack:
        parts.append(" ".join(params.tech_stack[:3]))
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Log run to agent_runs (sync, for use inside thread executor)
# ---------------------------------------------------------------------------


def _log_agent_run(
    user_id: str,
    run_id: str,
    query: str,
    params: SearchParameters,
    status: str,
    result_count: int | None = None,
    duration_ms: int | None = None,
) -> None:
    """Log this NL search run to the agent_runs table."""
    from app.core.sync_db import _get_sync_factory
    from app.models.db import AgentRun

    factory = _get_sync_factory()
    now = datetime.now(timezone.utc)
    with factory() as db:
        agent_run = AgentRun(
            id=uuid.UUID(run_id),
            user_id=user_id,
            agent_type="nl_job_search",
            status=status,
            input={"query": query, "extracted_parameters": params.to_dict()},
            output={"results_count": result_count} if result_count is not None else None,
            duration_ms=duration_ms,
            started_at=now,
            completed_at=now if status != "running" else None,
        )
        db.add(agent_run)
        db.commit()


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------


def nl_search_node(state: AgentState) -> AgentState:
    """
    LangGraph node: parse natural language job query into structured parameters.

    Flow:
    1. Extract parameters from NL query via LLM
    2. Validate (role_title required — reject with 422 equivalent if missing)
    3. Return structured interpretation for user confirmation (HITL gate)
    4. On approval, pass to Job_Search_Agent via PinchTab
    """
    start_ts = time.monotonic()
    session = None

    try:
        user_id = state["user_id"]
        run_id = state["run_id"]
        ctx = state["context"]
        query = ctx.get("query", "")

        if not query.strip():
            return {
                **state,
                "status": "failed",
                "error": "Query cannot be empty.",
            }

        # Get LLM via model router
        model_settings = fetch_model_settings(user_id)
        if not model_settings:
            raise ValueError("No active model settings configured for user")

        llm = _build_llm(model_settings)

        # Step 1: Extract parameters from NL query
        params = extract_parameters(llm, query)

        # Step 2: Validate — role_title is required
        if not validate_search_params(params):
            duration_ms = int((time.monotonic() - start_ts) * 1000)
            _log_agent_run(
                user_id=user_id,
                run_id=run_id,
                query=query,
                params=params,
                status="failed",
                duration_ms=duration_ms,
            )
            return {
                **state,
                "status": "failed",
                "error": "Could not identify a role title. Please include a job title in your query.",
            }

        # Step 3: Check if we should execute (user already confirmed) or ask for confirmation
        confirmed = ctx.get("confirmed", False)

        if not confirmed:
            # Return interpretation for user confirmation (HITL gate)
            duration_ms = int((time.monotonic() - start_ts) * 1000)
            _log_agent_run(
                user_id=user_id,
                run_id=run_id,
                query=query,
                params=params,
                status="awaiting_approval",
                duration_ms=duration_ms,
            )
            return {
                **state,
                "status": "awaiting_approval",
                "pending_action": {
                    "type": "search_confirmation",
                    "interpretation": params.to_dict(),
                    "original_query": query,
                },
                "messages": state["messages"] + [
                    AIMessage(
                        content=f"I interpreted your search as: {params.role_title}"
                        f"{f' ({params.seniority})' if params.seniority else ''}"
                        f"{f' in {params.location}' if params.location else ''}"
                        f"{f' ({params.remote_preference})' if params.remote_preference else ''}."
                        " Please confirm to execute the search."
                    )
                ],
            }

        # Step 4: User confirmed — execute search via PinchTab (Job_Search_Agent pattern)
        search_query = _build_search_query(params)
        location = params.location or "Remote"

        from app.agents.job_search import _extract_jobs_from_text, _score_job
        from app.core.sync_db import fetch_user_profile_text

        user_profile = fetch_user_profile_text(user_id)
        max_results = min(int(ctx.get("max_results", 10)), 25)

        jobs_raw: list[dict] = []
        try:
            session = new_session(user_id)
            url = (
                f"https://www.linkedin.com/jobs/search/"
                f"?keywords={search_query.replace(' ', '%20')}"
                f"&location={location.replace(' ', '%20')}&f_TPR=r86400"
            )
            session.navigate(url, block_images=True)
            time.sleep(2)
            page_text = session.text()
            jobs_raw = _extract_jobs_from_text(llm, page_text, max_results)
        except Exception as browser_exc:
            logger.warning("PinchTab unavailable (%s) — using fallback", browser_exc)
            # Fallback: return empty results rather than mock data for NL search
            jobs_raw = []

        # Score jobs against user profile
        scored = [
            {**job, "match_score": _score_job(llm, job, user_profile)}
            for job in jobs_raw
        ]
        scored.sort(key=lambda j: j["match_score"], reverse=True)

        duration_ms = int((time.monotonic() - start_ts) * 1000)

        _log_agent_run(
            user_id=user_id,
            run_id=run_id,
            query=query,
            params=params,
            status="completed",
            result_count=len(scored),
            duration_ms=duration_ms,
        )

        top = scored[0] if scored else {}
        summary = (
            f"Found {len(scored)} jobs for '{params.role_title}'"
            f"{f' in {params.location}' if params.location else ''}. "
            f"Top match: {top.get('title')} at {top.get('company')} ({top.get('match_score')}%)"
            if scored
            else f"No jobs found for '{params.role_title}'"
            f"{f' in {params.location}' if params.location else ''}."
        )

        return {
            **state,
            "status": "completed",
            "result": {
                "matches": scored,
                "total_found": len(jobs_raw),
                "interpretation": params.to_dict(),
                "original_query": query,
            },
            "messages": state["messages"] + [AIMessage(content=summary)],
        }

    except Exception as exc:
        logger.error("NL search agent failed for user %s: %s", state.get("user_id"), exc)
        return {**state, "status": "failed", "error": str(exc)}
    finally:
        if session:
            session.close()
