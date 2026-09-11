"""FastAPI dependencies for authentication and database access."""
import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.supabase_auth import (
    get_or_provision_user,
    subject_from_payload,
    verify_auth_jwt,
)
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

    # Clerk's `sub` is a text id (user_2abc...), stored in users.supabase_uid.
    # Provisioning (including the concurrent-first-request race) lives in
    # app.core.supabase_auth so middleware and routers share one code path.
    auth_subject = subject_from_payload(payload)
    return await get_or_provision_user(db, auth_subject, payload)


CurrentUser = Annotated[User, Depends(get_current_user)]
