"""
conftest.py — E2E test fixtures for CareerCraft AI Playwright browser tests.

Requirements before running:
    - Full Docker Compose stack running (frontend, backend, worker, redis)
    - pip install pytest-playwright playwright httpx
    - playwright install chromium
    - Environment variables set: TEST_EMAIL, TEST_PASSWORD, TEST_JWT, TEST_JOB_URL
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page

E2E_DIR = Path(__file__).parent
SCREENSHOT_DIR = E2E_DIR / "screenshots"
VIDEO_DIR = E2E_DIR / "videos"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)


# ── Environment Validation ──────────────────────────────────────────────────

def _check_env_vars() -> list[str]:
    missing = []
    for var in ("TEST_EMAIL", "TEST_PASSWORD", "TEST_JWT"):
        if not os.getenv(var):
            missing.append(var)
    return missing

def _check_backend_health() -> tuple[bool, str]:
    api_url = os.getenv("API_URL", "http://localhost:8000/api/v1")
    try:
        r = httpx.get(f"{api_url}/health", timeout=10.0)
        if r.status_code == 200 and r.json().get("status") == "ok":
            return True, ""
        return False, f"/health returned {r.status_code}: {r.text[:200]}"
    except httpx.ConnectError:
        return False, f"Backend not reachable at {api_url}. Run: docker compose up -d"
    except Exception as e:
        return False, str(e)

def pytest_configure(config):
    E2E_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    VIDEO_DIR.mkdir(exist_ok=True)


def pytest_collection_modifyitems(config, items):
    run_e2e = os.getenv("RUN_E2E", "").lower() in ("1", "true", "yes")
    if not run_e2e:
        missing = _check_env_vars()
        health_ok, health_msg = _check_backend_health()

        if missing or not health_ok:
            reasons = []
            if missing:
                reasons.append(f"Missing env vars: {', '.join(missing)}")
            if not health_ok:
                reasons.append(f"Backend: {health_msg}")

            skip_msg = "E2E prerequisite check failed:\n  " + "\n  ".join(reasons)
            skip_msg += "\n\nSet environment variables and start services: docker compose up -d"
            skip_msg += "\nThen run with: RUN_E2E=1 pytest backend/tests/e2e/ -v -s --headed"

            for item in items:
                if "e2e" in str(item.fspath) or any(
                    marker.name in ("e2e", "browser", "integration")
                    for marker in item.own_markers
                ):
                    item.add_marker(pytest.mark.skip(reason=skip_msg))


# ── API Client ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def api_client():
    jwt = os.getenv("TEST_JWT", "")
    api_url = os.getenv("API_URL", "http://localhost:8000/api/v1")
    client = httpx.Client(
        base_url=api_url,
        headers={
            "Authorization": f"Bearer {jwt}",
            "Content-Type": "application/json",
        },
        timeout=120.0,
    )
    yield client
    client.close()


# ── Playwright Browser ──────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def browser_context(playwright):
    headless = os.getenv("HEADLESS", "0").lower() in ("1", "true", "yes")
    slow_mo = int(os.getenv("SLOW_MO", "500"))
    browser = playwright.chromium.launch(
        headless=headless,
        slow_mo=slow_mo,
        args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        record_video_dir=str(VIDEO_DIR),
        record_video_size={"width": 1920, "height": 1080},
    )
    yield context
    context.close()
    browser.close()


@pytest.fixture(scope="function")
def page(browser_context, request) -> Page:
    p = browser_context.new_page()
    p.set_default_timeout(60000)
    yield p
    p.close()


# ── Screenshot Helper ──────────────────────────────────────────────────────

def screenshot(page: Page, test_name: str, step: str) -> None:
    path = SCREENSHOT_DIR / test_name
    path.mkdir(exist_ok=True)
    filepath = str(path / f"{step}.png")
    page.screenshot(path=filepath, full_page=True)
    print(f"📸 Screenshot: {test_name}/{step}.png")


# ── SSE Stream Helper ──────────────────────────────────────────────────────

def wait_for_sse_complete(
    api_client: httpx.Client,
    run_id: str,
    timeout_s: int = 120,
) -> dict:
    checkpoint_seen = False
    events: list[dict] = []
    result: dict = {}
    start = time.time()

    with api_client.stream("GET", f"/agents/{run_id}/stream") as response:
        for line in response.iter_lines():
            if time.time() - start > timeout_s:
                raise TimeoutError(
                    f"Agent run {run_id} did not complete within {timeout_s}s"
                )

            if line.startswith("event: "):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data: "):
                payload_str = line.split(":", 1)[1].strip()
                try:
                    payload = __import__("json").loads(payload_str)
                except Exception:
                    payload = {"raw": payload_str}
                events.append({"type": event_type, "payload": payload})
                print(f"  SSE [{event_type}]: {str(payload)[:120]}")

                if event_type == "complete":
                    result = payload
                    break
                if event_type == "checkpoint":
                    checkpoint_seen = True
                    result = {"checkpoint": payload, "run_id": run_id}
                    break
                if event_type == "error":
                    raise RuntimeError(
                        f"Agent error: {payload.get('message', 'Unknown error')}"
                    )

    return {"result": result, "events": events, "checkpoint_seen": checkpoint_seen}
