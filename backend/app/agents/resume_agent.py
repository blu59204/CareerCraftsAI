import base64
import logging
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState
from app.services.ats_service import compute_ats_score
from app.services.pdf_service import generate_resume_pdf, generate_resume_docx
from app.services.rag_service import retrieve
from app.services.storage_service import upload_file

logger = logging.getLogger(__name__)

THINKING_PROMPT = """You are a strategic resume consultant. Your job is to THINK critically about \
which parts of the candidate's background are most relevant to this specific job.

CANDIDATE'S FULL BACKGROUND:
{context}

JOB DESCRIPTION:
{jd}

CRITICAL THINKING TASK:
1. Identify the top 3-5 requirements from the JD (must-haves)
2. For each project/experience the candidate has, score its relevance (HIGH/MEDIUM/LOW)
3. Select ONLY the projects and experiences that are HIGH or MEDIUM relevance
4. Identify which skills to emphasize and which to omit
5. Decide the best narrative angle (what story does this resume tell?)

RESPOND IN THIS FORMAT:
KEY_REQUIREMENTS: <comma-separated>
SELECTED_PROJECTS: <list only the project names to INCLUDE>
OMITTED: <what to leave out and why>
NARRATIVE: <1 sentence>
SKILLS_TO_EMPHASIZE: <comma-separated skills matching JD>
REASONING: <brief explanation>"""

RESUME_SYSTEM_PROMPT = """You are an ATS-optimized resume writer. Your output must pass automated \
Applicant Tracking Systems (Greenhouse, Workday, Taleo, iCIMS).

Use ONLY the provided RAG context and job description to tailor.

STRICT FORMAT RULES:
- Single column layout only. NO tables, columns, text boxes, graphics.
- Use ONLY: SUMMARY, EXPERIENCE, EDUCATION, SKILLS, CERTIFICATIONS, PROJECTS
- Dates in "Month YYYY" — bullet points with action verbs + numbers/percentages
- Mirror keywords from JD naturally. Contact on first line.

Return ONLY the resume text — no commentary, no markdown fences.

CANDIDATE BACKGROUND:
{rag_context}

JOB DESCRIPTION:
{job_desc}

TONE: {tone}"""

TOKEN_BUDGET = 4000


# ── Pure function for prompt building ───────────────────────────
def build_resume_prompt(chunks, job_desc: str, tone: str) -> list:
    rag_context = "\n\n".join(
        chunk.page_content if hasattr(chunk, "page_content") else str(chunk)
        for chunk in chunks
    )
    return [
        SystemMessage(content=RESUME_SYSTEM_PROMPT.format(
            rag_context=rag_context, job_desc=job_desc, tone=tone,
        )),
        HumanMessage(content="Generate the tailored resume. Output only the resume text."),
    ]


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


def _resume_pending_action(
    rewritten_text: str, full_name: str | None, template: str,
    jd_text: str, thinking_output: str,
    pdf_path: str | None = None, docx_path: str | None = None,
    pdf_b64: str | None = None,
) -> dict:
    result: dict = {
        "type": "resume_ready",
        "resume_text": rewritten_text,
        "thinking": thinking_output,
    }
    if pdf_path:
        result["pdf_path"] = pdf_path
    if docx_path:
        result["docx_path"] = docx_path
    if pdf_b64:
        result["pdf_b64"] = pdf_b64
    if jd_text:
        ats = compute_ats_score(rewritten_text, jd_text)
        result["ats_score"] = {
            "composite_score": ats.composite_score,
            "keyword_score": ats.keyword_score,
            "readability_score": ats.readability_score,
            "format_score": ats.format_score,
            "missing_keywords": ats.missing_keywords[:10],
            "suggestions": ats.suggestions[:5],
        }
    return result


