from __future__ import annotations

from pydantic import BaseModel, Field

from . import _COMMON

SYSTEM_PROMPT = _COMMON + """
You write cover letters a hiring manager actually reads. 3-4 short paragraphs, 220-320 words: (1) a specific hook tying ONE real achievement to THEIR stated need; (2) two evidence-backed paragraphs mapping requirements to experience; (3) a confident close with a clear ask. Match the company's tone from the research notes. No cliches, no restating the resume."""


class CoverLetterOutput(BaseModel):
    cover_letter_markdown: str
    hook_used: str
    requirements_addressed: list[str] = Field(default_factory=list)
    word_count: int = Field(ge=0)
    tone: str
    alternative_openings: list[str] = Field(default_factory=list, max_length=2)


OUTPUT_SCHEMA = CoverLetterOutput


def build_user_prompt(context: dict, rag_chunks: list[str] | None = None) -> str:
    jd = context.get("jd_text", context.get("job_description", "NOT_PROVIDED"))
    company = context.get("company", context.get("company_name", "NOT_PROVIDED"))
    role = context.get("target_role", context.get("target_title", "NOT_PROVIDED"))
    tone = context.get("tone", "professional")
    chunks = "\n\n".join(rag_chunks or [])
    return (
        f"JOB_DESCRIPTION:\n{jd}\n\nCOMPANY: {company}\nTARGET_ROLE: {role}\nTONE: {tone}\n\n"
        f"CANDIDATE SOURCE:\n{chunks or 'NOT_PROVIDED'}\n\nReturn JSON only."
    )
