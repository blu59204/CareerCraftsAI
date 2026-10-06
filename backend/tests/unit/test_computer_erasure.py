import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


@pytest.fixture
def relay_module(monkeypatch, tmp_path):
    for key in ("SANDBOX_RELAY_TOKEN", "COMPUTER_TOKEN", "COMPUTER_SUPERVISOR_TOKEN"):
        monkeypatch.setenv(key, "fixture-token-never-live")
    path = Path(__file__).resolve().parents[3] / "deploy/computers/relay.py"
    spec = importlib.util.spec_from_file_location("fixture_relay", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DB_PATH = str(tmp_path / "sessions.db")
    with module.database() as db:
        db.execute(
            "CREATE TABLE sessions(user_id TEXT PRIMARY KEY, enabled INTEGER, "
            "running INTEGER, touched REAL, purged INTEGER DEFAULT 0)"
        )
    return module


@pytest.mark.asyncio
async def test_purge_is_owner_scoped_idempotent_and_blocks_recreation(relay_module, monkeypatch):
    relay = relay_module
    owner, other = str(uuid4()), str(uuid4())
    with relay.database() as db:
        db.executemany("INSERT INTO sessions VALUES (?,1,1,0,0)", [(owner,), (other,)])
    supervisor = AsyncMock(return_value={"purged": True})
    monkeypatch.setattr(relay, "supervisor", supervisor)
    assert await relay.purge(UUID(owner)) == {"purged": True}
    assert await relay.purge(UUID(owner)) == {"purged": True}
    assert supervisor.await_args.args == (relay.identity(owner), "purge")
    with relay.database() as db:
        assert (
            dict(db.execute("SELECT * FROM sessions WHERE user_id=?", (other,)).fetchone())[
                "running"
            ]
            == 1
        )
    with pytest.raises(HTTPException) as error:
        await relay.ensure(owner, True)
    assert error.value.status_code == 410


@pytest.mark.asyncio
async def test_failed_purge_retains_retry_state_and_never_claims_success(relay_module, monkeypatch):
    relay = relay_module
    owner = str(uuid4())
    with relay.database() as db:
        db.execute("INSERT INTO sessions VALUES (?,1,1,0,0)", (owner,))
    monkeypatch.setattr(relay, "supervisor", AsyncMock(side_effect=HTTPException(503, "busy")))
    with pytest.raises(HTTPException):
        await relay.purge(UUID(owner))
    with relay.database() as db:
        row = db.execute("SELECT * FROM sessions WHERE user_id=?", (owner,)).fetchone()
    assert row["enabled"] == 0 and row["running"] == 1 and row["purged"] == 1


def test_purge_route_requires_relay_authentication(relay_module):
    client = TestClient(relay_module.app)
    assert client.delete("/users/" + str(uuid4())).status_code == 401


@pytest.mark.asyncio
async def test_removed_relay_configuration_cannot_skip_a_previous_computer_owner(
    monkeypatch,
):
    from unittest.mock import MagicMock

    from app.services import computer_service as service

    monkeypatch.setattr(service.settings, "SANDBOX_RELAY_URL", "")
    monkeypatch.setattr(service.settings, "SANDBOX_RELAY_TOKEN", "")
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = uuid4()
    db.execute.return_value = result
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=db)
    context.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: context)
    with pytest.raises(RuntimeError, match="Restore sandbox"):
        await service.purge_user(uuid4())
    result.scalar_one_or_none.return_value = None
    await service.purge_user(uuid4())
