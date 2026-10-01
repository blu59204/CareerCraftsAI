# ruff: noqa: ASYNC221 - disposable CLI container orchestration
"""Public URL fallback against live GitHub and a disposable profile database."""

import asyncio
import os
import secrets
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
name = "careercraft-b-github-check"


async def main():
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-d",
            "--name",
            name,
            "-p",
            "127.0.0.1::5432",
            "-e",
            "POSTGRES_HOST_AUTH_METHOD=trust",
            "pgvector/pgvector:pg16",
        ],
        check=True,
        capture_output=True,
    )
    try:
        port = (
            subprocess.check_output(["docker", "port", name, "5432/tcp"], text=True)
            .strip()
            .split(":")[-1]
        )
        for _ in range(30):
            if (
                subprocess.run(
                    ["docker", "exec", name, "pg_isready", "-U", "postgres"],
                    capture_output=True,
                    check=False,
                ).returncode
                == 0
            ):
                break
            await asyncio.sleep(0.5)
        for file in [
            "backend/tests/fixtures/b_jobs_setup.sql",
            "supabase/migrations/20261001092000_b_github_profiles.sql",
        ]:
            subprocess.run(
                [
                    "docker",
                    "exec",
                    "-i",
                    name,
                    "psql",
                    "-U",
                    "postgres",
                    "-v",
                    "ON_ERROR_STOP=1",
                ],
                input=(ROOT / file).read_text(),
                text=True,
                check=True,
                capture_output=True,
            )
        os.environ["DATABASE_URL"] = (
            f"postgresql+asyncpg://postgres@127.0.0.1:{port}/postgres"
        )
        os.environ["REDIS_URL"] = "redis://localhost:6379/15"
        os.environ["APP_SECRET_KEY"] = secrets.token_hex(32)
        from app.services import github_profile

        async def disconnected(*args, **kwargs):
            return None

        github_profile.get_connection = disconnected
        user = uuid.UUID("00000000-0000-0000-0000-000000000001")
        assert await github_profile.get_profile(user) is None
        result = await github_profile.refresh_profile(
            user, "https://github.com/octocat"
        )
        assert set(result) == {"skills", "top_repos", "suggested_projects"}
        assert result["top_repos"]
        assert await github_profile.get_profile(user) == result
        cached = await github_profile.refresh_profile(
            user, "https://github.com/octocat"
        )
        assert cached == result
        await github_profile.delete_profile(user)
        assert await github_profile.get_profile(user) is None
        try:
            await github_profile.refresh_profile(user)
        except LookupError:
            pass
        else:
            raise AssertionError("Deleted profile rehydrated")
        print(
            "PASS: live public GitHub fallback, stable contract, durable cache, delete tombstone; OAuth deliberately disconnected"
        )
    finally:
        subprocess.run(["docker", "rm", "-f", name], check=True, capture_output=True)


asyncio.run(main())
