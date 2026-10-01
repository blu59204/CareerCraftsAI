"""Content identity for saved resumes and score responses."""

import hashlib


def content_version(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
