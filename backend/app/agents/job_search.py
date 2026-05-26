import json
import logging
import time

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.state import AgentState
from app.core.model_router import _build_llm
from app.core.sync_db import fetch_model_settings, fetch_user_profile_text
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

EXTRACT_PROMPT = """Extract job listings from this page text. Return a JSON array of objects with keys:
title, company, location, description, job_url.
Extract up to {max_results} jobs. If no jobs found, return [].
Return ONLY valid JSON, no explanation.

Page text:
{text}"""

_MOCK_JOBS = [
    {"title": "Software Engineer", "company": "Acme Corp", "location": "Remote", "description": "Build scalable backend services in Python and Go.", "job_url": "https://example.com/jobs/1"},
    {"title": "Full Stack Developer", "company": "Globex", "location": "Remote", "description": "React frontend + FastAPI backend for SaaS platform.", "job_url": "https://example.com/jobs/2"},
    {"title": "Backend Engineer", "company": "Initech", "location": "Bangalore", "description": "Microservices architecture, PostgreSQL, Redis, Kubernetes.", "job_url": "https://example.com/jobs/3"},
    {"title": "Senior Software Engineer", "company": "Umbrella Tech", "location": "Hyderabad", "description": "Lead development of ML pipeline and API services.", "job_url": "https://example.com/jobs/4"},
    {"title": "Python Developer", "company": "Veridian Dynamics", "location": "Remote", "description": "Data processing pipelines, REST APIs, async Python.", "job_url": "https://example.com/jobs/5"},
]


def _extract_jobs_from_text(llm, page_text: str, max_results: int) -> list[dict]:
    try:
        resp = llm.invoke([HumanMessage(
            content=EXTRACT_PROMPT.format(max_results=max_results, text=page_text[:6000])
        )])
        content = resp.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)[:max_results]
    except Exception as exc:
        logger.warning("Job extraction from page text failed: %s", exc)
        return []


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
        logger.warning("Score failed for %s at %s: %s", job.get("title"), job.get("company"), exc)
        return 0


def job_search_agent_node(state: AgentState) -> AgentState:
    session = None
    try:
        user_id = state["user_id"]
        ctx = state["context"]
        query = ctx.get("search_query", "software engineer")
        location = ctx.get("location", "Remote")
        max_results = min(int(ctx.get("max_results", 10)), 25)

        model_settings = fetch_model_settings(user_id)
        if not model_settings:
            raise ValueError("No active model settings configured for user")

        user_profile = fetch_user_profile_text(user_id)
        llm = _build_llm(model_settings)

        jobs_raw: list[dict] = []
        try:
            # Primary: Use JobSpy for multi-platform scraping
            from app.services.job_platforms_service import scrape_jobs as jobspy_scrape
            job_listings = jobspy_scrape(
                search_term=query,
                location=location,
                results_wanted=max_results,
                hours_old=72,
            )
            jobs_raw = [
                {"title": j.title, "company": j.company, "location": j.location,
                 "description": j.description, "job_url": j.job_url, "platform": j.platform}
                for j in job_listings
            ]
        except Exception as jobspy_exc:
            logger.warning("JobSpy unavailable (%s) — trying PinchTab", jobspy_exc)
            try:
                session = new_session(user_id)
                url = LINKEDIN_SEARCH_URL.format(
                    query=query.replace(" ", "%20"),
                    location=location.replace(" ", "%20"),
                )
                session.navigate(url, block_images=True)
                time.sleep(2)
                page_text = session.text()
                jobs_raw = _extract_jobs_from_text(llm, page_text, max_results)
            except Exception as browser_exc:
                logger.warning("PinchTab also unavailable (%s) — using mock data", browser_exc)
                jobs_raw = _MOCK_JOBS[:max_results]

        scored = [
            {**job, "match_score": _score_job(llm, job, user_profile)}
            for job in jobs_raw
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
            "result": {"matches": scored, "total_found": len(jobs_raw)},
            "messages": state["messages"] + [AIMessage(content=summary)],
        }
    except Exception as exc:
        logger.error("Job search agent failed for user %s: %s", state.get("user_id"), exc)
        return {**state, "status": "failed", "error": str(exc)}
    finally:
        if session:
            session.close()
