import os
import subprocess
import sys
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models import User


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture(scope="session", autouse=True)
def migrated_database(settings):
    """Bring the test database to head once per test session."""
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        env={**os.environ, "ALEMBIC_DATABASE_URL": settings.test_database_url},
    )


@pytest_asyncio.fixture
async def session(settings, migrated_database):
    engine = create_async_engine(settings.test_database_url)
    connection = await engine.connect()
    transaction = await connection.begin()
    # join_transaction_mode="create_savepoint" is REQUIRED, not decorative: the
    # service layer calls `await db.commit()` (Tasks 9, 11, 12). Without it, that
    # commit would commit this fixture's outer transaction, the rollback below
    # would become a no-op, and rows would leak between tests.
    maker = async_sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    db: AsyncSession = maker()
    try:
        yield db
    finally:
        await db.close()
        await transaction.rollback()
        await connection.close()
        await engine.dispose()


@pytest_asyncio.fixture
async def user(session) -> User:
    record = User(id=uuid.uuid4(), email=f"{uuid.uuid4().hex}@example.com")
    session.add(record)
    await session.flush()
    return record
