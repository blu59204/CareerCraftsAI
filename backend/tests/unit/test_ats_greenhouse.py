"""Unit tests for the Greenhouse ATS adapter (Task 3, slice 3c).

Loads a hand-crafted fixture into a real headless Chromium page via
page.set_content() — no network access, no sandbox container.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from app.applications.adapters.greenhouse import greenhouse_adapter

FIXTURE = (Path(__file__).parent.parent / "fixtures" / "ats" / "greenhouse_apply.html").read_text(
    encoding="utf-8"
)


@pytest.fixture
async def page():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await browser.new_page()
        await pg.set_content(FIXTURE)
        yield pg
        await browser.close()


async def test_detect_true_for_boards_url(page):
    url = "https://boards.greenhouse.io/acme/jobs/12345"
    assert await greenhouse_adapter.detect(url, page) is True


async def test_detect_true_for_embed_url(page):
    assert await greenhouse_adapter.detect(
        "https://www.acme.com/careers?greenhouse.io/embed/job_app", page
    ) is True


async def test_detect_true_via_dom_fallback(page):
    # Neither host matches, but the fixture's <form action> still points at
    # greenhouse.io (the embedded-widget case).
    assert await greenhouse_adapter.detect("https://www.acme.com/careers", page) is True


async def test_detect_false_for_unrelated_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await browser.new_page()
        await pg.set_content("<html><body><form action='https://example.com/apply'></form></body></html>")
        assert await greenhouse_adapter.detect("https://example.com/careers", pg) is False
        await browser.close()


async def test_extract_fields(page):
    fields = await greenhouse_adapter.extract_fields(page)
    by_id = {f.field_id: f for f in fields}

    assert by_id["first_name"].input_type == "text"
    assert by_id["first_name"].required is True
    assert by_id["email"].input_type == "text"
    assert by_id["resume"].input_type == "file"
    assert by_id["how_heard"].input_type == "select"
    assert "LinkedIn" in by_id["how_heard"].options

    # Radio group: two <input type=radio name="work_authorized"> collapse
    # into one field, labeled from the fieldset legend, with both options.
    radio = by_id["work_authorized"]
    assert radio.input_type == "radio"
    assert radio.required is True
    assert set(radio.options) == {"Yes", "No"}
    assert radio.value is None  # neither option checked in the fixture

    # Single required checkbox stays a plain boolean field.
    checkbox = by_id["self_id_agree"]
    assert checkbox.input_type == "checkbox"
    assert checkbox.required is True
    assert checkbox.value is False


async def test_locate_submit(page):
    submit = await greenhouse_adapter.locate_submit(page)
    assert submit is not None
    assert await submit.count() == 1
    assert (await submit.inner_text()).strip().lower() == "submit application"


async def test_validate_flags_required_empty_fields(page):
    fields = await greenhouse_adapter.extract_fields(page)
    issues = await greenhouse_adapter.validate(page, fields)
    flagged = {issue.field_id for issue in issues}
    # first_name/last_name/email are empty text inputs; the radio group has
    # nothing selected; the checkbox is unchecked. All required, all empty.
    assert "first_name" in flagged
    assert "work_authorized" in flagged
    assert "self_id_agree" in flagged
    # phone/how_heard/cover_letter are not required, so must not be flagged.
    assert "phone" not in flagged
    assert "how_heard" not in flagged


async def test_fill_fields_text_select_radio_checkbox(page):
    from app.applications.models import ResolvedAnswer

    fields = await greenhouse_adapter.extract_fields(page)
    answers = [
        ResolvedAnswer(field_id="first_name", value="Ada", source="user", confidence=1.0),
        ResolvedAnswer(field_id="how_heard", value="Referral", source="user", confidence=1.0),
        ResolvedAnswer(field_id="work_authorized", value="Yes", source="user", confidence=1.0),
        ResolvedAnswer(field_id="self_id_agree", value=True, source="user", confidence=1.0),
    ]
    await greenhouse_adapter.fill_fields(page, fields, answers)

    assert await page.locator("#first_name").input_value() == "Ada"
    assert await page.locator("#how_heard").input_value() == "referral"
    assert await page.locator("#work_auth_yes").is_checked() is True
    assert await page.locator("#self_id_agree").is_checked() is True
