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

    def get_message_metadata(self, message_id: str) -> dict:
        """Fetch header metadata only (From/Subject/Date/List-Unsubscribe).

        Read path used opportunistically while listing inbox-cleanup
        candidates, so a failure degrades to `{}` (same pattern as
        `search_threads`/`get_thread`) rather than raising and aborting the
        whole list. Gmail's `format=metadata` never includes the message
        body, but its `snippet` field is a short body preview — stripped
        here so this method can never surface any message content.
        """
        query = urlencode(
            {
                "format": "metadata",
                "metadataHeaders": ["From", "Subject", "Date", "List-Unsubscribe"],
            },
            doseq=True,
        )
        try:
            result = proxy_request(
                user_id=self.user_id,
                provider="gmail",
                method="GET",
                path=f"gmail/v1/users/me/messages/{message_id}?{query}",
            )
        except Exception:
            return {}
        if not isinstance(result.data, dict):
            return {}
        data = dict(result.data)
        data.pop("snippet", None)
        return data

    def archive_message(self, message_id: str) -> dict:
        """Remove INBOX label via Gmail's messages.modify.

        Batch cleanup action over a list of already-known message IDs, so —
        like the read paths above — a single failed ID degrades to `{}`
        instead of raising and aborting every other message in the batch.
        """
        try:
            result = proxy_request(
                user_id=self.user_id,
                provider="gmail",
                method="POST",
                path=f"gmail/v1/users/me/messages/{message_id}/modify",
                json_data={"removeLabelIds": ["INBOX"]},
            )
        except Exception:
            return {}
        return result.data if isinstance(result.data, dict) else {}

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
