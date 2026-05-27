import logging

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.state import AgentState
from app.agents.thinking import think_and_select
from app.core.model_router import _build_llm
from app.core.sync_db import fetch_model_settings
from app.services.rag_service import retrieve

logger = logging.getLogger(__name__)

_HEADLINE_PROMPT = (
    "Write a LinkedIn headline (max 220 chars) for this candidate targeting: {role}. "
    "Strategic direction: {thinking}\n"
    "Context: {context}. Return ONLY the headline text, no explanation."
)
_ABOUT_PROMPT = (
    "Write a LinkedIn About section (max 2600 chars, 3 paragraphs) targeting: {role}. "
    "Strategic direction: {thinking}\n"
    "Context: {context}. Return ONLY the about text."
)
_BULLETS_PROMPT = (
    "Write 5 LinkedIn experience bullet points using the STAR method targeting: {role}. "
    "ONLY include experiences relevant to this role (per thinking analysis): {thinking}\n"
    "Context: {context}. Return ONLY the bullets, one per line starting with •."
)


def linkedin_agent_node(state: AgentState) -> AgentState:
    try:
        user_id = state["user_id"]
        target_role = state["context"].get("target_role", "software engineer")

        model_settings = fetch_model_settings(user_id)
        if not model_settings:
            raise ValueError("No active model settings configured for user")

        chunks = retrieve(user_id, "resume", target_role, model_settings, k=5)
        context_text = "\n".join(c.page_content for c in chunks)

        llm = _build_llm(model_settings)

        # ── Think: Which experiences to highlight, what narrative ─────
        thinking = think_and_select(
            llm=llm,
            task_description=f"Optimize LinkedIn profile for {target_role}",
            user_context=context_text,
            target_context=f"Target role: {target_role}",
            selection_criteria="Which experiences/skills are most relevant? What narrative positions this person best?",
        )

        headline = llm.invoke([
            HumanMessage(
                content=_HEADLINE_PROMPT.format(
                    role=target_role, context=context_text, thinking=thinking
                )
            )
        ]).content

        about = llm.invoke([
            HumanMessage(
                content=_ABOUT_PROMPT.format(
                    role=target_role, context=context_text, thinking=thinking
                )
            )
        ]).content

        bullets = llm.invoke([
            HumanMessage(
                content=_BULLETS_PROMPT.format(
                    role=target_role, context=context_text, thinking=thinking
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
                "thinking": thinking,
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
