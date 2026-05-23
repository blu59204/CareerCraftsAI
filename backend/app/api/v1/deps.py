from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.db import User


async def get_current_user(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    clerk_id: str | None = None

    try:
        from clerk_backend_api import Clerk
        from clerk_backend_api.security.types import AuthenticateRequestOptions

        clerk = Clerk(bearer_auth=settings.CLERK_SECRET_KEY)

        class _FakeRequest:
            def __init__(self, auth_header: str):
                self.headers = {"authorization": auth_header}
                self.url = "http://localhost/"
                self.method = "GET"

        state = clerk.authenticate_request(
            _FakeRequest(authorization),
            AuthenticateRequestOptions(secret_key=settings.CLERK_SECRET_KEY),
        )
        if not state.is_signed_in:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        payload = state.payload or {}
        clerk_id = payload.get("sub")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    if not clerk_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    from sqlalchemy import select

    result = await db.execute(select(User).where(User.clerk_id == clerk_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user
