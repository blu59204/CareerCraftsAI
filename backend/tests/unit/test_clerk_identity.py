import httpx
import pytest

from app.core.config import settings
from app.core.supabase_auth import ClerkIdentityError, get_verified_primary_email


@pytest.mark.asyncio
async def test_get_verified_primary_email_uses_clerks_primary_verified_address(monkeypatch) -> None:
    monkeypatch.setattr(settings, "CLERK_SECRET_KEY", "clerk-secret")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/users/user_123"
        assert request.headers["Authorization"] == "Bearer clerk-secret"
        return httpx.Response(
            200,
            json={
                "primary_email_address_id": "email_1",
                "email_addresses": [
                    {
                        "id": "email_1",
                        "email_address": "Person@Example.com",
                        "verification": {"status": "verified"},
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        email = await get_verified_primary_email("user_123", client=client)

    assert email == "person@example.com"


@pytest.mark.asyncio
async def test_get_verified_primary_email_rejects_unverified_primary(monkeypatch) -> None:
    monkeypatch.setattr(settings, "CLERK_SECRET_KEY", "clerk-secret")

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "primary_email_address_id": "email_1",
                "email_addresses": [
                    {
                        "id": "email_1",
                        "email_address": "person@example.com",
                        "verification": {"status": "unverified"},
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ClerkIdentityError):
            await get_verified_primary_email("user_123", client=client)
