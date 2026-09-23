"""
test_live_screen_smoke.py — browser smoke coverage for every authenticated
screen, at desktop and mobile widths, against a live deployed stack.

Asserts each screen: doesn't bounce to /login, renders its heading, shows no
session-verification error, throws no console errors (favicon noise
excluded), and issues no failing /api/v1/ calls. Mobile runs additionally
assert no horizontal overflow and that the primary action isn't obscured by
a fixed overlay.

Requires RUN_LIVE_E2E=1 plus TEST_JWT, TEST_EMAIL, TEST_PASSWORD, WEB_URL,
API_URL (see conftest.py's `_auth_state` fixture, which skips otherwise).
"""
from __future__ import annotations

import os
import re

import pytest
from playwright.sync_api import Page, expect

from .screen_manifest import AUTHENTICATED_SCREENS

WEB_URL = os.getenv("WEB_URL", "http://localhost:3000")

# Statuses that always mean a screen is broken.
_ALWAYS_FAILS = {401, 403, 409, 422, 429}

# GET endpoints that restore a previously saved result keyed by a natural
# identifier (not an id issued by a prior write), where 404 legitimately
# means "nothing saved yet" on a fresh account rather than a broken route.
# Verified against backend/app/api/v1/company.py:62 + the company screen's
# `apiClient.get(/company/${name}/intel)` (see CompanyResearchPage) — the
# documented case (a fresh account 404s here before ever researching a
# company). Any other GET 404 — including on these same screens for a
# different path — still fails the test; extend this list only when you've
# confirmed a screen does the same kind of "restore, else 404" probe.
_PERMITTED_404_GET_PATTERNS = [
    re.compile(r"/api/v1/company/[^/]+/intel(?:$|[/?])"),
]


def _is_permitted_404(response) -> bool:
    if response.status != 404 or response.request.method != "GET":
        return False
    return any(pattern.search(response.url) for pattern in _PERMITTED_404_GET_PATTERNS)


def _track_api_failures(page: Page) -> list[str]:
    """Attach a response listener recording failing /api/v1/ calls."""
    failures: list[str] = []

    def _on_response(response) -> None:
        if "/api/v1/" not in response.url:
            return
        status = response.status
        if status in _ALWAYS_FAILS or status >= 500:
            is_failure = True
        elif status == 404:
            is_failure = not _is_permitted_404(response)
        else:
            is_failure = False
        if is_failure:
            try:
                detail = response.text()[:500]
            except Exception:
                detail = "<no body>"
            failures.append(f"{response.request.method} {response.url} -> {status}: {detail}")

    page.on("response", _on_response)
    return failures


def _screenshot_name(screen, suffix: str = "") -> str:
    slug = screen.path.strip("/").replace("/", "-") or "root"
    return f"{slug}{suffix}.png"


def _assert_screen_loads(page: Page, screen) -> None:
    console_errors: list[str] = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    api_failures = _track_api_failures(page)

    page.goto(f"{WEB_URL}{screen.path}", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")

    assert "/login" not in page.url
    expect(page.get_by_text(screen.heading, exact=False).first).to_be_visible()
    assert not page.get_by_text("Unable to verify your session").is_visible()

    real_console_errors = [e for e in console_errors if "favicon" not in e.lower()]
    assert not real_console_errors, f"console errors on {screen.path}: {real_console_errors}"
    assert not api_failures, f"failed API calls on {screen.path}:\n" + "\n".join(api_failures)


@pytest.mark.e2e
# Overrides pyproject.toml's global 60s pytest-timeout: page load +
# networkidle wait + assertions can bump close to the 60s cap under a slow
# live stack, matching the timeout convention applied to the other e2e files.
@pytest.mark.timeout(600)
@pytest.mark.parametrize("screen", AUTHENTICATED_SCREENS, ids=lambda item: item.path)
def test_authenticated_screen_loads(authenticated_page, screen, artifact_dir):
    page = authenticated_page
    _assert_screen_loads(page, screen)
    page.screenshot(path=artifact_dir / _screenshot_name(screen), full_page=True)


@pytest.mark.e2e
@pytest.mark.timeout(600)
@pytest.mark.parametrize("screen", AUTHENTICATED_SCREENS, ids=lambda item: item.path)
def test_authenticated_screen_loads_mobile(authenticated_mobile_page, screen, artifact_dir):
    page = authenticated_mobile_page
    _assert_screen_loads(page, screen)

    no_overflow = page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    assert no_overflow, f"{screen.path} has horizontal overflow at 390x844"

    # "Reachable" = Playwright's actionability checks pass (visible, stable,
    # enabled, receives pointer events) — a fixed overlay covering the target
    # raises "intercepts pointer events" on hover, same as on click, without
    # triggering whatever the action actually does. The dominant real-world
    # failure is a fixed bottom nav/footer covering a page's real CTA, which
    # sits later in the DOM than header/nav chrome — so target the last
    # visible interactive element, not the first (a logo link or hamburger
    # menu, which tells us nothing about a bottom overlay).
    candidates = page.get_by_role("button").or_(page.get_by_role("link"))
    count = candidates.count()
    if count:
        primary_action = candidates.nth(count - 1)
        if primary_action.is_visible():
            primary_action.hover(timeout=5000)

    page.screenshot(path=artifact_dir / _screenshot_name(screen, "-mobile"), full_page=True)
