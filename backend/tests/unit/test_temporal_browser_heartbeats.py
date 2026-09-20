"""Heartbeat and cancellation coverage for long-running browser activities."""

import asyncio

import pytest


@pytest.mark.asyncio
async def test_browser_heartbeat_runs_until_a_long_running_stage_finishes(monkeypatch) -> None:
    """Browser work must refresh Temporal's heartbeat while it is in flight."""
    from app.workflows import activities

    heartbeats: list[dict] = []
    monkeypatch.setattr(activities.activity, "heartbeat", lambda detail: heartbeats.append(detail))
    monkeypatch.setattr(activities.activity, "is_cancelled", lambda: False)

    result = await activities.run_with_browser_heartbeats(
        asyncio.sleep(0.04, result={"status": "completed"}),
        stage="browser_prepare",
        heartbeat_interval_seconds=0.005,
    )

    assert result == {"status": "completed"}
    assert len(heartbeats) >= 2
    assert all(heartbeat["stage"] == "browser_prepare" for heartbeat in heartbeats)
    assert all("elapsed_seconds" in heartbeat for heartbeat in heartbeats)


@pytest.mark.asyncio
async def test_browser_heartbeat_cancels_stage_when_temporal_requests_cancellation(
    monkeypatch,
) -> None:
    """A cancellation request stops browser work before the next side effect."""
    from app.workflows import activities

    heartbeats: list[dict] = []
    checks = iter([False, True])
    monkeypatch.setattr(activities.activity, "heartbeat", lambda detail: heartbeats.append(detail))
    monkeypatch.setattr(activities.activity, "is_cancelled", lambda: next(checks, True))

    with pytest.raises(asyncio.CancelledError):
        await activities.run_with_browser_heartbeats(
            asyncio.sleep(1),
            stage="browser_review",
            heartbeat_interval_seconds=0.005,
        )

    assert any(heartbeat["cancellation_requested"] for heartbeat in heartbeats)
