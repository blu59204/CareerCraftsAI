"""
auto_apply_pipeline_v2.py — End-to-end automated job application pipeline.

10-step pipeline: search → tailor resume → cover letter → ATS → HITL 1 →
form fill → HITL 2 → submit → save → schedule follow-ups.

Coordinates JobSearchAgent, CoverLetterAgent, FormFillerService, ATSService,
PDFService, and FollowUpAgent. 2 mandatory HITL gates.
"""
from __future__ import annotations

import asyncio
import io
import tempfile
import uuid
from datetime import datetime, timezone

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState
from app.tools.form_filler import FormFillerService
from app.tools.platform_detector import detect_platform


class AutoApplyPipeline(BaseAgent):
    async def run(self, state: AgentState) -> AgentState:
        ctx = state["context"]
        job_url = ctx["job_url"]
        user_id = state["user_id"]

        await self.emitter.thinking(1, "Fetching job details from listing...")
        from app.agents.job_search_agent_v2 import JobSearchAgent
        job_agent = JobSearchAgent(self.db, self.redis)
        await job_agent.set_run_id(state["run_id"])
        job_details = await job_agent.get_job_details(job_url, user_id)

        await self.emitter.thinking(2, "Tailoring your resume to this role...")
        from app.agents.resume_agent import resume_agent_node
        resume_state = AgentState(
            user_id=user_id, run_id=state["run_id"], task_type="resume_optimize",
            context={"jd_text": job_details.get("description", "")[:3000]},
            messages=[], status="running", pending_action=None, result=None, error=None,
        )
        resume_result = resume_agent_node(resume_state)
        resume_text = (resume_result.get("result") or {}).get("resume_text", "")
        ats_data = (resume_result.get("result") or {}).get("ats_score", {})

        await self.emitter.thinking(3, "Writing cover letter...")
        from app.agents.cover_letter_agent_v2 import CoverLetterAgent
        cl_agent = CoverLetterAgent(self.db, self.redis)
        await cl_agent.set_run_id(state["run_id"])
        cl_state = AgentState(
            user_id=user_id, run_id=state["run_id"], task_type="cover_letter",
            context={
                "job_description": job_details.get("description", ""),
                "company_name": job_details.get("company", ""),
                "hiring_manager": "Hiring Manager",
            },
            messages=[], status="running", pending_action=None, result=None, error=None,
        )
        cl_result_state = await cl_agent.run(cl_state)
        cl_text = (cl_result_state.get("result") or {}).get("cover_letter", "")

        await self.emitter.thinking(4, "Ready for your review before applying...")
        state = await self._hitl_checkpoint(state, "review_application_materials", {
            "resume_text": resume_text,
            "ats_score": ats_data.get("score", 0) if isinstance(ats_data, dict) else 0,
            "ats_suggestions": ats_data.get("suggestions", []) if isinstance(ats_data, dict) else [],
            "cover_letter": cl_text,
            "job_title": job_details.get("title", ""),
            "company": job_details.get("company", ""),
        })
        if state.get("status") == "awaiting_approval":
            return state

        approved_cl = ctx.get("edited_cover_letter", cl_text)
        approved_resume = ctx.get("edited_resume", resume_text)

        await self.emitter.thinking(5, "Generating PDF resume...")
        from app.tools.pdf_service import PDFService
        pdf_svc = PDFService()
        pdf_bytes = pdf_svc.generate(approved_resume)
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.write(pdf_bytes)
        tmp.close()
        resume_path = tmp.name

        platform = detect_platform(job_url)
        await self.emitter.thinking(6, f"Filling application form on {platform}...")
        from app.services.browser_control_service import BrowserControlService
        browser = BrowserControlService(user_id=user_id)
        form_filler = FormFillerService(browser)

        from app.core.sync_db import _get_sync_factory
        from app.models.db import User, UserPreferences
        from sqlalchemy import select

        user_profile: dict = {}
        factory = _get_sync_factory()
        with factory() as db:
            user_result = db.execute(select(User).where(User.id == uuid.UUID(user_id)))
            user = user_result.scalar_one_or_none()
            if user:
                user_profile = {
                    "full_name": user.full_name or "",
                    "email": user.email or "",
                    "phone": user.phone or "",
                    "linkedin_url": user.linkedin_url or "",
                }
            pref_result = db.execute(
                select(UserPreferences).where(UserPreferences.user_id == uuid.UUID(user_id))
            )
            prefs = pref_result.scalars().first()
            if prefs:
                user_profile["experience_years"] = str(prefs.years_experience or 3)
                user_profile["target_roles"] = prefs.target_roles or []

        fill_methods = {
            "linkedin": form_filler.fill_linkedin_easy_apply,
            "indeed": form_filler.fill_indeed_apply,
            "naukri": form_filler.fill_naukri,
        }
        fill_fn = fill_methods.get(platform, form_filler.fill_generic_form)
        fill_result = await fill_fn(job_url, user_id, resume_path, approved_cl, user_profile)
        await self.emitter.tool_result("form_fill", {
            "platform": platform, "screenshots": len(fill_result.get("screenshots", [])),
        })

        state = await self._hitl_checkpoint(state, "submit_application", {
            "platform": platform,
            "company": job_details.get("company", ""),
            "role": job_details.get("title", ""),
            "form_screenshots": fill_result.get("screenshots", []),
            "warning": "This will submit your application. Cannot be undone.",
        })
        if state.get("status") == "awaiting_approval":
            await browser.close()
            return state

        await self.emitter.thinking(7, "Submitting application...")
        submit_result = await form_filler.submit_application(platform, user_id)
        await browser.close()

        from app.models.db import JobApplication
        app_id = uuid.uuid4()
        with factory() as db:
            app = JobApplication(
                id=app_id, user_id=uuid.UUID(user_id),
                company=job_details.get("company", "Unknown"),
                role=job_details.get("title", "Unknown"),
                job_url=job_url, status="applied",
                applied_at=datetime.now(timezone.utc),
                jd_text=job_details.get("description", "")[:5000],
                cover_letter=approved_cl,
            )
            db.add(app)
            db.commit()

        await self.emitter.thinking(8, "Scheduling follow-up emails...")
        from app.agents.followup_agent import schedule_followups
        await schedule_followups(user_id, str(app_id), datetime.now(timezone.utc))

        result = {
            "status": "applied",
            "application_id": str(app_id),
            "company": job_details.get("company", ""),
            "role": job_details.get("title", ""),
            "confirmation_screenshot": submit_result.get("confirmation_screenshot"),
            "followups_scheduled": ["day-5", "day-12"],
        }
        await self.emitter.complete(result, 0, 0)
        state["result"] = result
        state["status"] = "completed"
        return state


async def auto_apply_pipeline_v2(state: AgentState) -> AgentState:
    import redis.asyncio as aioredis
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        redis = aioredis.from_url("redis://localhost:6379", decode_responses=True)
        try:
            agent = AutoApplyPipeline(db, redis)
            await agent.set_run_id(state["run_id"])
            return await agent.run(state)
        finally:
            await redis.aclose()
