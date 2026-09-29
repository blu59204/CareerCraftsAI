import subprocess
import sys
from pathlib import Path

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
def test_database_echo_is_development_only(environment, expected):
    child_code = f"""
import importlib
from unittest.mock import patch

import app.core.database as database_module

database_module.settings.APP_ENV = {environment!r}
with patch("sqlalchemy.ext.asyncio.create_async_engine") as create_engine:
    importlib.reload(database_module)
assert create_engine.call_args.kwargs["echo"] is {expected!r}
"""
    subprocess.run(
        [sys.executable, "-c", child_code],
        cwd=Path(__file__).parents[2],
        check=True,
    )
