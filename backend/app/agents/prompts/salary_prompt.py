from __future__ import annotations
from pydantic import BaseModel, Field
from . import _COMMON
SYSTEM_PROMPT = _COMMON + """
Compensation analyst. p25/p50/p75/p90 + negotiation script. Never invent data."""
class NegotiationScript(BaseModel):
    anchor: str
    justification: list[str] = Field(default_factory=list)
    concessions: list[str] = Field(default_factory=list)
    walk_away: str
    email_version: str
class SalaryOutput(BaseModel):
    currency: str
    p25: int = Field(ge=0)
    p50: int = Field(ge=0)
    p75: int = Field(ge=0)
    p90: int = Field(ge=0)
    derivation: list[str] = Field(default_factory=list)
    recommended_ask: int = Field(ge=0)
    negotiation_script: NegotiationScript
    data_points_used: int = Field(ge=0)
    recency: str
    confidence: float = Field(ge=0, le=1)
OUTPUT_SCHEMA = SalaryOutput
def build_user_prompt(context: dict, rag_chunks: list[str] | None = None) -> str:
    return f"ROLE: {context.get('role', 'NOT_PROVIDED')} LOC: {context.get('location', 'NOT_PROVIDED')}\nReturn JSON only."
