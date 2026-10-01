"""Apply supabase/migrations/*.sql in filename order, once each.

Applied files are recorded in public.schema_migrations, so a deploy runs
only what is new:

    DATABASE_URL=postgresql://user:pass@host:5432/db python scripts/migrate.py

A fresh database needs deploy/oracle-vm/postgres-bootstrap.sql first (the
Oracle Compose stack runs it on first start; --bootstrap applies it here).

A database migrated by hand before this runner existed has no ledger. The
runner refuses to touch it until you record what is already applied:

    python scripts/migrate.py --baseline              # every file
    python scripts/migrate.py --baseline 0040_x.sql   # up to and including one

Each file runs as one implicit transaction unless it manages its own with
BEGIN/COMMIT, and a failure stops the run with nothing recorded for it.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "supabase" / "migrations"
BOOTSTRAP = ROOT / "deploy" / "oracle-vm" / "postgres-bootstrap.sql"

LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS public.schema_migrations (
    filename text PRIMARY KEY,
    checksum text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now(),
    baseline boolean NOT NULL DEFAULT false
)
"""


def libpq_url(url: str) -> str:
    """Accept the app's SQLAlchemy URL (postgresql+asyncpg://...) as well."""
    return re.sub(r"^postgresql\+\w+://", "postgresql://", url)


def migration_files() -> list[Path]:
    return sorted(MIGRATIONS.glob("*.sql"), key=lambda path: path.name)


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ledger_exists(conn: psycopg.Connection) -> bool:
    return (
        conn.execute("SELECT to_regclass('public.schema_migrations')").fetchone()[0]
        is not None
    )


def _schema_exists(conn: psycopg.Connection) -> bool:
    return conn.execute("SELECT to_regclass('public.users')").fetchone()[0] is not None


def applied(conn: psycopg.Connection) -> dict[str, str]:
    rows = conn.execute(
        "SELECT filename, checksum FROM public.schema_migrations"
    ).fetchall()
    return dict(rows)


def _record(conn: psycopg.Connection, path: Path, *, baseline: bool) -> None:
    conn.execute(
        "INSERT INTO public.schema_migrations (filename, checksum, baseline)"
        " VALUES (%s, %s, %s) ON CONFLICT (filename) DO NOTHING",
        (path.name, checksum(path), baseline),
    )


def baseline(conn: psycopg.Connection, upto: str | None) -> list[str]:
    files = migration_files()
    names = [path.name for path in files]
    if upto is not None and upto not in names:
        raise SystemExit(f"--baseline: {upto} is not in {MIGRATIONS}")
    conn.execute(LEDGER_DDL)
    recorded = []
    for path in files:
        _record(conn, path, baseline=True)
        recorded.append(path.name)
        if path.name == upto:
            break
    return recorded


def migrate(conn: psycopg.Connection, *, dry_run: bool = False) -> list[str]:
    if not _ledger_exists(conn):
        if _schema_exists(conn):
            raise SystemExit(
                "This database already has tables but no migration ledger. Record what "
                "is applied with --baseline (optionally up to a file name), then rerun."
            )
        if not dry_run:
            conn.execute(LEDGER_DDL)
    done = applied(conn) if _ledger_exists(conn) else {}
    for name, digest in done.items():
        path = MIGRATIONS / name
        if path.exists() and checksum(path) != digest:
            print(f"warning: {name} changed after it was applied", file=sys.stderr)
    pending = [path for path in migration_files() if path.name not in done]
    ran = []
    for path in pending:
        if dry_run:
            ran.append(path.name)
            continue
        print(f"applying {path.name}", flush=True)
        try:
            # No parameters, so psycopg sends the whole file in one simple
            # query: one implicit transaction, or the file's own BEGIN/COMMIT.
            conn.execute(path.read_text(encoding="utf-8"))
        except psycopg.Error as exc:
            raise SystemExit(
                f"{path.name} failed, nothing recorded for it: {exc}"
            ) from exc
        _record(conn, path, baseline=False)
        ran.append(path.name)
    return ran


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument(
        "--bootstrap", action="store_true", help="apply the bootstrap SQL first"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="list pending files only"
    )
    parser.add_argument(
        "--baseline",
        nargs="?",
        const="",
        metavar="FILE",
        help="record files as applied without running them (all, or up to FILE)",
    )
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("set DATABASE_URL or pass --database-url")

    with psycopg.connect(libpq_url(args.database_url), autocommit=True) as conn:
        if args.baseline is not None:
            recorded = baseline(conn, args.baseline or None)
            print(f"recorded {len(recorded)} migrations as already applied")
            return 0
        if args.bootstrap and not args.dry_run:
            conn.execute(BOOTSTRAP.read_text(encoding="utf-8"))
        ran = migrate(conn, dry_run=args.dry_run)
    verb = "pending" if args.dry_run else "applied"
    print(f"{len(ran)} {verb}" + "".join(f"\n  {name}" for name in ran))
    return 0


if __name__ == "__main__":
    sys.exit(main())
