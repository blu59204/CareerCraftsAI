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

# Endpoints a user must be able to reach even before agreeing to the
# Terms of Service / Privacy Policy: checking their own status, recording
# agreement itself, exporting their data, and deleting their account. A
# data-access or erasure right can't be legally conditioned on first
# accepting new terms, so those two stay reachable regardless. Every other
# endpoint is blocked until policy_accepted_at is set, whether the request
# came through the sign-up form or hit the API directly.
_CONSENT_EXEMPT_PATHS = {
    ("GET", "/api/v1/users/me"),
    ("POST", "/api/v1/users/me/consent"),
    ("GET", "/api/v1/users/me/export"),
    ("DELETE", "/api/v1/users/me"),
    ("POST", "/api/v1/users/me/cancel-deletion"),
}


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
    user = await get_or_provision_user(db, auth_subject, payload)

    if (
        user.policy_accepted_at is None
        and (
            request.method,
            request.url.path,
        )
        not in _CONSENT_EXEMPT_PATHS
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "policy_consent_required",
                "message": "Agree to the Terms of Service and Privacy Policy to continue.",
            },
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
