"""GenericAdapter tests — this adapter is a thin wrapper around the same
schema_extractor/validator/SUBMIT_NAME/CONFIRMATION logic
application_workflow.py already runs inline (see that module's
review_snapshot/fill_known_fields for the original inline implementation)."""
from __future__ import annotations

from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from app.applications.adapters.generic import GenericAdapter
from app.applications.models import ResolvedAnswer

FIXTURE = (Path(__file__).parent.parent / "fixtures" / "ats" / "generic_apply.html").read_text()


@pytest.fixture
async def page():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await browser.new_page()
        await pg.set_content(FIXTURE)
        yield pg
        await browser.close()


@pytest.mark.asyncio
async def test_detect_always_matches():
    adapter = GenericAdapter()
    assert await adapter.detect("https://any-unknown-ats.example.test/apply", page=None) is True


@pytest.mark.asyncio
async def test_extract_fields(page):
    adapter = GenericAdapter()
    fields = await adapter.extract_fields(page)
    by_id = {f.field_id: f for f in fields}
    assert by_id["email"].input_type == "text"
    assert by_id["email"].required is True
    assert by_id["resume"].input_type == "file"
    assert by_id["resume"].required is True


@pytest.mark.asyncio
async def test_validate_flags_missing_required_fields(page):
    adapter = GenericAdapter()
    fields = await adapter.extract_fields(page)
    issues = await adapter.validate(page, fields)
    assert {issue.field_id for issue in issues} == {"email", "resume"}


@pytest.mark.asyncio
async def test_fill_fields_and_upload_clears_validation(page):
    adapter = GenericAdapter()
    fields = await adapter.extract_fields(page)
    answers = [ResolvedAnswer(
        field_id="email", value="me@example.test", source="profile", confidence=0.99,
    )]
    await adapter.fill_fields(page, fields, answers)
    await adapter.upload_documents(page, b"%PDF-resume")

    refreshed = await adapter.extract_fields(page)
    issues = await adapter.validate(page, refreshed)
    assert issues == []


@pytest.mark.asyncio
async def test_locate_submit_and_verify_confirmation(page):
    adapter = GenericAdapter()
    submit = await adapter.locate_submit(page)
    assert submit is not None
    await submit.click()
    confirmed, text, _url = await adapter.verify_confirmation(page)
    assert confirmed is True
    assert "thank you for applying" in text.lower()
