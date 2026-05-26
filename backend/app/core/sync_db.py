"""
sync_db.py — Thread-safe synchronous DB helpers for agent node functions.

Agent nodes run inside a thread-pool executor (harness → orchestrator.invoke).
The shared AsyncSessionLocal engine is bound to the main event loop and cannot
be reused from a worker thread.  A dedicated *synchronous* SQLAlchemy engine is
created once (protected by a threading.Lock) and reused across all calls,
avoiding both connection pool exhaustion and the asyncio.run() RuntimeError.
"""
import threading

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_lock = threading.Lock()
_sync_engine = None
_sync_factory = None


def _get_sync_factory():
    global _sync_engine, _sync_factory
    if _sync_engine is None:
        with _lock:
            if _sync_engine is None:
                # Convert async URL to sync: postgresql+asyncpg → postgresql+psycopg
                sync_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg")
                _sync_engine = create_engine(
                    sync_url,
                    pool_size=5,
                    max_overflow=10,
                    pool_pre_ping=True,
                )
                _sync_factory = sessionmaker(_sync_engine, class_=Session, expire_on_commit=False)
    return _sync_factory


def fetch_model_settings(user_id: str):
    """Return active UserModelSettings row for user_id, or None."""
    from app.models.db import UserModelSettings

    factory = _get_sync_factory()
    with factory() as db:
        result = db.execute(
            select(UserModelSettings).where(
                UserModelSettings.user_id == user_id,
                UserModelSettings.is_active == True,  # noqa: E712
            )
        )
        return result.scalars().first()


def fetch_user_full_name(user_id: str) -> str:
    """Return user full_name string, or empty string."""
    from app.models.db import User

    factory = _get_sync_factory()
    with factory() as db:
        result = db.execute(select(User.full_name).where(User.id == user_id))
        return result.scalars().first() or ""


def fetch_user_profile_text(user_id: str) -> str:
    """Return primary resume raw_text (first 2000 chars) for user, or empty string."""
    from app.models.db import UserDocument

    factory = _get_sync_factory()
    with factory() as db:
        result = db.execute(
            select(UserDocument).where(
                UserDocument.user_id == user_id,
                UserDocument.doc_type == "resume",
                UserDocument.is_primary == True,  # noqa: E712
            )
        )
        doc = result.scalars().first()
        return doc.raw_text[:2000] if doc and doc.raw_text else ""
