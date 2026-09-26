"""Fixtures for LLM-backed integration tests.

These run real agents against a real provider, so they need real infrastructure:

    INTEGRATION=1
    DATABASE_URL=postgresql+asyncpg://...    # migrated DB (bootstrap + supabase/migrations)
    REDIS_URL=redis://...
    APP_SECRET_KEY=<32+ chars>               # encrypts the provider key in the test DB
    INTEGRATION_LLM_PROVIDER=deepseek        # anthropic|openai|google|deepseek|openrouter|nvidia_nim|ollama
    INTEGRATION_LLM_MODEL=deepseek-flash
    INTEGRATION_LLM_API_KEY=<provider key>   # not needed for ollama
    EMBEDDING_PROVIDER=ollama                # required when the chat provider has no embeddings API
    INTEGRATION_OLLAMA_URL=http://localhost:11434   # where embeddings are served, if ollama

Every test that uses ``test_model_settings`` is skipped (not failed) when no
provider is configured, so plain ``pytest tests/integration`` stays green.
The key is only ever held in memory and, AES-256-GCM encrypted, in the test DB.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

import pytest


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    api_key: str | None
    ollama_url: str | None


@pytest.fixture(scope="session")
def llm_config() -> LLMConfig:
    if os.environ.get("INTEGRATION") != "1":
        pytest.skip("Set INTEGRATION=1 to run LLM-backed integration tests")
    provider = os.environ.get("INTEGRATION_LLM_PROVIDER", "").strip().lower()
    api_key = os.environ.get("INTEGRATION_LLM_API_KEY") or None
    if not provider or (provider != "ollama" and not api_key):
        pytest.skip("Set INTEGRATION_LLM_PROVIDER and INTEGRATION_LLM_API_KEY to run LLM-backed tests")
    return LLMConfig(
        provider=provider,
        model=os.environ.get("INTEGRATION_LLM_MODEL", ""),
        api_key=api_key,
        ollama_url=os.environ.get("INTEGRATION_OLLAMA_URL") or None,
    )


@pytest.fixture(scope="session")
def test_db():
    """Sync session factory — the same one agent nodes use."""
    from app.core.sync_db import _get_sync_factory

    return _get_sync_factory()


@pytest.fixture(scope="session")
def test_user(test_db, llm_config):
    from app.models.db import User

    with test_db() as db:
        user = User(
            email=f"integration-{uuid.uuid4().hex[:10]}@example.com",
            full_name="Priya Sharma",
            clerk_user_id=f"user_integration_{uuid.uuid4().hex[:12]}",
            headline="Senior Python Engineer",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)

    yield user

    with test_db() as db:
        row = db.get(User, user.id)
        if row is not None:
            db.delete(row)
            db.commit()


@pytest.fixture(scope="session")
def test_model_settings(test_db, test_user, llm_config):
    from app.core.config import settings
    from app.core.security import encrypt_api_key
    from app.models.db import UserModelSettings

    with test_db() as db:
        row = UserModelSettings(
            user_id=test_user.id,
            provider=llm_config.provider,
            model_name=llm_config.model or None,
            api_key_enc=(
                encrypt_api_key(llm_config.api_key, settings.APP_SECRET_KEY) if llm_config.api_key else None
            ),
            ollama_url=llm_config.ollama_url,
            is_active=True,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        db.expunge(row)
    return row
