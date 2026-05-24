from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage


class _MutableFakeLLM:
    """Mutable LLM stand-in: supports ``mock_llm.responses = [...]`` after construction."""

    def __init__(self, responses: list[str] | None = None):
        self.responses: list[str] = responses or ["mocked LLM response"]
        self._call_count = 0

    def invoke(self, messages) -> AIMessage:
        if self._call_count < len(self.responses):
            content = self.responses[self._call_count]
        else:
            content = self.responses[-1] if self.responses else ""
        self._call_count += 1
        return AIMessage(content=content)


@pytest.fixture
def mock_llm():
    return _MutableFakeLLM()


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = "00000000-0000-0000-0000-000000000001"
    user.email = "test@example.com"
    user.clerk_id = "user_test123"
    return user
