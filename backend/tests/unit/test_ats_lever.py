"""Unit tests for the Lever ATS adapter (Task 3, slice 3c).

Loads a hand-crafted fixture into a real headless Chromium page via
page.set_content() — no network access, no sandbox container.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from app.applications.adapters.lever import lever_adapter

FIXTURE = (Path(__file__).parent.parent / "fixtures" / "ats" / "lever_apply.html").read_text(
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


async def test_detect_true_for_jobs_lever_co_url(page):
    assert await lever_adapter.detect(
        "https://jobs.lever.co/acme/11111111-2222-3333-4444-555555555555", page
    ) is True


async def test_detect_true_via_dom_fallback(page):
    # Host doesn't match jobs.lever.co, but the fixture's <form action>
    # still points at lever.co.
    assert await lever_adapter.detect("https://www.acme.com/careers", page) is True


async def test_detect_false_for_unrelated_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await browser.new_page()
        await pg.set_content("<html><body><form action='https://example.com/apply'></form></body></html>")
        assert await lever_adapter.detect("https://example.com/careers", pg) is False
        await browser.close()


async def test_extract_fields(page):
    fields = await lever_adapter.extract_fields(page)
    by_id = {f.field_id: f for f in fields}

    assert by_id["name"].input_type == "text"
    assert by_id["name"].required is True
    assert by_id["resume"].input_type == "file"
    assert by_id["resume"].required is True
    assert by_id["work_auth"].input_type == "select"
    assert by_id["work_auth"].required is True
    assert set(by_id["work_auth"].options) == {"Select an option", "Yes", "No"}

    # Radio group (not required in this fixture): three inputs sharing
    # name="gender" collapse into one field labeled from the legend.
    gender = by_id["gender"]
    assert gender.input_type == "radio"
    assert gender.required is False
    assert set(gender.options) == {"Male", "Female", "Decline to self-identify"}

    # Single required checkbox.
    consent = by_id["consent"]
    assert consent.input_type == "checkbox"
    assert consent.required is True
    assert consent.value is False


async def test_locate_submit(page):
    submit = await lever_adapter.locate_submit(page)
    assert submit is not None
    assert await submit.count() == 1
    assert (await submit.inner_text()).strip().lower() == "submit application"


async def test_validate_flags_required_empty_fields(page):
    fields = await lever_adapter.extract_fields(page)
    issues = await lever_adapter.validate(page, fields)
    flagged = {issue.field_id for issue in issues}
    assert "name" in flagged
    assert "email" in flagged
    assert "resume" in flagged
    assert "work_auth" in flagged
    assert "consent" in flagged
    # Optional fields must not be flagged.
    assert "phone" not in flagged
    assert "gender" not in flagged


async def test_fill_fields_text_select_radio_checkbox(page):
    from app.applications.models import ResolvedAnswer

    fields = await lever_adapter.extract_fields(page)
    answers = [
        ResolvedAnswer(field_id="name", value="Grace Hopper", source="user", confidence=1.0),
        ResolvedAnswer(field_id="work_auth", value="Yes", source="user", confidence=1.0),
        ResolvedAnswer(field_id="gender", value="Female", source="user", confidence=1.0),
        ResolvedAnswer(field_id="consent", value=True, source="user", confidence=1.0),
    ]
    await lever_adapter.fill_fields(page, fields, answers)

    assert await page.locator("#name").input_value() == "Grace Hopper"
    assert await page.locator("#work_auth").input_value() == "yes"
    assert await page.locator("#gender_female").is_checked() is True
    assert await page.locator("#consent").is_checked() is True
