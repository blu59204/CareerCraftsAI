"""Nango webhook verification using the documented raw-body HMAC."""

import hashlib
import hmac


def verify_nango_webhook(*, body: bytes, signature: str | None, signing_key: str) -> bool:
    if not signature or not signing_key:
        return False
    expected = hmac.new(signing_key.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def webhook_event_hash(body: bytes) -> str:
    """Stable replay key when Nango does not include an event identifier."""
    return hashlib.sha256(body).hexdigest()
