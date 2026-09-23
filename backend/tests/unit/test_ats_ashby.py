"""AshbyAdapter tests against the representative fixture at
tests/fixtures/ats/ashby_apply.html (see that file's header note — the
markup was not verified against a real Ashby posting)."""
from __future__ import annotations

from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from app.applications.adapters.ashby import AshbyAdapter
from app.applications.models import ResolvedAnswer

FIXTURE = (Path(__file__).parent.parent / "fixtures" / "ats" / "ashby_apply.html").read_text()


@pytest.fixture
async def page():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await browser.new_page()
        await pg.set_content(FIXTURE)
        yield pg
        await browser.close()


@pytest.mark.asyncio
async def test_detect_matches_ashby_urls():
    adapter = AshbyAdapter()
    assert await adapter.detect("https://jobs.ashbyhq.com/acme/12345", page=None) is True
    assert await adapter.detect("https://boards.greenhouse.io/acme/1", page=None) is False


@pytest.mark.asyncio
async def test_extract_fields_covers_all_field_kinds(page):
    adapter = AshbyAdapter()
    fields = await adapter.extract_fields(page)
    by_id = {f.field_id: f for f in fields}

    assert by_id["full_name"].input_type == "text"
    assert by_id["full_name"].required is True

    assert by_id["source"].input_type == "select"
    assert by_id["source"].required is True
    assert "LinkedIn" in by_id["source"].options

    assert by_id["work_authorized"].input_type == "radio"
    assert by_id["work_authorized"].required is True
    assert set(by_id["work_authorized"].options) == {"Yes", "No"}

    assert by_id["resume"].input_type == "file"
    assert by_id["resume"].required is True


@pytest.mark.asyncio
async def test_validate_reports_all_missing_required_fields(page):
    adapter = AshbyAdapter()
    fields = await adapter.extract_fields(page)
    issues = await adapter.validate(page, fields)
    flagged = {issue.field_id for issue in issues}
    assert {"full_name", "email", "source", "work_authorized", "resume"} <= flagged


@pytest.mark.asyncio
async def test_fill_fields_writes_resolved_answers(page):
    adapter = AshbyAdapter()
    fields = await adapter.extract_fields(page)
    answers = [
        ResolvedAnswer(field_id="full_name", value="Ada Lovelace",
                       source="profile", confidence=0.99),
        ResolvedAnswer(field_id="email", value="ada@example.test",
                       source="profile", confidence=0.99),
        ResolvedAnswer(field_id="source", value="Referral", source="user", confidence=1.0),
        ResolvedAnswer(field_id="work_authorized", value="Yes", source="user", confidence=1.0),
    ]
    await adapter.fill_fields(page, fields, answers)

    assert await page.locator("#full_name").input_value() == "Ada Lovelace"
    assert await page.locator("#email").input_value() == "ada@example.test"
    assert await page.locator("#source").input_value() == "referral"
    assert await page.locator('input[name="work_authorized"][value="yes"]').is_checked()


@pytest.mark.asyncio
async def test_upload_documents_targets_resume_and_cover_letter_fields(page):
    adapter = AshbyAdapter()
    await adapter.upload_documents(page, b"%PDF-resume", b"%PDF-cover")
    names_js = "e => Array.from(e.files).map(f => f.name)"
    resume_files = await page.locator("#resume").evaluate(names_js)
    cover_files = await page.locator("#cover_letter").evaluate(names_js)
    assert resume_files == ["resume.pdf"]
    assert cover_files == ["cover_letter.pdf"]


@pytest.mark.asyncio
async def test_locate_submit_and_verify_confirmation(page):
    adapter = AshbyAdapter()
    submit = await adapter.locate_submit(page)
    assert submit is not None
    await submit.click()
    confirmed, text, _url = await adapter.verify_confirmation(page)
    assert confirmed is True
    assert "thank you for applying" in text.lower()
