"""JWT verification for Supabase Auth and Clerk-backed sessions.

Supabase migrated to asymmetric JWT signing (ES256 by default for new projects).
We fetch the project's JWKS and verify with the matching public key when the token
header indicates an asymmetric algorithm. Legacy HS256 tokens are still verified
with SUPABASE_JWT_SECRET.

When CLERK_ISSUER is configured, Clerk session tokens are verified through the
Clerk JWKS and accepted by the same backend dependency layer.

Algorithm is pinned to the set _ALLOWED_ALGORITHMS — `alg:none` and any unexpected
algorithm are rejected (prevents algorithm confusion / CWE-327).
"""

from __future__ import annotations

import logging

import httpx
import jwt
from fastapi import HTTPException
from jwt.exceptions import PyJWKClientError
from jwt import PyJWKClient

from app.core.config import settings

logger = logging.getLogger(__name__)

_ALLOWED_ALGORITHMS = ["ES256", "RS256", "HS256"]
_ASYMMETRIC = {"ES256", "RS256"}

_JWKS_URL = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
_jwks_client = PyJWKClient(_JWKS_URL, cache_keys=True, lifespan=3600)
_clerk_jwks_client: PyJWKClient | None = None


def _get_signing_key(token: str):
    return _jwks_client.get_signing_key_from_jwt(token).key


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]


def _clerk_issuer() -> str | None:
    return settings.CLERK_ISSUER.rstrip("/") if settings.CLERK_ISSUER else None


def _get_clerk_signing_key(token: str):
    global _clerk_jwks_client

    issuer = _clerk_issuer()
    if not issuer:
        raise HTTPException(status_code=401, detail="Clerk auth is not configured")

    jwks_url = settings.CLERK_JWKS_URL or f"{issuer}/.well-known/jwks.json"
    if _clerk_jwks_client is None:
        _clerk_jwks_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)
    return _clerk_jwks_client.get_signing_key_from_jwt(token).key


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
            if not header.get("kid"):
                raise HTTPException(status_code=401, detail="Invalid token")
            try:
                key = _get_signing_key(token)
            except PyJWKClientError as exc:
                logger.error(f"JWKS key lookup failed: {exc} | token_prefix={token[:32]}")
                raise HTTPException(status_code=401, detail="Invalid token") from exc
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

    payload["_auth_provider"] = "supabase"
    return payload


def verify_clerk_jwt(token: str) -> dict:
    """Verify a Clerk session JWT using the configured Clerk issuer JWKS."""
    issuer = _clerk_issuer()
    if not issuer:
        raise HTTPException(status_code=401, detail="Clerk auth is not configured")

    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        logger.error("Clerk JWT header parse failed: %s | token_prefix=%s", exc, token[:32])
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    alg = header.get("alg")
    if alg not in {"RS256", "ES256"}:
        logger.error("Clerk JWT alg not allowed: %s | token_prefix=%s", alg, token[:32])
        raise HTTPException(status_code=401, detail="Invalid token")
    if not header.get("kid"):
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        try:
            key = _get_clerk_signing_key(token)
        except PyJWKClientError as exc:
            logger.error("Clerk JWKS key lookup failed: %s | token_prefix=%s", exc, token[:32])
            raise HTTPException(status_code=401, detail="Invalid token") from exc

        verify_aud = bool(settings.CLERK_JWT_AUDIENCE)
        payload = jwt.decode(
            token,
            key,
            algorithms=[alg],
            issuer=issuer,
            audience=settings.CLERK_JWT_AUDIENCE if verify_aud else None,
            options={"require": ["exp", "sub"], "verify_aud": verify_aud},
        )
    except jwt.ExpiredSignatureError as exc:
        logger.error("Clerk JWT expired: %s | token_prefix=%s", exc, token[:32])
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        logger.error("Clerk JWT verify failed: %s | token_prefix=%s", exc, token[:32])
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    allowed_parties = _split_csv(settings.CLERK_AUTHORIZED_PARTIES)
    authorized_party = str(payload.get("azp") or "").rstrip("/")
    if allowed_parties and authorized_party not in allowed_parties:
        logger.error("Clerk JWT azp not allowed: %s", authorized_party)
        raise HTTPException(status_code=401, detail="Invalid token")

    if not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid token: missing sub")

    payload["_auth_provider"] = "clerk"
    return payload


def verify_auth_jwt(token: str) -> dict:
    """Verify the current app auth token.

    Clerk is used when CLERK_ISSUER matches the token issuer. Otherwise the
    legacy Supabase verifier is used so existing tests and local setups keep
    working until Clerk env vars are added.
    """
    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
    except jwt.InvalidTokenError:
        return verify_supabase_jwt(token)

    issuer = str(unverified.get("iss") or "").rstrip("/")
    if _clerk_issuer() and issuer == _clerk_issuer():
        return verify_clerk_jwt(token)
    return verify_supabase_jwt(token)


async def fetch_clerk_user_profile(user_id: str) -> dict:
    """Fetch Clerk user details needed for first-request provisioning."""
    if not settings.CLERK_SECRET_KEY:
        return {}

    url = f"https://api.clerk.com/v1/users/{user_id}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            url,
            headers={"Authorization": f"Bearer {settings.CLERK_SECRET_KEY}"},
        )

    if response.status_code == 404:
        raise HTTPException(status_code=401, detail="Clerk user not found")
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("Clerk user fetch failed: %s", exc)
        return {}

    data = response.json()
    email_addresses = data.get("email_addresses") or []
    primary_email_id = data.get("primary_email_address_id")
    primary_email = next(
        (email for email in email_addresses if email.get("id") == primary_email_id),
        email_addresses[0] if email_addresses else {},
    )
    phone_numbers = data.get("phone_numbers") or []
    primary_phone_id = data.get("primary_phone_number_id")
    primary_phone = next(
        (phone for phone in phone_numbers if phone.get("id") == primary_phone_id),
        phone_numbers[0] if phone_numbers else {},
    )
    unsafe_metadata = data.get("unsafe_metadata") or {}
    first_name = data.get("first_name") or ""
    last_name = data.get("last_name") or ""
    full_name = unsafe_metadata.get("full_name") or " ".join(
        part for part in (first_name, last_name) if part
    )

    return {
        "email": primary_email.get("email_address"),
        "full_name": full_name or None,
        "avatar_url": data.get("image_url"),
        "phone": unsafe_metadata.get("phone") or primary_phone.get("phone_number"),
        "headline": unsafe_metadata.get("headline"),
        "linkedin_url": unsafe_metadata.get("linkedin_url"),
    }
