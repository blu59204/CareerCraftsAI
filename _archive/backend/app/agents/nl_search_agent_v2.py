"""
nl_search_agent_v2.py — Natural-language job search agent.

Parses plain-English queries into structured search parameters via LLM,
then delegates to JobSearchAgent for live scraping + scoring across platforms.
"""
from __future__ import annotations

import asyncio
import json
import logging

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

PARSE_PROMPT = """Parse this job search query into structured parameters. Return JSON only.
Query: "{query}"
Return: {{"query": "job title keywords", "location": "city or Remote", "salary_min": number_or_null, "experience_years": number_or_null, "platforms": ["linkedin","indeed","naukri"], "remote": true_or_false}}"""


class NLSearchAgent(BaseAgent):
    async def run(self, state: AgentState) -> AgentState:
        ctx = state["context"]
        natural_query = ctx.get("query", "").strip()
        if not natural_query:
            state["status"] = "failed"
            state["error"] = "Query cannot be empty"
            return state

        await self.emitter.thinking(1, f"Parsing: '{natural_query}'...")
        llm = await self._get_llm(state["user_id"])
        resp = await llm.ainvoke([{"role": "user", "content": PARSE_PROMPT.format(query=natural_query)}])

        try:
            raw = resp.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            state["status"] = "failed"
            state["error"] = "Could not parse natural language query"
            return state

        await self.emitter.tool_result("nl_parse", parsed)

        confirmed = ctx.get("confirmed", False)
        if not confirmed:
            state = await self._hitl_checkpoint(state, "search_confirmation", {
                "interpretation": parsed,
                "original_query": natural_query,
            })
            return state

        await self.emitter.thinking(2, "Running structured search...")
        state["context"].update(parsed)

        from app.agents.job_search_agent_v2 import JobSearchAgent
        agent = JobSearchAgent(self.db, self.redis)
        await agent.set_run_id(state["run_id"])
        result_state = await agent.run(state)
        state["result"] = result_state["result"]
        state["status"] = "completed"
        await self.emitter.complete(state["result"], 0, 0)
        return state


def nl_search_agent_node_v2(state: AgentState) -> AgentState:
    import redis.asyncio as aioredis
    from app.core.database import AsyncSessionLocal

    async def _run():
        async with AsyncSessionLocal() as db:
            redis = aioredis.from_url("redis://localhost:6379", decode_responses=True)
            try:
                agent = NLSearchAgent(db, redis)
                await agent.set_run_id(state["run_id"])
                return await agent.run(state)
            finally:
                await redis.aclose()
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _run()).result()
