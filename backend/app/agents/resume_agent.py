import base64
import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.state import AgentState
from app.core.model_router import _build_llm
from app.core.sync_db import fetch_model_settings, fetch_user_full_name
from app.services.ats_service import compute_ats_score
from app.services.pdf_service import generate_resume_pdf, generate_resume_docx

from app.services.rag_service import retrieve

logger = logging.getLogger(__name__)

# Step 1: Critical thinking — analyze and select relevant content
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
KEY_REQUIREMENTS: <comma-separated top requirements from JD>
SELECTED_PROJECTS: <list only the project names/roles to INCLUDE>
OMITTED: <what to leave out and why>
NARRATIVE: <1 sentence describing the story this resume should tell>
SKILLS_TO_EMPHASIZE: <comma-separated skills that match JD>
REASONING: <brief explanation of your selection logic>"""

# Step 2: Write the resume using only selected content
RESUME_SYSTEM_PROMPT = """You are an ATS-optimized resume writer. Your output must pass automated \
Applicant Tracking Systems (Greenhouse, Workday, Taleo, iCIMS).

CRITICAL INSTRUCTION: You have been given a THINKING ANALYSIS that tells you which projects \
and experiences to include. ONLY include what was selected. Do NOT include everything — \
a focused, relevant resume beats a comprehensive one.

STRICT FORMAT RULES:
- Single column layout only. NO tables, NO columns, NO text boxes, NO graphics.
- Use ONLY these section headers (uppercase): SUMMARY, EXPERIENCE, EDUCATION, SKILLS, CERTIFICATIONS, PROJECTS
- Dates in "Month YYYY" or "MM/YYYY" format (e.g., "Jan 2023 – Present")
- Bullet points start with strong action verbs, quantify with numbers/percentages
- Each bullet ≤ 2 lines. Use Google XYZ formula: "Accomplished [X] as measured by [Y], by doing [Z]"
- Mirror exact keywords and phrases from the job description naturally
- No headers/footers, no icons, no skill bars, no images
- Contact info on first line: Full Name, then email | phone | LinkedIn URL

CONTENT RULES:
- Lead with a 2-3 sentence SUMMARY tailored to the specific role
- EXPERIENCE: reverse chronological, 3-5 bullets per role — ONLY roles selected in thinking
- PROJECTS: ONLY include projects marked as relevant in the thinking analysis
- SKILLS: flat comma-separated list — ONLY skills identified as relevant
- Quantify achievements wherever possible (%, $, team size, time saved)

Return ONLY the resume text — no commentary, no markdown fences, no ```."""


def resume_agent_node(state: AgentState) -> AgentState:
    try:
        user_id = state["user_id"]
        jd_text = state["context"].get("jd_text", "")

        model_settings = fetch_model_settings(user_id)
        if not model_settings:
            raise ValueError("No active model settings configured for user")

        full_name = fetch_user_full_name(user_id)
        template = state["context"].get("template", "modern")

        resume_chunks = retrieve(user_id, "resume", jd_text, model_settings, k=8)
        context_text = "\n\n".join(chunk.page_content for chunk in resume_chunks)

        llm = _build_llm(model_settings)

        # ── Step 1: Critical Thinking — select relevant content ──────
        thinking_response = llm.invoke([
            SystemMessage(content="You are a strategic resume analyst. Think critically."),
            HumanMessage(content=THINKING_PROMPT.format(context=context_text, jd=jd_text)),
        ])
        thinking_output = thinking_response.content

        # ── Step 2: Write resume using only selected content ─────────
        response = llm.invoke([
            SystemMessage(content=RESUME_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"THINKING ANALYSIS (follow this selection):\n{thinking_output}\n\n"
                    f"CANDIDATE CONTEXT:\n{context_text}\n\n"
                    f"JOB DESCRIPTION:\n{jd_text}"
                )
            ),
        ])
        rewritten_text = response.content

        # Generate PDF and DOCX
        pdf_bytes = generate_resume_pdf(rewritten_text, full_name=full_name, template=template)
        pdf_b64 = base64.b64encode(pdf_bytes).decode()
        docx_bytes = generate_resume_docx(rewritten_text, full_name=full_name)
        docx_b64 = base64.b64encode(docx_bytes).decode()

        # ATS validation
        ats_result = None
        if jd_text:
            ats = compute_ats_score(rewritten_text, jd_text)
            ats_result = {
                "composite_score": ats.composite_score,
                "keyword_score": ats.keyword_score,
                "readability_score": ats.readability_score,
                "format_score": ats.format_score,
                "missing_keywords": ats.missing_keywords[:10],
                "suggestions": ats.suggestions[:5],
            }

        return {
            **state,
            "status": "awaiting_approval",
            "pending_action": {
                "type": "resume_ready",
                "resume_text": rewritten_text,
                "pdf_b64": pdf_b64,
                "docx_b64": docx_b64,
                "ats_score": ats_result,
                "thinking": thinking_output,
            },
            "messages": state["messages"] + [AIMessage(content=rewritten_text[:200])],
        }
    except Exception as exc:
        logger.error("Resume agent failed for user %s: %s", state.get("user_id"), exc)
        return {**state, "status": "failed", "error": str(exc)}
