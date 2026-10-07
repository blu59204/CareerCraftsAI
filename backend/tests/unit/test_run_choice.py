"""Per-run model / resume picks: ownership is enforced and the pick is honored."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.run_utils import _check_run_choices
from app.core import sync_db


def _db(found: bool):
    result = MagicMock()
    result.first.return_value = (uuid.uuid4(),) if found else None
    return SimpleNamespace(execute=AsyncMock(return_value=result))


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["model_setting_id", "resume_document_id"])
async def test_foreign_id_is_404(key):
    user = SimpleNamespace(id=uuid.uuid4())
    with pytest.raises(HTTPException) as exc:
        await _check_run_choices(_db(False), user, {key: str(uuid.uuid4())})
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_malformed_id_is_422_and_owned_or_absent_passes():
    user = SimpleNamespace(id=uuid.uuid4())
    with pytest.raises(HTTPException) as exc:
        await _check_run_choices(_db(True), user, {"model_setting_id": "nope"})
    assert exc.value.status_code == 422
    await _check_run_choices(_db(True), user, {"model_setting_id": str(uuid.uuid4())})
    await _check_run_choices(_db(False), user, {})  # no picks -> no ownership query


def _factory(rows):
    """Stand-in for _get_sync_factory(): successive execute() calls return `rows`."""
    db = MagicMock()
    db.execute.side_effect = [
        MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=r))))
        for r in rows
    ]
    session = MagicMock()
    session.__enter__.return_value = db
    session.__exit__.return_value = False
    return lambda: (lambda: session)


def test_fetch_model_settings_uses_chosen_row_else_active():
    chosen, active = object(), object()
    user = str(uuid.uuid4())
    with patch.object(sync_db, "_get_sync_factory", _factory([chosen])):
        with sync_db.run_choice({"model_setting_id": str(uuid.uuid4())}):
            assert sync_db.fetch_model_settings(user) is chosen
    # picked id is not the user's (lookup finds nothing) -> falls back to the active row
    with patch.object(sync_db, "_get_sync_factory", _factory([None, active])):
        with sync_db.run_choice({"model_setting_id": str(uuid.uuid4())}):
            assert sync_db.fetch_model_settings(user) is active
    # no pick -> active row
    with patch.object(sync_db, "_get_sync_factory", _factory([active])):
        assert sync_db.fetch_model_settings(user) is active


def test_choice_is_reset_after_run():
    with sync_db.run_choice({"model_setting_id": str(uuid.uuid4())}):
        assert sync_db._chosen("model_setting_id") is not None
    assert sync_db._chosen("model_setting_id") is None
