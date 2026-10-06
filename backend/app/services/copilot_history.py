"""Owner-scoped chat storage. Only server-produced assistant/tool messages persist."""

import json
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.core.database import AsyncSessionLocal
from app.models.db import AgentRun, CopilotConversation, User


def merge_user_messages(stored, incoming):
    known = {m["id"] for m in stored}
    fresh = [m for m in incoming if m.get("role") == "user" and m.get("id") not in known]
    if not fresh:
        raise HTTPException(422, "Send a new message to continue this chat")
    if any(len(json.dumps(m).encode()) > 60000 for m in fresh):
        raise HTTPException(422, "Message is too large. Send a shorter message.")
    messages = [*stored, *fresh]
    if len(messages) > 500 or len(json.dumps(messages)) > 500000:
        raise HTTPException(422, "This chat is full. Start a new chat to continue.")
    return messages


async def owner(db, clerk_id):
    user = (
        await db.execute(select(User).where(User.clerk_user_id == clerk_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(404, "User account not found")
    return user.id


async def list_threads(clerk_id):
    async with AsyncSessionLocal() as db:
        user_id = await owner(db, clerk_id)
        rows = (
            await db.execute(
                select(
                    CopilotConversation.thread_id,
                    CopilotConversation.title,
                    CopilotConversation.updated_at,
                )
                .where(CopilotConversation.user_id == user_id)
                .order_by(CopilotConversation.updated_at.desc())
                .limit(100)
            )
        ).all()
        return [
            {
                "thread_id": r.thread_id,
                "title": r.title,
                "updated_at": r.updated_at.isoformat(),
            }
            for r in rows
        ]


async def get_thread(clerk_id, thread_id):
    async with AsyncSessionLocal() as db:
        user_id = await owner(db, clerk_id)
        row = await db.get(CopilotConversation, (user_id, thread_id))
        if row is None:
            raise HTTPException(404, "Chat not found")
        return {
            "thread_id": row.thread_id,
            "title": row.title,
            "messages": row.messages,
        }


async def start_turn(clerk_id, thread_id, run_id, incoming):
    async with AsyncSessionLocal() as db:
        user_id = await owner(db, clerk_id)
        from app.api.v1.run_utils import check_run_admission

        await check_run_admission(db, User(id=user_id))
        first = next(
            (str(m.get("content", "")) for m in incoming if m.get("role") == "user"),
            "New chat",
        )
        await db.execute(
            insert(CopilotConversation)
            .values(user_id=user_id, thread_id=thread_id, title=first[:100], messages=[])
            .on_conflict_do_nothing()
        )
        row = (
            await db.execute(
                select(CopilotConversation)
                .where(
                    CopilotConversation.user_id == user_id,
                    CopilotConversation.thread_id == thread_id,
                )
                .with_for_update()
            )
        ).scalar_one()
        now = datetime.now(UTC)
        if (
            row.active_run_id
            and row.active_since
            and row.active_since > now - timedelta(minutes=10)
        ):
            raise HTTPException(409, "This chat is already responding. Wait for it to finish.")
        row.messages = merge_user_messages(row.messages, incoming)
        row.active_run_id, row.active_since, row.updated_at = run_id, now, now
        execution_id = uuid.uuid4()
        db.add(
            AgentRun(
                id=execution_id,
                user_id=user_id,
                agent_type="chat_orchestrator",
                status="running",
                tokens_used=0,
                input={
                    "thread_id": thread_id,
                    "run_id": run_id,
                    "preview": first[:500],
                },
            )
        )
        await db.commit()
        return user_id, row.messages, execution_id


async def finish_turn(
    user_id, thread_id, run_id, messages=None, *, execution_id=None, status="completed"
):
    async with AsyncSessionLocal() as db:
        values = {
            "active_run_id": None,
            "active_since": None,
            "updated_at": datetime.now(UTC),
        }
        if messages is not None:
            values["messages"] = messages
        await db.execute(
            update(CopilotConversation)
            .where(
                CopilotConversation.user_id == user_id,
                CopilotConversation.thread_id == thread_id,
                CopilotConversation.active_run_id == run_id,
            )
            .values(**values)
        )
        if execution_id is not None:
            run = await db.get(AgentRun, execution_id)
            if run is not None and run.user_id == user_id:
                # A model failure recorded during the turn must not be converted
                # to success by the protocol's normal RUN_FINISHED event.
                if (run.output or {}).get("error"):
                    status = "failed"
                run.status = status
                run.completed_at = datetime.now(UTC)
                run.duration_ms = max(
                    0, int((run.completed_at - run.started_at).total_seconds() * 1000)
                )
                if status == "failed":
                    run.output = {"error": "Chat interrupted or model unavailable"}
        await db.commit()
