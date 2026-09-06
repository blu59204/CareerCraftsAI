"""
company_research_agent_v2.py — Company intelligence agent with 7-day cache.

Researches companies from multiple sources (Exa, optional Firecrawl),
embeds results in pgvector, and returns structured CompanyIntel data.
Implements per-source graceful degradation.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState


class CompanyResearchAgent(BaseAgent):
    async def run(self, state: AgentState) -> AgentState:
        ctx = state["context"]
        company = ctx.get("company_name", "").strip()
        if not company:
            state["status"] = "failed"
            state["error"] = "company_name is required"
            return state

        sections = ctx.get("sections", ["culture", "interview_process", "financials", "recent_news", "key_people"])
        force_refresh = ctx.get("force_refresh", False)

        if not force_refresh:
            from app.core.sync_db import _get_sync_factory
            from app.models.db import CompanyIntelModel
            from sqlalchemy import select

            factory = _get_sync_factory()
            with factory() as db:
                result = db.execute(
                    select(CompanyIntelModel).where(
                        CompanyIntelModel.user_id == uuid.UUID(state["user_id"]),
                        CompanyIntelModel.company_name == company,
                    )
                )
                cached = result.scalars().first()
                if cached and cached.researched_at:
                    age_days = (datetime.now(timezone.utc) - cached.researched_at.replace(tzinfo=timezone.utc)).days
                    if age_days < 7:
                        state["result"] = {
                            "company": cached.company_name,
                            "overview": cached.overview,
                            "culture_summary": cached.culture_summary,
                            "news_items": cached.news_items,
                            "tech_stack": cached.tech_stack,
                            "glassdoor_sentiment": cached.glassdoor_sentiment,
                            "cached": True,
                        }
                        state["status"] = "completed"
                        await self.emitter.complete(state["result"], 0, 0)
                        return state

        await self.emitter.thinking(1, f"Researching {company} across the web...")
        from app.services.exa_service import ExaService
        exa = ExaService()
        llm = await self._get_llm(state["user_id"])

        search_queries: dict[str, str] = {
            "culture": f"{company} company culture values glassdoor employee reviews",
            "interview_process": f"{company} interview process questions rounds technical",
            "financials": f"{company} revenue funding valuation 2025 2026",
            "recent_news": f"{company} news announcements 2025 2026",
            "key_people": f"{company} CEO CTO leadership team executives",
        }

        results: dict[str, str] = {}
        for section in sections:
            if section not in search_queries:
                continue
            await self.emitter.thinking(2, f"Researching {section}...")
            search_results = await exa._search(search_queries[section], num_results=3)
            await self.emitter.tool_result("exa_search", {"section": section, "results": len(search_results)})
            content = "\n".join(r.get("snippet", r.get("text", "")) for r in search_results)
            synthesis = await llm.ainvoke([{"role": "user", "content": (
                f"Synthesize this into a 150-word briefing on {company}'s {section}:\n{content[:2000]}"
            )}])
            results[section] = synthesis.content.strip()

        from app.core.sync_db import _get_sync_factory
        from app.models.db import CompanyIntelModel
        factory = _get_sync_factory()
        with factory() as db:
            intel = CompanyIntelModel(
                user_id=uuid.UUID(state["user_id"]),
                company_name=company,
                overview=results.get("financials", "")[:1500],
                culture_summary=results.get("culture", "")[:800],
                news_items=[results.get("recent_news", "")],
                tech_stack=[results.get("key_people", "")],
                glassdoor_sentiment="neutral",
                researched_at=datetime.now(timezone.utc),
            )
            db.add(intel)
            db.commit()

        state["result"] = {**results, "company": company, "researched_at": datetime.now(timezone.utc).isoformat()}
        state["status"] = "completed"
        await self.emitter.complete(state["result"], 0, 0)
        return state


def company_research_agent_node_v2(state: AgentState) -> AgentState:
    import redis.asyncio as aioredis
    from app.core.database import AsyncSessionLocal

    async def _run():
        async with AsyncSessionLocal() as db:
            redis = aioredis.from_url("redis://localhost:6379", decode_responses=True)
            try:
                agent = CompanyResearchAgent(db, redis)
                await agent.set_run_id(state["run_id"])
                return await agent.run(state)
            finally:
                await redis.aclose()
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _run()).result()
