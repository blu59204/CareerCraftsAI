"""Unit tests for the /notifications API — auth-gating only. Deeper
behavior (preference gating, list/mark-read semantics) is covered at the
service layer in test_notification_service.py, matching this repo's existing
split between route-level auth tests and service-level logic tests."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def make_client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_list_notifications_requires_auth():
    async with make_client() as client:
        resp = await client.get("/api/v1/notifications")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_mark_notification_read_requires_auth():
    async with make_client() as client:
        resp = await client.patch("/api/v1/notifications/00000000-0000-0000-0000-000000000000/read")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_mark_all_read_requires_auth():
    async with make_client() as client:
        resp = await client.post("/api/v1/notifications/read-all")
    assert resp.status_code == 401
