import logging
import base64
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import httpx
from langchain_google_community import GmailToolkit

from app.core.config import settings
from app.core.security import decrypt_api_key, encrypt_api_key
from app.core.sync_db import _get_sync_factory
from app.models.db import User

logger = logging.getLogger(__name__)
# Public OAuth endpoint, not a credential.
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105  # nosec B105
GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


class GmailMCPClient:
    """Gmail operations via langchain-google-community GmailToolkit."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._toolkit: GmailToolkit | None = None
        self._available: bool | None = None

    def _get_toolkit(self) -> GmailToolkit | None:
        if self._available is False:
            return None
        if self._toolkit is None:
            try:
                self._toolkit = GmailToolkit()
                self._available = True
            except Exception as exc:
                logger.warning(
                    "Gmail OAuth credentials not available for user %s: %s",
                    self.user_id,
                    exc,
                )
                self._available = False
                return None
        return self._toolkit

    def _get_google_tokens(self) -> tuple[str | None, str | None, datetime | None]:
        factory = _get_sync_factory()
        with factory() as db:
            user = db.get(User, uuid.UUID(self.user_id))
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

    def _store_access_token(self, access_token: str, expires_in: int = 3600) -> None:
        factory = _get_sync_factory()
        with factory() as db:
            user = db.get(User, uuid.UUID(self.user_id))
            if not user:
                return
            user.google_access_token_enc = encrypt_api_key(access_token, settings.APP_SECRET_KEY)
            user.google_token_expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=max(expires_in - 60, 60),
            )
            db.commit()

    def _refresh_google_access_token(self, refresh_token: str) -> str | None:
        if not settings.GOOGLE_OAUTH_CLIENT_ID or not settings.GOOGLE_OAUTH_CLIENT_SECRET:
            logger.warning("Google OAuth client credentials missing; cannot refresh Gmail token")
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
        self._store_access_token(access_token, int(payload.get("expires_in") or 3600))
        return access_token

    def _get_valid_google_access_token(self) -> str | None:
        access_token, refresh_token, expires_at = self._get_google_tokens()
        if not access_token and refresh_token:
            return self._refresh_google_access_token(refresh_token)
        if not access_token:
            return None

        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= datetime.now(timezone.utc) + timedelta(seconds=30):
                return self._refresh_google_access_token(refresh_token) if refresh_token else None
        return access_token

    def _send_with_google_api(self, to: str, subject: str, body: str) -> dict | None:
        access_token = self._get_valid_google_access_token()
        if not access_token:
            return None

        message = EmailMessage()
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")

        response = httpx.post(
            GMAIL_SEND_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            json={"raw": raw},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def search_threads(self, query: str, max_results: int = 10) -> list[dict]:
        try:
            toolkit = self._get_toolkit()
            if toolkit is None:
                return []
            tools = {t.name: t for t in toolkit.get_tools()}
            search_tool = tools.get("search_gmail")
            if not search_tool:
                logger.warning("Gmail search tool not available")
                return []
            return search_tool.run({"query": query, "max_results": max_results}) or []
        except Exception as exc:
            logger.warning("Gmail search failed for user %s: %s", self.user_id, exc)
            return []

    def get_thread(self, thread_id: str) -> dict:
        try:
            toolkit = self._get_toolkit()
            if toolkit is None:
                return {}
            tools = {t.name: t for t in toolkit.get_tools()}
            return tools["get_gmail_thread"].run({"thread_id": thread_id}) or {}
        except Exception as exc:
            logger.warning("Gmail get_thread failed for user %s: %s", self.user_id, exc)
            return {}

    def send_message(self, to: str, subject: str, body: str) -> dict:
        """Send email. MUST only be called after explicit human approval."""
        api_result = self._send_with_google_api(to, subject, body)
        if api_result is not None:
            return api_result

        toolkit = self._get_toolkit()
        if toolkit is None:
            raise RuntimeError(
                "Gmail OAuth credentials are not configured. Connect Google again and approve Gmail access."
            )
        tools = {t.name: t for t in toolkit.get_tools()}
        return tools["send_gmail_message"].run({"to": [to], "subject": subject, "message": body})
