from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field
from . import _COMMON
SYSTEM_PROMPT = _COMMON + """
Live interview coach. ASK mode asks next question. EVALUATE scores clarity/relevance/depth 0-10."""
class InterviewCoachOutput(BaseModel):
    mode: Literal["ask", "evaluate"]
    question: str | None = None
    question_type: str | None = None
    clarity: int | None = Field(default=None, ge=0, le=10)
    relevance: int | None = Field(default=None, ge=0, le=10)
    depth: int | None = Field(default=None, ge=0, le=10)
    strength: str | None = None
    improvement: str | None = None
    model_answer: str | None = None
    session_summary: str | None = None
OUTPUT_SCHEMA = InterviewCoachOutput
def build_user_prompt(context: dict, rag_chunks: list[str] | None = None) -> str:
    return f"CONTEXT: {context}\nReturn JSON only."
