import asyncio
import base64
import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.state import AgentState
from app.core.model_router import _build_llm
from app.services.pdf_service import generate_resume_pdf
from app.services.rag_service import retrieve

logger = logging.getLogger(__name__)

RESUME_SYSTEM_PROMPT = """You are a professional resume writer using the Google XYZ formula.
Given the candidate's experience (from context) and a job description, rewrite the resume to:
1. Mirror keywords from the JD naturally
2. Quantify achievements where possible
3. Keep bullet points under 2 lines each
4. Use strong action verbs

Return ONLY the resume text — no commentary, no markdown fences."""


def _get_model_settings(user_id: str):
    async def _fetch():
        from sqlalchemy import select

        from app.core.database import AsyncSessionLocal
        from app.models.db import UserModelSettings

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(UserModelSettings).where(
                    UserModelSettings.user_id == user_id,
                    UserModelSettings.is_active == True,  # noqa: E712
                )
            )
            return result.scalar_one_or_none()

    return asyncio.run(_fetch())


def resume_agent_node(state: AgentState) -> AgentState:
    try:
        user_id = state["user_id"]
        jd_text = state["context"].get("jd_text", "")

        model_settings = _get_model_settings(user_id)
        if not model_settings:
            raise ValueError("No active model settings configured for user")

        resume_chunks = retrieve(user_id, "resume", jd_text, model_settings, k=5)
        context_text = "\n\n".join(chunk.page_content for chunk in resume_chunks)

        llm = _build_llm(model_settings)
        response = llm.invoke([
            SystemMessage(content=RESUME_SYSTEM_PROMPT),
            HumanMessage(
                content=f"CANDIDATE CONTEXT:\n{context_text}\n\nJOB DESCRIPTION:\n{jd_text}"
            ),
        ])
        rewritten_text = response.content

        pdf_bytes = generate_resume_pdf(rewritten_text, full_name="")
        pdf_b64 = base64.b64encode(pdf_bytes).decode()

        return {
            **state,
            "status": "awaiting_approval",
            "pending_action": {
                "type": "resume_ready",
                "resume_text": rewritten_text,
                "pdf_b64": pdf_b64,
            },
            "messages": state["messages"] + [AIMessage(content=rewritten_text[:200])],
        }
    except Exception as exc:
        logger.error("Resume agent failed for user %s: %s", state.get("user_id"), exc)
        return {**state, "status": "failed", "error": str(exc)}
