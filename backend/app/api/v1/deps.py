from fastapi import Depends, HTTPException, Header, Request
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

    token = authorization[7:]
    clerk_id: str | None = None

    try:
        from clerk_backend_api import Clerk
        from clerk_backend_api.security.types import AuthenticateRequestOptions
        import httpx

        clerk = Clerk(bearer_auth=settings.CLERK_SECRET_KEY)
        # Build a minimal request-like object clerk can verify
        class _FakeRequest:
            def __init__(self, auth_header: str):
                self.headers = {"authorization": auth_header}
                self.url = "http://localhost/"
                self.method = "GET"

        fake_req = _FakeRequest(authorization)
        state = clerk.authenticate_request(
            fake_req,
            AuthenticateRequestOptions(secret_key=settings.CLERK_SECRET_KEY),
        )
        if not state.is_signed_in:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        payload = state.payload or {}
        clerk_id = payload.get("sub")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if not clerk_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    from sqlalchemy import select
    result = await db.execute(select(User).where(User.clerk_id == clerk_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user
