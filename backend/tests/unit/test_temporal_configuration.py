"""Startup validation for the opt-in Temporal runtime."""

from __future__ import annotations

import pytest

from app.core.config import Settings


def _set_required_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-32-chars-minimum!!")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-jwt-secret-hs256")


def test_temporal_validation_rejects_partial_mtls_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    _set_required_environment(monkeypatch)
    monkeypatch.setenv("TEMPORAL_ENABLED", "true")
    monkeypatch.setenv("TEMPORAL_TLS_CERT_PATH", str(tmp_path / "client.pem"))
    monkeypatch.delenv("TEMPORAL_TLS_KEY_PATH", raising=False)

    with pytest.raises(ValueError, match="both TEMPORAL_TLS_CERT_PATH and TEMPORAL_TLS_KEY_PATH"):
        Settings(_env_file=None).validate_temporal_configuration()


def test_temporal_validation_rejects_unsafe_heartbeat_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_environment(monkeypatch)
    monkeypatch.setenv("TEMPORAL_ENABLED", "true")
    monkeypatch.setenv("TEMPORAL_ACTIVITY_START_TO_CLOSE_TIMEOUT_S", "30")
    monkeypatch.setenv("TEMPORAL_ACTIVITY_HEARTBEAT_TIMEOUT_S", "30")

    with pytest.raises(ValueError, match="must be lower than"):
        Settings(_env_file=None).validate_temporal_configuration()


def test_temporal_validation_allows_disabled_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_environment(monkeypatch)
    settings = Settings(_env_file=None)

    assert settings.validate_temporal_configuration() is None
