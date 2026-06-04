"""Shared Google OAuth token access for backend services (Gmail, Drive).

Reads the per-user encrypted Google tokens, refreshes the access token when it
is missing/expired (requires GOOGLE_OAUTH_CLIENT_ID/SECRET), and returns a valid
access token or None when the user has not connected Google.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import settings
from app.core.security import decrypt_api_key, encrypt_api_key
from app.core.sync_db import _get_sync_factory
from app.models.db import User

logger = logging.getLogger(__name__)
# Public OAuth endpoint, not a credential.
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105  # nosec B105


def _get_tokens(user_id: str) -> tuple[str | None, str | None, datetime | None]:
    factory = _get_sync_factory()
    with factory() as db:
        user = db.get(User, uuid.UUID(user_id))
        if not user:
            return None, None, None
        access_token = (
            decrypt_api_key(user.google_access_token_enc, settings.APP_SECRET_KEY)
            if user.google_access_token_enc
            else None
        )
        refresh_token = (
            decrypt_api_key(user.google_refresh_token_enc, settings.APP_SECRET_KEY)
            if user.google_refresh_token_enc
            else None
        )
        return access_token, refresh_token, user.google_token_expires_at


def _store_access_token(user_id: str, access_token: str, expires_in: int = 3600) -> None:
    factory = _get_sync_factory()
    with factory() as db:
        user = db.get(User, uuid.UUID(user_id))
        if not user:
            return
        user.google_access_token_enc = encrypt_api_key(access_token, settings.APP_SECRET_KEY)
        user.google_token_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=max(expires_in - 60, 60),
        )
        db.commit()


def _refresh(user_id: str, refresh_token: str) -> str | None:
    if not settings.GOOGLE_OAUTH_CLIENT_ID or not settings.GOOGLE_OAUTH_CLIENT_SECRET:
        logger.warning("Google OAuth client credentials missing; cannot refresh access token")
        return None

    response = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    access_token = payload.get("access_token")
    if not access_token:
        return None
    _store_access_token(user_id, access_token, int(payload.get("expires_in") or 3600))
    return access_token


def get_valid_google_access_token(user_id: str) -> str | None:
    """Return a non-expired Google access token for the user, refreshing if needed."""
    access_token, refresh_token, expires_at = _get_tokens(user_id)

    if not access_token and refresh_token:
        return _refresh(user_id, refresh_token)
    if not access_token:
        return None

    if expires_at:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc) + timedelta(seconds=30):
            return _refresh(user_id, refresh_token) if refresh_token else None

    return access_token
