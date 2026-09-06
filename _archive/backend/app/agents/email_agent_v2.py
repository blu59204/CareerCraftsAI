"""
email_agent_v2.py — Email outreach agent with Gmail OAuth + HITL approval gate.

Drafts personalized cold outreach emails to recruiters, requires explicit
human approval before sending via the user's Gmail account.
"""
from __future__ import annotations

import asyncio
import uuid

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState

EMAIL_DRAFT_PROMPT = """Write a {email_type} email for a job application.

Recruiter: {recruiter_name} at {company}
Job Title: {job_title}

Thread Context (recent Gmail conversations):
{thread_context}

Candidate Background:
{background}

Requirements:
- Professional tone, under 150 words
- Mention specific skills or experience relevant to the role
- Include a clear call to action (request a brief call or meeting)
- Do NOT include placeholders or bracketed text

Write the complete email including subject line.
Format: Subject: <subject>\n\n<body>"""


class EmailAgent(BaseAgent):
    async def run(self, state: AgentState) -> AgentState:
        ctx = state["context"]
        recruiter_name = ctx.get("recruiter_name", "Hiring Manager")
        company = ctx.get("recruiter_company", ctx.get("company_name", "the company"))
        job_title = ctx.get("job_title", "")
        email_type = ctx.get("email_type", "outreach")

        await self.emitter.thinking(1, "Reading your recent Gmail threads for context...")
        thread_context = "No recent thread history available."

        recruiter_email = ctx.get("recruiter_email")
        if not recruiter_email:
            await self.emitter.thinking(2, f"Finding {recruiter_name}'s email via Hunter.io...")
            from app.services.hunter_service import HunterService
            hunter = HunterService()
            domain = company.lower().replace(" ", "").replace(",", "") + ".com"
            parts = recruiter_name.split()
            result = await hunter.find_email(domain, parts[0] if parts else "", parts[-1] if len(parts) > 1 else "")
            if result and result.get("email"):
                recruiter_email = result["email"]

        if not recruiter_email:
            state["status"] = "failed"
            state["error"] = f"Could not find email for {recruiter_name} at {company}"
            return state

        await self.emitter.thinking(3, "Retrieving your background for personalized email...")
        from app.services.rag_service import retrieve
        from app.core.sync_db import fetch_model_settings, fetch_user_profile_text
        ms = fetch_model_settings(state["user_id"])
        background = fetch_user_profile_text(state["user_id"])
        if ms:
            chunks = retrieve(state["user_id"], "resume", f"{job_title} {company}", ms, k=3)
            background = "\n".join(c.page_content for c in chunks) if chunks else background

        await self.emitter.thinking(4, "Drafting email...")
        llm = await self._get_llm(state["user_id"])
        prompt = EMAIL_DRAFT_PROMPT.format(
            email_type=email_type, recruiter_name=recruiter_name,
            company=company, job_title=job_title,
            thread_context=thread_context, background=background[:1500],
        )
        response = await llm.ainvoke([{"role": "user", "content": prompt}])

        body = response.content.strip()
        subject = f"Interest in {job_title} at {company}" if job_title else f"Introduction regarding {company}"
        if body.lower().startswith("subject:"):
            lines = body.split("\n", 2)
            subject = lines[0].replace("SUBJECT:", "").replace("Subject:", "").strip()
            body = lines[2].strip() if len(lines) > 2 else body

        from app.core.sync_db import _get_sync_factory
        from app.models.db import Lead
        factory = _get_sync_factory()
        with factory() as db:
            lead = Lead(
                id=uuid.uuid4(), user_id=uuid.UUID(state["user_id"]),
                name=recruiter_name, email=recruiter_email,
                company=company, status="contacted",
            )
            db.add(lead)
            db.commit()
            email_id = str(lead.id)

        state = await self._hitl_checkpoint(state, "send_email", {
            "to": recruiter_email,
            "subject": subject,
            "body": body,
            "email_id": email_id,
        })
        return state


def email_agent_node_v2(state: AgentState) -> AgentState:
    import redis.asyncio as aioredis
    from app.core.database import AsyncSessionLocal

    async def _run():
        async with AsyncSessionLocal() as db:
            redis = aioredis.from_url("redis://localhost:6379", decode_responses=True)
            try:
                agent = EmailAgent(db, redis)
                await agent.set_run_id(state["run_id"])
                return await agent.run(state)
            finally:
                await redis.aclose()
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _run()).result()
