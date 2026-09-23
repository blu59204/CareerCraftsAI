"""Deterministic label -> canonical question_key mapping.

Rule-based, not LLM-based: the same wording variants of a question ("Will
you require visa sponsorship?", "Do you need employer sponsorship?") must
always resolve to the same key so a saved answer is reused, and so this
stays testable and auditable. Order matters — first match wins.
"""
from __future__ import annotations

import re

_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"visa|sponsorship", re.I), "authorization.requires_sponsorship"),
    (re.compile(r"authoriz(e|ation)\s+to\s+work|legally\s+(authorized|entitled)", re.I),
     "authorization.work_authorized"),
    (re.compile(r"willing\s+to\s+relocate|open\s+to\s+relocat", re.I),
     "location.willing_to_relocate"),
    (re.compile(r"expected\s+salary|desired\s+salary|salary\s+expectation", re.I),
     "compensation.expected_salary"),
    (re.compile(r"current\s+salary|current\s+compensation", re.I), "compensation.current_salary"),
    (re.compile(r"notice\s+period", re.I), "experience.notice_period_days"),
    (re.compile(r"years?\s+of\s+experience", re.I), "experience.years_experience"),
    (re.compile(r"first\s*name", re.I), "personal.first_name"),
    (re.compile(r"last\s*name|surname", re.I), "personal.last_name"),
    (re.compile(r"full\s*name|^name$", re.I), "personal.full_name"),
    (re.compile(r"e-?mail", re.I), "personal.email"),
    (re.compile(r"phone|mobile", re.I), "personal.phone"),
    (re.compile(r"linkedin", re.I), "links.linkedin_url"),
    (re.compile(r"github", re.I), "links.github_url"),
    (re.compile(r"portfolio|website|personal\s+site", re.I), "links.portfolio_url"),
    (re.compile(r"current\s+(company|employer)", re.I), "experience.current_company"),
    (re.compile(r"current\s+title|current\s+role", re.I), "experience.current_title"),
    (re.compile(r"city", re.I), "location.city"),
    (re.compile(r"remote|hybrid|on-?site", re.I), "work.remote_preference"),
]


def normalize_question(label: str) -> str | None:
    """Return the canonical question_key for a label, or None if the label
    does not match a known factual question (e.g. a free-form "why this
    role?" question, which the answer resolver treats as generative)."""
    for pattern, key in _RULES:
        if pattern.search(label):
            return key
    return None
