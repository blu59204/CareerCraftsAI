"""Supabase JWT verification — pinned to HS256.

Supabase project tokens are signed with the JWT secret (HS256).
We pin the algorithm to prevent algorithm confusion attacks (CWE-327).
Tokens specifying alg:none or any other algorithm are rejected.
"""

from __future__ import annotations

import jwt
from fastapi import HTTPException

from app.core.config import settings

# Pinned algorithm — NEVER read from untrusted token header
_ALLOWED_ALGORITHMS = ["HS256"]


def verify_supabase_jwt(token: str) -> dict:
    """Verify a Supabase JWT token with pinned HS256 algorithm.

    Rejects: alg:none, ES256, RS256, or any algorithm not in _ALLOWED_ALGORITHMS.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=_ALLOWED_ALGORITHMS,
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
