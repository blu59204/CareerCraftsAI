from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field
from . import _COMMON
SYSTEM_PROMPT = _COMMON + """
Convert plain-English job request to structured search."""
class NLSearchOutput(BaseModel):
    titles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    remote: Literal["remote", "hybrid", "onsite", "any"] = "any"
    experience_min: int | None = None
    experience_max: int | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    company_types: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    posted_within_days: int = 30
    clarifying_question: str | None = None
OUTPUT_SCHEMA = NLSearchOutput
def build_user_prompt(context: dict, rag_chunks: list[str] | None = None) -> str:
    return f"QUERY: {context.get('query', 'NOT_PROVIDED')}\nReturn JSON only."
