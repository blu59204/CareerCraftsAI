"""What the agents have remembered about the signed-in member, and the
controls to forget it. Memory rows are keyed by the member's id as text."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db
from app.models.db import User

router = APIRouter(prefix="/memory", tags=["memory"])

# kind -> (table, columns shown). Fixed strings: nothing from the request is
# ever interpolated into SQL.
_KINDS = {
    "learnings": (
        "agent_memory_learnings",
        "id, agent_type, learning AS text, success_rate, sample_count, created_at",
    ),
    "preferences": (
        "agent_memory_preferences",
        "id, preference_key AS label, preference_value AS text, created_at",
    ),
    "procedures": (
        "agent_memory_procedures",
        "id, agent_type, trigger_desc AS text, success_count, last_used_at, created_at",
    ),
    "episodes": (
        "agent_memory_episodes",
        "id, agent_type, task_type, strategy, success, context_summary, "
        "output_summary AS text, created_at",
    ),
}
_LIST = {
    kind: text(
        f"SELECT {cols} FROM {table} WHERE user_id = :uid ORDER BY created_at DESC LIMIT 100"  # noqa: S608
    )
    for kind, (table, cols) in _KINDS.items()
}
_DELETE_ONE = {
    kind: text(f"DELETE FROM {table} WHERE user_id = :uid AND id = :id")  # noqa: S608
    for kind, (table, _) in _KINDS.items()
}
_DELETE_ALL = {
    kind: text(f"DELETE FROM {table} WHERE user_id = :uid")  # noqa: S608
    for kind, (table, _) in _KINDS.items()
}


@router.get("")
async def list_memory(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = str(current_user.id)
    out: dict[str, list[dict]] = {}
    for kind, statement in _LIST.items():
        rows = await db.execute(statement, {"uid": uid})
        out[kind] = [dict(row) for row in rows.mappings().all()]
    return out


@router.delete("")
async def forget_everything(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = str(current_user.id)
    for statement in _DELETE_ALL.values():
        await db.execute(statement, {"uid": uid})
    await db.commit()
    return {"deleted": "all"}


@router.delete("/{kind}/{item_id}")
async def forget_one(
    kind: str,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    statement = _DELETE_ONE.get(kind)
    if statement is None:
        raise HTTPException(status_code=404, detail="Unknown memory type")
    result = await db.execute(statement, {"uid": str(current_user.id), "id": item_id})
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"deleted": item_id}
