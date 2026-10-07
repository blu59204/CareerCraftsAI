"""Request-scoped identity for background graph execution.

AG-UI chat turns run inside a LangGraph node, not an API dependency, so the
chat graph cannot take a CurrentUser argument. The JWT middleware records the
authenticated Clerk subject here; the chat graph reads it back so every tool
is scoped to the caller and never trusts a client-supplied user id.
"""

import contextlib
import contextvars

current_user_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_user_id", default=None
)


def set_current_user_id(user_id: str | None) -> contextvars.Token:
    return current_user_id.set(user_id)


def reset_current_user_id(token: contextvars.Token) -> None:
    with contextlib.suppress(ValueError):
        current_user_id.reset(token)
