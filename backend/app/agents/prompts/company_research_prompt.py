from __future__ import annotations
from pydantic import BaseModel, Field
from . import _COMMON
SYSTEM_PROMPT = _COMMON + """
Company research analyst. Cite source index for every claim. No claim without source."""
class NewsItem(BaseModel):
    headline: str
    date: str | None = None
    source_idx: int = 0
class KeyPerson(BaseModel):
    name: str
    title: str
    relevance: str
    source_idx: int = 0
class CompanyResearchOutput(BaseModel):
    overview: str
    size_stage: str
    financials: str
    recent_news: list[NewsItem] = Field(default_factory=list)
    culture: list[str] = Field(default_factory=list)
    interview_process: list[str] = Field(default_factory=list)
    key_people: list[KeyPerson] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    talking_points: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
OUTPUT_SCHEMA = CompanyResearchOutput
def build_user_prompt(context: dict, rag_chunks: list[str] | None = None) -> str:
    return f"COMPANY: {context.get('company_name', 'NOT_PROVIDED')}\nReturn JSON only."
