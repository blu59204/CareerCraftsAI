import pytest

from app.core.config import Settings


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-32-chars-minimum!!")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")

    settings = Settings(_env_file=None)

    assert settings.APP_SECRET_KEY == "test-secret-key-32-chars-minimum!!"
    assert settings.DATABASE_URL == "postgresql+asyncpg://user:pass@localhost/db"
    assert settings.APP_ENV == "development"


def test_settings_require_secret_key(monkeypatch):
    monkeypatch.delenv("APP_SECRET_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(Exception):
        Settings(_env_file=None)

