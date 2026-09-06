from __future__ import annotations
from pydantic import BaseModel, Field
from . import _COMMON
SYSTEM_PROMPT = _COMMON + """
You draft recruiter outreach. Connection note <=300 chars, InMail <=900 chars, email <=150 words. One reason, one proof, one ask. Drafts only."""
class LinkedInOutreachOutput(BaseModel):
    connection_note: str
    inmail: str
    email_subject: str
    email_body: str
    personalization_used: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
OUTPUT_SCHEMA = LinkedInOutreachOutput
def build_user_prompt(context: dict, rag_chunks: list[str] | None = None) -> str:
    chunks = "\n\n".join(rag_chunks or [])
    return f"CONTEXT: {context}\nSOURCE: {chunks or 'NOT_PROVIDED'}\nReturn JSON only."
