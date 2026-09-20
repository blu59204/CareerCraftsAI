"""Input validation at the integrations trust boundary."""

from urllib.parse import urlsplit, urlunsplit


class InvalidReturnPath(ValueError):
    pass


def validate_return_path(value: str) -> str:
    """Accept only an application-relative path to prevent open redirects."""
    if (
        not value
        or len(value) > 2048
        or "\\" in value
        or any(c.isspace() for c in value)
    ):
        raise InvalidReturnPath("return_path must be a relative application path")
    parsed = urlsplit(value)
    if (
        parsed.scheme
        or parsed.netloc
        or not parsed.path.startswith("/")
        or parsed.path.startswith("//")
    ):
        raise InvalidReturnPath("return_path must be a relative application path")
    return urlunsplit(("", "", parsed.path, parsed.query, ""))
