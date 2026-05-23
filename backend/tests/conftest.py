import pytest
from unittest.mock import AsyncMock, MagicMock
from langchain_core.language_models.fake_chat_models import FakeChatModel


@pytest.fixture
def mock_llm():
    return FakeChatModel(responses=["mocked LLM response"])


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
