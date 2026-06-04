"""JWT verification for Supabase Auth sessions.

Supabase projects sign access tokens with an asymmetric key (ES256/RS256)
exposed via JWKS, or — for legacy projects — with the shared HS256 secret.
We inspect the token header and verify accordingly, so both schemes work.
"""
import logging
from typing import Any

import jwt
from fastapi import HTTPException
from jwt import PyJWKClient

from app.core.config import settings

logger = logging.getLogger(__name__)

_ASYMMETRIC_ALGS = ("ES256", "RS256")

# Tolerate clock drift between this server and Supabase's token issuer so a
# freshly minted token whose `iat`/`nbf` is a few seconds ahead is still accepted.
_CLOCK_SKEW_LEEWAY = 60

# Lazily-built JWKS client (caches signing keys across requests).
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_url = settings.SUPABASE_URL.rstrip("/") + "/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=600)
    return _jwks_client


def verify_supabase_jwt(token: str) -> dict[str, Any]:
    """Verify a Supabase JWT token (asymmetric JWKS or legacy HS256)."""
    try:
        alg = jwt.get_unverified_header(token).get("alg", "HS256")

        if alg in _ASYMMETRIC_ALGS:
            signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=list(_ASYMMETRIC_ALGS),
                audience="authenticated",
                leeway=_CLOCK_SKEW_LEEWAY,
            )
        else:
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
                leeway=_CLOCK_SKEW_LEEWAY,
            )

        payload["_auth_provider"] = "supabase"
        return payload
    except jwt.ExpiredSignatureError as exc:
        logger.error("Supabase JWT expired: %s", exc)
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as exc:
        logger.error("Supabase JWT invalid: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as exc:  # JWKS fetch / key resolution failures
        logger.error("Supabase JWT verification error: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid token")


def verify_auth_jwt(token: str) -> dict[str, Any]:
    """Verify authentication JWT token (Supabase only)."""
    return verify_supabase_jwt(token)
