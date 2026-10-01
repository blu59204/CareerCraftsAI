"""Regression tests for Fix 2: Browser Use Naukri pilot (2026-06-13 audit).

Bugs caught:
  1. apply_naukri() returned status="applied" immediately — submitted the
     application without going through the HITL checkpoint.  New code returns
     status="draft_saved" and emits a checkpoint event.

  2. _build_bu_llm() built a parallel LLM that bypassed TokenTrackingCallback
     — browser-use token consumption was invisible to the daily budget.

  3. No session semaphore — unlimited Chromium instances could OOM the VPS.

  4. No structured logging — browser failures had no traceable log events.
"""

import asyncio
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("INTEGRATION") != "1",
        reason="live browser/network — run with INTEGRATION=1",
    ),
]


# ---------------------------------------------------------------------------
# 1. HITL regression: apply_naukri must NOT return "applied"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_naukri_never_returns_applied_status():
    """OLD code: returned ApplyResult(status='applied') — submitted without approval.
    NEW code: returns ApplyResult(status='draft_saved') — HITL gate preserved.
    """
    from app.services.auto_apply_service import apply_naukri

    fake_llm = MagicMock()
    job_url = "https://www.naukri.com/job-listings-python-engineer-example-123"

    # apply_naukri now delegates to apply_to_any_portal → fill_and_submit_form
    with (
        patch(
            "app.services.form_filler_service.fill_and_submit_form",
            new=AsyncMock(return_value={"status": "ready_for_review", "message": "fields filled"}),
        ),
        patch("app.services.auto_apply_service.emit"),
        patch("app.services.auto_apply_service._human_delay", new=AsyncMock()),
    ):
        result = await apply_naukri(fake_llm, "usr_test", job_url)

    assert (
        result.status != "applied"
    ), f"apply_naukri returned status='applied' — HITL bypass! Got: {result.status}"
    assert result.status == "draft_saved", f"Expected 'draft_saved', got '{result.status}'"


@pytest.mark.asyncio
async def test_apply_naukri_requires_manual_preserved():
    """REQUIRES_MANUAL path must still propagate through the fix."""
    from app.services.auto_apply_service import apply_naukri

    with (
        patch(
            "app.services.form_filler_service.fill_and_submit_form",
            new=AsyncMock(return_value={"status": "requires_manual", "message": "login wall"}),
        ),
        patch("app.services.auto_apply_service.emit"),
        patch("app.services.auto_apply_service._human_delay", new=AsyncMock()),
    ):
        result = await apply_naukri(MagicMock(), "usr_test", "https://naukri.com/job/1")

    assert result.status == "requires_manual"


@pytest.mark.asyncio
async def test_apply_naukri_failed_on_exception():
    """Exception inside browser task must surface as status='failed', not crash."""
    from app.services.auto_apply_service import apply_naukri

    with patch(
        "app.services.auto_apply_service.run_browser_task",
        new=AsyncMock(side_effect=RuntimeError("Chromium crashed")),
    ):
        result = await apply_naukri(MagicMock(), "usr_test", "https://naukri.com/job/2")

    assert result.status == "failed"
    assert result.platform == "naukri"


# ---------------------------------------------------------------------------
# 4. Session semaphore — concurrency cap
# ---------------------------------------------------------------------------


def test_session_semaphore_respects_config_limit():
    """_get_semaphore() must create a semaphore with the configured limit.
    OLD code: no semaphore — unlimited Chromium sessions could OOM VPS.
    NEW code: semaphore value equals BROWSER_USE_MAX_CONCURRENT_SESSIONS.
    """
    # Reset the module-level singleton so the test controls the limit
    import app.services.browser_control_service as bcs

    original = bcs._session_semaphore
    bcs._session_semaphore = None

    with patch("app.services.browser_control_service.settings") as mock_settings:
        mock_settings.BROWSER_USE_MAX_CONCURRENT_SESSIONS = 3
        mock_settings.BASE_DIR = "."
        sem = bcs._get_semaphore()

    assert sem._value == 3, f"Expected semaphore value=3, got {sem._value}"
    bcs._session_semaphore = original  # restore


# ---------------------------------------------------------------------------
# 5. _build_bu_llm prefers Ollama when configured
# ---------------------------------------------------------------------------


