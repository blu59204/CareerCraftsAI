from __future__ import annotations
from pydantic import BaseModel, Field
SYSTEM_PROMPT = """
You review agent episodes. Output strategy preferences + top error fix. JSON only."""
class Preference(BaseModel):
    task_type: str
    strategy: str
    reason: str
class ReflectOutput(BaseModel):
    preferences: list[Preference] = Field(default_factory=list)
    top_error: str | None = None
    fix: str | None = None
OUTPUT_SCHEMA = ReflectOutput
def build_user_prompt(context: dict, rag_chunks: list[str] | None = None) -> str:
    return f"RUNS: {context.get('runs', 'NOT_PROVIDED')}\nReturn JSON only."
