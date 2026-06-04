"""FastAPI dependencies for authentication and database access."""
import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.supabase_auth import verify_auth_jwt
from app.models.db import User

logger = logging.getLogger(__name__)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and verify the Bearer token, then fetch or provision the user."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = auth_header.removeprefix("Bearer ").strip()
    payload = verify_auth_jwt(token)

    auth_subject = payload["sub"]
    auth_provider = payload.get("_auth_provider", "supabase")

    # Check if user exists
    result = await db.execute(
        select(User).where(User.supabase_uid == auth_subject)
    )
    user = result.scalar_one_or_none()

    # Auto-provision user if doesn't exist
    if user is None:
        email = payload.get("email")
        if not email:
            raise HTTPException(status_code=401, detail="Email not found in token")

        stmt = (
            pg_insert(User)
            .values(
                supabase_uid=auth_subject,
                email=email,
                full_name=payload.get("user_metadata", {}).get("full_name"),
                avatar_url=payload.get("user_metadata", {}).get("avatar_url"),
            )
            .on_conflict_do_nothing(index_elements=["supabase_uid"])
        )
        await db.execute(stmt)
        await db.commit()

        # Fetch the created user
        result = await db.execute(
            select(User).where(User.supabase_uid == auth_subject)
        )
        user = result.scalar_one_or_none()

        if user is None:
            raise HTTPException(status_code=500, detail="User provisioning failed")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