def test_build_bu_llm_uses_ollama_when_url_configured():
    """OLD code: always used BYOK model — expensive for navigation steps.
    NEW code: uses Ollama when BROWSER_USE_OLLAMA_URL is set.
    """
    import sys
    import types

    # browser_use is not installed in the test venv — inject a minimal mock module
    # so that the lazy `from browser_use import ...` inside _build_bu_llm succeeds.
    mock_bu = types.ModuleType("browser_use")
    mock_ollama_cls = MagicMock(return_value=MagicMock())
    mock_bu.ChatOllama = mock_ollama_cls
    mock_bu.ChatOpenAI = MagicMock(return_value=MagicMock())
    mock_bu.ChatAnthropic = MagicMock(return_value=MagicMock())
    mock_bu.ChatGoogle = MagicMock(return_value=MagicMock())
    mock_bu.Agent = MagicMock()
    mock_bu.Browser = MagicMock()

    sys.modules["browser_use"] = mock_bu
    try:
        import importlib
        import app.services.browser_control_service as bcs

        importlib.reload(bcs)  # pick up the freshly injected module

        with patch("app.services.browser_control_service.settings") as mock_settings:
            mock_settings.BROWSER_USE_OLLAMA_URL = "http://localhost:11434"
            mock_settings.BROWSER_USE_OLLAMA_MODEL = "llama3.2"
            mock_settings.APP_SECRET_KEY = "secret"
            mock_settings.BASE_DIR = "."
            mock_settings.BROWSER_USE_MAX_CONCURRENT_SESSIONS = 4
            bcs._session_semaphore = None  # reset semaphore singleton

            bcs._build_bu_llm("usr_test")

        mock_ollama_cls.assert_called_once_with(
            model="llama3.2",
            host="http://localhost:11434",
        )
    finally:
        del sys.modules["browser_use"]


def test_build_bu_llm_falls_back_to_byok_when_no_ollama():
    """When BROWSER_USE_OLLAMA_URL is empty, fall back to BYOK model."""
    import sys
    import types

    mock_bu = types.ModuleType("browser_use")
    mock_ollama_cls = MagicMock(return_value=MagicMock())
    mock_openai_cls = MagicMock(return_value=MagicMock())
    mock_bu.ChatOllama = mock_ollama_cls
    mock_bu.ChatOpenAI = mock_openai_cls
    mock_bu.ChatAnthropic = MagicMock(return_value=MagicMock())
    mock_bu.ChatGoogle = MagicMock(return_value=MagicMock())
    mock_bu.Agent = MagicMock()
    mock_bu.Browser = MagicMock()

    mock_ms = MagicMock()
    mock_ms.provider = "openai"
    mock_ms.model_name = "gpt-4o-mini"
    mock_ms.api_key_enc = "enc_key"

    sys.modules["browser_use"] = mock_bu
    try:
        import importlib
        import app.services.browser_control_service as bcs

        importlib.reload(bcs)

        with (
            patch("app.services.browser_control_service.settings") as mock_settings,
            patch("app.core.security.decrypt_api_key", return_value="plaintext"),
            patch("app.core.sync_db.fetch_model_settings", return_value=mock_ms),
        ):
            mock_settings.BROWSER_USE_OLLAMA_URL = ""
            mock_settings.APP_SECRET_KEY = "secret"
            mock_settings.BASE_DIR = "."
            mock_settings.BROWSER_USE_MAX_CONCURRENT_SESSIONS = 4
            bcs._session_semaphore = None

            bcs._build_bu_llm("usr_test")

        mock_ollama_cls.assert_not_called()
        mock_openai_cls.assert_called_once()
    finally:
        del sys.modules["browser_use"]


# ---------------------------------------------------------------------------
# 7. Universal portal routing — apply_to_any_portal / _detect_portal
# ---------------------------------------------------------------------------


def test_detect_portal_known_domains():
    """_detect_portal must identify common portals from URL."""
    from app.services.auto_apply_service import _detect_portal

    assert _detect_portal("https://www.linkedin.com/jobs/view/123") == "LinkedIn"
    assert _detect_portal("https://www.naukri.com/job-listings/python-engineer-123") == "Naukri"
    assert _detect_portal("https://www.indeed.com/viewjob?jk=abc") == "Indeed"
    assert _detect_portal("https://boards.greenhouse.io/company/jobs/456") == "Greenhouse"
    assert _detect_portal("https://company.lever.co/jobs/789") == "Lever"
    assert _detect_portal("https://company.myworkdayjobs.com/en-US/External/job") == "Workday"


