import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.config import get_settings
from app.main import app as fastapi_app
from app.models import User
from app.security.tokens import create_access_token


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
    record = User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex}@example.com",
        privacy_consent_at=datetime.now(UTC),
    )
    session.add(record)
    await session.flush()
    return record


@pytest_asyncio.fixture
async def client(session):
    async def override_get_db():
        yield session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(user, settings) -> dict[str, str]:
    token = create_access_token(user.id, settings.jwt_secret, settings.jwt_ttl_seconds)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path):
    """Keep uploaded test videos out of the developer's real storage directory."""
    from app.api.deps import get_storage
    from app.services.storage import LocalFilesystemStorage

    storage = LocalFilesystemStorage(root=tmp_path / "videos")
    fastapi_app.dependency_overrides[get_storage] = lambda: storage
    yield storage
    fastapi_app.dependency_overrides.pop(get_storage, None)


@pytest_asyncio.fixture
async def make_attempt(session):
    from datetime import UTC, datetime, timedelta

    from app.models import Attempt

    async def _make(owner, **overrides):
        now = overrides.pop("created_at", datetime.now(UTC))
        attempt = Attempt(
            id=uuid.uuid4(),
            user_id=owner.id,
            exercise_type=overrides.pop("exercise_type", "squat"),
            status=overrides.pop("status", "queued"),
            cv_job_id=overrides.pop("cv_job_id", f"job-{uuid.uuid4().hex[:8]}"),
            original_video_ref=overrides.pop("original_video_ref", "ref.mp4"),
            created_at=now,
            expires_at=overrides.pop("expires_at", now + timedelta(days=30)),
            consent_at=overrides.pop("consent_at", now),
            **overrides,
        )
        session.add(attempt)
        await session.flush()
        return attempt

    return _make


@pytest_asyncio.fixture
async def other_user(session):
    from app.models import User

    record = User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex}@example.com",
        privacy_consent_at=datetime.now(UTC),
    )
    session.add(record)
    await session.flush()
    return record
