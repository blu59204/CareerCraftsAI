import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class PinchTabClient:
    """
    Thin wrapper around PinchTab HTTP API.
    Uses X-Agent-Id header for per-user tab isolation — no session creation needed.
    API ref: http://localhost:9867 (POST /navigate, GET /snapshot, POST /action)
    """

    def __init__(self, agent_id: str):
        self._base = settings.PINCHTAB_URL.rstrip("/")
        self._headers = {
            "Content-Type": "application/json",
            "X-Agent-Id": agent_id,
        }
        if settings.PINCHTAB_TOKEN:
            self._headers["Authorization"] = f"Bearer {settings.PINCHTAB_TOKEN}"

    def _post(self, path: str, data: dict) -> dict:
        resp = httpx.post(
            f"{self._base}/{path}",
            json=data,
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def _get(self, path: str, params: dict | None = None) -> dict:
        resp = httpx.get(
            f"{self._base}/{path}",
            params=params,
            headers=self._headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def navigate(self, url: str, block_images: bool = True) -> dict:
        return self._post("navigate", {"url": url, "blockImages": block_images})

    def snapshot(self) -> dict:
        """Returns compact interactive snapshot. Parses jobs from page text."""
        return self._get("snapshot", {"format": "compact", "filter": "interactive"})

    def text(self) -> str:
        """Returns Readability-filtered page text."""
        data = self._get("snapshot", {"format": "text"})
        return data.get("text", "") if isinstance(data, dict) else str(data)

    def fill(self, selector: str, value: str) -> dict:
        return self._post("action", {"action": "fill", "selector": selector, "value": value})

    def click(self, selector: str) -> dict:
        return self._post("action", {"action": "click", "selector": selector})

    def close(self) -> None:
        try:
            self._post("tab/close", {})
        except Exception as exc:
            logger.debug("PinchTab tab close failed for agent %s: %s", self._headers["X-Agent-Id"], exc)


def new_session(user_id: str) -> PinchTabClient:
    """
    Return a PinchTabClient scoped to this user.
    PinchTab isolates tabs by X-Agent-Id — no explicit session creation required.
    """
    return PinchTabClient(agent_id=f"careercraft-{user_id}")
