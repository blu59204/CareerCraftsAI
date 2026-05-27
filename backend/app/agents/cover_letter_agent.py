"""
cover_letter_agent.py — LangGraph node for personalized cover letter generation.

Uses RAG context (top 5 resume chunks) and the job description to generate
a cover letter in the user's chosen tone (formal/casual/bold). The result
is stored in `user_documents` and `cover_letter_versions`, logged to
`agent_runs`, and returned with `awaiting_approval` status for HITL gate.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.state import AgentState
from app.core.model_router import _build_llm
from app.core.sync_db import _get_sync_factory, fetch_model_settings
from app.services.rag_service import retrieve

logger = logging.getLogger(__name__)

VALID_TONES = {"formal", "casual", "bold"}

SYSTEM_PROMPTS = {
    "formal": (
        "You are a professional cover letter writer. Write in a polished, formal tone. "
        "Use complete sentences, professional language, and maintain a respectful distance. "
        "Avoid slang or overly casual phrasing."
    ),
    "casual": (
        "You are a cover letter writer with a friendly, approachable style. Write in a "
        "conversational yet professional tone. Be personable and warm while still "
        "demonstrating competence and enthusiasm."
    ),
    "bold": (
        "You are a cover letter writer with a confident, assertive style. Write with "
        "strong conviction, lead with impact statements, and make bold claims backed by "
        "evidence. Be direct and memorable."
    ),
}

BASE_SYSTEM_PROMPT = """
Given the candidate's resume context and a job description, write a compelling cover letter that:
1. Opens with a strong hook relevant to the specific role
2. Connects the candidate's experience directly to job requirements
3. Highlights 2-3 key achievements that demonstrate fit
4. Closes with a confident call to action

