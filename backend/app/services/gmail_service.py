import logging
from langchain_google_community import GmailToolkit

logger = logging.getLogger(__name__)


class GmailMCPClient:
    """Gmail operations via langchain-google-community GmailToolkit."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._toolkit: GmailToolkit | None = None

    def _get_toolkit(self) -> GmailToolkit:
        if self._toolkit is None:
            self._toolkit = GmailToolkit()
        return self._toolkit

    def search_threads(self, query: str, max_results: int = 10) -> list[dict]:
        try:
            toolkit = self._get_toolkit()
            tools = {t.name: t for t in toolkit.get_tools()}
            search_tool = tools.get("search_gmail")
            if not search_tool:
                logger.warning("Gmail search tool not available")
                return []
            return search_tool.run({"query": query, "max_results": max_results}) or []
        except Exception as exc:
            logger.warning("Gmail search failed for user %s: %s", self.user_id, exc)
            return []

    def get_thread(self, thread_id: str) -> dict:
        try:
            toolkit = self._get_toolkit()
            tools = {t.name: t for t in toolkit.get_tools()}
            return tools["get_gmail_thread"].run({"thread_id": thread_id}) or {}
        except Exception as exc:
            logger.warning("Gmail get_thread failed for user %s: %s", self.user_id, exc)
            return {}

    def send_message(self, to: str, subject: str, body: str) -> dict:
        """Send email. MUST only be called after explicit human approval."""
        toolkit = self._get_toolkit()
        tools = {t.name: t for t in toolkit.get_tools()}
        return tools["send_gmail_message"].run({"to": [to], "subject": subject, "message": body})
