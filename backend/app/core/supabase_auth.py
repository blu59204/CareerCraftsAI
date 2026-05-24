"""Supabase JWT verification.

Backend verifies access tokens locally using SUPABASE_JWT_SECRET (HS256).
No network call to Supabase per request.
"""

from __future__ import annotations

import jwt
from fastapi import HTTPException

from app.core.config import settings


def verify_supabase_jwt(token: str) -> dict:
    """Decode and validate a Supabase access token.

    Returns the decoded payload. Raises HTTPException(401) on any failure.
    Validates audience="authenticated", expiration, and signature.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    if not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid token: missing sub")

    return payload
