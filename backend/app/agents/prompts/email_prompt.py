from __future__ import annotations
from pydantic import BaseModel
from . import _COMMON
SYSTEM_PROMPT = _COMMON + """
You draft job-seeker emails <=180 words, warm, professional. Detect action required."""
class EmailOutput(BaseModel):
    subject: str
    body: str
    intent_detected: str
    action_required: str | None = None
    suggested_send_time: str | None = None
OUTPUT_SCHEMA = EmailOutput
def build_user_prompt(context: dict, rag_chunks: list[str] | None = None) -> str:
    chunks = "\n\n".join(rag_chunks or [])
    return f"CONTEXT: {context}\nSOURCE: {chunks or 'NOT_PROVIDED'}\nReturn JSON only."
