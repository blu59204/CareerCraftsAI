"""Lets the member answer the agent's open questions by replying to the
"waiting for you" email.

The questions the agent could not answer are kept on the extension task. The
email lists them with a short reference. The member's reply is read through
the Gmail connection they already made (no inbound mail service): numbered
lines are saved as approved answers, so this and every later application
fills them automatically.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.db import ExtensionTask, User

logger = logging.getLogger(__name__)

MAX_QUESTIONS = 10
MAX_ANSWER_CHARS = 1000
_WINDOW = timedelta(days=14)
_QUOTE_START = re.compile(
    r"^(on .{0,200}wrote:?|-{2,}\s*(original message|forwarded)|from:\s.+)$", re.I
)
_NUMBERED = re.compile(r"^\s*(\d{1,2})\s*[:.)\-]\s*(.*)$")


def ref_for(task_id: uuid.UUID | str) -> str:
    return "CC-" + str(task_id).replace("-", "")[:8]


def question_lines(questions: list[dict]) -> str:
    return "\n".join(f"{i}. {q['label']}" for i, q in enumerate(questions, 1))


def _decode(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")
    except Exception:
        return ""


def message_text(message: dict) -> str:
    """Plain-text body of a Gmail message resource (first text/plain part)."""

    def walk(part: dict) -> str:
        if str(part.get("mimeType", "")).startswith("text/plain"):
            return _decode(((part.get("body") or {}).get("data")) or "")
        for child in part.get("parts") or []:
            text = walk(child)
            if text:
                return text
        return ""

    return walk(message.get("payload") or {})


def reply_only(text: str) -> str:
    """What the member typed, without the quoted email below it."""
    kept = []
    for line in text.replace("\r", "").split("\n"):
        stripped = line.strip()
        if stripped.startswith(">") or _QUOTE_START.match(stripped) or stripped == "--":
            break
        kept.append(line)
    return "\n".join(kept).strip()


def parse_answers(text: str, count: int) -> dict[int, str]:
    """{question number: answer}. Lines like "2: 12 LPA". A single question
    can be answered with plain text. Continuation lines extend the previous
    answer. Numbers outside the list are ignored."""
    text = reply_only(text)
    answers: dict[int, str] = {}
    current = None
    for line in text.split("\n"):
        match = _NUMBERED.match(line)
        if match and 1 <= int(match.group(1)) <= count:
            current = int(match.group(1))
            answers[current] = match.group(2).strip()
        elif current is not None and line.strip():
            answers[current] = (answers[current] + " " + line.strip()).strip()
    if not answers and count == 1 and text:
        answers[1] = " ".join(text.split())
    return {n: a[:MAX_ANSWER_CHARS] for n, a in answers.items() if a}


def _address(header: str) -> str:
    match = re.search(r"<([^>]+)>", header)
    return (match.group(1) if match else header).strip().lower()


def member_reply(thread: dict, member_email: str) -> dict | None:
    """Latest message in the thread written by the member."""
    mine = [
        m
        for m in thread.get("messages", [])
        if _address(
            next(
                (
                    str(h.get("value", ""))
                    for h in (m.get("payload") or {}).get("headers", [])
                    if str(h.get("name", "")).lower() == "from"
                ),
                "",
            )
        )
        == member_email.lower()
    ]
    return max(mine, key=lambda m: int(m.get("internalDate") or 0)) if mine else None


async def _open_tasks(db, owner: uuid.UUID) -> list[ExtensionTask]:
    rows = (
        (
            await db.execute(
                select(ExtensionTask).where(
                    ExtensionTask.user_id == owner,
                    ExtensionTask.status == "needs_input",
                    ExtensionTask.updated_at > datetime.now(UTC) - _WINDOW,
                )
            )
        )
        .scalars()
        .all()
    )
    return [t for t in rows if (t.payload or {}).get("open_questions")]


async def collect_answers(user_id: str, gmail_factory=None) -> dict:
    """Read replies to the member's "waiting for you" emails and save them."""
    from app.applications import profile_service
    from app.services.extension_service import answer_key
    from app.services.gmail_service import GmailMCPClient

    owner = uuid.UUID(user_id)
    saved = tasks_answered = 0
    async with AsyncSessionLocal() as db:
        tasks = await _open_tasks(db, owner)
        if not tasks:
            return {"answers_saved": 0, "tasks_answered": 0}
        user = await db.get(User, owner)
        if user is None or not user.email:
            return {"answers_saved": 0, "tasks_answered": 0}
        gmail = (gmail_factory or GmailMCPClient)(user_id)
        for task in tasks:
            payload = dict(task.payload or {})
            questions = payload["open_questions"][:MAX_QUESTIONS]
            hits = await asyncio.to_thread(
                gmail.search_threads, f'"{ref_for(task.id)}" newer_than:14d', 5
            )
            reply = None
            for thread_id in dict.fromkeys(h.get("threadId") for h in hits if h.get("threadId")):
                thread = await asyncio.to_thread(gmail.get_thread, thread_id)
                reply = member_reply(thread, user.email)
                if reply:
                    break
            if reply is None or reply.get("id") == payload.get("answered_by_message"):
                continue
            answers = parse_answers(message_text(reply), len(questions))
            if not answers:
                continue
            for number, value in answers.items():
                label = questions[number - 1]["label"]
                await profile_service.save_approved_answer(
                    db, owner, questions[number - 1].get("key") or answer_key(label), label, value
                )
                saved += 1
            payload["answered_by_message"] = reply.get("id")
            payload["open_questions"] = [q for i, q in enumerate(questions, 1) if i not in answers]
            if not payload["open_questions"] and task.job_application_id:
                payload["restart_pending"] = True
            task.payload = payload
            tasks_answered += 1
            await _confirm(owner, task, len(answers), len(payload["open_questions"]))
        await db.commit()
    restarted = await restart_answered(user_id)
    return {"answers_saved": saved, "tasks_answered": tasks_answered, "restarted": restarted}


