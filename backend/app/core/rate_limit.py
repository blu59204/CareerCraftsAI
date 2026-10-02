import logging

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)


def _get_user_or_ip(request: Request) -> str:
    """Extract user ID from JWT for per-user rate limiting, fallback to IP."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer ccx_"):
        # Browser-extension device token: limit per paired device.
        import hashlib

        return "ext:" + hashlib.sha256(auth.encode()).hexdigest()[:16]
    # Only a subject the middleware already verified counts. Reading it from
    # the unverified token would let a forged JWT with a random `sub` get a
    # fresh bucket on every request, including on public routes.
    user = getattr(request.state, "user", None)
    if isinstance(user, dict) and user.get("sub"):
        return str(user["sub"])
    return get_remote_address(request)


limiter = Limiter(key_func=_get_user_or_ip)

# Stricter limits for sensitive endpoints (use as decorator):
# @limiter.limit("5/minute")  — for API key submission
# @limiter.limit("10/minute") — for auth endpoints
