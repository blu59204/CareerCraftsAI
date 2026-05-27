"""Backfill supabase_uid for existing Clerk users.

Idempotent. Run once after applying migration 0009. For each public.users row
with supabase_uid IS NULL:
  1. Look up email via Clerk API (using old clerk_id stored in supabase_uid pre-rename).
  2. Create or fetch a Supabase auth user with that email (email confirmed).
  3. Update public.users.supabase_uid to the new Supabase UUID.

After this script, prompt users to set a password (Supabase password reset) or
sign in with Google to reattach Gmail/Drive tokens.

Required env vars:
  CLERK_SECRET_KEY      — read old Clerk users
  SUPABASE_URL          — admin API endpoint
  SUPABASE_SERVICE_KEY  — admin API key
  DATABASE_URL          — Postgres conn string

Usage:
  python scripts/migrate_clerk_users.py --dry-run
  python scripts/migrate_clerk_users.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


async def list_pending(db: AsyncSession) -> list[tuple[str, str, str | None]]:
    """Rows where supabase_uid still holds the old Clerk id (`user_…` prefix)."""
    rows = await db.execute(
        text(
            "SELECT id::text, supabase_uid, email FROM public.users "
            "WHERE supabase_uid IS NOT NULL AND supabase_uid LIKE 'user_%'"
        )
    )
    return [(r[0], r[1], r[2]) for r in rows.all()]


async def fetch_clerk_email(http: httpx.AsyncClient, clerk_id: str, secret: str) -> str | None:
    try:
        resp = await http.get(
            f"https://api.clerk.com/v1/users/{clerk_id}",
            headers={"Authorization": f"Bearer {secret}"},
            timeout=15.0,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        primary_id = data.get("primary_email_address_id")
        for addr in data.get("email_addresses", []):
            if addr.get("id") == primary_id:
                return addr.get("email_address")
        # fallback: any
        emails = data.get("email_addresses", [])
        return emails[0]["email_address"] if emails else None
    except httpx.RequestError:
        return None


async def ensure_supabase_user(
    http: httpx.AsyncClient, email: str, supabase_url: str, service_key: str
) -> str | None:
    """Create (or fetch existing) Supabase auth user, return UUID."""
    headers = {
        "Authorization": f"Bearer {service_key}",
        "apikey": service_key,
        "Content-Type": "application/json",
    }
    create = await http.post(
        f"{supabase_url}/auth/v1/admin/users",
        headers=headers,
        json={"email": email, "email_confirm": True},
        timeout=15.0,
    )
    if create.status_code == 200 or create.status_code == 201:
        return create.json().get("id")

    # Already exists — look up by email
    list_resp = await http.get(
        f"{supabase_url}/auth/v1/admin/users",
        headers=headers,
        params={"email": email},
        timeout=15.0,
    )
    if list_resp.status_code != 200:
        return None
    users = list_resp.json().get("users", [])
    return users[0]["id"] if users else None


async def run(apply: bool) -> int:
    clerk_secret = os.environ.get("CLERK_SECRET_KEY")
    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY")
    db_url = os.environ.get("DATABASE_URL")

    missing = [k for k, v in {
        "CLERK_SECRET_KEY": clerk_secret,
        "SUPABASE_URL": supabase_url,
        "SUPABASE_SERVICE_KEY": service_key,
        "DATABASE_URL": db_url,
    }.items() if not v]
    if missing:
        print(f"Missing env vars: {', '.join(missing)}", file=sys.stderr)
        return 2

    engine = create_async_engine(db_url, echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    migrated = 0
    failed: list[dict[str, Any]] = []

    async with Session() as db, httpx.AsyncClient() as http:
        pending = await list_pending(db)
        print(f"Found {len(pending)} users to migrate.")

        for row_id, old_clerk_id, db_email in pending:
            email = db_email or await fetch_clerk_email(http, old_clerk_id, clerk_secret)
            if not email:
                failed.append({"id": row_id, "clerk_id": old_clerk_id, "reason": "no_email"})
                continue

            if not apply:
                print(f"[dry-run] would migrate {row_id} ({email}) from clerk={old_clerk_id}")
                continue

            new_uid = await ensure_supabase_user(http, email, supabase_url, service_key)
            if not new_uid:
                failed.append({"id": row_id, "email": email, "reason": "supabase_create_failed"})
                continue

            await db.execute(
                text("UPDATE public.users SET supabase_uid = :uid WHERE id = :id"),
                {"uid": new_uid, "id": row_id},
            )
            await db.commit()
            migrated += 1
            print(f"migrated {email}: {old_clerk_id} → {new_uid}")

    print(f"\nDone. migrated={migrated}  failed={len(failed)}")
    for f in failed:
        print(f"FAIL {f}")
    return 0 if not failed else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="Perform writes (else dry-run)")
    p.add_argument("--dry-run", action="store_true", help="Default behaviour")
    args = p.parse_args()
    return asyncio.run(run(apply=args.apply))


if __name__ == "__main__":
    sys.exit(main())
