"""
followup_agent_v2.py — Follow-up email agent with auto-cancel on recruiter reply.

Schedules day-5 and day-12 follow-ups via BullMQ, checks for recruiter
replies before sending, and requires HITL approval for each send.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState


class FollowUpAgent(BaseAgent):
    async def run(self, state: AgentState) -> AgentState:
        ctx = state["context"]
        application_id = ctx.get("application_id", "")
        day = ctx.get("day", 5)

        await self.emitter.thinking(1, f"Checking if recruiter replied (day {day} follow-up)...")
        has_reply = await self._has_recruiter_replied(
            state["user_id"], application_id,
        )
        if has_reply:
            result = {"status": "cancelled", "reason": "Recruiter already replied"}
            await self.emitter.complete(result, 0, 0)
            state["result"] = result
            state["status"] = "completed"
            return state

        from app.core.sync_db import _get_sync_factory
        from app.models.db import JobApplication, User
        from sqlalchemy import select

        factory = _get_sync_factory()
        with factory() as db:
            app_result = db.execute(
                select(JobApplication).where(JobApplication.id == ctx["application_id"])
            )
            application = app_result.scalar_one_or_none()
            if not application:
                state["status"] = "failed"
                state["error"] = f"Application {application_id} not found"
                return state

            company = application.company
            role = application.role
            user_result = db.execute(select(User).where(User.id == application.user_id))
            user = user_result.scalar_one_or_none()
            user_email = user.email if user else ""

        from app.services.rag_service import retrieve
        from app.core.sync_db import fetch_model_settings, fetch_user_profile_text
        ms = fetch_model_settings(state["user_id"])
        background = fetch_user_profile_text(state["user_id"])
        if ms:
            chunks = retrieve(state["user_id"], "resume", role, ms, k=2)
            background = "\n".join(c.page_content for c in chunks) if chunks else background

        await self.emitter.thinking(2, "Drafting follow-up email...")
        llm = await self._get_llm(state["user_id"])
        day_text = "5-day" if day == 5 else "12-day"
        resp = await llm.ainvoke([{"role": "user", "content": (
            f"Write a {day_text} follow-up email for a {role} application at {company}. "
            f"Brief, professional, adds value (mention recent industry news or relevant project). "
            f"Include availability for a call. Under 120 words.\n\n"
            f"Candidate background: {background[:500]}"
        )}])

        state = await self._hitl_checkpoint(state, "send_followup_email", {
            "to": user_email,
            "subject": f"Following up: {role} at {company}",
            "body": resp.content.strip(),
            "day": day,
            "application_id": application_id,
        })
        return state

    async def _has_recruiter_replied(self, user_id: str, application_id: str) -> bool:
        from app.services.gmail_service import GmailMCPClient
        from app.core.sync_db import _get_sync_factory
        from app.models.db import JobApplication, User
        from sqlalchemy import select

        factory = _get_sync_factory()
        with factory() as db:
            app_result = db.execute(
                select(JobApplication).where(JobApplication.id == application_id)
            )
            app = app_result.scalar_one_or_none()
            if not app:
                return False

            user_result = db.execute(select(User).where(User.id == app.user_id))
            user = user_result.scalar_one_or_none()
            user_email = (user.email or "").lower()
            company = (app.company or "")

        if not user_email or not company:
            return False

        gmail = GmailMCPClient(user_id)
        query = f"{company} newer_than:30d"
        threads = gmail.search_threads(query, max_results=5)
        if not isinstance(threads, list):
            return False

        for thread in threads:
            thread_id = thread.get("threadId") or thread.get("id", "")
            if not thread_id:
                continue
            try:
                details = gmail.get_thread(thread_id)
            except Exception:
                continue
            messages = details.get("messages", [])
            for msg in reversed(messages):
                headers = msg.get("payload", {}).get("headers", [])
                from_addr = ""
                for h in headers:
                    if h.get("name", "").lower() == "from":
                        from_addr = h.get("value", "").lower()
                        break
                if from_addr and user_email not in from_addr:
                    return True
        return False

    async def schedule(self, application_id: str, user_id: str, email_thread_id: str = "") -> None:
        from app.services.queue_service import enqueue_followup
        await enqueue_followup(user_id, application_id, email_thread_id)


def followup_agent_node_v2(state: AgentState) -> AgentState:
    import redis.asyncio as aioredis
    from app.core.database import AsyncSessionLocal

    async def _run():
        async with AsyncSessionLocal() as db:
            redis = aioredis.from_url("redis://localhost:6379", decode_responses=True)
            try:
                agent = FollowUpAgent(db, redis)
                await agent.set_run_id(state["run_id"])
                return await agent.run(state)
            finally:
                await redis.aclose()
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _run()).result()
