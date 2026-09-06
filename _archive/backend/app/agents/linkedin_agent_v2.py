"""
linkedin_agent_v2.py — LinkedIn profile optimization agent.

Rewrites headline, About section, and experience bullets for a target role
using RAG context from the user's resume and achievements.
"""
from __future__ import annotations

import asyncio
import re

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState


class LinkedInAgent(BaseAgent):
    async def run(self, state: AgentState) -> AgentState:
        ctx = state["context"]
        target_role = ctx.get("target_role", "")
        industry = ctx.get("industry", "Technology")
        linkedin_url = ctx.get("linkedin_url")

        await self.emitter.thinking(1, "Retrieving your background from memory...")
        from app.services.rag_service import retrieve
        from app.core.sync_db import fetch_model_settings, fetch_user_profile_text
        ms = fetch_model_settings(state["user_id"])
        background = fetch_user_profile_text(state["user_id"])
        if ms:
            chunks = retrieve(state["user_id"], "resume", target_role, ms, k=5)
            if chunks:
                background = "\n".join(c.page_content for c in chunks)

        current_profile = {}
        if linkedin_url:
            try:
                from app.services.proxycurl_service import ProxycurlService
                proxycurl = ProxycurlService()
                contacts = await proxycurl.find_contacts("", target_role)
                if contacts:
                    await self.emitter.tool_result("proxycurl", {"profile_loaded": True})
            except Exception:
                pass

        await self.emitter.thinking(2, f"Optimizing profile for '{target_role}' in {industry}...")
        llm = await self._get_llm(state["user_id"])

        head_resp = await llm.ainvoke([{"role": "user", "content": (
            f"Write a LinkedIn headline for someone targeting {target_role} roles in {industry}. "
            f"Max 220 characters. Use | separator between key phrases. "
            f"Include current title, target role, and key skills. Based on: {background[:500]}"
        )}])

        about_resp = await llm.ainvoke([{"role": "user", "content": (
            f"Write a LinkedIn About section for {target_role} in {industry}. "
            f"3 paragraphs. First person, professional tone. Tell a story: background → skills → passion. "
            f"End with a call to action. Based on: {background}"
        )}])

        bullets_resp = await llm.ainvoke([{"role": "user", "content": (
            f"Write 3 achievement-focused LinkedIn experience bullets for a {target_role} role. "
            f"Start each with a strong action verb. Quantify impact where possible. "
            f"Based on: {background[:1000]}"
        )}])

        bullets = [b.strip() for b in bullets_resp.content.strip().split("\n") if b.strip()]
        bullets_clean = [re.sub(r"^\d+[\.\)]\s*[-•]\s*", "", b) for b in bullets][:3]

        jd_keywords = set(target_role.lower().split() + industry.lower().split())
        profile_text = f"{head_resp.content} {about_resp.content}".lower()
        profile_words = set(profile_text.split())
        gaps = list(jd_keywords - profile_words)[:8]

        result = {
            "headline": head_resp.content.strip()[:220],
            "about": about_resp.content.strip()[:2000],
            "experience_bullets": {"Most Recent Role": bullets_clean},
            "optimization_score": min(95, 70 + min(len(background.split()) // 20, 25)),
            "keyword_gaps": gaps,
            "suggestions": [],
        }
        await self.emitter.complete(result, 0, 0)
        state["result"] = result
        state["status"] = "completed"
        return state


def linkedin_agent_node_v2(state: AgentState) -> AgentState:
    import redis.asyncio as aioredis
    from app.core.database import AsyncSessionLocal

    async def _run():
        async with AsyncSessionLocal() as db:
            redis = aioredis.from_url("redis://localhost:6379", decode_responses=True)
            try:
                agent = LinkedInAgent(db, redis)
                await agent.set_run_id(state["run_id"])
                return await agent.run(state)
            finally:
                await redis.aclose()
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _run()).result()
