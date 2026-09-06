import logging

from langchain_core.messages import AIMessage

from app.agents._llm_json import call_llm_json
from app.agents.prompts.resume_prompt import OUTPUT_SCHEMA as ResumeOutput
from app.agents.prompts.resume_prompt import SYSTEM_PROMPT as RESUME_JSON_SYSTEM_PROMPT
from app.agents.prompts.resume_prompt import build_user_prompt as build_resume_json_prompt
from app.agents.state import AgentState
from app.services.ats_service import compute_ats_score
from app.services.pdf_service import generate_resume_pdf
from app.services.rag_service import retrieve
from app.services.storage_service import upload_file

logger = logging.getLogger(__name__)


# ── Fallback (used when LLM is unavailable) ─────────────────────
def _fallback_resume_text(context_text: str, full_name: str | None, jd_text: str) -> str:
    name = full_name or "Candidate"
    source = context_text.strip() or "Resume context not available."
    summary = (
        f"{name}\n\nSUMMARY\n"
        "Software professional focused on practical delivery and reliable product outcomes."
    )
    if jd_text:
        summary += " Resume draft aligned to supplied job description keywords."
    return f"{summary}\n\nEXPERIENCE\n{source[:1800]}\n\nSKILLS\nSoftware engineering, collaboration, delivery\n"


def _persist_resume_document(
    user_id: str,
    full_name: str | None,
    template: str,
    parsed: "ResumeOutput",
    jd_text: str,
    pdf_bytes: bytes,
) -> str:
    """Upload the tailored PDF to storage and record a UserDocument row.

    Returns the new document id (str). No base64 is ever returned or stored —
    downloads go through GET /resume/download/{document_id}.
    """
    from app.core.sync_db import _get_sync_factory, _to_uuid
    from app.models.db import UserDocument
    from app.services.storage_service import delete_file

    storage_path = upload_file(user_id, "resume.pdf", pdf_bytes, "application/pdf")
    factory = _get_sync_factory()
    try:
        with factory() as session:
            doc = UserDocument(
                user_id=_to_uuid(user_id),
                doc_type="resume_tailored",
                filename="resume.pdf",
                storage_path=storage_path,
                raw_text=parsed.resume_markdown,
                ats_score=parsed.ats_score,
                ats_data={
                    "keywords_matched": parsed.keywords_matched,
                    "keywords_missing": parsed.keywords_missing,
                },
            )
            session.add(doc)
            session.commit()
            return str(doc.id)
    except Exception:
        try:
            delete_file(storage_path, user_id)
        except Exception as cleanup_exc:
            logger.warning("Orphan storage cleanup failed for %s: %s", storage_path, cleanup_exc)
        raise


def _score_parsed_resume(parsed: "ResumeOutput", jd_text: str) -> "ResumeOutput":
    """Overwrite the self-graded ATS score with the real computed score."""
    if not jd_text:
        return parsed
    ats = compute_ats_score(parsed.resume_markdown, jd_text)
    parsed.ats_score = ats.composite_score
    if getattr(ats, "missing_keywords", None):
        parsed.keywords_missing = list(ats.missing_keywords[:10])
    return parsed


def _resume_pending_action(parsed: "ResumeOutput", pdf_document_id: str | None) -> dict:
    """Pending/review payload: schema dump + document id. No binary data."""
    result: dict = parsed.model_dump()
    result["type"] = "resume_ready"
    result["pdf_document_id"] = pdf_document_id
    return result


