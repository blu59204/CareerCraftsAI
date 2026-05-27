"""Supabase JWT verification — supports asymmetric (ES256/RS256) via JWKS and legacy HS256.

Supabase migrated to asymmetric JWT signing (ES256 by default for new projects).
We fetch the project's JWKS and verify with the matching public key when the token
header indicates an asymmetric algorithm. Legacy HS256 tokens are still verified
with SUPABASE_JWT_SECRET.

Algorithm is pinned to the set _ALLOWED_ALGORITHMS — `alg:none` and any unexpected
algorithm are rejected (prevents algorithm confusion / CWE-327).
"""

from __future__ import annotations

import logging

import jwt
from fastapi import HTTPException
from jwt import PyJWKClient

from app.core.config import settings

logger = logging.getLogger(__name__)

_ALLOWED_ALGORITHMS = ["ES256", "RS256", "HS256"]
_ASYMMETRIC = {"ES256", "RS256"}

_JWKS_URL = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
_jwks_client = PyJWKClient(_JWKS_URL, cache_keys=True, lifespan=3600)


def _get_signing_key(token: str):
    return _jwks_client.get_signing_key_from_jwt(token).key


def verify_supabase_jwt(token: str) -> dict:
    """Verify a Supabase JWT — asymmetric via JWKS or legacy HS256."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        logger.error(f"JWT header parse failed: {exc} | token_prefix={token[:32]}")
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    alg = header.get("alg")
    if alg not in _ALLOWED_ALGORITHMS:
        logger.error(f"JWT alg not allowed: {alg} | token_prefix={token[:32]}")
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        if alg in _ASYMMETRIC:
            key = _get_signing_key(token)
        else:
            key = settings.SUPABASE_JWT_SECRET

        payload = jwt.decode(
            token,
            key,
            algorithms=[alg],
            audience="authenticated",
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        logger.error(f"JWT expired: {exc} | token_prefix={token[:32]}")
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        logger.error(f"JWT verify failed: {exc} | token_prefix={token[:32]}")
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    if not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid token: missing sub")

    return payload
