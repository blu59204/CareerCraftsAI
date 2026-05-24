import asyncio
import logging

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.state import AgentState
from app.core.model_router import _build_llm
from app.services.rag_service import retrieve

logger = logging.getLogger(__name__)

_HEADLINE_PROMPT = (
    "Write a LinkedIn headline (max 220 chars) for this candidate targeting: {role}. "
    "Context: {context}. Return ONLY the headline text, no explanation."
)
_ABOUT_PROMPT = (
    "Write a LinkedIn About section (max 2600 chars, 3 paragraphs) targeting: {role}. "
    "Context: {context}. Return ONLY the about text."
)
_BULLETS_PROMPT = (
    "Write 5 LinkedIn experience bullet points using the STAR method targeting: {role}. "
    "Context: {context}. Return ONLY the bullets, one per line starting with •."
)


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


def linkedin_agent_node(state: AgentState) -> AgentState:
    try:
        user_id = state["user_id"]
        target_role = state["context"].get("target_role", "software engineer")

        model_settings = _get_model_settings(user_id)
        if not model_settings:
            raise ValueError("No active model settings configured for user")

        chunks = retrieve(user_id, "resume", target_role, model_settings, k=5)
        context_text = "\n".join(c.page_content for c in chunks)

        llm = _build_llm(model_settings)

        headline = llm.invoke([
            HumanMessage(
                content=_HEADLINE_PROMPT.format(
                    role=target_role, context=context_text
                )
            )
        ]).content

        about = llm.invoke([
            HumanMessage(
                content=_ABOUT_PROMPT.format(
                    role=target_role, context=context_text
                )
            )
        ]).content

        bullets = llm.invoke([
            HumanMessage(
                content=_BULLETS_PROMPT.format(
                    role=target_role, context=context_text
                )
            )
        ]).content

        return {
            **state,
            "status": "awaiting_approval",
            "pending_action": {
                "type": "linkedin_edits",
                "headline": headline.strip(),
                "about": about.strip(),
                "experience_bullets": bullets.strip(),
            },
            "messages": state["messages"] + [
                AIMessage(content="LinkedIn sections ready for review.")
            ],
        }
    except Exception as exc:
        logger.error(
            "LinkedIn agent failed for user %s: %s", state.get("user_id"), exc
        )
        return {**state, "status": "failed", "error": str(exc)}
