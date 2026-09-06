from __future__ import annotations
from typing import Literal
from pydantic import BaseModel
from . import _COMMON
SYSTEM_PROMPT = _COMMON + """
Draft day-5 / day-12 follow-up <=110 words. Reference role and date."""
class FollowupOutput(BaseModel):
    subject: str
    body: str
    followup_stage: Literal["day5", "day12"]
OUTPUT_SCHEMA = FollowupOutput
def build_user_prompt(context: dict, rag_chunks: list[str] | None = None) -> str:
    chunks = "\n\n".join(rag_chunks or [])
    return f"CONTEXT: {context}\nSOURCE: {chunks or 'NOT_PROVIDED'}\nReturn JSON only."
