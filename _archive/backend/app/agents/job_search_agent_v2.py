"""
job_search_agent_v2.py — Job search agent using JobSpy + Playwright browser automation.

Searches LinkedIn, Indeed, Naukri, and Glassdoor for job listings, then
scores matches against the user's resume profile.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState
from app.tools.platform_detector import (
    JOB_CARD_SELECTORS, PLATFORM_SEARCH_URLS, detect_platform, extract_job_details_selectors,
)
from app.services.job_platforms_service import scrape_jobs, JobListing

logger = logging.getLogger(__name__)


class JobSearchAgent(BaseAgent):
    """Search jobs across platforms, score matches, and extract detailed JD from URLs."""

    async def run(self, state: AgentState) -> AgentState:
        ctx = state["context"]
        query = ctx.get("query", "")
        location = ctx.get("location", "Remote")
        platforms = ctx.get("platforms", ["linkedin", "indeed", "naukri"])
        salary_min = ctx.get("salary_min", 0)
        experience_years = ctx.get("experience_years", 0)

        await self.emitter.thinking(1, f"Searching {len(platforms)} platforms for '{query}'...")

        all_jobs: list[dict[str, Any]] = []

        for platform in platforms:
            await self.emitter.thinking(2, f"Searching {platform}...")
            try:
                jobs = await self._search_platform(platform, query, location, state["user_id"])
                all_jobs.extend(jobs)
                await self.emitter.tool_result("job_search", {"platform": platform, "found": len(jobs)})
            except Exception as exc:
                await self.emitter.tool_result("job_search", {"platform": platform, "error": str(exc)})

        if not all_jobs:
            from app.services.job_platforms_service import scrape_jobs, _job_listings_to_dicts
            listings = scrape_jobs(query, location, 50, 72, platforms)
            all_jobs = _job_listings_to_dicts(listings)

        await self.emitter.thinking(3, "Scoring matches against your profile...")
        from app.services.rag_service import retrieve, get_embedding_model

        resume_text = ""
        from app.core.sync_db import fetch_model_settings, fetch_user_profile_text
        ms = fetch_model_settings(state["user_id"])
        if ms:
            chunks = retrieve(state["user_id"], "resume", query, ms, k=3)
            resume_text = " ".join(c.page_content for c in chunks)
        if not resume_text:
            resume_text = fetch_user_profile_text(state["user_id"])

        scored_jobs = [self._score_job(job, resume_text, experience_years, salary_min) for job in all_jobs]
        scored_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)

        result = {"jobs": scored_jobs[:50], "total": len(scored_jobs)}
        await self.emitter.complete(result, 0, 0)
        state["result"] = result
        state["status"] = "completed"
        return state

    async def _search_platform(
        self, platform: str, query: str, location: str, user_id: str,
    ) -> list[dict[str, Any]]:
        from app.services.browser_control_service import BrowserControlService
        browser = BrowserControlService(user_id=user_id)
        try:
            url_template = PLATFORM_SEARCH_URLS.get(platform)
            if not url_template:
                return []

            query_slug = query.replace(" ", "-").lower()
            url = url_template.format(query=query, location=location, query_slug=query_slug)
            await browser.navigate(url, user_id)
            await asyncio.sleep(2.0)

            selectors = JOB_CARD_SELECTORS.get(platform, JOB_CARD_SELECTORS["generic"])
            found = await browser.element_exists(selectors["container"], user_id)
            if not found:
                return []

            jobs: list[dict[str, Any]] = []
            for container_idx in range(20):
                try:
                    container = f"{selectors['container']}:nth-child({container_idx + 1})"
                    exists = await browser.element_exists(container, user_id)
                    if not exists:
                        break
                    title = await browser.get_text(f"{container} {selectors['title']}", user_id)
                    company = await browser.get_text(f"{container} {selectors['company']}", user_id)
                    location_text = await browser.get_text(f"{container} {selectors['location']}", user_id)
                    href = await browser.get_attribute(f"{container} {selectors['url']}", "href", user_id)
                    if title:
                        jobs.append({
                            "title": title.strip(),
                            "company": company.strip(),
                            "location": location_text.strip(),
                            "url": href if href else "",
                            "platform": platform,
                        })
                except Exception:
                    continue
            return jobs[:20]
        finally:
            await browser.close()

    def _score_job(
        self, job: dict[str, Any], resume_text: str, experience_years: int, salary_min: int,
    ) -> dict[str, Any]:
        job_text = f"{job.get('title', '')} {job.get('description', '')}".lower()
        resume_words = set(resume_text.lower().split())
        job_words = set(job_text.split())
        overlap = resume_words & job_words
        keyword_score = len(overlap) / max(len(job_words), 1) * 60
        location_score = 20 if "remote" in job.get("location", "").lower() else 10
        exp_score = 20 if experience_years >= 3 else 10
        job["match_score"] = min(100, int(keyword_score + location_score + exp_score))
        return job

    async def get_job_details(self, job_url: str, user_id: str) -> dict[str, Any]:
        from app.services.browser_control_service import BrowserControlService
        browser = BrowserControlService(user_id=user_id)
        try:
            await browser.navigate(job_url, user_id)
            await asyncio.sleep(2.0)
            platform = detect_platform(job_url)
            selectors = extract_job_details_selectors(platform)
            title = await browser.get_text(selectors["title"], user_id)
            company = await browser.get_text(selectors["company"], user_id)
            description = await browser.get_text(selectors["description"], user_id)
            apply_url = job_url
            if "apply_button" in selectors:
                try:
                    apply_url = await browser.get_attribute(selectors["apply_button"], "href", user_id)
                except Exception:
                    pass
            return {
                "title": title.strip(),
                "company": company.strip(),
                "description": description,
                "apply_url": apply_url or job_url,
                "platform": platform,
            }
        finally:
            await browser.close()


def job_search_agent_node(state: AgentState) -> AgentState:
    """Orchestrator-compatible wrapper function."""
    import redis.asyncio as aioredis
    from app.core.database import AsyncSessionLocal

    async def _run():
        async with AsyncSessionLocal() as db:
            redis = aioredis.from_url("redis://localhost:6379", decode_responses=True)
            try:
                agent = JobSearchAgent(db, redis)
                await agent.set_run_id(state["run_id"])
                return await agent.run(state)
            finally:
                await redis.aclose()

    import asyncio as _asyncio
    try:
        loop = _asyncio.get_running_loop()
    except RuntimeError:
        return _asyncio.run(_run())
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_asyncio.run, _run()).result()
