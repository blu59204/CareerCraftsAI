"""
cover_letter_agent_v2.py — Cover letter agent using extended thinking with Anthropic.

Generates personalized cover letters using RAG context and Claude extended thinking.
"""
from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState

COVER_LETTER_SYSTEM = """You are an expert cover letter writer. Write a compelling, personalized cover letter \
for a job application. Use the candidate's background context and the job description to craft \
a letter that demonstrates fit, enthusiasm, and value. Keep it under {word_limit} words. \
Tone: {tone}. Address it to {hiring_manager}."""


class CoverLetterAgent(BaseAgent):
    async def run(self, state: AgentState) -> AgentState:
        ctx = state["context"]
        job_desc = ctx["job_description"]
        company = ctx.get("company_name", "the company")
        hiring_manager = ctx.get("hiring_manager", "Hiring Manager")
        tone = ctx.get("tone", "professional")
        word_limit = ctx.get("word_limit", 350)

        await self.emitter.thinking(1, "Retrieving your background from memory...")
        from app.services.rag_service import retrieve
        from app.core.sync_db import fetch_model_settings

        ms = fetch_model_settings(state["user_id"])
        chunks = retrieve(state["user_id"], "resume", job_desc, ms, k=5) if ms else []
        background = "\n".join(c.page_content for c in chunks)

        await self.emitter.thinking(2, f"Crafting personalized cover letter for {company}...")
        llm = await self._get_llm(state["user_id"])

        prompt = COVER_LETTER_SYSTEM.format(
            word_limit=word_limit, tone=tone, hiring_manager=hiring_manager,
        )
        full_prompt = f"{prompt}\n\nCompany: {company}\nJob Description:\n{job_desc[:2000]}\n\nCandidate Background:\n{background[:2000]}"

        response = await llm.ainvoke([HumanMessage(content=full_prompt)])
        professional = response.content.strip()[:word_limit * 6]

        await self.emitter.thinking(3, "Generating concise variant...")
        conc_response = await llm.ainvoke([HumanMessage(
            content=f"Rewrite this cover letter in 200 words or less, more direct and concise:\n\n{professional}"
        )])
        concise = conc_response.content.strip()[:1200]

        jd_hash = hashlib.sha256(job_desc[:500].encode()).hexdigest()[:16]
        version_id = uuid.uuid4()
        from app.core.sync_db import _get_sync_factory
        from app.models.db import CoverLetterVersion
        factory = _get_sync_factory()
        with factory() as db:
            version = CoverLetterVersion(
                id=version_id, user_id=uuid.UUID(state["user_id"]),
                job_application_id=None, document_id=None,
                tone=tone, version_number=1,
            )
            db.add(version)
            db.commit()

        result = {
            "cover_letter_id": str(version_id),
            "cover_letter": professional,
            "variants": [
                {"tone": "professional", "text": professional},
                {"tone": "concise", "text": concise},
            ],
            "word_count": len(professional.split()),
        }
        await self.emitter.complete(result, 0, 0)
        state["result"] = result
        state["status"] = "completed"
        return state


def cover_letter_node_v2(state: AgentState) -> AgentState:
    import redis.asyncio as aioredis
    from app.core.database import AsyncSessionLocal

    async def _run():
        async with AsyncSessionLocal() as db:
            redis = aioredis.from_url("redis://localhost:6379", decode_responses=True)
            try:
                agent = CoverLetterAgent(db, redis)
                await agent.set_run_id(state["run_id"])
                return await agent.run(state)
            finally:
                await redis.aclose()
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _run()).result()
