"""Gmail and Drive services use the Nango proxy without Google tokens."""

from __future__ import annotations

import base64

from app.integrations.schemas import IntegrationProxyResponse
from app.services.drive_service import upload_to_drive
from app.services.gmail_service import GmailMCPClient


def test_gmail_send_uses_nango_proxy(monkeypatch) -> None:
    captured = {}

    def fake_proxy_request(**kwargs):
        captured.update(kwargs)
        return IntegrationProxyResponse(status_code=200, data={"id": "message-1"})

    monkeypatch.setattr("app.services.gmail_service.proxy_request", fake_proxy_request)

    assert GmailMCPClient("00000000-0000-0000-0000-000000000001").send_message(
        "to@example.com", "Subject", "Body"
    ) == {"id": "message-1"}
    assert captured["provider"] == "gmail"
    assert captured["method"] == "POST"
    assert captured["path"] == "gmail/v1/users/me/messages/send"
    raw = captured["json_data"]["raw"]
    assert b"Subject: Subject" in base64.urlsafe_b64decode(raw + "==")


def test_gmail_draft_uses_nango_proxy(monkeypatch) -> None:
    captured = {}

    def fake_proxy_request(**kwargs):
        captured.update(kwargs)
        return IntegrationProxyResponse(status_code=200, data={"id": "draft-1"})

    monkeypatch.setattr("app.services.gmail_service.proxy_request", fake_proxy_request)

    assert GmailMCPClient("00000000-0000-0000-0000-000000000001").save_draft(
        "to@example.com", "Subject", "Body"
    ) == {"id": "draft-1"}
    assert captured["path"] == "gmail/v1/users/me/drafts"
    raw = captured["json_data"]["message"]["raw"]
    assert b"To: to@example.com" in base64.urlsafe_b64decode(raw + "==")


def test_gmail_get_message_metadata_uses_nango_proxy(monkeypatch) -> None:
    captured = {}

    def fake_proxy_request(**kwargs):
        captured.update(kwargs)
        return IntegrationProxyResponse(
            status_code=200,
            data={
                "id": "msg-1",
                "snippet": "a body preview that must never leak",
                "payload": {"headers": [{"name": "From", "value": "a@b.com"}]},
            },
        )

    monkeypatch.setattr("app.services.gmail_service.proxy_request", fake_proxy_request)

    result = GmailMCPClient("00000000-0000-0000-0000-000000000001").get_message_metadata("msg-1")

    assert captured["provider"] == "gmail"
    assert captured["method"] == "GET"
    assert captured["path"].startswith("gmail/v1/users/me/messages/msg-1?")
    assert "format=metadata" in captured["path"]
    assert captured["path"].count("metadataHeaders=") == 4
    assert "snippet" not in result
    assert result["payload"]["headers"][0]["value"] == "a@b.com"


def test_gmail_get_message_metadata_degrades_on_failure(monkeypatch) -> None:
    def fake_proxy_request(**kwargs):
        raise RuntimeError("Gmail is not connected through Nango")

    monkeypatch.setattr("app.services.gmail_service.proxy_request", fake_proxy_request)

    assert (
        GmailMCPClient("00000000-0000-0000-0000-000000000001").get_message_metadata("msg-1")
        == {}
    )


def test_gmail_archive_message_uses_nango_proxy(monkeypatch) -> None:
    captured = {}

    def fake_proxy_request(**kwargs):
        captured.update(kwargs)
        return IntegrationProxyResponse(status_code=200, data={"id": "msg-1", "labelIds": []})

    monkeypatch.setattr("app.services.gmail_service.proxy_request", fake_proxy_request)

    result = GmailMCPClient("00000000-0000-0000-0000-000000000001").archive_message("msg-1")

    assert captured["method"] == "POST"
    assert captured["path"] == "gmail/v1/users/me/messages/msg-1/modify"
    assert captured["json_data"] == {"removeLabelIds": ["INBOX"]}
    assert result == {"id": "msg-1", "labelIds": []}


def test_gmail_archive_message_degrades_on_failure(monkeypatch) -> None:
    def fake_proxy_request(**kwargs):
        raise RuntimeError("Gmail is not connected through Nango")

    monkeypatch.setattr("app.services.gmail_service.proxy_request", fake_proxy_request)

    assert GmailMCPClient("00000000-0000-0000-0000-000000000001").archive_message("msg-1") == {}


def test_drive_upload_uses_nango_proxy(monkeypatch) -> None:
    captured = {}

    def fake_proxy_request(**kwargs):
        captured.update(kwargs)
        return IntegrationProxyResponse(status_code=200, data={"id": "drive-1"})

    monkeypatch.setattr("app.services.drive_service.proxy_request", fake_proxy_request)

    assert upload_to_drive(
        "00000000-0000-0000-0000-000000000001", "resume.pdf", b"pdf", "application/pdf"
    ) == {"id": "drive-1"}
    assert captured["provider"] == "google_drive"
    assert captured["method"] == "POST"
    assert captured["path"].startswith("upload/drive/v3/files?")
    assert b'"name": "resume.pdf"' in captured["content"]
