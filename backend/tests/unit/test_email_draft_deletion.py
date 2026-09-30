import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1.email import _discard_drafts, approve_and_send


@pytest.mark.parametrize("single", [False, True])
def test_discard_only_updates_current_users_pending_email_runs(single):
    user_id, draft_id = uuid.uuid4(), uuid.uuid4()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [draft_id]
    db = SimpleNamespace(execute=AsyncMock(return_value=result))

    assert asyncio.run(_discard_drafts(db, user_id, draft_id if single else None)) == 1
    statement = db.execute.call_args.args[0]
    compiled = statement.compile()
    sql = str(compiled)
    assert sql.startswith("UPDATE agent_runs SET")
    assert "agent_runs.user_id =" in sql
    assert "agent_runs.agent_type =" in sql
    assert "agent_runs.status =" in sql
    assert user_id in compiled.params.values()
    assert "email" in compiled.params.values()
    assert "awaiting_approval" in compiled.params.values()
    assert "cancelled" in compiled.params.values()
    assert (draft_id in compiled.params.values()) is single


def test_missing_or_sent_draft_is_not_deleted():
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db = SimpleNamespace(execute=AsyncMock(return_value=result))
    with pytest.raises(HTTPException) as error:
        asyncio.run(_discard_drafts(db, uuid.uuid4(), uuid.uuid4()))
    assert error.value.status_code == 404
    assert asyncio.run(_discard_drafts(db, uuid.uuid4())) == 0


def test_discarded_draft_cannot_be_approved_for_sending():
    result = MagicMock()
    result.scalar_one_or_none.return_value = SimpleNamespace(status="cancelled")
    db = SimpleNamespace(execute=AsyncMock(return_value=result))
    user = SimpleNamespace(id=uuid.uuid4())
    with pytest.raises(HTTPException) as error:
        asyncio.run(approve_and_send(str(uuid.uuid4()), db=db, current_user=user))
    assert error.value.status_code == 400
