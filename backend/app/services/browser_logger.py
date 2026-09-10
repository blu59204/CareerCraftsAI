"""browser_logger.py — Structured per-action logging for browser-use tasks.

Every browser action (navigate, fill, click, extract, submit) is emitted as a
structured JSON log line so failures can be replayed from logs alone.

Screenshot-on-failure: when BROWSER_DEBUG_SCREENSHOTS=true, a PNG is saved to
BROWSER_DEBUG_DIR/{run_id}/{timestamp}.png on any exception inside a browser task.
Mount BROWSER_DEBUG_DIR as a Docker named volume to persist screenshots across
container restarts.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Literal

from app.core.config import settings
from app.core.event_bus import emit

logger = logging.getLogger(__name__)

ActionType = Literal["navigate", "fill", "click", "extract", "submit", "login", "captcha", "error"]


def log_browser_action(
    *,
    run_id: str | None,
    action: ActionType,
    url: str = "",
    field: str = "",
    detail: str = "",
    duration_ms: int | None = None,
    success: bool = True,
) -> None:
    """Emit a structured log line for every browser action.

    Each line is machine-parseable JSON via the standard Python logging formatter;
    callers supply the semantic fields and this function handles both the log record
    and the SSE event so the frontend browser-panel and server logs stay in sync.
    """
    record: dict = {
        "browser_action": action,
        "url": url[:300] if url else "",
        "field": field,
        "detail": detail[:500] if detail else "",
        "success": success,
    }
    if duration_ms is not None:
        record["duration_ms"] = duration_ms

    level = logging.INFO if success else logging.WARNING
    logger.log(level, "browser_action=%s url=%s field=%s success=%s detail=%s",
               action, record["url"], field, success, record["detail"])

    if run_id:
        emit(run_id, "browser", {
            "phase": action,
            "url": record["url"],
            "field": field,
            "detail": record["detail"],
            "success": success,
            **({"duration_ms": duration_ms} if duration_ms is not None else {}),
        })


def save_debug_screenshot(
    *,
    run_id: str | None,
    page,  # playwright Page — typed as Any to avoid hard import
    reason: str = "failure",
) -> str | None:
    """Save a Playwright page screenshot to the debug volume on failure.

    Returns the path where the screenshot was saved, or None if screenshots are
    disabled or the save failed.

    Only active when BROWSER_DEBUG_SCREENSHOTS=true.
    """
    if not settings.BROWSER_DEBUG_SCREENSHOTS:
        return None

    import asyncio
    debug_dir = Path(settings.BROWSER_DEBUG_DIR)
    sub = debug_dir / (run_id or "unknown")
    sub.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    path = sub / f"{reason}_{ts}.png"

    async def _snap():
        try:
            await page.screenshot(path=str(path), full_page=True)
            logger.info("Debug screenshot saved: %s", path)
            if run_id:
                emit(run_id, "browser", {
                    "phase": "screenshot_saved",
                    "path": str(path),
                    "reason": reason,
                })
            return str(path)
        except Exception as exc:
            logger.debug("Failed to save debug screenshot: %s", exc)
            return None

    try:
        return asyncio.get_event_loop().run_until_complete(_snap())
    except RuntimeError:
        # We're already inside a running event loop — schedule as task
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, _snap())
            try:
                return future.result(timeout=5)
            except Exception:
                return None


class BrowserActionTimer:
    """Context manager that measures action duration and logs the result."""

    def __init__(
        self,
        *,
        run_id: str | None,
        action: ActionType,
        url: str = "",
        field: str = "",
        detail: str = "",
    ):
        self.run_id = run_id
        self.action = action
        self.url = url
        self.field = field
        self.detail = detail
        self._start: float = 0.0

    def __enter__(self) -> "BrowserActionTimer":
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        duration_ms = int((time.monotonic() - self._start) * 1000)
        success = exc_type is None
        log_browser_action(
            run_id=self.run_id,
            action=self.action,
            url=self.url,
            field=self.field,
            detail=str(exc_val)[:300] if not success else self.detail,
            duration_ms=duration_ms,
            success=success,
        )
