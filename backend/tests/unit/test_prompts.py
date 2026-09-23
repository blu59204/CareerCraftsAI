from __future__ import annotations

import importlib

import pytest

PROMPT_MODULES = [
    "resume_prompt",
    "job_search_prompt",
    "cover_letter_prompt",
    "linkedin_prompt",
    "linkedin_outreach_prompt",
    "email_prompt",
    "followup_prompt",
    "email_monitor_prompt",
    "interview_coach_prompt",
    "interview_prep_prompt",
    "company_research_prompt",
    "salary_prompt",
    "nl_search_prompt",
    "auto_apply_prompt",
    "orchestrator_prompt",
    "harness_reflect_prompt",
]


def _depth(schema: dict, level: int = 0) -> int:
    props = schema.get("properties", {})
    if not props:
        return level
    return max(
        [_depth(v, level + 1) if isinstance(v, dict) else level for v in props.values()],
        default=level,
    )


@pytest.mark.parametrize("name", PROMPT_MODULES)
def test_prompt_contract(name: str):
    mod = importlib.import_module(f"app.agents.prompts.{name}")
    assert mod.SYSTEM_PROMPT and len(mod.SYSTEM_PROMPT) > 50
    assert hasattr(mod.OUTPUT_SCHEMA, "model_json_schema")
    assert "JSON" in mod.build_user_prompt({})
    schema = mod.OUTPUT_SCHEMA.model_json_schema()
    assert _depth(schema) <= 3, f"{name} nests too deep for small models"
