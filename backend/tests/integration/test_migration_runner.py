"""scripts/migrate.py applies every migration to a fresh database, once.

Run docker compose -p careercraft-workflow-tests -f docker-compose.test.yml up -d
then RUN_WORKFLOW_INTEGRATION=1 pytest tests/integration/test_migration_runner.py.
"""

import importlib.util
import os
import uuid
from pathlib import Path

import psycopg
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_WORKFLOW_INTEGRATION") != "1",
    reason="Disposable workflow infrastructure required",
)

ADMIN_URL = "postgresql://workflow_test:workflow_test@127.0.0.1:55439/workflow_test"
SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "migrate.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("migrate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fresh_database():
    name = f"migrate_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    yield ADMIN_URL.rsplit("/", 1)[0] + f"/{name}"
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


def test_every_migration_applies_once_on_a_fresh_database(fresh_database):
    runner = _load_runner()
    files = [path.name for path in runner.migration_files()]

    assert runner.main(["--database-url", fresh_database, "--bootstrap"]) == 0
    with psycopg.connect(fresh_database) as conn:
        assert set(runner.applied(conn)) == set(files)
        columns = conn.execute(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_name = 'user_preferences'"
        ).fetchall()
    assert ("daily_search_enabled",) in columns

    # A second run finds nothing to do.
    with psycopg.connect(fresh_database, autocommit=True) as conn:
        assert runner.migrate(conn) == []


def test_an_unledgered_database_must_be_baselined_first(fresh_database):
    runner = _load_runner()
    with psycopg.connect(fresh_database, autocommit=True) as conn:
        conn.execute("CREATE TABLE public.users (id uuid PRIMARY KEY)")
        with pytest.raises(SystemExit, match="--baseline"):
            runner.migrate(conn)

        first = runner.migration_files()[0].name
        assert runner.baseline(conn, first) == [first]
        pending = runner.migrate(conn, dry_run=True)
    assert first not in pending
    assert len(pending) == len(runner.migration_files()) - 1