def test_detect_portal_unknown_domain_returns_domain_name():
    """Unknown domains return the first segment of the domain, not crash."""
    from app.services.auto_apply_service import _detect_portal

    result = _detect_portal("https://careers.somecompany.com/jobs/apply/123")
    assert result  # not empty
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_apply_to_any_portal_draft_saved_and_checkpoint_emitted():
    """apply_to_any_portal must return draft_saved and emit checkpoint for any URL."""
    from app.services.auto_apply_service import apply_to_any_portal

    emitted: list[dict] = []

    def _capture(run_id, event_type, payload):
        emitted.append({"event_type": event_type, "payload": payload})

    with (
        patch(
            "app.services.form_filler_service.fill_and_submit_form",
            new=AsyncMock(return_value={"status": "ready_for_review", "message": "fields filled"}),
        ),
        patch("app.services.auto_apply_service.emit", side_effect=_capture),
        patch("app.services.auto_apply_service._human_delay", new=AsyncMock()),
    ):
        result = await apply_to_any_portal(
            MagicMock(),
            "usr_test",
            "https://boards.greenhouse.io/acmecorp/jobs/123",
            run_id="run_x",
        )

    assert result.status == "draft_saved"
    assert result.status != "applied"
    checkpoints = [e for e in emitted if e["event_type"] == "checkpoint"]
    assert len(checkpoints) == 1
    assert checkpoints[0]["payload"]["type"] == "apply_review"
    assert checkpoints[0]["payload"]["portal"] == "Greenhouse"


@pytest.mark.asyncio
async def test_apply_to_any_portal_works_on_unknown_ats_url():
    """Any ATS URL (not in the known list) must still go through HITL."""
    from app.services.auto_apply_service import apply_to_any_portal

    emitted: list[dict] = []

    with (
        patch(
            "app.services.form_filler_service.fill_and_submit_form",
            new=AsyncMock(return_value={"status": "ready_for_review", "message": "ok"}),
        ),
        patch(
            "app.services.auto_apply_service.emit",
            side_effect=lambda *a, **k: emitted.append(a),
        ),
        patch("app.services.auto_apply_service._human_delay", new=AsyncMock()),
    ):
        result = await apply_to_any_portal(
            MagicMock(),
            "u",
            "https://careers.unknowncompany.io/apply?id=999",
            run_id="r99",
        )

    assert result.status == "draft_saved"
    assert any("checkpoint" in str(e) for e in emitted)


@pytest.mark.asyncio
async def test_apply_to_job_routes_any_platform_through_universal():
    """apply_to_job with any platform string must route through apply_to_any_portal."""
    from app.services.auto_apply_service import apply_to_job

    with (
        patch(
            "app.services.form_filler_service.fill_and_submit_form",
            new=AsyncMock(return_value={"status": "ready_for_review", "message": "done"}),
        ),
        patch("app.services.auto_apply_service.emit"),
        patch("app.services.auto_apply_service._human_delay", new=AsyncMock()),
    ):
        # "wellfound" is NOT in PLATFORM_HANDLERS — must still work
        result = await apply_to_job(
            MagicMock(),
            "u",
            "wellfound",
            "https://wellfound.com/jobs/apply/456",
            run_id="r2",
        )

    assert result.status == "draft_saved"
    assert result.status != "applied"


def test_browser_action_timer_logs_on_success():
    from app.services.browser_logger import BrowserActionTimer

    logged: list[dict] = []

    def _capture(*, run_id, action, url, field, detail, duration_ms, success):
        logged.append({"action": action, "success": success, "duration_ms": duration_ms})

    with patch("app.services.browser_logger.log_browser_action", side_effect=_capture):
        with BrowserActionTimer(run_id="r1", action="navigate", url="https://naukri.com"):
            pass  # simulated success

    assert len(logged) == 1
    assert logged[0]["action"] == "navigate"
    assert logged[0]["success"] is True
    assert logged[0]["duration_ms"] >= 0


def test_browser_action_timer_logs_failure_on_exception():
    from app.services.browser_logger import BrowserActionTimer

    logged: list[dict] = []

    def _capture(*, run_id, action, url, field, detail, duration_ms, success):
        logged.append({"action": action, "success": success, "detail": detail})

    with patch("app.services.browser_logger.log_browser_action", side_effect=_capture):
        try:
            with BrowserActionTimer(run_id="r1", action="fill", url="https://naukri.com"):
                raise ValueError("selector not found")
        except ValueError:
            pass

    assert len(logged) == 1
    assert logged[0]["success"] is False
    assert "selector not found" in logged[0]["detail"]
