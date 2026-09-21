"""Gmail operations through the Nango credential proxy."""

from __future__ import annotations

import base64
from email.message import EmailMessage
from urllib.parse import urlencode

from app.integrations.exceptions import IntegrationActionError
from app.services.integration_proxy_service import proxy_request


class GmailSendError(RuntimeError):
    """Raised when Nango or Gmail cannot send an approved message."""


class GmailMCPClient:
    """Compatibility surface for agents; credentials stay exclusively in Nango."""

    def __init__(self, user_id: str):
        self.user_id = user_id

    def search_threads(self, query: str, max_results: int = 10) -> list[dict]:
        try:
            result = proxy_request(
                user_id=self.user_id,
                provider="gmail",
                method="GET",
                path=(
                    "gmail/v1/users/me/messages?"
                    f"{urlencode({'q': query, 'maxResults': max_results})}"
                ),
            )
        except Exception:
            return []
        return result.data.get("messages", []) if isinstance(result.data, dict) else []

    def get_thread(self, thread_id: str) -> dict:
        try:
            result = proxy_request(
                user_id=self.user_id,
                provider="gmail",
                method="GET",
                path=f"gmail/v1/users/me/threads/{thread_id}",
            )
        except Exception:
            return {}
        return result.data if isinstance(result.data, dict) else {}

    def send_message(self, to: str, subject: str, body: str) -> dict:
        message = EmailMessage()
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")
        try:
            result = proxy_request(
                user_id=self.user_id,
                provider="gmail",
                method="POST",
                path="gmail/v1/users/me/messages/send",
                json_data={"raw": raw},
            )
        except IntegrationActionError as exc:
            raise GmailSendError("Gmail rejected the approved message") from exc
        except Exception as exc:
            raise GmailSendError("Gmail is not connected through Nango") from exc
        if not isinstance(result.data, dict):
            raise GmailSendError("Gmail returned an invalid response")
        return result.data

    def save_draft(self, to: str, subject: str, body: str) -> dict:
        message = EmailMessage()
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")
        try:
            result = proxy_request(
                user_id=self.user_id,
                provider="gmail",
                method="POST",
                path="gmail/v1/users/me/drafts",
                json_data={"message": {"raw": raw}},
            )
        except IntegrationActionError as exc:
            raise GmailSendError("Gmail rejected the draft") from exc
        except Exception as exc:
            raise GmailSendError("Gmail is not connected through Nango") from exc
        if not isinstance(result.data, dict):
            raise GmailSendError("Gmail returned an invalid response")
        return result.data
