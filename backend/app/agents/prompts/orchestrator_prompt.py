from __future__ import annotations
from pydantic import BaseModel, Field
from . import _COMMON
SYSTEM_PROMPT = _COMMON + """
Pick exactly one task_type from the allowed list. Else unsupported."""
class OrchestratorOutput(BaseModel):
    task_type: str
    reason: str
    extracted_context: dict = Field(default_factory=dict)
OUTPUT_SCHEMA = OrchestratorOutput
def build_user_prompt(context: dict, rag_chunks: list[str] | None = None) -> str:
    return f"REQUEST: {context.get('request', 'NOT_PROVIDED')}\nReturn JSON only."
