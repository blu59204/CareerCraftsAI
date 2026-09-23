"""
salary_agent_v2.py — Salary intelligence and negotiation script agent.

Researches market compensation for a role via Exa, builds p25/p50/p75/p90
percentiles, classifies user's offer, generates negotiation script. Uses
Claude extended thinking when Anthropic provider is active.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState

SALARY_SYSTEM_PROMPT = """You are a compensation expert. Analyze salary data and return JSON with:
- percentiles: {{p25, p50, p75, p90}} in whole numbers
- total_comp: {{base, equity_annual, bonus, total}}
- your_offer_percentile: position of the offer in the market (0-100, or null if no offer)
- negotiation_script: opening statement with specific counter-offer at p75, 2 data-backed justifications
- key_talking_points: list of 3-4 strategic points for negotiation"""


class SalaryAgent(BaseAgent):
    async def run(self, state: AgentState) -> AgentState:
        ctx = state["context"]
        role = ctx["role"]
        location = ctx["location"]
        experience_years = ctx.get("experience_years", 5)
        offer_amount = ctx.get("offer_amount")
        company = ctx.get("company_name", "")

        await self.emitter.thinking(1, f"Gathering salary data for {role} in {location}...")
        from app.services.exa_service import ExaService
        exa = ExaService()
        queries = [
            f"{role} salary {location} 2026",
            f"{role} compensation levels.fyi glassdoor {location}",
            f"senior {role} total compensation breakdown {location}",
        ]
        salary_data: list[str] = []
        for q in queries:
            results = await exa._search(q, num_results=3)
            salary_data.extend(r.get("snippet", r.get("text", "")) for r in results)
            await self.emitter.tool_result("exa_salary", {"query": q, "results": len(results)})

        await self.emitter.thinking(2, "Calculating percentiles and negotiation script...")
        llm = await self._get_llm(state["user_id"])
        offer_text = f"\nCandidate's current offer: ${offer_amount:,}" if offer_amount else ""

        messages = [
            SystemMessage(content=SALARY_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"Salary data from web search:\n{chr(10).join(salary_data[:10])}\n\n"
                f"Role: {role}\nLocation: {location}\nExperience: {experience_years} years"
                f"{offer_text}\nCompany: {company or 'Not specified'}"
            )),
        ]

        response = await llm.ainvoke(messages)
        try:
            raw = response.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            result_data = json.loads(raw)
        except json.JSONDecodeError:
            result_data = {
                "percentiles": {"p25": 0, "p50": 0, "p75": 0, "p90": 0},
                "total_comp": {"base": 0, "equity_annual": 0, "bonus": 0, "total": 0},
                "negotiation_script": "Salary data unavailable. Consider researching on levels.fyi or Glassdoor.",
                "key_talking_points": ["Market data was insufficient for this role/location combination."],
            }

        report_id = uuid.uuid4()
        from app.core.sync_db import _get_sync_factory
        from app.models.db import SalaryReport
        factory = _get_sync_factory()
        with factory() as db:
            report = SalaryReport(
                id=report_id, user_id=uuid.UUID(state["user_id"]),
                role=role, company=company or None, location=location,
                p25=result_data["percentiles"]["p25"],
                p50=result_data["percentiles"]["p50"],
                p75=result_data["percentiles"]["p75"],
                offer_amount=offer_amount,
                negotiation_script=result_data,
                data_sources=[r[:200] for r in salary_data],
            )
            db.add(report)
            db.commit()

        result_data["report_id"] = str(report_id)
        await self.emitter.complete(result_data, 0, 0)
        state["result"] = result_data
        state["status"] = "completed"
        return state


def salary_agent_node_v2(state: AgentState) -> AgentState:
    import redis.asyncio as aioredis
    from app.core.database import AsyncSessionLocal

    async def _run():
        async with AsyncSessionLocal() as db:
            redis = aioredis.from_url("redis://localhost:6379", decode_responses=True)
            try:
                agent = SalaryAgent(db, redis)
                await agent.set_run_id(state["run_id"])
                return await agent.run(state)
            finally:
                await redis.aclose()
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _run()).result()
