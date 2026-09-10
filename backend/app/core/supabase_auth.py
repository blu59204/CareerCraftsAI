"""Supabase Auth verification — JWKS-based JWT decode (ES256).

Fetches and caches the Supabase project's public keys from the JWKS endpoint,
then verifies tokens locally with the correct asymmetric key.
"""

from __future__ import annotations

import logging
from typing import Any

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models import User

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)
_CLOCK_SKEW_LEEWAY = 60

# JWKS client — fetches and caches Supabase public keys for ES256 verification
_JWKS_URL = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
_jwks_client = jwt.PyJWKClient(_JWKS_URL, cache_keys=True, lifespan=3600)


def verify_token(token: str) -> dict[str, Any]:
    """Decode and validate a Supabase JWT using JWKS (ES256). Returns payload dict."""
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
            leeway=_CLOCK_SKEW_LEEWAY,
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


verify_auth_jwt = verify_token


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract Bearer token, verify locally, load User by supabase_uid."""
    if not token:
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    payload = verify_token(token)
    supabase_uid = payload.get("sub") or payload.get("user_id") or payload.get("supabase_uid")
    if not supabase_uid:
        raise HTTPException(status_code=401, detail="Invalid token — missing sub claim")

    result = await db.execute(select(User).where(User.supabase_uid == supabase_uid))
    user = result.scalars().first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user
verify_supabase_jwt = verify_token  # alias used by test_edge_cases
