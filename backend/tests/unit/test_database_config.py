import importlib
from unittest.mock import patch

import pytest


@pytest.mark.parametrize(
    "environment, expected",
    [
        ("development", True),
        ("test", False),
        ("staging", False),
        ("production", False),
    ],
)
def test_database_echo_is_development_only(environment, expected, monkeypatch):
    import app.core.database as database_module

    monkeypatch.setattr(database_module.settings, "APP_ENV", environment)
    with patch("sqlalchemy.ext.asyncio.create_async_engine") as create_engine:
        importlib.reload(database_module)
    assert create_engine.call_args.kwargs["echo"] is expected
