from __future__ import annotations

from pydantic import BaseModel, Field

from . import _COMMON

SYSTEM_PROMPT = _COMMON + """
You are an expert resume writer and ATS specialist. Tailor the candidate's resume to the target job description. Preserve every real fact; rewrite bullets to mirror the JD's language and priorities; quantify only with numbers already present in the source; order sections by relevance to the JD; keep to 1 page for <8 years experience, 2 pages otherwise. Identify keywords in the JD absent from the resume. Score ATS match 0-100 (weights: hard-skill keywords 40, title alignment 20, experience relevance 25, format/section completeness 15)."""


class ResumeOutput(BaseModel):
    resume_markdown: str
    summary: str
    ats_score: int = Field(ge=0, le=100)
    keywords_matched: list[str] = Field(default_factory=list)
    keywords_missing: list[str] = Field(default_factory=list)
    changes_made: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


OUTPUT_SCHEMA = ResumeOutput


def build_user_prompt(context: dict, rag_chunks: list[str] | None = None) -> str:
    jd = context.get("jd_text", context.get("job_description", "NOT_PROVIDED"))
    title = context.get("target_title", context.get("target_role", "NOT_PROVIDED"))
    tone = context.get("tone", "professional")
    chunks = "\n\n".join(rag_chunks or [])
    return (
        f"JOB_DESCRIPTION:\n{jd}\n\nTARGET_TITLE: {title}\nTONE: {tone}\n\n"
        f"RESUME SOURCE:\n{chunks or 'NOT_PROVIDED'}\n\nReturn JSON only."
    )
