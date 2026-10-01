"""Checks that a tailored resume says nothing the candidate's own documents
and typed facts do not support.

Tailoring may reorder, reword and select. It may not add. The model is told
that, but a prompt is not a guarantee, so this module compares the output to
the source: every number, and every name-like term (acronyms, camel-case and
dotted tech names, mid-sentence capitalised words), must already appear in
the source text. Anything else is reported as unsupported.

The check is deliberately literal. A false alarm costs a regenerate; a missed
fabrication costs the candidate's credibility with an employer.
"""

from __future__ import annotations

import json
import re

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_TERM = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[.+#][A-Za-z0-9+#]*)*")
_BULLET_PREFIX = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_HEADING_WORDS = {
    "summary", "professional", "experience", "work", "education", "skills", "projects",
    "certifications", "languages", "awards", "technical", "core", "competencies",
    "achievements", "present", "current", "profile", "contact", "publications",
    "volunteer", "interests", "references", "tools", "additional", "key", "highlights",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "jan", "feb", "mar", "apr", "jun",
    "jul", "aug", "sep", "sept", "oct", "nov", "dec", "remote", "hybrid", "onsite",
}  # fmt: skip


def _flatten(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def source_text(chunks: list[str], facts: dict | None, *extras: str | None) -> str:
    """Everything the candidate has said about themselves, as one string."""
    parts = [*chunks, _flatten(facts), *(extra or "" for extra in extras)]
    return "\n".join(parts)


def _numbers(text: str) -> set[str]:
    return {match.replace(",", "").rstrip(".") for match in _NUMBER.findall(text)}


def _name_like(token: str, at_sentence_start: bool) -> bool:
    if token.lower() in _HEADING_WORDS or len(token) < 2:
        return False
    inner_caps = any(c.isupper() for c in token[1:])
    has_symbol = any(c in token for c in "+#") or ("." in token.strip("."))
    if inner_caps or has_symbol:
        return True
    return token[0].isupper() and not at_sentence_start


def unsupported_claims(markdown: str, source: str) -> list[str]:
    """Numbers and name-like terms in `markdown` that `source` never mentions."""
    source_lower = source.lower()
    known_numbers = _numbers(source)
    found: list[str] = []
    seen: set[str] = set()

    def flag(item: str) -> None:
        if item.lower() not in seen:
            seen.add(item.lower())
            found.append(item)

    for line in markdown.splitlines():
        body = _BULLET_PREFIX.sub("", line).lstrip("# ").strip()
        # Link targets and emails are checked as a whole by contact handling.
        body = re.sub(r"\(https?://[^)]*\)|\S+@\S+|https?://\S+", " ", body)
        for number in _numbers(body):
            if number not in known_numbers:
                flag(number)
        for match in _TERM.finditer(body):
            token = match.group(0).rstrip(".")
            preceding = body[: match.start()].rstrip()
            sentence_start = not preceding or preceding.endswith((".", ":", "|"))
            if _name_like(token, sentence_start) and token.lower() not in source_lower:
                flag(token)
    return found