async def restart_answered(user_id: str) -> int:
    """Run the application again once all its questions are answered: the
    paused attempt is closed and a new one starts, which fills the saved
    answers by itself. If the old attempt has not finished closing yet, the
    restart waits for the next pass (30 minutes)."""
    from app.workflows.extension_activities import OPEN_TASK_STATUSES
    from app.workflows.starters import signal_extension_update, start_auto_apply

    owner = uuid.UUID(user_id)
    restarted = 0
    async with AsyncSessionLocal() as db:
        rows = (
            (
                await db.execute(
                    select(ExtensionTask).where(
                        ExtensionTask.user_id == owner,
                        ExtensionTask.updated_at > datetime.now(UTC) - _WINDOW,
                    )
                )
            )
            .scalars()
            .all()
        )
        for task in rows:
            payload = dict(task.payload or {})
            if not payload.get("restart_pending") or not task.job_application_id:
                continue
            try:
                if task.status in OPEN_TASK_STATUSES:
                    await signal_extension_update(
                        task.workflow_id,
                        {
                            "stage": "cancelled",
                            "details": {"message": "Restarting with your answers"},
                        },
                    )
                    await asyncio.sleep(3)
                    await db.refresh(task)
                    if task.status in OPEN_TASK_STATUSES:
                        continue
                result = await start_auto_apply(owner, task.job_application_id)
            except Exception:
                logger.warning("Could not restart application %s", task.id, exc_info=True)
                continue
            if result.get("status") == "queued":
                payload.pop("restart_pending")
                task.payload = payload
                restarted += 1
        await db.commit()
    return restarted


async def _confirm(owner: uuid.UUID, task: ExtensionTask, saved: int, left: int) -> None:
    from app.workflows.starters import start_notification

    payload = task.payload or {}
    where = payload.get("company") or "your application"
    body = f"Saved {saved} answer{'s' if saved != 1 else ''} from your email for {where}."
    body += (
        f" {left} question{'s are' if left != 1 else ' is'} still open."
        if left
        else " The application is starting again with your answers."
    )
    try:
        await start_notification(
            owner,
            type="application_update",
            title="Your answers were saved",
            body=body,
            link="/applications",
        )
    except Exception:
        logger.warning("Could not confirm saved answers", exc_info=True)
