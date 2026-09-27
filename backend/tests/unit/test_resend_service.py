"""Unit tests for resend_service — httpx.post mocked with real httpx.Response
objects (no live network), following this repo's httpx.MockTransport-style
convention for other HTTP-calling services."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from app.services import resend_service


def _settings_with_key(monkeypatch):
    monkeypatch.setattr(resend_service.settings, "RESEND_API_KEY", "re_test_key")


def test_send_transactional_email_skips_when_no_api_key(monkeypatch):
    monkeypatch.setattr(resend_service.settings, "RESEND_API_KEY", "")
    result = resend_service.send_transactional_email("a@b.com", "Subject", "<p>hi</p>")
    assert result == {"skipped": True}


def test_send_transactional_email_success_sends_idempotency_header(monkeypatch):
    _settings_with_key(monkeypatch)
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["headers"] = headers
        return httpx.Response(200, json={"id": "email_123"}, request=httpx.Request("POST", url))

    with patch.object(resend_service.httpx, "post", side_effect=fake_post):
        result = resend_service.send_transactional_email(
            "a@b.com", "Subject", "<p>hi</p>", idempotency_key="notification-email/abc"
        )

    assert result == {"id": "email_123"}
    assert captured["headers"]["Idempotency-Key"] == "notification-email/abc"


def test_send_transactional_email_429_raises_rate_limited_with_retry_after(monkeypatch):
    _settings_with_key(monkeypatch)

    def fake_post(url, headers=None, json=None, timeout=None):
        return httpx.Response(429, headers={"Retry-After": "7"}, json={"message": "rate limited"})

    with patch.object(resend_service.httpx, "post", side_effect=fake_post):
        with pytest.raises(resend_service.EmailRateLimited) as exc_info:
            resend_service.send_transactional_email("a@b.com", "Subject", "<p>hi</p>")

    assert exc_info.value.retry_after == 7.0


def test_send_transactional_email_409_raises_rate_limited_not_rejected(monkeypatch):
    """A 409 (idempotency conflict, either invalid_idempotent_request or
    concurrent_idempotent_requests) means "retry later", not "this request
    is permanently bad" — must not be treated as EmailRejected."""
    _settings_with_key(monkeypatch)

    def fake_post(url, headers=None, json=None, timeout=None):
        return httpx.Response(409, json={"message": "conflict"})

    with patch.object(resend_service.httpx, "post", side_effect=fake_post):
        with pytest.raises(resend_service.EmailRateLimited):
            resend_service.send_transactional_email("a@b.com", "Subject", "<p>hi</p>")


def test_send_transactional_email_400_raises_rejected(monkeypatch):
    _settings_with_key(monkeypatch)

    def fake_post(url, headers=None, json=None, timeout=None):
        return httpx.Response(400, json={"message": "invalid recipient"})

    with patch.object(resend_service.httpx, "post", side_effect=fake_post):
        with pytest.raises(resend_service.EmailRejected):
            resend_service.send_transactional_email("bad-address", "Subject", "<p>hi</p>")


def test_send_transactional_email_500_raises_base_delivery_error(monkeypatch):
    _settings_with_key(monkeypatch)

    def fake_post(url, headers=None, json=None, timeout=None):
        return httpx.Response(500, json={"message": "oops"}, request=httpx.Request("POST", url))

    with patch.object(resend_service.httpx, "post", side_effect=fake_post):
        with pytest.raises(resend_service.EmailDeliveryError):
            resend_service.send_transactional_email("a@b.com", "Subject", "<p>hi</p>")


def test_send_transactional_email_network_error_raises_delivery_error(monkeypatch):
    _settings_with_key(monkeypatch)

    def fake_post(url, headers=None, json=None, timeout=None):
        raise httpx.ConnectError("connection refused")

    with patch.object(resend_service.httpx, "post", side_effect=fake_post):
        with pytest.raises(resend_service.EmailDeliveryError):
            resend_service.send_transactional_email("a@b.com", "Subject", "<p>hi</p>")
