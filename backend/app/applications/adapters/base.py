"""ATS adapter contract (Task 3, slice 3b).

Each supported ATS (Greenhouse, Lever, Ashby, ...) implements this Protocol
against its own DOM structure. application_workflow.py tries adapters in
order via `detect()` and falls back to the generic DOM path only when none
match. All methods operate on a Playwright `page` — no adapter method
touches the database directly (persistence stays in application_workflow.py
and the answer resolver).
"""
from __future__ import annotations

from typing import Protocol

from app.applications.models import ApplicationField, ResolvedAnswer, ValidationIssue


class ATSAdapter(Protocol):
    name: str

    async def detect(self, url: str, page) -> bool:
        """Return True if this adapter recognizes the current page/URL."""
        ...

    async def open_application(self, page, job_url: str) -> None:
        """Navigate to the job URL and reach the application form (clicking
        an 'Apply' button if the ATS requires it)."""
        ...

    async def extract_fields(self, page) -> list[ApplicationField]:
        ...

    async def fill_fields(
        self, page, fields: list[ApplicationField], answers: list[ResolvedAnswer],
    ) -> None:
        """Fill every field whose ResolvedAnswer has a non-None value. Never
        fill a field whose answer is unresolved — that is a checkpoint, not
        a best-effort guess."""
        ...

    async def upload_documents(
        self, page, resume: bytes, cover_letter: bytes | None = None,
    ) -> None:
        """Identify the resume upload field explicitly; upload the cover
        letter to its own field only when the form has one — never to the
        resume field."""
        ...

    async def validate(self, page, fields: list[ApplicationField]) -> list[ValidationIssue]:
        ...

    async def locate_submit(self, page):
        """Return the submit control locator, or None if not present/unique/enabled."""
        ...

    async def verify_confirmation(self, page) -> tuple[bool, str, str]:
        """Return (confirmed, confirmation_text, confirmation_url)."""
        ...


_REGISTRY: list[ATSAdapter] = []


def register(adapter: ATSAdapter) -> None:
    _REGISTRY.append(adapter)


async def detect_adapter(url: str, page) -> ATSAdapter | None:
    for adapter in _REGISTRY:
        if await adapter.detect(url, page):
            return adapter
    return None
