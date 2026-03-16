"""Session ID management via contextvars."""

import os
import uuid
from contextvars import ContextVar

_session_id: ContextVar[str | None] = ContextVar("tracectrl_session_id", default=None)


def new_session() -> str:
    """Generate a new session ID and store it in context."""
    sid = os.getenv("TRACECTRL_SESSION_ID") or str(uuid.uuid4())
    _session_id.set(sid)
    return sid


def current_session_id() -> str | None:
    """Return the current session ID, or None if not set."""
    return _session_id.get()


def set_session_id(sid: str) -> None:
    """Explicitly set the session ID (for cross-agent propagation)."""
    _session_id.set(sid)
