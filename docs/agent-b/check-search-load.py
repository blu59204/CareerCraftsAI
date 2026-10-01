"""Disposable catalog load check: actual API/query/rules, controlled auth/BYOK."""

import os
import secrets
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
name = "careercraft-b-load-check"


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True)


def main():
    docker(
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
    )
    try:
        port = docker("port", name, "5432/tcp").strip().split(":")[-1]
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
            time.sleep(0.5)
        for file in [
            "backend/tests/fixtures/b_jobs_setup.sql",
            "supabase/migrations/20261001090000_b_job_search_defaults.sql",
            "supabase/migrations/20261001091000_b_job_catalog.sql",
            "backend/tests/fixtures/b_jobs_check.sql",
        ]:
            # github fixture table is needed by the complete RLS check.
            if file.endswith("b_jobs_check.sql"):
                migration = (
                    ROOT / "supabase/migrations/20261001092000_b_github_profiles.sql"
                )
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
                    input=migration.read_text(),
                    text=True,
                    check=True,
                    capture_output=True,
                )
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
        sql = "UPDATE job_catalog SET data=jsonb_build_object('job_id',job_id,'url',url,'job_url',url,'title',title,'company',company,'description','Python FastAPI PostgreSQL','posted_at',posted_at,'remote','remote'); UPDATE job_source_health SET next_allowed_at=now()+interval '1 hour';"
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
            input=sql,
            text=True,
            check=True,
            capture_output=True,
        )
        os.environ["DATABASE_URL"] = (
            f"postgresql+asyncpg://postgres@127.0.0.1:{port}/postgres"
        )
        os.environ["REDIS_URL"] = "redis://localhost:6379/15"
        os.environ["APP_SECRET_KEY"] = secrets.token_hex(32)
        import uvicorn
        from app.api.v1 import job_basis
        from app.api.v1.deps import get_current_user, get_db
        from app.services import github_profile, job_catalog, job_matching
        from app.services.job_connectors import Source
        from fastapi import FastAPI

        uid = uuid.UUID("00000000-0000-0000-0000-000000000001")

        async def user():
            return SimpleNamespace(id=uid)

        async def basis(*args, **kwargs):
            return SimpleNamespace(id=uid), None

        async def basis_text(*args, **kwargs):
            return "Python FastAPI PostgreSQL", str(uid)

        async def no_profile(*args, **kwargs):
            return None

        async def no_semantic(*args, **kwargs):
            return {}

        job_basis.resolve_basis = basis
        job_matching.basis_text = basis_text
        job_matching.semantic_scores = no_semantic
        github_profile.get_profile = no_profile
        job_catalog.sources = lambda: [Source("recorded:test", "greenhouse", "test")]
        app = FastAPI()
        app.include_router(job_basis.router, prefix="/jobs")
        app.dependency_overrides[get_current_user] = user

        async def db():
            from app.services.jobs_database import AsyncSessionLocal

            async with AsyncSessionLocal() as session:
                yield session

        app.dependency_overrides[get_db] = db
        server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=8769, log_level="error")
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.1)
        assert server.started
        result = subprocess.run(
            [
                str(ROOT / ".validation-venv/Scripts/python.exe"),
                "-m",
                "locust",
                "-f",
                str(ROOT / "docs/agent-b/search-locust.py"),
                "--headless",
                "--host=http://127.0.0.1:8769",
                "--users=20",
                "--spawn-rate=4",
                "--run-time=30s",
                "--only-summary",
                "--csv",
                str(ROOT / "docs/agent-b/search-load"),
            ],
            check=False,
        )
        assert result.returncode == 0
        server.should_exit = True
        thread.join(10)
        print(
            "PASS: 20 users; actual catalog endpoint and rules ranking over 100,000 rows; controlled auth and absent BYOK/GitHub"
        )
    finally:
        docker("rm", "-f", name)


if __name__ == "__main__":
    main()
