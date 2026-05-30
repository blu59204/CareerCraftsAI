import logging

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)


def _get_user_or_ip(request: Request) -> str:
    """Extract user ID from JWT for per-user rate limiting, fallback to IP."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        try:
            import jwt
            token = auth.removeprefix("Bearer ").strip()
            payload = jwt.decode(token, options={"verify_signature": False})
            return payload.get("sub", get_remote_address(request))
        except Exception as exc:
            logger.debug("Rate limit JWT subject extraction failed: %s", exc)
    return get_remote_address(request)


limiter = Limiter(key_func=_get_user_or_ip)

# Stricter limits for sensitive endpoints (use as decorator):
# @limiter.limit("5/minute")  — for API key submission
# @limiter.limit("10/minute") — for auth endpoints