# ── LangGraph node (registered in the orchestrator) ──
def resume_agent_node(state: AgentState) -> AgentState:
    """LangGraph node: tailors the resume via prompts/resume_prompt + JSON parsing.

    All prompt text lives in app/agents/prompts/resume_prompt.py. The result
    equals OUTPUT_SCHEMA.model_dump() + {"pdf_document_id"}. No binary data
    is placed in state, SSE events, or the DB — the PDF is stored in
    Supabase Storage and downloaded via GET /resume/download/{document_id}.
    """
    from app.core.sync_db import fetch_model_settings, fetch_user_full_name
    from app.core.model_router import _build_llm
    from app.core.event_bus import emit

    run_id = state["run_id"]
    user_id = state["user_id"]
    ctx = state.get("context", {})
    jd_text = ctx.get("jd_text", ctx.get("job_description", ""))
    tone = ctx.get("tone", "professional")
    full_name = None
    template = ctx.get("template", "modern")

    try:
        emit(run_id, "thinking", {"step": "start", "message": "Retrieving resume context from RAG..."})
        model_settings = fetch_model_settings(user_id)
        if not model_settings:
            raise ValueError("No active model settings configured for user")

        full_name = fetch_user_full_name(user_id)

        emit(run_id, "tool_call", {"tool": "rag_retrieve", "input": {"doc_type": "resume", "query_len": len(jd_text)}})
        resume_chunks = retrieve(user_id, "resume", jd_text, model_settings, k=8)
        chunk_texts = [c.page_content if hasattr(c, "page_content") else str(c) for c in resume_chunks]
        emit(run_id, "tool_result", {"tool": "rag_retrieve", "output": {"chunks": len(resume_chunks)}})

        llm = _build_llm(model_settings)

        emit(run_id, "thinking", {"step": "tailor", "message": "Tailoring resume to job description..."})
        parsed = call_llm_json(
            llm,
            RESUME_JSON_SYSTEM_PROMPT,
            build_resume_json_prompt(
                {"jd_text": jd_text, "tone": tone, "template": template},
                chunk_texts,
            ),
            ResumeOutput,
        )
        parsed = _score_parsed_resume(parsed, jd_text)

        emit(run_id, "thinking", {"step": "pdf", "message": "Generating PDF and storing..."})
        emit(run_id, "tool_call", {"tool": "pdf_store", "input": {"template": template}})
        pdf_bytes = generate_resume_pdf(parsed.resume_markdown, full_name=full_name, template=template)
        try:
            pdf_document_id = _persist_resume_document(
                user_id, full_name, template, parsed, jd_text, pdf_bytes
            )
        except Exception as se:
            logger.warning("Resume PDF persist failed, continuing without download: %s", se)
            pdf_document_id = None
            parsed.warnings = list(parsed.warnings or []) + ["PDF storage unavailable — preview only."]
        emit(run_id, "tool_result", {"tool": "pdf_store", "output": {"pdf_document_id": pdf_document_id}})

        pending = _resume_pending_action(parsed, pdf_document_id)
        emit(run_id, "complete", {"result": pending})
        return {
            **state,
            "status": "awaiting_approval",
            "pending_action": pending,
            "result": pending,
            "messages": state.get("messages", []) + [AIMessage(content=parsed.resume_markdown[:200])],
        }
    except Exception as exc:
        logger.error("Resume agent failed for user %s: %s", user_id, exc)
        emit(run_id, "thinking", {"step": "fallback", "message": "Live LLM call failed — using fallback resume draft."})
        fallback_text = _fallback_resume_text("", full_name, jd_text)
        fallback = _score_parsed_resume(
            ResumeOutput(
                resume_markdown=fallback_text,
                summary="Fallback draft — live model call failed.",
                ats_score=0,
                keywords_matched=[],
                keywords_missing=[],
                changes_made=[],
                warnings=["LLM unavailable; showing extractive fallback."],
            ),
            jd_text,
        )
        try:
            pdf_bytes = generate_resume_pdf(fallback.resume_markdown, full_name=full_name, template=template)
            try:
                pdf_document_id = _persist_resume_document(
                    user_id, full_name, template, fallback, jd_text, pdf_bytes
                )
            except Exception as se:
                logger.warning("Fallback PDF persist failed, continuing without download: %s", se)
                pdf_document_id = None
                fallback.warnings = list(fallback.warnings or []) + ["PDF storage unavailable — preview only."]
        except Exception as se:
            logger.warning("Fallback PDF generation failed: %s", se)
            return {**state, "status": "error", "error": str(se)}
        emit(run_id, "complete", {"result": _resume_pending_action(fallback, pdf_document_id)})
        return {
            **state,
            "status": "awaiting_approval",
            "pending_action": _resume_pending_action(fallback, pdf_document_id),
            "result": _resume_pending_action(fallback, pdf_document_id),
            "messages": state.get("messages", []) + [AIMessage(content="Resume fallback draft ready for review.")],
        }
