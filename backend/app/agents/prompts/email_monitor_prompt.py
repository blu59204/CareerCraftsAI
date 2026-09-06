from __future__ import annotations
from pydantic import BaseModel, Field
from . import _COMMON
SYSTEM_PROMPT = _COMMON + """
Classify inbox messages. Never reply, only surface items."""
class EmailMonitorItem(BaseModel):
    message_id: str
    label: str
    company: str | None = None
    role: str | None = None
    deadline: str | None = None
    action: str | None = None
    priority: str = "low"
    application_id_hint: str | None = None
class EmailMonitorOutput(BaseModel):
    items: list[EmailMonitorItem] = Field(default_factory=list)
OUTPUT_SCHEMA = EmailMonitorOutput
def build_user_prompt(context: dict, rag_chunks: list[str] | None = None) -> str:
    return f"THREADS: {context.get('threads', 'NOT_PROVIDED')}\nReturn JSON only."
