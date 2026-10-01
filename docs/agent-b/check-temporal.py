import asyncio
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("APP_SECRET_KEY", secrets.token_hex(32))
os.environ.setdefault("CLERK_SECRET_KEY", "test-only")
from app.workflows.scheduled import ensure_schedules, schedule_specs
from temporalio.testing import WorkflowEnvironment


async def main():
    async with await WorkflowEnvironment.start_local() as env:
        await ensure_schedules(env.client)
        await ensure_schedules(env.client)
        for name, _, _ in schedule_specs():
            desc = await env.client.get_schedule_handle(name).describe()
            assert desc.schedule.policy.overlap.name == "SKIP"
        print(
            "PASS: real disposable Temporal server; schedules registered twice without duplication; SKIP verified"
        )


asyncio.run(main())
