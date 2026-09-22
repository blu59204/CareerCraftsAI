"""
nl_search_agent.py — NL (Natural Language) Job Search Agent.

Parses plain-language job search queries into structured SearchParameters,
validates them, and returns a structured interpretation for user confirmation
before delegating to the existing Job_Search_Agent.
"""

import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from app.agents._llm_json import call_llm_json
from app.agents.prompts.nl_search_prompt import SYSTEM_PROMPT, OUTPUT_SCHEMA, build_user_prompt
from app.agents.state import AgentState
from app.core.model_router import _build_llm
from app.core.sync_db import fetch_model_settings

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

def extract_parameters(llm: BaseChatModel, query: str) -> SearchParameters:
    """Use LLM to extract structured search parameters from a natural language query."""
    parsed = call_llm_json(
        llm,
        SYSTEM_PROMPT,
        build_user_prompt({"query": query}),
        OUTPUT_SCHEMA,
    )
    salary_range = (
        (parsed.salary_min, parsed.salary_max)
        if parsed.salary_min is not None and parsed.salary_max is not None
        else None
    )

    return SearchParameters(
        role_title=parsed.titles[0] if parsed.titles else None,
        seniority=None,
        location=parsed.locations[0] if parsed.locations else None,
        remote_preference=parsed.remote,
        industry=parsed.company_types[0] if parsed.company_types else None,
        salary_range=salary_range,
        company_size=None,
        tech_stack=parsed.skills,
        additional_constraints=parsed.exclude,
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
    from app.core.event_bus import suppress_terminal_events
    if suppress_terminal_events.get():
        return  # The durable worker commits the authoritative run state.
    from app.core.sync_db import _get_sync_factory
    from app.models.db import AgentRun

    factory = _get_sync_factory()
    now = datetime.now(timezone.utc)
    with factory() as db:
        run_uuid = uuid.UUID(run_id)
        agent_run = db.get(AgentRun, run_uuid)
        if agent_run is None:
            agent_run = AgentRun(
                id=run_uuid,
                user_id=user_id,
                agent_type="nl_job_search",
                started_at=now,
            )
            db.add(agent_run)
        agent_run.status = status
        agent_run.input = {"query": query, "extracted_parameters": params.to_dict()}
        agent_run.output = {"results_count": result_count} if result_count is not None else None
        agent_run.duration_ms = duration_ms
        agent_run.completed_at = now if status != "running" else None
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
    4. On approval, scrape live jobs via JobSpy, score, and return matches
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

        # Step 4: User confirmed — scrape live jobs via JobSpy
        search_query = _build_search_query(params)
        location = params.location or "Remote"

        from app.agents.job_search import _score_job, _job_listings_to_dicts
        from app.core.sync_db import fetch_user_profile_text
        from app.services.job_platforms_service import scrape_jobs

        user_profile = fetch_user_profile_text(user_id)
        max_results = min(int(ctx.get("max_results", 10)), 25)

        listings = scrape_jobs(search_query, location, max_results * 2, 72)
        jobs_raw = _job_listings_to_dicts(listings)

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
        return {**state, "status": "failed", "error": "Agent failed"}
    finally:
        if session:
            session.close()
