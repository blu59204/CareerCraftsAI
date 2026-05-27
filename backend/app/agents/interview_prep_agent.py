import logging

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.state import AgentState
from app.core.model_router import _build_llm
from app.core.sync_db import fetch_model_settings
from app.services.rag_service import retrieve

logger = logging.getLogger(__name__)

_QUESTIONS_PROMPT = """You are an expert interview coach. Generate interview preparation materials for the following candidate.

Target Role: {role}
Company: {company}
Candidate Background (from resume):
{context}

STRATEGIC ANALYSIS (use this to tailor questions):
{thinking}

Generate exactly this structure:
1. Five behavioral questions (STAR format) tailored to the role — focus on the candidate's RELEVANT experiences only
2. Five technical/domain questions for this role — target likely weak spots and strengths
3. Three questions the candidate should ask the interviewer — show strategic thinking
4. One 60-second elevator pitch based on the candidate's STRONGEST relevant background

Format your response as JSON with keys:
  behavioral_questions, technical_questions, questions_to_ask, elevator_pitch

Return ONLY valid JSON, no markdown fences."""


def interview_prep_agent_node(state: AgentState) -> AgentState:
    try:
        import json

        user_id = state["user_id"]
        ctx = state["context"]
        target_role = ctx.get("target_role", ctx.get("role", "software engineer"))
        company = ctx.get("company", "the company")

        model_settings = fetch_model_settings(user_id)
        if not model_settings:
            raise ValueError("No active model settings configured for user")

        chunks = retrieve(user_id, "resume", target_role, model_settings, k=5)
        context_text = "\n".join(c.page_content for c in chunks) if chunks else "No resume context available."

        llm = _build_llm(model_settings)

        # ── Think: What are the candidate's strengths/gaps for this role ──
        from app.agents.thinking import think_and_select
        thinking = think_and_select(
            llm=llm,
            task_description=f"Prepare interview for {target_role} at {company}",
            user_context=context_text,
            target_context=f"Role: {target_role}, Company: {company}",
            selection_criteria="What are the candidate's strongest stories? Where are the gaps they'll be questioned on?",
        )

        response = llm.invoke([
            HumanMessage(
                content=_QUESTIONS_PROMPT.format(
                    role=target_role,
                    company=company,
                    context=context_text,
                    thinking=thinking,
                )
            )
        ])

        raw = response.content.strip()
        # Strip markdown fences robustly (handles trailing ```)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rstrip("`").strip()
        try:
            prep_data = json.loads(raw)
        except json.JSONDecodeError as exc:
            return {
                **state,
                "status": "failed",
                "error": f"interview_prep_agent: LLM returned non-JSON response: {exc}",
            }

        return {
            **state,
            "status": "completed",
            "result": {
                "type": "interview_prep",
                "target_role": target_role,
                "company": company,
                **prep_data,
            },
            "messages": state["messages"] + [
                AIMessage(content=f"Interview prep ready for {target_role} at {company}.")
            ],
        }
    except Exception as exc:
        logger.error("Interview prep agent failed for user %s: %s", state.get("user_id"), exc)
        return {**state, "status": "failed", "error": str(exc)}
