"""Fire-and-forget in-process tasks that must not be garbage-collected.

asyncio keeps only a weak reference to a task, so an un-stored
create_task() result can be collected mid-run. Durable work belongs in a
Temporal workflow; this is only for best-effort, in-process follow-ups.
"""

import asyncio

_background_tasks: set[asyncio.Task] = set()


def spawn_background(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task
