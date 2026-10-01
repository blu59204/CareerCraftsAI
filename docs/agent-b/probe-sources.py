"""Read-only source probe; writes health counts, never descriptions or secrets."""

import asyncio
import json
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
# Public HTTP only; these placeholders are never connected to or persisted.
os.environ.setdefault("APP_SECRET_KEY", secrets.token_hex(32))
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres@127.0.0.1/unused")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/15")
from app.services.job_catalog import sources
from app.services.job_connectors import fetch_page


async def main():
    semaphore = asyncio.Semaphore(6)

    async def one(source):
        async with semaphore:
            try:
                result = await asyncio.wait_for(fetch_page(source), 18)
                row = {
                    "id": source.id,
                    "family": source.family,
                    "status": "healthy",
                    "jobs": len(result.jobs),
                    "dated_jobs": sum(bool(j["posted_at"]) for j in result.jobs),
                    "pagination": bool(result.next_cursor),
                }
            except Exception as exc:  # noqa: BLE001 - isolated source health probe
                row = {
                    "id": source.id,
                    "family": source.family,
                    "status": "unavailable",
                    "error_type": type(exc).__name__,
                }
            return row

    rows = await asyncio.gather(*(one(source) for source in sources()))
    (ROOT / "docs/agent-b/SOURCE_HEALTH.json").write_text(
        json.dumps(rows, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "sources": len(rows),
                "healthy": sum(r["status"] == "healthy" for r in rows),
                "jobs": sum(r.get("jobs", 0) for r in rows),
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