Return ONLY the cover letter text — no commentary, no markdown fences, no subject line."""


def _build_cover_letter_prompt(resume_chunks_text: str, jd_text: str, tone: str) -> list:
    """Build the message list for cover letter generation."""
    system_content = SYSTEM_PROMPTS[tone] + "\n\n" + BASE_SYSTEM_PROMPT
    user_content = (
        f"CANDIDATE RESUME CONTEXT:\n{resume_chunks_text}\n\n"
        f"JOB DESCRIPTION:\n{jd_text}\n\n"
        f"Write the cover letter in a {tone} tone."
    )
    return [
        SystemMessage(content=system_content),
        HumanMessage(content=user_content),
    ]


def _store_cover_letter(
    user_id: str,
    job_application_id: str,
    cover_letter_text: str,
    tone: str,
) -> dict:
    """
    Store the generated cover letter in user_documents and cover_letter_versions.
    Returns dict with document_id, version_number.
    """
    from sqlalchemy import func, select, update

    from app.models.db import CoverLetterVersion, JobApplication, UserDocument

    factory = _get_sync_factory()
    with factory() as db:
        # Create user_documents entry
        doc_id = uuid.uuid4()
        doc = UserDocument(
            id=doc_id,
            user_id=user_id,
            doc_type="cover_letter",
            filename=f"cover_letter_{tone}_{doc_id.hex[:8]}.txt",
            storage_path=f"cover_letters/{user_id}/{doc_id}.txt",
            raw_text=cover_letter_text,
            is_primary=False,
        )
        db.add(doc)

        # Determine next version number for this application
        version_result = db.execute(
            select(func.coalesce(func.max(CoverLetterVersion.version_number), 0)).where(
                CoverLetterVersion.job_application_id == job_application_id
            )
        )
        next_version = version_result.scalar() + 1

        # Create cover_letter_versions entry
        version = CoverLetterVersion(
            id=uuid.uuid4(),
            user_id=user_id,
            job_application_id=job_application_id,
            document_id=doc_id,
            tone=tone,
            version_number=next_version,
        )
        db.add(version)

        # Update job_applications.cover_letter_id to point to latest
        db.execute(
            update(JobApplication)
            .where(JobApplication.id == job_application_id)
            .values(cover_letter_id=doc_id)
        )

        db.commit()

        return {
            "document_id": str(doc_id),
            "version_number": next_version,
        }


def _log_agent_run(
    user_id: str,
    status: str,
    input_data: dict,
    output_data: dict | None,
    tokens_used: int | None,
    duration_ms: int,
) -> str:
    """Log this run to agent_runs table. Returns run ID."""
    from app.models.db import AgentRun

    factory = _get_sync_factory()
    run_id = uuid.uuid4()
    with factory() as db:
        run = AgentRun(
            id=run_id,
            user_id=user_id,
            agent_type="cover_letter",
            status=status,
            input=input_data,
            output=output_data,
            tokens_used=tokens_used,
            duration_ms=duration_ms,
            completed_at=datetime.now(timezone.utc) if status != "running" else None,
        )
        db.add(run)
        db.commit()
    return str(run_id)


def cover_letter_node(state: AgentState) -> AgentState:
    """LangGraph node for cover letter generation."""
    start_ts = time.monotonic()

    try:
        user_id = state["user_id"]
        context = state["context"]
        tone = context.get("tone", "formal")
        job_application_id = context.get("job_application_id")
        jd_text = context.get("jd_text", "")

        # Validate tone
        if tone not in VALID_TONES:
            return {
                **state,
                "status": "failed",
                "error": f"Invalid tone: '{tone}'. Must be one of: formal, casual, bold",
            }

        # Validate job_application_id is provided
        if not job_application_id:
            return {
                **state,
                "status": "failed",
                "error": "job_application_id is required",
            }

        # Get model settings
        model_settings = fetch_model_settings(user_id)
        if not model_settings:
            return {
                **state,
                "status": "failed",
                "error": "No active model configured. Add a model in Settings.",
            }

        # Check primary resume exists
        from app.core.sync_db import fetch_user_profile_text

        primary_resume_text = fetch_user_profile_text(user_id)
        if not primary_resume_text:
            return {
                **state,
                "status": "failed",
                "error": "No primary resume found. Please upload a resume first.",
            }

        # Retrieve top 5 resume chunks via RAG
        resume_chunks = retrieve(user_id, "resume", jd_text, model_settings, k=5)
        context_text = "\n\n".join(chunk.page_content for chunk in resume_chunks)

        # If RAG returns nothing, fall back to the raw profile text
        if not context_text.strip():
            context_text = primary_resume_text

        # ── Think: Which achievements to highlight, what angle ────────
        from app.agents.thinking import think_and_select
        llm = _build_llm(model_settings)

        thinking = think_and_select(
            llm=llm,
            task_description=f"Write a {tone} cover letter for this job application",
            user_context=context_text,
            target_context=jd_text,
            selection_criteria="Which 2-3 achievements create the strongest case? What's the unique hook?",
        )

        # Build prompt and invoke LLM via model_router
        messages = _build_cover_letter_prompt(context_text, jd_text, tone)
        # Inject thinking into the user message
        messages[-1] = HumanMessage(
            content=(
                f"STRATEGIC THINKING (follow this):\n{thinking}\n\n"
                f"{messages[-1].content}"
            )
        )
        response = llm.invoke(messages)
        cover_letter_text = response.content

        # Extract token usage if available
        tokens_used = None
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            tokens_used = response.usage_metadata.get("total_tokens")

        duration_ms = int((time.monotonic() - start_ts) * 1000)

        # Store in user_documents and cover_letter_versions
        store_result = _store_cover_letter(
            user_id=user_id,
            job_application_id=job_application_id,
            cover_letter_text=cover_letter_text,
            tone=tone,
        )

        # Log to agent_runs
        _log_agent_run(
            user_id=user_id,
            status="awaiting_approval",
            input_data={
                "job_application_id": str(job_application_id),
                "tone": tone,
                "jd_text_length": len(jd_text),
            },
            output_data={
                "document_id": store_result["document_id"],
                "version_number": store_result["version_number"],
                "content_length": len(cover_letter_text),
            },
            tokens_used=tokens_used,
            duration_ms=duration_ms,
        )

        return {
            **state,
            "status": "awaiting_approval",
            "pending_action": {
                "type": "cover_letter_review",
                "content": cover_letter_text,
                "tone": tone,
                "job_application_id": str(job_application_id),
                "document_id": store_result["document_id"],
                "version_number": store_result["version_number"],
            },
            "messages": state["messages"] + [AIMessage(content=cover_letter_text[:200])],
        }

    except Exception as exc:
        duration_ms = int((time.monotonic() - start_ts) * 1000)
        logger.error("Cover letter agent failed for user %s: %s", state.get("user_id"), exc)

        # Log failure to agent_runs
        try:
            _log_agent_run(
                user_id=state["user_id"],
                status="failed",
                input_data={"context": str(state.get("context", {}))[:500]},
                output_data=None,
                tokens_used=None,
                duration_ms=duration_ms,
            )
        except Exception:
            logger.warning("Failed to log agent_run for cover letter failure")

        return {**state, "status": "failed", "error": str(exc)}
