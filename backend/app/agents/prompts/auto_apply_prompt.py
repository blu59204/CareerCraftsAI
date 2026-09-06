from __future__ import annotations
from pydantic import BaseModel, Field
from . import _COMMON
SYSTEM_PROMPT = _COMMON + """
Map form fields to candidate data. Unknown required -> NEEDS_HUMAN. Do not submit."""
class FormField(BaseModel):
    field_id: str
    value: str
    confidence: float = Field(ge=0, le=1)
    needs_human: bool
    note: str | None = None
class AutoApplyOutput(BaseModel):
    fields: list[FormField] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    ready_to_submit: bool = False
OUTPUT_SCHEMA = AutoApplyOutput
def build_user_prompt(context: dict, rag_chunks: list[str] | None = None) -> str:
    return f"FIELDS: {context.get('fields', 'NOT_PROVIDED')}\nReturn JSON only."
