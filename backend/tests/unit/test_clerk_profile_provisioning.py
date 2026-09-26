"""Users get their real, verified email from Clerk — not a placeholder.

Clerk session tokens carry no email claim by default, so provisioning used
to store "<subject>@users.noreply.clerk", which then ended up in job
application forms and follow-up emails.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core import supabase_auth

PROFILE = {"email": "priya@example.com", "full_name": "Priya R", "avatar_url": None}


@pytest.mark.asyncio
async def test_new_user_is_provisioned_with_the_clerk_email(monkeypatch):
    inserted = {}
    user = SimpleNamespace(email="priya@example.com")

    async def execute(statement):
        inserted.update(statement.compile().params)

    db = MagicMock()
    db.execute = AsyncMock(side_effect=execute)
    db.commit = AsyncMock()
    monkeypatch.setattr(supabase_auth, "_select_by_uid", AsyncMock(side_effect=[None, user]))
    monkeypatch.setattr(supabase_auth, "fetch_clerk_profile", AsyncMock(return_value=PROFILE))

    result = await supabase_auth.get_or_provision_user(db, "user_abc", {"sub": "user_abc"})

    assert result is user
    assert inserted["email"] == "priya@example.com"
    assert inserted["full_name"] == "Priya R"


@pytest.mark.asyncio
async def test_token_claims_win_over_a_clerk_lookup(monkeypatch):
    inserted = {}

    async def execute(statement):
        inserted.update(statement.compile().params)

    db = MagicMock()
    db.execute = AsyncMock(side_effect=execute)
    db.commit = AsyncMock()
    lookup = AsyncMock(return_value=PROFILE)
    monkeypatch.setattr(supabase_auth, "_select_by_uid", AsyncMock(side_effect=[None, object()]))
    monkeypatch.setattr(supabase_auth, "fetch_clerk_profile", lookup)

    await supabase_auth.get_or_provision_user(
        db, "user_abc", {"sub": "user_abc", "email": "claim@example.com"}
    )

    assert inserted["email"] == "claim@example.com"
    lookup.assert_not_awaited()


@pytest.mark.asyncio
async def test_existing_placeholder_email_is_repaired_once(monkeypatch):
    user = SimpleNamespace(
        id="u1",
        supabase_uid="user_abc",
        email="user_abc@users.noreply.clerk",
        full_name=None,
        avatar_url=None,
    )
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    monkeypatch.setattr(supabase_auth, "_select_by_uid", AsyncMock(return_value=user))
    lookup = AsyncMock(return_value=PROFILE)
    monkeypatch.setattr(supabase_auth, "fetch_clerk_profile", lookup)

    await supabase_auth.get_or_provision_user(db, "user_abc", {"sub": "user_abc"})
    await supabase_auth.get_or_provision_user(db, "user_abc", {"sub": "user_abc"})

    assert user.email == "priya@example.com"
    assert user.full_name == "Priya R"
    lookup.assert_awaited_once()  # a real email is never looked up again


@pytest.mark.asyncio
async def test_placeholder_stays_when_clerk_is_unavailable(monkeypatch):
    user = SimpleNamespace(
        id="u1",
        supabase_uid="user_abc",
        email="user_abc@users.noreply.clerk",
        full_name=None,
        avatar_url=None,
    )
    db = MagicMock()
    db.commit = AsyncMock()
    monkeypatch.setattr(supabase_auth, "_select_by_uid", AsyncMock(return_value=user))
    monkeypatch.setattr(supabase_auth, "fetch_clerk_profile", AsyncMock(return_value=None))

    result = await supabase_auth.get_or_provision_user(db, "user_abc", {"sub": "user_abc"})

    assert result.email == "user_abc@users.noreply.clerk"
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_clerk_profile_is_skipped_without_a_secret(monkeypatch):
    monkeypatch.setattr(supabase_auth.settings, "CLERK_SECRET_KEY", "")
    assert await supabase_auth.fetch_clerk_profile("user_abc") is None
