from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.supabase_auth import fetch_clerk_user_profile, verify_auth_jwt
from app.models.db import User


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    payload = verify_auth_jwt(token)

    auth_subject = payload["sub"]
    clerk_profile = (
        await fetch_clerk_user_profile(auth_subject)
        if payload.get("_auth_provider") == "clerk"
        else {}
    )
    email = (
        clerk_profile.get("email")
        or payload.get("email")
        or payload.get("email_address")
        or payload.get("primary_email_address")
    )
    if not email:
        raise HTTPException(
            status_code=401,
            detail="Authenticated token is missing an email address",
        )

    result = await db.execute(
        select(User)
        .options(selectinload(User.model_settings))
        .where(User.supabase_uid == auth_subject)
    )
    user = result.scalar_one_or_none()

    if user is None:
        result = await db.execute(
            select(User)
            .options(selectinload(User.model_settings))
            .where(User.email == email)
        )
        user = result.scalar_one_or_none()
        if user is not None:
            user.supabase_uid = auth_subject
            await db.flush()

    if user is None:
        # Auto-provision: JWT is valid so the Supabase auth user exists.
        # Use INSERT ... ON CONFLICT DO NOTHING to handle concurrent first requests
        # from the same user without a unique constraint violation.
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        meta = payload.get("user_metadata") or {}
        stmt = (
            pg_insert(User)
            .values(
                supabase_uid=auth_subject,
                email=email,
                full_name=clerk_profile.get("full_name") or meta.get("full_name") or meta.get("name"),
                avatar_url=clerk_profile.get("avatar_url") or meta.get("avatar_url") or meta.get("picture"),
                phone=clerk_profile.get("phone") or meta.get("phone"),
                headline=clerk_profile.get("headline") or meta.get("headline"),
                linkedin_url=clerk_profile.get("linkedin_url") or meta.get("linkedin_url"),
            )
            .on_conflict_do_nothing(index_elements=["supabase_uid"])
        )
        await db.execute(stmt)
        await db.flush()

        result = await db.execute(
            select(User)
            .options(selectinload(User.model_settings))
            .where(User.supabase_uid == auth_subject)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=500, detail="User provisioning failed")

    return user
