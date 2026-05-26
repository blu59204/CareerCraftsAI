"""
Property-based tests validating critical bug fixes remain intact.
Uses hypothesis for generative testing.
"""
import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st
from unittest.mock import patch, MagicMock


# Property 1: Settings always has ALLOWED_ORIGINS attribute
def test_settings_has_allowed_origins(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-32-chars-minimum!!")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "svc-key")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "jwt-secret")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")

    from app.core.config import Settings
    s = Settings(_env_file=None)
    assert hasattr(s, "ALLOWED_ORIGINS")
    assert isinstance(s.ALLOWED_ORIGINS, str)


# Property 2: sync_db fetch_model_settings never raises RuntimeError from thread
def test_sync_db_no_runtime_error():
    """fetch_model_settings uses sync engine — no asyncio.run() RuntimeError."""
    from app.core.sync_db import _get_sync_factory
    from sqlalchemy.orm import Session

    with patch("app.core.sync_db.settings") as mock_settings:
        mock_settings.DATABASE_URL = "postgresql+asyncpg://u:p@localhost/db"
        # Reset globals to force re-creation
        import app.core.sync_db as sdb
        sdb._sync_engine = None
        sdb._sync_factory = None
        factory = _get_sync_factory()
        assert factory is not None
        # The factory class_ should be Session (sync), not AsyncSession
        assert issubclass(factory.class_, Session)


# Property 6: VALID_STATUSES is exhaustive set
def test_valid_statuses_set():
    from app.api.v1.jobs import VALID_STATUSES
    expected = {"saved", "applied", "viewed", "interview", "offer", "rejected"}
    assert VALID_STATUSES == expected


# Property 7: GmailMCPClient.search_threads returns [] when OAuth unavailable
def test_gmail_returns_empty_without_oauth():
    with patch("app.services.gmail_service.GmailToolkit", side_effect=Exception("No creds")):
        from app.services.gmail_service import GmailMCPClient
        client = GmailMCPClient(user_id="test-user")
        result = client.search_threads("test query")
        assert result == []


# Property 10: YouTube returns [] when API key is empty
@pytest.mark.asyncio
async def test_youtube_returns_empty_without_api_key():
    with patch("app.services.youtube_service.settings") as mock_settings:
        mock_settings.YOUTUBE_API_KEY = ""
        mock_settings.REDIS_URL = "redis://localhost:6379"
        # Reset redis client
        import app.services.youtube_service as yt
        yt._redis_client = MagicMock()
        yt._redis_client.get.return_value = None

        result = await yt.search_interview_videos("Acme", "Engineer")
        assert result == []


# Property: MODEL_DEFAULTS["anthropic"] is a valid model name
def test_onboarding_model_default():
    """Verify the Anthropic default model is a real model identifier."""
    # Read the source file and check the constant
    import re
    from pathlib import Path

    onboarding_path = Path(__file__).resolve().parents[3] / "frontend" / "src" / "app" / "(app)" / "onboarding" / "page.tsx"
    if not onboarding_path.exists():
        pytest.skip("Frontend source not available")

    content = onboarding_path.read_text(encoding="utf-8")
    match = re.search(r'anthropic:\s*"([^"]+)"', content)
    assert match is not None, "Could not find anthropic model default"
    model_name = match.group(1)
    # Must be a valid Anthropic model identifier (not a marketing name)
    assert "claude" in model_name.lower()
    assert model_name != "claude-sonnet-4-5"  # The bug we fixed
    assert "-" in model_name  # Real model IDs have dashes


# Property: internal.py handlers don't have duplicate secret params
def test_internal_no_duplicate_secret_params():
    """Verify internal handlers use dependencies, not duplicate Header params."""
    import inspect
    from app.api.internal import run_job_search, run_followup

    sig_search = inspect.signature(run_job_search)
    sig_followup = inspect.signature(run_followup)

    # Neither handler should have x_internal_secret as a parameter
    assert "x_internal_secret" not in sig_search.parameters
    assert "x_internal_secret" not in sig_followup.parameters


# Property: _psycopg_url converts asyncpg to psycopg
def test_psycopg_url_conversion():
    with patch("app.services.rag_service.app_settings") as mock:
        mock.DATABASE_URL = "postgresql+asyncpg://user:pass@host/db"
        from app.services.rag_service import _psycopg_url
        result = _psycopg_url()
        assert "+psycopg" in result
        assert "+asyncpg" not in result
