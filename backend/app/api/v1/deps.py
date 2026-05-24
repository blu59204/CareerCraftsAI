from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.supabase_auth import verify_supabase_jwt
from app.models.db import User


async def get_current_user(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    payload = verify_supabase_jwt(token)

    supabase_uid = payload["sub"]
    email = payload.get("email")

    result = await db.execute(select(User).where(User.supabase_uid == supabase_uid))
    user = result.scalar_one_or_none()

    if user is None and email:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is not None and user.supabase_uid != supabase_uid:
            user.supabase_uid = supabase_uid
            await db.flush()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return user
