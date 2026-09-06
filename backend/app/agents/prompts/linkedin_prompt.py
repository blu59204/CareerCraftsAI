from __future__ import annotations
from pydantic import BaseModel, Field
from . import _COMMON
SYSTEM_PROMPT = _COMMON + """
You are a LinkedIn profile strategist. Rewrite headline (<=220 chars), About (<=2000 chars, first person), top 3 experiences (3-4 bullets each, outcome-first). Optimize for recruiter search terms."""
class LinkedInExperience(BaseModel):
    title: str
    company: str
    bullets: list[str] = Field(default_factory=list)
class LinkedInOutput(BaseModel):
    headline: str
    about: str
    experiences: list[LinkedInExperience] = Field(default_factory=list)
    target_keywords: list[str] = Field(default_factory=list)
    before_after_notes: list[str] = Field(default_factory=list)
OUTPUT_SCHEMA = LinkedInOutput
def build_user_prompt(context: dict, rag_chunks: list[str] | None = None) -> str:
    role = context.get("target_role", "NOT_PROVIDED")
    chunks = "\n\n".join(rag_chunks or [])
    return f"TARGET_ROLE: {role}\nSOURCE:\n{chunks or 'NOT_PROVIDED'}\nReturn JSON only."
