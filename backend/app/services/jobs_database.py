"""Search services run in both API and synchronous-agent event loops.

Do not reuse asyncpg connections between those loops. NullPool retains the
existing session pattern while making each session own its connection.
"""

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
    connect_args={"statement_cache_size": 0},
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