# ── Class-based ResumeAgent (BaseAgent) ─────────────────────────
class ResumeAgent(BaseAgent):
    async def run(self, state: AgentState) -> AgentState:
        await self.set_run_id(state["run_id"])
        user_id = state["user_id"]
        ctx = state.get("context", {})
        jd_text = ctx.get("jd_text", ctx.get("job_description", ""))
        tone = ctx.get("tone", "professional")
        full_name = ctx.get("full_name")
        template = ctx.get("template", "modern")
        context_text = ""
        tokens_used = 0

        try:
            # Load model_settings for RAG / LLM
            from app.core.sync_db import fetch_model_settings
            model_settings = fetch_model_settings(user_id)
            if not model_settings:
                raise ValueError("No active model settings configured for user")

            # Step 1: RAG retrieval
            await self.emitter.thinking(1, "Retrieving your resume and achievements from memory...")
            resume_chunks = retrieve(user_id, "resume", jd_text, model_settings, k=5)
            context_text = "\n\n".join(
                chunk.page_content if hasattr(chunk, "page_content") else str(chunk)
                for chunk in resume_chunks
            )
            await self.emitter.tool_result("rag_retrieve", {
                "chunks": len(resume_chunks),
            })

            # Step 2: Generate tailored resume
            await self.emitter.thinking(2, "Tailoring resume to job description...")
            llm = await self._get_llm(user_id)
            prompt = build_resume_prompt(resume_chunks, jd_text, tone)
            response = await llm.ainvoke(prompt, config={"max_tokens": TOKEN_BUDGET})
            resume_text = response.content
            if hasattr(response, "usage_metadata"):
                tokens_used = response.usage_metadata.get("total_tokens", 0)

            # Step 3: ATS scoring
            await self.emitter.thinking(3, "Scoring resume against ATS criteria...")
            ats_result = compute_ats_score(resume_text, jd_text)
            await self.emitter.tool_result("ats_score", {
                "composite": ats_result.composite_score,
                "keyword": ats_result.keyword_score,
                "missing_keywords": ats_result.missing_keywords[:5],
            })

            # Step 4: PDF generation + upload
            await self.emitter.thinking(4, "Generating PDF and storing...")
            pdf_bytes = generate_resume_pdf(resume_text, full_name=full_name, template=template)
            docx_bytes = generate_resume_docx(resume_text, full_name=full_name)

            pdf_path = None
            docx_path = None
            try:
                pdf_path = upload_file(user_id, "resume.pdf", pdf_bytes, "application/pdf")
                docx_path = upload_file(user_id, "resume.docx", docx_bytes,
                                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            except Exception as se:
                logger.warning("Storage upload failed: %s", se)

            doc_id = str(uuid4())
            result = {
                "document_id": doc_id,
                "resume_text": resume_text,
                "ats_score": ats_result.composite_score,
                "ats_suggestions": ats_result.suggestions[:5] if ats_result.suggestions else [],
                "download_url": f"/api/v1/resume/download/{doc_id}",
                "pdf_path": pdf_path,
                "docx_path": docx_path,
            }

            await self.emitter.complete(result, tokens_used, 0)
            state["result"] = result
            state["tokens_used"] = tokens_used
            state["status"] = "completed"
            return state

        except Exception as exc:
            logger.error("ResumeAgent failed for user %s: %s", user_id, exc)
            fallback_text = _fallback_resume_text(context_text, full_name, jd_text)
            await self.emitter.thinking(0, "LLM unavailable — using fallback resume draft.")
            pending = _resume_pending_action(
                fallback_text, full_name, template, jd_text,
                "Fallback draft — live model call failed.",
            )
            return {
                **state,
                "status": "awaiting_approval",
                "pending_action": pending,
                "messages": state.get("messages", []) + [
                    AIMessage(content="Resume fallback draft ready for review.")
                ],
            }


# ── Node function for LangGraph compatibility (existing orchestrator) ──
def resume_agent_node(state: AgentState) -> AgentState:
    """LangGraph node: wraps ResumeAgent.run() for the existing orchestrator."""
    from app.services.sse_service import SSEPublisher
    from app.core.sync_db import fetch_model_settings, fetch_user_full_name
    from app.core.model_router import _build_llm
    from app.core.event_bus import emit

    run_id = state["run_id"]
    user_id = state["user_id"]
    ctx = state.get("context", {})
    jd_text = ctx.get("jd_text", "")
    full_name = None
    template = ctx.get("template", "modern")
    context_text = ""

    try:
        emit(run_id, "thinking", {"text": "Retrieving resume context from RAG..."})
        model_settings = fetch_model_settings(user_id)
        if not model_settings:
            raise ValueError("No active model settings configured for user")

        full_name = fetch_user_full_name(user_id)

        emit(run_id, "tool_call", {"tool_name": "rag_retrieve", "input": {"doc_type": "resume", "query_len": len(jd_text)}})
        resume_chunks = retrieve(user_id, "resume", jd_text, model_settings, k=8)
        context_text = "\n\n".join(chunk.page_content for chunk in resume_chunks)
        emit(run_id, "tool_result", {"tool_name": "rag_retrieve", "output": {"chunks": len(resume_chunks)}})

        llm = _build_llm(model_settings)

        emit(run_id, "thinking", {"text": "Analyzing job requirements and selecting relevant experience..."})
        thinking_response = llm.invoke([
            SystemMessage(content="You are a strategic resume analyst. Think critically."),
            HumanMessage(content=THINKING_PROMPT.format(context=context_text, jd=jd_text)),
        ])
        thinking_output = thinking_response.content

        emit(run_id, "thinking", {"text": "Writing ATS-optimized resume..."})
        response = llm.invoke([
            SystemMessage(content=RESUME_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"THINKING ANALYSIS:\n{thinking_output}\n\n"
                f"CANDIDATE CONTEXT:\n{context_text}\n\n"
                f"JOB DESCRIPTION:\n{jd_text}"
            )),
        ])
        rewritten_text = response.content

        emit(run_id, "thinking", {"text": "Scoring against ATS criteria..."})
        emit(run_id, "tool_call", {"tool_name": "ats_score", "input": {"text_len": len(rewritten_text)}})

        pdf_bytes = generate_resume_pdf(rewritten_text, full_name=full_name, template=template)
        docx_bytes = generate_resume_docx(rewritten_text, full_name=full_name)

        pdf_path = None
        docx_path = None
        try:
            pdf_path = upload_file(user_id, "resume.pdf", pdf_bytes, "application/pdf")
            docx_path = upload_file(user_id, "resume.docx", docx_bytes,
                                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            emit(run_id, "tool_result", {"tool_name": "ats_score", "output": {"pdf_stored": True, "docx_stored": True}})
        except Exception as se:
            logger.warning("Storage upload failed: %s", se)
            emit(run_id, "tool_result", {"tool_name": "ats_score", "output": {"storage_error": str(se)}})

        try:
            pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        except Exception:
            pdf_b64 = None
        pending = _resume_pending_action(rewritten_text, full_name, template, jd_text, thinking_output,
                                         pdf_path=pdf_path, docx_path=docx_path, pdf_b64=pdf_b64)
        return {
            **state,
            "status": "awaiting_approval",
            "pending_action": pending,
            "messages": state.get("messages", []) + [AIMessage(content=rewritten_text[:200])],
        }
    except Exception as exc:
        logger.error("Resume agent failed for user %s: %s", user_id, exc)
        fallback_text = _fallback_resume_text(context_text, full_name, jd_text)
        emit(run_id, "thinking", {"text": "Live LLM call failed — using fallback resume draft."})
        return {
            **state,
            "status": "awaiting_approval",
            "pending_action": _resume_pending_action(
                fallback_text, full_name, template, jd_text,
                "Fallback draft — live model call failed.",
            ),
            "messages": state.get("messages", []) + [AIMessage(content="Resume fallback draft ready for review.")],
        }
