"""Clerk Auth verification — JWKS-based JWT decode (RS256).

Historical module name: this file used to verify Supabase ES256 tokens. The
module path and every exported name are kept because routers, middleware and
tests import them (``verify_token`` / ``verify_auth_jwt`` / ``verify_supabase_jwt``
are all the same callable).

Clerk signs session tokens with RS256 using keys published at
``{CLERK_ISSUER}/.well-known/jwks.json``. The ``sub`` claim is a *text* id such
as ``user_2abc...`` — not a UUID — and is stored in ``users.supabase_uid``,
which is a TEXT column. The RLS policies in
``supabase/migrations/0028_clerk_third_party_auth_rls.sql`` match on that exact
column via ``auth.jwt() ->> 'sub'``, so the column name stays as-is.

The JWKS client is built lazily on first verification, never at import time —
an unset or unreachable JWKS URL must not break importing the app (or
collecting the test suite).
"""

from __future__ import annotations

import logging
from typing import Any

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models import User

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)
_CLOCK_SKEW_LEEWAY = 60
_ALGORITHMS = ["RS256"]

# Built lazily by _get_jwks_client(); tests patch this attribute directly.
_jwks_client: jwt.PyJWKClient | None = None


def _jwks_url() -> str:
    """Resolve the JWKS endpoint from explicit config or from the issuer."""
    if settings.CLERK_JWKS_URL:
        return settings.CLERK_JWKS_URL
    if settings.CLERK_ISSUER:
        return f"{settings.CLERK_ISSUER.rstrip('/')}/.well-known/jwks.json"
    return ""


def _get_jwks_client() -> jwt.PyJWKClient:
    """Return the process-wide JWKS client, constructing it on first use.

    Constructing at import time would make a bad/missing URL a hard import
    failure for every module that touches auth.
    """
    global _jwks_client
    if _jwks_client is None:
        url = _jwks_url()
        if not url:
            logger.error(
                "Clerk auth is not configured — set CLERK_JWKS_URL or CLERK_ISSUER"
            )
            raise HTTPException(status_code=401, detail="Authentication not configured")
        _jwks_client = jwt.PyJWKClient(url, cache_keys=True, lifespan=3600)
    return _jwks_client


def reset_jwks_client() -> None:
    """Drop the cached JWKS client (config reload / tests)."""
    global _jwks_client
    _jwks_client = None


def verify_token(token: str) -> dict[str, Any]:
    """Decode and validate a Clerk JWT using JWKS (RS256). Returns payload dict."""
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        options: dict[str, Any] = {"require": ["exp", "sub"]}
        kwargs: dict[str, Any] = {}
        if settings.CLERK_AUDIENCE:
            kwargs["audience"] = settings.CLERK_AUDIENCE
        else:
            # Clerk session tokens have no fixed `aud` — don't demand one.
            options["verify_aud"] = False
        if settings.CLERK_ISSUER:
            kwargs["issuer"] = settings.CLERK_ISSUER
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=_ALGORITHMS,
            leeway=_CLOCK_SKEW_LEEWAY,
            options=options,
            **kwargs,
        )
        return payload
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


verify_auth_jwt = verify_token


def subject_from_payload(payload: dict[str, Any]) -> str:
    """Pull the auth subject out of a verified payload, or raise 401."""
    subject = payload.get("sub") or payload.get("user_id") or payload.get("supabase_uid")
    if not subject:
        raise HTTPException(status_code=401, detail="Invalid token — missing sub claim")
    return str(subject)


def _profile_from_payload(payload: dict[str, Any], subject: str) -> dict[str, Any]:
    """Map Clerk claims onto User columns.

    ``users.email`` is NOT NULL, but Clerk only emits an ``email`` claim when the
    instance is configured to add it as a custom session claim. Fall back to a
    deterministic, non-deliverable placeholder so first-sight provisioning never
    fails; the profile endpoints can correct it later.
    """
    meta = payload.get("user_metadata") or {}
    email = (
        payload.get("email")
        or payload.get("primary_email_address")
        or meta.get("email")
        or f"{subject}@users.noreply.clerk"
    )
    return {
        "supabase_uid": subject,
        "email": email,
        "full_name": payload.get("full_name")
        or payload.get("name")
        or meta.get("full_name"),
        "avatar_url": payload.get("image_url")
        or payload.get("picture")
        or meta.get("avatar_url"),
    }


async def _select_by_uid(db: AsyncSession, subject: str) -> User | None:
    result = await db.execute(select(User).where(User.supabase_uid == subject))
    return result.scalars().first()


async def get_or_provision_user(
    db: AsyncSession,
    subject: str,
    payload: dict[str, Any] | None = None,
) -> User:
    """Load the User for a Clerk subject, creating the row on first sight.

    Nothing else creates ``public.users`` rows any more — the Supabase
    ``on_auth_user_created`` trigger lived on ``auth.users``, which does not
    exist here. So the first authenticated request for a subject provisions it.

    Race handling: two concurrent first requests for the same subject both miss
    the SELECT. The INSERT uses ``ON CONFLICT (supabase_uid) DO NOTHING`` so the
    loser is a no-op instead of a unique violation, and any other integrity
    error (e.g. the unique ``email`` index) is caught, rolled back, and followed
    by a re-SELECT. Either way both requests end up with the same row.
    """
    payload = payload or {}
    user = await _select_by_uid(db, subject)
    if user is not None:
        return user

    values = _profile_from_payload(payload, subject)
    try:
        await db.execute(
            pg_insert(User)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["supabase_uid"])
        )
        await db.commit()
    except IntegrityError as exc:
        # Concurrent insert won the race, or the email collides with an existing
        # row. Roll back and fall through to the re-SELECT below.
        await db.rollback()
        logger.info("User provisioning conflict for %s: %s", subject, exc.orig)

    user = await _select_by_uid(db, subject)
    if user is not None:
        return user

    # Not a supabase_uid race — an existing row already owns this email. Adopt it
    # only if it has never been bound to an auth subject (pre-Clerk rows);
    # otherwise refuse rather than hand over somebody else's account.
    result = await db.execute(select(User).where(User.email == values["email"]))
    existing = result.scalars().first()
    if existing is not None and not existing.supabase_uid:
        existing.supabase_uid = subject
        await db.commit()
        await db.refresh(existing)
        logger.info("Bound pre-existing user %s to auth subject %s", existing.id, subject)
        return existing

    logger.error("User provisioning failed for subject %s", subject)
    raise HTTPException(status_code=500, detail="User provisioning failed")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract Bearer token, verify locally, load (or provision) User by subject."""
    if not token:
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    payload = verify_token(token)
    subject = subject_from_payload(payload)
    return await get_or_provision_user(db, subject, payload)


verify_supabase_jwt = verify_token  # alias used by test_edge_cases
