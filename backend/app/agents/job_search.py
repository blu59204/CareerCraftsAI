import asyncio
import logging
import time

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.state import AgentState
from app.core.model_router import _build_llm
from app.services.pinchtab_service import new_session

logger = logging.getLogger(__name__)

LINKEDIN_SEARCH_URL = (
    "https://www.linkedin.com/jobs/search/?keywords={query}&location={location}&f_TPR=r86400"
)
SCORE_PROMPT = """Rate how well this job matches the candidate profile. Return ONLY a number 0-100.

Candidate profile:
{profile}

Job: {title} at {company}
Description: {description}

Score (0-100):"""


def _get_model_settings(user_id: str):
    async def _fetch():
        from sqlalchemy import select

        from app.core.database import AsyncSessionLocal
        from app.models.db import UserModelSettings

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(UserModelSettings).where(
                    UserModelSettings.user_id == user_id,
                    UserModelSettings.is_active == True,  # noqa: E712
                )
            )
            return result.scalar_one_or_none()

    return asyncio.run(_fetch())


def _get_user_profile(user_id: str) -> str:
    async def _fetch():
        from sqlalchemy import select

        from app.core.database import AsyncSessionLocal
        from app.models.db import UserDocument

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(UserDocument).where(
                    UserDocument.user_id == user_id,
                    UserDocument.doc_type == "resume",
                    UserDocument.is_primary == True,  # noqa: E712
                )
            )
            doc = result.scalar_one_or_none()
            return doc.raw_text[:2000] if doc and doc.raw_text else ""

    return asyncio.run(_fetch())


def _score_job(llm, job: dict, profile: str) -> int:
    try:
        resp = llm.invoke([HumanMessage(
            content=SCORE_PROMPT.format(
                profile=profile,
                title=job.get("title", ""),
                company=job.get("company", ""),
                description=str(job.get("description", ""))[:500],
            )
        )])
        digits = "".join(c for c in resp.content.strip()[:3] if c.isdigit())
        return int(digits) if digits else 0
    except Exception as exc:
        logger.warning(
            "Score failed for %s at %s: %s",
            job.get("title"),
            job.get("company"),
            exc,
        )
        return 0


def job_search_agent_node(state: AgentState) -> AgentState:
    session = None
    try:
        user_id = state["user_id"]
        ctx = state["context"]
        query = ctx.get("search_query", "software engineer")
        location = ctx.get("location", "Remote")
        max_results = min(int(ctx.get("max_results", 10)), 25)

        model_settings = _get_model_settings(user_id)

        # Open browser session early so navigate errors are attributed correctly
        session = new_session(user_id)
        url = LINKEDIN_SEARCH_URL.format(
            query=query.replace(" ", "%20"),
            location=location.replace(" ", "%20"),
        )
        session.navigate(url)
        time.sleep(2)
        snapshot_data = session.snapshot()

        if not model_settings:
            raise ValueError("No active model settings configured for user")

        user_profile = _get_user_profile(user_id)
        llm = _build_llm(model_settings)

        jobs = snapshot_data.get("jobs", [])[:max_results]
        scored = [
            {**job, "match_score": _score_job(llm, job, user_profile)}
            for job in jobs
        ]
        scored.sort(key=lambda j: j["match_score"], reverse=True)

        top = scored[0] if scored else {}
        summary = (
            f"Found {len(scored)} jobs. Top match: {top.get('title')} at "
            f"{top.get('company')} ({top.get('match_score')}%)"
            if scored
            else "No jobs found."
        )

        return {
            **state,
            "status": "completed",
            "result": {"matches": scored, "total_found": len(jobs)},
            "messages": state["messages"] + [AIMessage(content=summary)],
        }
    except Exception as exc:
        logger.error(
            "Job search agent failed for user %s: %s",
            state.get("user_id"),
            exc,
        )
        return {**state, "status": "failed", "error": str(exc)}
    finally:
        if session:
            session.close()
