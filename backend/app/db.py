from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


@lru_cache
def session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Cached per URL: one engine, one connection pool, for the process lifetime.

    Without the cache, the request-scoped `get_db` dependency would build a fresh
    engine — and a fresh pool — on every request.
    """
    engine = create_async_engine(database_url, pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False)
