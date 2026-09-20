"""Google Drive uploads through the Nango credential proxy."""

from __future__ import annotations

import json

from app.integrations.exceptions import IntegrationActionError
from app.services.integration_proxy_service import proxy_request


class DriveError(RuntimeError):
    """Raised when a Nango-managed Drive upload cannot complete."""


def upload_to_drive(
    user_id: str,
    filename: str,
    content: bytes,
    mime_type: str = "application/octet-stream",
) -> dict:
    """Upload a document without retrieving a Google OAuth token."""
    boundary = "careercraft-drive-boundary"
    metadata = json.dumps({"name": filename})
    body = (
        (
            f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{metadata}\r\n--{boundary}\r\nContent-Type: {mime_type}\r\n\r\n"
        ).encode()
        + content
        + f"\r\n--{boundary}--".encode()
    )
    try:
        result = proxy_request(
            user_id=user_id,
            provider="google_drive",
            method="POST",
            path="upload/drive/v3/files?uploadType=multipart&fields=id,name,webViewLink",
            headers={"Content-Type": f"multipart/related; boundary={boundary}"},
            content=body,
        )
    except IntegrationActionError as exc:
        raise DriveError("Google Drive rejected the upload") from exc
    except Exception as exc:
        raise DriveError("Google Drive is not connected through Nango") from exc
    if not isinstance(result.data, dict):
        raise DriveError("Google Drive returned an invalid response")
    return result.data
