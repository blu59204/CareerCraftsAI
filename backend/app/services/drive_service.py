"""Upload files to a user's Google Drive using their connected Google account.

Requires the `drive.file` scope (granted when the user connects Google). That
scope lets the app create and manage only the files it creates — it cannot read
the rest of the user's Drive. Uses a multipart upload so metadata (filename) and
content go in a single request.
"""
import logging

import httpx

from app.services.google_oauth_service import get_valid_google_access_token

logger = logging.getLogger(__name__)

DRIVE_UPLOAD_URL = (
    "https://www.googleapis.com/upload/drive/v3/files"
    "?uploadType=multipart&fields=id,name,webViewLink"
)


class DriveError(RuntimeError):
    """Raised when a Drive upload cannot complete, with an actionable reason."""


def _extract_drive_error(response: httpx.Response) -> str:
    try:
        err = response.json().get("error", {})
    except Exception:
        return f"Drive API error {response.status_code}"
    message = err.get("message") if isinstance(err, dict) else None
    status = response.status_code
    lowered = (message or "").lower()
    if status == 403 and "insufficient" in lowered:
        return (
            "Google was connected without Drive permission. Disconnect Google in "
            "Settings, then Connect again and approve Drive access."
        )
    if status == 403 and "has not been used" in lowered:
        return "Google Drive API is not enabled in the Google Cloud project. Enable it and retry."
    if status == 401:
        return "Google rejected the stored token. Disconnect and reconnect Google in Settings."
    return message or f"Drive API error {status}"


def upload_to_drive(
    user_id: str,
    filename: str,
    content: bytes,
    mime_type: str = "application/octet-stream",
) -> dict:
    """Upload bytes to the user's Drive. Returns {id, name, webViewLink}."""
    access_token = get_valid_google_access_token(user_id)
    if not access_token:
        raise DriveError(
            "Google is not connected (or the token could not be refreshed). "
            "Connect Google in Settings and approve Drive access."
        )

    boundary = "careercraft-drive-boundary"
    metadata = f'{{"name": {_json_string(filename)}}}'
    body = (
        f"--{boundary}\r\n"
        "Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{metadata}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8") + content + f"\r\n--{boundary}--".encode("utf-8")

    response = httpx.post(
        DRIVE_UPLOAD_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": f"multipart/related; boundary={boundary}",
        },
        content=body,
        timeout=60,
    )
    if response.status_code >= 400:
        raise DriveError(_extract_drive_error(response))
    return response.json()


def _json_string(value: str) -> str:
    """Minimal JSON string escaping for the filename in the metadata part."""
    import json

    return json.dumps(value)
