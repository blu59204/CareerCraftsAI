"""Configuration validation for the feature-flagged Nango gateway."""

import pytest

from app.core.config import Settings


def _set_required_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-32-chars-minimum!!")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-jwt-secret-hs256")


def test_nango_disabled_does_not_require_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_environment(monkeypatch)

    Settings(_env_file=None).validate_nango_configuration()


def test_nango_enabled_requires_backend_secret_and_webhook_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_environment(monkeypatch)
    monkeypatch.setenv("NANGO_ENABLED", "true")

    with pytest.raises(ValueError, match="NANGO_SECRET_KEY"):
        Settings(_env_file=None).validate_nango_configuration()


def test_nango_enabled_accepts_server_only_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_environment(monkeypatch)
    monkeypatch.setenv("NANGO_ENABLED", "true")
    monkeypatch.setenv("NANGO_SECRET_KEY", "test-server-key")
    monkeypatch.setenv("NANGO_WEBHOOK_SECRET", "test-webhook-key")

    Settings(_env_file=None).validate_nango_configuration()


def test_nango_provider_keys_parse_as_deployment_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_environment(monkeypatch)
    monkeypatch.setenv("NANGO_PROVIDER_CONFIG_KEYS", '{"gmail":"google-mail-prod"}')

    settings = Settings(_env_file=None)

    assert settings.NANGO_PROVIDER_CONFIG_KEYS == {"gmail": "google-mail-prod"}
