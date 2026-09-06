from __future__ import annotations
from pydantic import BaseModel, Field
from . import _COMMON
SYSTEM_PROMPT = _COMMON + """
Build interview prep pack: 12-18 questions, 5-day plan, ranked topics, questions to ask."""
class PrepQuestion(BaseModel):
    q: str
    type: str
    intent: str
class PlanDay(BaseModel):
    day: int
    focus: str
    tasks: list[str] = Field(default_factory=list)
class InterviewPrepOutput(BaseModel):
    questions: list[PrepQuestion] = Field(default_factory=list)
    study_plan: list[PlanDay] = Field(default_factory=list)
    topics_ranked: list[str] = Field(default_factory=list)
    questions_to_ask: list[str] = Field(default_factory=list)
    video_search_queries: list[str] = Field(default_factory=list)
OUTPUT_SCHEMA = InterviewPrepOutput
def build_user_prompt(context: dict, rag_chunks: list[str] | None = None) -> str:
    return f"ROLE: {context.get('role', 'NOT_PROVIDED')}\nReturn JSON only."
