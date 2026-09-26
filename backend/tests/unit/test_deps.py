from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.deps import get_current_user


def _make_request(method: str, path: str) -> MagicMock:
    request = MagicMock()
    request.method = method
    request.url.path = path
    request.headers.get.return_value = "Bearer faketoken"
    return request


@pytest.mark.asyncio
async def test_blocks_access_when_consent_missing_on_non_exempt_path(mock_user, mock_db):
    mock_user.policy_accepted_at = None
    request = _make_request("GET", "/api/v1/dashboard")

    with (
        patch("app.api.v1.deps.verify_auth_jwt", return_value={}),
        patch("app.api.v1.deps.subject_from_payload", return_value="user_123"),
        patch("app.api.v1.deps.get_or_provision_user", AsyncMock(return_value=mock_user)),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(request, db=mock_db)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error"] == "policy_consent_required"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/users/me"),
        ("POST", "/api/v1/users/me/consent"),
        ("GET", "/api/v1/users/me/export"),
        ("DELETE", "/api/v1/users/me"),
    ],
)
@pytest.mark.asyncio
async def test_allows_exempt_paths_when_consent_missing(mock_user, mock_db, method, path):
    mock_user.policy_accepted_at = None
    request = _make_request(method, path)

    with (
        patch("app.api.v1.deps.verify_auth_jwt", return_value={}),
        patch("app.api.v1.deps.subject_from_payload", return_value="user_123"),
        patch("app.api.v1.deps.get_or_provision_user", AsyncMock(return_value=mock_user)),
    ):
        result = await get_current_user(request, db=mock_db)

    assert result is mock_user


@pytest.mark.asyncio
async def test_allows_access_when_consent_recorded(mock_user, mock_db):
    mock_user.policy_accepted_at = datetime.now(UTC)
    request = _make_request("GET", "/api/v1/dashboard")

    with (
        patch("app.api.v1.deps.verify_auth_jwt", return_value={}),
        patch("app.api.v1.deps.subject_from_payload", return_value="user_123"),
        patch("app.api.v1.deps.get_or_provision_user", AsyncMock(return_value=mock_user)),
    ):
        result = await get_current_user(request, db=mock_db)

    assert result is mock_user


@pytest.mark.asyncio
async def test_missing_bearer_token_still_401(mock_db):
    request = MagicMock()
    request.headers.get.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(request, db=mock_db)

    assert exc_info.value.status_code == 401
