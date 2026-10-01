"""Generic DOM adapter; register last so platform-specific adapters match first."""

from __future__ import annotations

from app.applications.adapters._dom import fill_fields, upload_resume_and_cover_letter
from app.applications.models import ApplicationField, ResolvedAnswer, ValidationIssue
from app.applications.schema_extractor import FIELD_SNAPSHOT_JS, extract_fields
from app.applications.submission import CONFIRMATION, SUBMIT_NAME
from app.applications.validator import validate_fields


class GenericAdapter:
    name = "generic"

    async def detect(self, url: str, page) -> bool:
        return True

    async def open_application(self, page, job_url: str) -> None:
        await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)

    async def extract_fields(self, page) -> list[ApplicationField]:
        raw = await page.evaluate(FIELD_SNAPSHOT_JS)
        return extract_fields(raw)

    async def fill_fields(
        self,
        page,
        fields: list[ApplicationField],
        answers: list[ResolvedAnswer],
    ) -> None:
        await fill_fields(page, fields, answers)

    async def upload_documents(
        self,
        page,
        resume: bytes,
        cover_letter: bytes | None = None,
    ) -> None:
        await upload_resume_and_cover_letter(page, resume, cover_letter)

    async def validate(self, page, fields: list[ApplicationField]) -> list[ValidationIssue]:
        return validate_fields(fields)

    async def locate_submit(self, page):
        submit = page.get_by_role("button", name=SUBMIT_NAME)
        if await submit.count() == 1 and await submit.is_visible() and await submit.is_enabled():
            return submit
        return None

    async def verify_confirmation(self, page) -> tuple[bool, str, str]:
        locator = page.get_by_text(CONFIRMATION)
        if await locator.count() == 0:
            return False, "", page.url
        text = (await locator.first.inner_text())[:12000]
        match = CONFIRMATION.search(text)
        return bool(match), match.group(0) if match else "", page.url


generic_adapter = GenericAdapter()
