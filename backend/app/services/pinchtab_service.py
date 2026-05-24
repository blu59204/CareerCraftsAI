import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class PinchTabClient:
    def __init__(self, session_id: str):
        self._base = settings.PINCHTAB_URL
        self._session = session_id

    def _post(self, path: str, data: dict) -> dict:
        resp = httpx.post(
            f"{self._base}/{path}", json={**data, "sessionId": self._session}
        )
        resp.raise_for_status()
        return resp.json()

    def navigate(self, url: str) -> dict:
        return self._post("navigate", {"url": url})

    def snapshot(self) -> dict:
        return self._post("snapshot", {})

    def fill(self, selector: str, value: str) -> dict:
        return self._post("fill", {"selector": selector, "value": value})

    def click(self, selector: str) -> dict:
        return self._post("action", {"action": "click", "selector": selector})

    def close(self) -> None:
        try:
            httpx.post(
                f"{self._base}/session/close", json={"sessionId": self._session}
            )
        except Exception as exc:
            logger.warning(
                "PinchTab session close failed for %s: %s", self._session, exc
            )


def new_session(user_id: str) -> PinchTabClient:
    """Create isolated browser session per user."""
    resp = httpx.post(
        f"{settings.PINCHTAB_URL}/session/new", json={"userId": user_id}
    )
    resp.raise_for_status()
    session_id = resp.json()["sessionId"]
    return PinchTabClient(session_id)
