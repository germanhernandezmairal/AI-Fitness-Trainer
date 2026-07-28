# Backend Attempts API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI backend that accepts exercise videos from the frontend, proxies them to Alejandro's CV service, receives results by signed webhook (with a polling fallback), and exposes attempt history and GDPR erasure.

**Architecture:** A single FastAPI app in `backend/` owning Postgres, the original video files, and job state. It implements two contracts from `docs/superpowers/specs/2026-07-27-api-contract-design.md`: a **public** boundary (frontend ↔ backend, JWT-authenticated) and an **internal** boundary (backend ↔ CV service, `X-API-Key` outbound + HMAC-verified webhooks inbound). Result-bearing schemas live in one shared Pydantic module so both sides of the boundary validate identically. A `fake-cv-service/` app implements the internal contract so the whole loop runs locally before Alejandro's service is ready.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2.0 (async) + asyncpg · Alembic · Pydantic v2 + pydantic-settings · httpx · PyAV (video probing) · APScheduler · pytest + pytest-asyncio + respx · Postgres 16 via Docker · `uv` for dependency management.

## Global Constraints

Copied verbatim from the spec. Every task's requirements implicitly include these.

- **API version prefix:** `/v1` on both boundaries.
- **Allowed upload formats:** MP4 (H.264 / AAC) and MOV. Nothing else.
- **Max upload file size:** 100 MB.
- **Max upload duration:** 60 seconds.
- **Retention period:** 30 days from creation, for the original video, annotated video, and any retained landmarks.
- **Status catalog (closed, identical on both boundaries):** `queued` → `processing` → `completed` | `failed`.
- **Failure codes (closed):** content errors *not* retried — `no_pose_detected`, `low_pose_confidence`, `no_movement_detected`; system errors retried with backoff — `storage_error`, `worker_error`.
- **Upload validation codes (closed, HTTP 400):** `unsupported_format`, `file_too_large`, `video_too_long`, `unknown_exercise_type`.
- **Form error codes (closed, per rep):** `knee_valgus`, `insufficient_depth`, `excessive_forward_lean`.
- **Failure shape on both boundaries:** `{ "status": "failed", "error": { "code": "...", "message": "..." } }`.
- **Webhook security:** `X-CV-Signature` = HMAC-SHA256 over the raw body; `X-CV-Timestamp` used to reject replays. Verify before trusting the payload.
- **Idempotency:** webhook and polling can both deliver the same result; applying a result twice must be safe.
- **Ownership:** a user may only read or delete their own attempts.
- **Exercise types (MVP):** `squat` only. Anything else → `unknown_exercise_type`.

## Decisions made for this plan (beyond the spec)

- **Auth:** dev-grade JWT. A real `users` table and a real `get_current_user` dependency with real ownership checks, but token issuance is a dev-only login endpoint taking an email. A later plan replaces issuance (registration, passwords, refresh) without touching attempts code.
- **Object storage:** the spec defers S3/MinIO. This plan defines a `Storage` protocol and ships `LocalFilesystemStorage`. Swapping in S3 later means one new class, no caller changes.
- **Background work:** APScheduler in-process (no Celery/Redis on the backend side). The two scheduled jobs are thin wrappers around plain async functions that are unit-tested directly.
- **Video probing:** PyAV (`av`), whose wheels bundle FFmpeg — no external `ffmpeg` binary needed on Windows.
- **Repo layout:** backend lives in `backend/`, leaving room for `frontend/` and Alejandro's `cv-service/` alongside it.

## File Structure

```
backend/
  pyproject.toml               deps + tool config (pytest, ruff)
  alembic.ini                  Alembic config
  docker-compose.yml           Postgres (dev + test) and the fake CV service
  .env.example                 every setting, documented
  README.md                    how to run, test, and demo the loop
  alembic/
    env.py                     async Alembic environment
    versions/                  migrations
  app/
    main.py                    FastAPI app, router wiring, lifespan (scheduler)
    config.py                  Settings (pydantic-settings) + get_settings()
    db.py                      engine, session factory, Base
    models/
      user.py                  User
      attempt.py               Attempt (the backend's mirror of a CV job)
    schemas/
      contract.py              SHARED across the boundary: enums, result, error, job payloads
      attempt.py               public-boundary response shapes only
    security/
      tokens.py                JWT issue/decode
      signing.py               HMAC sign/verify for webhooks
    services/
      storage.py               Storage protocol + LocalFilesystemStorage
      validation.py            upload validation → the four 400 codes
      cv_client.py             the internal boundary client (POST/GET/DELETE jobs)
      attempts.py              orchestration: create, apply result, delete
      jobs.py                  reconcile stale attempts, purge expired
    api/
      deps.py                  get_db, get_current_user, get_storage, get_cv_client
      auth_dev.py              dev-only login
      attempts.py              public router
      webhooks.py              CV callback receiver
  tests/
    conftest.py                DB, client, and auth fixtures
    fixtures/                  squat.mp4 and friends
    ...                        one test module per task
fake-cv-service/
  main.py                      runnable implementation of the internal contract
  Dockerfile
```

---

### Task 1: Project scaffold, settings, and health check

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/docker-compose.yml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_health.py`
- Modify: `.gitignore` (repo root)

**Interfaces:**
- Consumes: nothing.
- Produces: `app.config.Settings` (a pydantic-settings model) and `app.config.get_settings() -> Settings` (lru-cached). `app.main.app` — the FastAPI instance. Every later task imports these.

- [ ] **Step 1: Create the dependency manifest**

Create `backend/pyproject.toml`:

```toml
[project]
name = "ai-fitness-trainer-backend"
version = "0.1.0"
description = "Backend for AI Fitness Trainer: attempts API and CV service integration"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "httpx>=0.28",
    "python-multipart>=0.0.12",
    "pyjwt>=2.10",
    "av>=13.1",
    "apscheduler>=3.11",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "respx>=0.22",
    "ruff>=0.8",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]
```

- [ ] **Step 2: Document every setting**

Create `backend/.env.example`:

```bash
# --- Database ---
DATABASE_URL=postgresql+asyncpg://fitness:fitness@localhost:5432/fitness
TEST_DATABASE_URL=postgresql+asyncpg://fitness:fitness@localhost:5432/fitness_test

# --- Auth (dev-grade; replaced by a real auth plan later) ---
JWT_SECRET=dev-only-change-me
JWT_TTL_SECONDS=86400

# --- CV service (internal boundary) ---
CV_SERVICE_URL=http://localhost:9000
CV_API_KEY=dev-cv-api-key
CV_WEBHOOK_SECRET=dev-webhook-secret
# How old an X-CV-Timestamp may be before the webhook is rejected as a replay.
WEBHOOK_TOLERANCE_SEC=300
# Where the CV service should send its callback. Must be reachable from the CV service.
BACKEND_PUBLIC_URL=http://localhost:8000

# --- Storage ---
STORAGE_DIR=./var/videos

# --- Upload limits (spec §6c) ---
MAX_UPLOAD_BYTES=104857600
MAX_DURATION_SEC=60

# --- Retention (spec §7) ---
RETENTION_DAYS=30

# --- Polling fallback ---
# An attempt still non-terminal this long after creation gets polled directly.
CV_POLL_AFTER_SEC=30
```

- [ ] **Step 3: Write the settings module**

Create `backend/app/__init__.py` (empty file) and `backend/app/config.py`:

```python
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://fitness:fitness@localhost:5432/fitness"
    test_database_url: str = "postgresql+asyncpg://fitness:fitness@localhost:5432/fitness_test"

    jwt_secret: str = "dev-only-change-me"
    jwt_ttl_seconds: int = 86400

    cv_service_url: str = "http://localhost:9000"
    cv_api_key: str = "dev-cv-api-key"
    cv_webhook_secret: str = "dev-webhook-secret"
    webhook_tolerance_sec: int = 300
    backend_public_url: str = "http://localhost:8000"

    storage_dir: Path = Path("./var/videos")

    max_upload_bytes: int = 104_857_600
    max_duration_sec: int = 60

    retention_days: int = 30

    cv_poll_after_sec: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Write the failing test**

Create `backend/tests/__init__.py` (empty file) and `backend/tests/test_health.py`:

```python
import httpx

from app.main import app


async def test_health_returns_ok():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 5: Install dependencies and run the test to verify it fails**

Run from `backend/`:

```bash
uv venv
uv pip install -e ".[dev]"
uv run pytest tests/test_health.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`.

(If `uv` is not installed: `pip install uv`, or substitute `python -m venv .venv` + `pip install -e ".[dev]"` and drop the `uv run` prefix from every later command.)

- [ ] **Step 6: Write the minimal app**

Create `backend/app/main.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="AI Fitness Trainer Backend", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `uv run pytest tests/test_health.py -v`
Expected: PASS.

- [ ] **Step 8: Add the Postgres service for dev and tests**

Create `backend/docker-compose.yml`:

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: fitness
      POSTGRES_PASSWORD: fitness
      POSTGRES_DB: fitness
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U fitness"]
      interval: 5s
      retries: 10

volumes:
  pgdata:
```

Bring it up and create the test database:

```bash
docker compose up -d db
docker compose exec db psql -U fitness -c "CREATE DATABASE fitness_test;"
```

Expected: `CREATE DATABASE`.

- [ ] **Step 9: Ignore backend artifacts**

Append to the repo-root `.gitignore`:

```gitignore
# Backend
backend/.venv/
backend/.env
backend/var/
backend/**/__pycache__/
backend/.pytest_cache/
```

- [ ] **Step 10: Commit**

```bash
git add backend/pyproject.toml backend/.env.example backend/docker-compose.yml \
        backend/app backend/tests .gitignore
git commit -m "feat(backend): scaffold FastAPI app with settings and health check"
```

---

### Task 2: Database layer, User and Attempt models, first migration

**Files:**
- Create: `backend/app/db.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/attempt.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/0001_initial.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `app.config.get_settings`.
- Produces:
  - `app.db.Base` — the declarative base every model inherits.
  - `app.db.session_factory(database_url: str) -> async_sessionmaker[AsyncSession]`.
  - `app.models.user.User` with `id: UUID`, `email: str`, `created_at: datetime`.
  - `app.models.attempt.Attempt` with exactly the columns in spec §2, plus `status` stored as a plain string holding an `AttemptStatus` value.
  - `tests/conftest.py` fixtures `session` (a rolled-back `AsyncSession`) and `user` (a persisted `User`), used by every later test module.

- [ ] **Step 1: Write the database plumbing**

Create `backend/app/db.py`:

```python
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
```

- [ ] **Step 2: Write the models**

Create `backend/app/models/__init__.py`:

```python
from app.models.attempt import Attempt
from app.models.user import User

__all__ = ["Attempt", "User"]
```

Create `backend/app/models/user.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

Create `backend/app/models/attempt.py`. Columns mirror spec §2 one-for-one:

```python
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    exercise_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    cv_job_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    original_video_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    annotated_video_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_attempts_user_created", "user_id", "created_at"),
        Index("ix_attempts_status", "status"),
        Index("ix_attempts_expires_at", "expires_at"),
    )
```

`cv_job_id` is nullable because the row is created before the CV service has accepted the job, and unique because idempotent result application (spec §8) keys on it.

- [ ] **Step 3: Configure Alembic**

Create `backend/alembic.ini`:

```ini
[alembic]
script_location = alembic
prepend_sys_path = .

[loggers]
keys = root

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[handler_console]
class = StreamHandler
args = (sys.stderr,)
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

Create `backend/alembic/script.py.mako`:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

Create `backend/alembic/env.py`. It reads the URL from an override (so tests can point it at the test database) falling back to settings:

```python
import asyncio
import os

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.db import Base
from app.models import Attempt, User  # noqa: F401  (imported so Base sees the tables)

target_metadata = Base.metadata


def _database_url() -> str:
    return os.environ.get("ALEMBIC_DATABASE_URL") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=_database_url(), target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_database_url())
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 4: Write the initial migration**

Create `backend/alembic/versions/0001_initial.py`:

```python
"""initial: users and attempts

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("exercise_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("cv_job_id", sa.String(100), nullable=True, unique=True),
        sa.Column("original_video_ref", sa.String(500), nullable=False),
        sa.Column("annotated_video_url", sa.String(1000), nullable=True),
        sa.Column("result", postgresql.JSONB, nullable=True),
        sa.Column("overall_score", sa.Integer, nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_attempts_user_created", "attempts", ["user_id", "created_at"])
    op.create_index("ix_attempts_status", "attempts", ["status"])
    op.create_index("ix_attempts_expires_at", "attempts", ["expires_at"])


def downgrade() -> None:
    op.drop_table("attempts")
    op.drop_table("users")
```

- [ ] **Step 5: Write the shared test fixtures**

Create `backend/tests/conftest.py`. Each test runs inside a transaction that is rolled back, so tests never see each other's rows:

```python
import os
import subprocess
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
        ["alembic", "upgrade", "head"],
        check=True,
        env={**os.environ, "ALEMBIC_DATABASE_URL": settings.test_database_url},
    )


@pytest_asyncio.fixture
async def session(settings, migrated_database):
    engine = create_async_engine(settings.test_database_url)
    connection = await engine.connect()
    transaction = await connection.begin()
    maker = async_sessionmaker(bind=connection, expire_on_commit=False)
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
```

- [ ] **Step 6: Write the failing test**

Create `backend/tests/test_models.py`:

```python
import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa

from app.models import Attempt


async def test_attempt_round_trips_every_contract_column(session, user):
    now = datetime.now(UTC)
    attempt = Attempt(
        id=uuid.uuid4(),
        user_id=user.id,
        exercise_type="squat",
        status="queued",
        cv_job_id="abc123",
        original_video_ref="videos/abc.mp4",
        expires_at=now + timedelta(days=30),
        consent_at=now,
    )
    session.add(attempt)
    await session.flush()

    loaded = await session.get(Attempt, attempt.id)
    assert loaded is not None
    assert loaded.status == "queued"
    assert loaded.cv_job_id == "abc123"
    assert loaded.annotated_video_url is None
    assert loaded.result is None
    assert loaded.overall_score is None
    assert loaded.error_code is None
    assert loaded.completed_at is None


async def test_cv_job_id_is_unique(session, user):
    now = datetime.now(UTC)

    def build() -> Attempt:
        return Attempt(
            id=uuid.uuid4(),
            user_id=user.id,
            exercise_type="squat",
            status="queued",
            cv_job_id="duplicate-job",
            original_video_ref="videos/x.mp4",
            expires_at=now + timedelta(days=30),
            consent_at=now,
        )

    session.add(build())
    await session.flush()
    session.add(build())

    try:
        await session.flush()
    except sa.exc.IntegrityError:
        return
    raise AssertionError("expected a unique-constraint violation on cv_job_id")
```

- [ ] **Step 7: Run the test to verify it fails**

Run from `backend/`: `uv run pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models'` (before Step 2's files exist) or, if written in order, the migration has not been applied yet.

- [ ] **Step 8: Apply the migration and re-run**

Run from `backend/`:

```bash
ALEMBIC_DATABASE_URL=postgresql+asyncpg://fitness:fitness@localhost:5432/fitness_test \
  uv run alembic upgrade head
uv run pytest tests/test_models.py -v
```

On PowerShell, set the variable first: `$env:ALEMBIC_DATABASE_URL="postgresql+asyncpg://fitness:fitness@localhost:5432/fitness_test"`.

Expected: both tests PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/db.py backend/app/models backend/alembic.ini backend/alembic \
        backend/tests/conftest.py backend/tests/test_models.py
git commit -m "feat(backend): add User and Attempt models with initial migration"
```

---

### Task 3: Shared contract schemas

This is the module both sides of the internal boundary validate against — spec §5 and §6 expressed once.

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/contract.py`
- Create: `backend/tests/test_contract_schemas.py`

**Interfaces:**
- Consumes: nothing.
- Produces (later tasks import all of these by these exact names):
  - Enums: `AttemptStatus` (`QUEUED/PROCESSING/COMPLETED/FAILED`), `FormErrorCode`, `FailureCode`, `UploadErrorCode`, `ExerciseType`.
  - `RepResult(rep_index, start_time_sec, end_time_sec, min_knee_angle_deg, score, errors)`.
  - `AnalysisResult(exercise_type, overall_score, summary, rep_count, reps, annotated_video_url, algorithm_version)`.
  - `ErrorPayload(code: FailureCode, message: str)`.
  - `JobAccepted(job_id: str, status: AttemptStatus)`.
  - `JobStatus(status: AttemptStatus, result: AnalysisResult | None, error: ErrorPayload | None)` — the shape returned by `GET /v1/jobs/{id}` *and* posted to the webhook.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_contract_schemas.py`. The first test parses the spec §5 example byte-for-byte:

```python
import pytest
from pydantic import ValidationError

from app.schemas.contract import (
    AnalysisResult,
    AttemptStatus,
    FailureCode,
    FormErrorCode,
    JobStatus,
)

SPEC_RESULT = {
    "exercise_type": "squat",
    "overall_score": 82,
    "summary": "Good depth overall, but knees collapse inward on 2 of 5 reps.",
    "rep_count": 5,
    "reps": [
        {
            "rep_index": 1,
            "start_time_sec": 2.1,
            "end_time_sec": 5.4,
            "min_knee_angle_deg": 78,
            "score": 90,
            "errors": [],
        },
        {
            "rep_index": 2,
            "start_time_sec": 6.0,
            "end_time_sec": 9.1,
            "min_knee_angle_deg": 65,
            "score": 60,
            "errors": ["knee_valgus", "insufficient_depth"],
        },
    ],
    "annotated_video_url": "https://cv-storage/x/annotated.mp4",
    "algorithm_version": "squat-rules-v1",
}


def test_parses_the_spec_example_verbatim():
    result = AnalysisResult.model_validate(SPEC_RESULT)

    assert result.overall_score == 82
    assert result.rep_count == 5
    assert result.reps[1].errors == [
        FormErrorCode.KNEE_VALGUS,
        FormErrorCode.INSUFFICIENT_DEPTH,
    ]
    assert result.algorithm_version == "squat-rules-v1"


def test_rejects_a_form_error_outside_the_closed_catalog():
    payload = {**SPEC_RESULT, "reps": [{**SPEC_RESULT["reps"][0], "errors": ["made_up_error"]}]}

    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(payload)


def test_parses_the_completed_job_status():
    status = JobStatus.model_validate({"status": "completed", "result": SPEC_RESULT})

    assert status.status is AttemptStatus.COMPLETED
    assert status.result is not None
    assert status.error is None


def test_parses_the_spec_failure_shape():
    status = JobStatus.model_validate(
        {"status": "failed", "error": {"code": "no_pose_detected", "message": "no human in frame"}}
    )

    assert status.status is AttemptStatus.FAILED
    assert status.error is not None
    assert status.error.code is FailureCode.NO_POSE_DETECTED
    assert status.result is None


def test_rejects_a_failure_code_outside_the_closed_catalog():
    with pytest.raises(ValidationError):
        JobStatus.model_validate(
            {"status": "failed", "error": {"code": "kaboom", "message": "x"}}
        )


def test_completed_status_requires_a_result():
    with pytest.raises(ValidationError):
        JobStatus.model_validate({"status": "completed", "result": None})


def test_failed_status_requires_an_error():
    with pytest.raises(ValidationError):
        JobStatus.model_validate({"status": "failed", "error": None})


def test_failure_codes_declare_whether_they_are_retryable():
    assert FailureCode.WORKER_ERROR.is_retryable is True
    assert FailureCode.STORAGE_ERROR.is_retryable is True
    assert FailureCode.NO_POSE_DETECTED.is_retryable is False
    assert FailureCode.LOW_POSE_CONFIDENCE.is_retryable is False
    assert FailureCode.NO_MOVEMENT_DETECTED.is_retryable is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_contract_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.schemas'`.

- [ ] **Step 3: Write the schemas**

Create `backend/app/schemas/__init__.py` (empty file) and `backend/app/schemas/contract.py`:

```python
"""The shared backend <-> CV service contract (spec §5, §6).

Both sides of the internal boundary validate against this module. Changing anything
here is a contract change and must be agreed with the CV service author.
"""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AttemptStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        return self in (AttemptStatus.COMPLETED, AttemptStatus.FAILED)


class ExerciseType(StrEnum):
    SQUAT = "squat"


class FormErrorCode(StrEnum):
    """Per-rep technique errors (spec §6a). Extensible per exercise."""

    KNEE_VALGUS = "knee_valgus"
    INSUFFICIENT_DEPTH = "insufficient_depth"
    EXCESSIVE_FORWARD_LEAN = "excessive_forward_lean"


class FailureCode(StrEnum):
    """Job failure codes (spec §6b)."""

    NO_POSE_DETECTED = "no_pose_detected"
    LOW_POSE_CONFIDENCE = "low_pose_confidence"
    NO_MOVEMENT_DETECTED = "no_movement_detected"
    STORAGE_ERROR = "storage_error"
    WORKER_ERROR = "worker_error"

    @property
    def is_retryable(self) -> bool:
        """Content errors mean the user re-records; system errors are retried."""
        return self in (FailureCode.STORAGE_ERROR, FailureCode.WORKER_ERROR)


class UploadErrorCode(StrEnum):
    """Backend-side upload rejections, HTTP 400 (spec §6c)."""

    UNSUPPORTED_FORMAT = "unsupported_format"
    FILE_TOO_LARGE = "file_too_large"
    VIDEO_TOO_LONG = "video_too_long"
    UNKNOWN_EXERCISE_TYPE = "unknown_exercise_type"


class RepResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rep_index: int
    start_time_sec: float
    end_time_sec: float
    min_knee_angle_deg: float
    score: int = Field(ge=0, le=100)
    errors: list[FormErrorCode] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_type: ExerciseType
    overall_score: int = Field(ge=0, le=100)
    summary: str
    rep_count: int = Field(ge=0)
    reps: list[RepResult] = Field(default_factory=list)
    annotated_video_url: str | None = None
    algorithm_version: str


class ErrorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: FailureCode
    message: str


class JobAccepted(BaseModel):
    """202 response from POST /v1/jobs."""

    model_config = ConfigDict(extra="ignore")

    job_id: str
    status: AttemptStatus


class JobStatus(BaseModel):
    """GET /v1/jobs/{id} response and the webhook callback body."""

    model_config = ConfigDict(extra="ignore")

    status: AttemptStatus
    result: AnalysisResult | None = None
    error: ErrorPayload | None = None

    @model_validator(mode="after")
    def check_payload_matches_status(self) -> Self:
        if self.status is AttemptStatus.COMPLETED and self.result is None:
            raise ValueError("a completed job must carry a result")
        if self.status is AttemptStatus.FAILED and self.error is None:
            raise ValueError("a failed job must carry an error")
        return self
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_contract_schemas.py -v`
Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas backend/tests/test_contract_schemas.py
git commit -m "feat(backend): add shared backend<->CV contract schemas"
```

---

### Task 4: Dev-grade JWT auth and the current-user dependency

**Files:**
- Create: `backend/app/security/__init__.py`
- Create: `backend/app/security/tokens.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/deps.py`
- Create: `backend/app/api/auth_dev.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_auth.py`
- Modify: `backend/tests/conftest.py`

**Interfaces:**
- Consumes: `Settings`, `User`, the `session` fixture.
- Produces:
  - `app.security.tokens.create_access_token(user_id: uuid.UUID, secret: str, ttl_seconds: int) -> str`
  - `app.security.tokens.decode_access_token(token: str, secret: str) -> uuid.UUID`, raising `InvalidToken`
  - `app.security.tokens.InvalidToken(Exception)`
  - `app.api.deps.get_db() -> AsyncSession` (FastAPI dependency)
  - `app.api.deps.get_current_user(...) -> User` (FastAPI dependency; 401 on any auth problem)
  - New conftest fixtures `client` (an `httpx.AsyncClient` bound to the app with `get_db` overridden to the test session) and `auth_headers` (a valid bearer header for the `user` fixture). Every later API test uses these.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_auth.py`:

```python
import uuid

import pytest

from app.security.tokens import InvalidToken, create_access_token, decode_access_token

SECRET = "test-secret"


def test_round_trips_a_user_id():
    user_id = uuid.uuid4()
    token = create_access_token(user_id, SECRET, ttl_seconds=60)

    assert decode_access_token(token, SECRET) == user_id


def test_rejects_a_token_signed_with_another_secret():
    token = create_access_token(uuid.uuid4(), SECRET, ttl_seconds=60)

    with pytest.raises(InvalidToken):
        decode_access_token(token, "a-different-secret")


def test_rejects_an_expired_token():
    token = create_access_token(uuid.uuid4(), SECRET, ttl_seconds=-1)

    with pytest.raises(InvalidToken):
        decode_access_token(token, SECRET)


def test_rejects_a_garbage_token():
    with pytest.raises(InvalidToken):
        decode_access_token("not-a-jwt", SECRET)


async def test_dev_login_issues_a_token_for_a_new_email(client):
    response = await client.post("/v1/auth/dev-login", json={"email": "new@example.com"})

    assert response.status_code == 200
    assert response.json()["access_token"]


@pytest.mark.xfail(reason="GET /v1/attempts lands in Task 10", strict=False)
async def test_protected_route_rejects_a_missing_token(client):
    response = await client.get("/v1/attempts")

    assert response.status_code == 401


@pytest.mark.xfail(reason="GET /v1/attempts lands in Task 10", strict=False)
async def test_protected_route_rejects_a_bad_token(client):
    response = await client.get("/v1/attempts", headers={"Authorization": "Bearer nope"})

    assert response.status_code == 401
```

The last two tests hit a route that does not exist until Task 10, so they are marked `xfail` here and un-marked in Task 10 Step 5.

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_auth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.security'`.

- [ ] **Step 3: Write the token module**

Create `backend/app/security/__init__.py` (empty file) and `backend/app/security/tokens.py`:

```python
import uuid
from datetime import UTC, datetime, timedelta

import jwt


class InvalidToken(Exception):
    """The token was missing, malformed, expired, or signed with the wrong secret."""


def create_access_token(user_id: uuid.UUID, secret: str, ttl_seconds: int) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str, secret: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise InvalidToken(str(exc)) from exc
```

- [ ] **Step 4: Write the dependencies**

Create `backend/app/api/__init__.py` (empty file) and `backend/app/api/deps.py`:

```python
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import session_factory
from app.models import User
from app.security.tokens import InvalidToken, decode_access_token

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_db(settings: SettingsDep) -> AsyncIterator[AsyncSession]:
    maker = session_factory(settings.database_url)
    async with maker() as session:
        yield session


DbDep = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    settings: SettingsDep,
    db: DbDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise unauthorized

    try:
        user_id = decode_access_token(authorization.split(" ", 1)[1], settings.jwt_secret)
    except InvalidToken:
        raise unauthorized from None

    user = await db.get(User, user_id)
    if user is None:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
```

- [ ] **Step 5: Write the dev login route**

Create `backend/app/api/auth_dev.py`. This is deliberately password-free and clearly labelled — a real auth plan replaces it:

```python
"""Dev-only token issuance. NOT for production: no password, no verification.

Replaced wholesale by the auth plan; nothing outside this module depends on how
tokens are issued, only on `get_current_user`.
"""

import uuid

import sqlalchemy as sa
from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from app.api.deps import DbDep, SettingsDep
from app.models import User
from app.security.tokens import create_access_token

router = APIRouter(prefix="/v1/auth", tags=["auth (dev)"])


class DevLoginRequest(BaseModel):
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/dev-login", response_model=TokenResponse)
async def dev_login(payload: DevLoginRequest, db: DbDep, settings: SettingsDep) -> TokenResponse:
    result = await db.execute(sa.select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(id=uuid.uuid4(), email=payload.email)
        db.add(user)
        await db.commit()

    token = create_access_token(user.id, settings.jwt_secret, settings.jwt_ttl_seconds)
    return TokenResponse(access_token=token)
```

`EmailStr` needs `email-validator`. Add `"email-validator>=2.2"` to the `dependencies` list in `pyproject.toml` and re-run `uv pip install -e ".[dev]"`.

- [ ] **Step 6: Wire the router into the app**

Replace `backend/app/main.py` with:

```python
from fastapi import FastAPI

from app.api import auth_dev

app = FastAPI(title="AI Fitness Trainer Backend", version="0.1.0")
app.include_router(auth_dev.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 7: Add the client and auth fixtures**

Append to `backend/tests/conftest.py`:

```python
import httpx

from app.api.deps import get_db
from app.main import app as fastapi_app
from app.security.tokens import create_access_token


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
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `uv run pytest tests/test_auth.py -v`
Expected: 5 PASS, 2 XFAIL (the two protected-route tests, until Task 10).

- [ ] **Step 9: Commit**

```bash
git add backend/app/security backend/app/api backend/app/main.py backend/pyproject.toml \
        backend/tests/conftest.py backend/tests/test_auth.py
git commit -m "feat(backend): add dev JWT auth and current-user dependency"
```

---

### Task 5: Storage abstraction

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/storage.py`
- Create: `backend/tests/test_storage.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `app.services.storage.Storage` — a `Protocol` with `save(data: BinaryIO, key: str) -> str`, `open(ref: str) -> BinaryIO`, `path_for(ref: str) -> Path`, `delete(ref: str) -> None`.
  - `app.services.storage.LocalFilesystemStorage(root: Path)` implementing it.
  - `save` returns an opaque **ref** string; every caller stores the ref in `Attempt.original_video_ref` and passes it back to `open`/`delete`. Nothing outside this module may assume the ref is a filesystem path.
  - `delete` is idempotent — deleting a missing ref is a no-op, which the erasure contract (Task 12) relies on.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_storage.py`:

```python
import io

import pytest

from app.services.storage import LocalFilesystemStorage


@pytest.fixture
def storage(tmp_path):
    return LocalFilesystemStorage(root=tmp_path)


def test_saves_and_reads_back(storage):
    ref = storage.save(io.BytesIO(b"video-bytes"), key="abc.mp4")

    with storage.open(ref) as handle:
        assert handle.read() == b"video-bytes"


def test_two_saves_with_the_same_key_do_not_collide(storage):
    first = storage.save(io.BytesIO(b"one"), key="same.mp4")
    second = storage.save(io.BytesIO(b"two"), key="same.mp4")

    assert first != second
    with storage.open(first) as handle:
        assert handle.read() == b"one"
    with storage.open(second) as handle:
        assert handle.read() == b"two"


def test_delete_removes_the_file(storage):
    ref = storage.save(io.BytesIO(b"bye"), key="gone.mp4")

    storage.delete(ref)

    with pytest.raises(FileNotFoundError):
        storage.open(ref)


def test_delete_is_idempotent(storage):
    ref = storage.save(io.BytesIO(b"bye"), key="gone.mp4")
    storage.delete(ref)

    storage.delete(ref)  # must not raise


def test_refs_cannot_escape_the_storage_root(storage):
    with pytest.raises(ValueError):
        storage.open("../../etc/passwd")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_storage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services'`.

- [ ] **Step 3: Write the implementation**

Create `backend/app/services/__init__.py` (empty file) and `backend/app/services/storage.py`:

```python
import shutil
import uuid
from pathlib import Path
from typing import BinaryIO, Protocol


class Storage(Protocol):
    """Where original uploaded videos live.

    `save` returns an opaque ref. Callers persist the ref and hand it back to
    `open`, `path_for`, and `delete`; they must never interpret its contents.
    Swapping in S3/MinIO later means writing a second implementation of this
    protocol and changing nothing else.
    """

    def save(self, data: BinaryIO, key: str) -> str: ...

    def open(self, ref: str) -> BinaryIO: ...

    def path_for(self, ref: str) -> Path: ...

    def delete(self, ref: str) -> None: ...


class LocalFilesystemStorage:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, ref: str) -> Path:
        candidate = (self.root / ref).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError(f"ref escapes the storage root: {ref!r}")
        return candidate

    def save(self, data: BinaryIO, key: str) -> str:
        ref = f"{uuid.uuid4().hex}-{Path(key).name}"
        destination = self._resolve(ref)
        with destination.open("wb") as out:
            shutil.copyfileobj(data, out)
        return ref

    def open(self, ref: str) -> BinaryIO:
        return self._resolve(ref).open("rb")

    def path_for(self, ref: str) -> Path:
        return self._resolve(ref)

    def delete(self, ref: str) -> None:
        self._resolve(ref).unlink(missing_ok=True)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_storage.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services backend/tests/test_storage.py
git commit -m "feat(backend): add storage protocol and local filesystem implementation"
```

---

### Task 6: Upload validation

Enforces the four HTTP-400 codes from spec §6c before any job is created.

**Files:**
- Create: `backend/app/services/validation.py`
- Create: `backend/tests/fixtures/__init__.py`
- Create: `backend/tests/fixtures/squat.mp4` (copied from Alejandro's branch)
- Create: `backend/tests/test_validation.py`

**Interfaces:**
- Consumes: `Settings`, `UploadErrorCode`, `ExerciseType`.
- Produces:
  - `app.services.validation.VideoInfo(duration_sec: float, container: str, video_codec: str)`
  - `app.services.validation.probe_video(path: Path) -> VideoInfo`, raising `UploadValidationError(UploadErrorCode.UNSUPPORTED_FORMAT)` on anything unreadable.
  - `app.services.validation.UploadValidationError(Exception)` with a `.code: UploadErrorCode`.
  - `app.services.validation.validate_upload(path: Path, filename: str, exercise_type: str, size_bytes: int, settings: Settings) -> ExerciseType` — returns the parsed exercise type or raises.

- [ ] **Step 1: Get the test fixture video**

The squat clip on Alejandro's branch is a real, small (~470 KB) MP4 — exactly the fixture this needs.

```bash
mkdir -p backend/tests/fixtures
git show origin/cv-pipeline:squat.mp4 > backend/tests/fixtures/squat.mp4
```

On PowerShell: `git show origin/cv-pipeline:squat.mp4 | Set-Content backend/tests/fixtures/squat.mp4 -Encoding Byte` (or use the Bash tool, which handles the redirect correctly).

Verify it is a real video:

```bash
uv run python -c "import av; c=av.open('tests/fixtures/squat.mp4'); print(c.format.name, float(c.duration)/1e6)"
```

Expected: a format name containing `mp4` and a positive duration.

- [ ] **Step 2: Write the failing test**

Create `backend/tests/fixtures/__init__.py` (empty file) and `backend/tests/test_validation.py`:

```python
from pathlib import Path

import pytest

from app.config import Settings
from app.schemas.contract import ExerciseType, UploadErrorCode
from app.services.validation import UploadValidationError, probe_video, validate_upload

FIXTURES = Path(__file__).parent / "fixtures"
SQUAT = FIXTURES / "squat.mp4"


@pytest.fixture
def limits() -> Settings:
    return Settings(max_upload_bytes=104_857_600, max_duration_sec=60)


def test_probes_a_real_mp4():
    info = probe_video(SQUAT)

    assert "mp4" in info.container
    assert info.duration_sec > 0


def test_accepts_a_valid_squat_upload(limits):
    exercise = validate_upload(
        SQUAT, "squat.mp4", "squat", size_bytes=SQUAT.stat().st_size, settings=limits
    )

    assert exercise is ExerciseType.SQUAT


def test_rejects_an_unknown_exercise_type(limits):
    with pytest.raises(UploadValidationError) as excinfo:
        validate_upload(
            SQUAT, "squat.mp4", "backflip", size_bytes=SQUAT.stat().st_size, settings=limits
        )

    assert excinfo.value.code is UploadErrorCode.UNKNOWN_EXERCISE_TYPE


def test_rejects_an_unsupported_extension(limits):
    with pytest.raises(UploadValidationError) as excinfo:
        validate_upload(SQUAT, "clip.avi", "squat", size_bytes=1000, settings=limits)

    assert excinfo.value.code is UploadErrorCode.UNSUPPORTED_FORMAT


def test_rejects_a_file_that_is_not_a_video(tmp_path, limits):
    fake = tmp_path / "fake.mp4"
    fake.write_bytes(b"this is definitely not a video")

    with pytest.raises(UploadValidationError) as excinfo:
        validate_upload(fake, "fake.mp4", "squat", size_bytes=fake.stat().st_size, settings=limits)

    assert excinfo.value.code is UploadErrorCode.UNSUPPORTED_FORMAT


def test_rejects_an_oversized_file(limits):
    small_limit = limits.model_copy(update={"max_upload_bytes": 100})

    with pytest.raises(UploadValidationError) as excinfo:
        validate_upload(SQUAT, "squat.mp4", "squat", size_bytes=5000, settings=small_limit)

    assert excinfo.value.code is UploadErrorCode.FILE_TOO_LARGE


def test_rejects_a_too_long_video(limits):
    short_limit = limits.model_copy(update={"max_duration_sec": 1})

    with pytest.raises(UploadValidationError) as excinfo:
        validate_upload(
            SQUAT, "squat.mp4", "squat", size_bytes=SQUAT.stat().st_size, settings=short_limit
        )

    assert excinfo.value.code is UploadErrorCode.VIDEO_TOO_LONG


def test_size_is_checked_before_the_expensive_probe(limits, tmp_path):
    """An oversized file must be rejected without decoding it."""
    junk = tmp_path / "huge.mp4"
    junk.write_bytes(b"not a video at all")
    small_limit = limits.model_copy(update={"max_upload_bytes": 5})

    with pytest.raises(UploadValidationError) as excinfo:
        validate_upload(junk, "huge.mp4", "squat", size_bytes=1000, settings=small_limit)

    assert excinfo.value.code is UploadErrorCode.FILE_TOO_LARGE
```

The last test matters: if probing ran first, an unreadable oversized file would report `unsupported_format` instead of `file_too_large` and the user would get useless advice.

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/test_validation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.validation'`.

- [ ] **Step 4: Write the implementation**

Create `backend/app/services/validation.py`:

```python
from dataclasses import dataclass
from pathlib import Path

import av

from app.config import Settings
from app.schemas.contract import ExerciseType, UploadErrorCode

ALLOWED_EXTENSIONS = {".mp4", ".mov"}


class UploadValidationError(Exception):
    """Rejected before a CV job is created. Maps to HTTP 400 (spec §6c)."""

    def __init__(self, code: UploadErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class VideoInfo:
    duration_sec: float
    container: str
    video_codec: str


def probe_video(path: Path) -> VideoInfo:
    try:
        with av.open(str(path)) as container:
            streams = container.streams.video
            if not streams:
                raise UploadValidationError(
                    UploadErrorCode.UNSUPPORTED_FORMAT, "file contains no video stream"
                )
            duration = float(container.duration) / 1_000_000 if container.duration else 0.0
            return VideoInfo(
                duration_sec=duration,
                container=container.format.name,
                video_codec=streams[0].codec_context.name,
            )
    except UploadValidationError:
        raise
    except Exception as exc:
        raise UploadValidationError(
            UploadErrorCode.UNSUPPORTED_FORMAT, f"could not decode the video: {exc}"
        ) from exc


def validate_upload(
    path: Path,
    filename: str,
    exercise_type: str,
    size_bytes: int,
    settings: Settings,
) -> ExerciseType:
    """Checks run cheapest-first so the reported code is the most useful one."""
    try:
        exercise = ExerciseType(exercise_type)
    except ValueError:
        raise UploadValidationError(
            UploadErrorCode.UNKNOWN_EXERCISE_TYPE, f"unknown exercise type {exercise_type!r}"
        ) from None

    if size_bytes > settings.max_upload_bytes:
        raise UploadValidationError(
            UploadErrorCode.FILE_TOO_LARGE,
            f"{size_bytes} bytes exceeds the {settings.max_upload_bytes} byte limit",
        )

    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise UploadValidationError(
            UploadErrorCode.UNSUPPORTED_FORMAT, "only MP4 and MOV uploads are accepted"
        )

    info = probe_video(path)
    if info.duration_sec > settings.max_duration_sec:
        raise UploadValidationError(
            UploadErrorCode.VIDEO_TOO_LONG,
            f"{info.duration_sec:.1f}s exceeds the {settings.max_duration_sec}s limit",
        )

    return exercise
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/test_validation.py -v`
Expected: 8 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/validation.py backend/tests/fixtures backend/tests/test_validation.py
git commit -m "feat(backend): validate uploads against the spec limits"
```

---

### Task 7: Webhook HMAC signing and verification

**Files:**
- Create: `backend/app/security/signing.py`
- Create: `backend/tests/test_signing.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `app.security.signing.sign_payload(body: bytes, timestamp: str, secret: str) -> str` — hex HMAC-SHA256 over `f"{timestamp}.".encode() + body`.
  - `app.security.signing.verify_signature(body: bytes, timestamp: str, signature: str, secret: str, tolerance_sec: int) -> None` — returns `None` or raises `SignatureError`.
  - `app.security.signing.SignatureError(Exception)`.
  - Task 11 (webhook receiver) and Task 14 (fake CV service) both use these, which is what guarantees they agree.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_signing.py`:

```python
import time

import pytest

from app.security.signing import SignatureError, sign_payload, verify_signature

SECRET = "shared-webhook-secret"
BODY = b'{"status":"completed"}'


def _now() -> str:
    return str(int(time.time()))


def test_accepts_a_correctly_signed_payload():
    timestamp = _now()
    signature = sign_payload(BODY, timestamp, SECRET)

    verify_signature(BODY, timestamp, signature, SECRET, tolerance_sec=300)


def test_rejects_a_tampered_body():
    timestamp = _now()
    signature = sign_payload(BODY, timestamp, SECRET)

    with pytest.raises(SignatureError):
        verify_signature(b'{"status":"failed"}', timestamp, signature, SECRET, tolerance_sec=300)


def test_rejects_the_wrong_secret():
    timestamp = _now()
    signature = sign_payload(BODY, timestamp, "some-other-secret")

    with pytest.raises(SignatureError):
        verify_signature(BODY, timestamp, signature, SECRET, tolerance_sec=300)


def test_rejects_a_replayed_old_timestamp():
    old = str(int(time.time()) - 3600)
    signature = sign_payload(BODY, old, SECRET)

    with pytest.raises(SignatureError):
        verify_signature(BODY, old, signature, SECRET, tolerance_sec=300)


def test_rejects_a_timestamp_from_the_future():
    future = str(int(time.time()) + 3600)
    signature = sign_payload(BODY, future, SECRET)

    with pytest.raises(SignatureError):
        verify_signature(BODY, future, signature, SECRET, tolerance_sec=300)


def test_rejects_a_non_numeric_timestamp():
    signature = sign_payload(BODY, "yesterday", SECRET)

    with pytest.raises(SignatureError):
        verify_signature(BODY, "yesterday", signature, SECRET, tolerance_sec=300)


def test_signature_binds_the_timestamp_to_the_body():
    """Reusing a valid signature under a fresher timestamp must fail."""
    old = str(int(time.time()) - 1000)
    signature = sign_payload(BODY, old, SECRET)

    with pytest.raises(SignatureError):
        verify_signature(BODY, _now(), signature, SECRET, tolerance_sec=300)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_signing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.security.signing'`.

- [ ] **Step 3: Write the implementation**

Create `backend/app/security/signing.py`:

```python
"""HMAC signing for the CV -> backend webhook (spec §4, §8).

The timestamp is part of the signed material, so a captured signature cannot be
replayed under a fresh timestamp.
"""

import hashlib
import hmac
import time


class SignatureError(Exception):
    """The webhook signature was absent, wrong, or too old to trust."""


def sign_payload(body: bytes, timestamp: str, secret: str) -> str:
    message = f"{timestamp}.".encode() + body
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_signature(
    body: bytes,
    timestamp: str,
    signature: str,
    secret: str,
    tolerance_sec: int,
) -> None:
    try:
        sent_at = int(timestamp)
    except (TypeError, ValueError):
        raise SignatureError("timestamp is not an integer") from None

    if abs(int(time.time()) - sent_at) > tolerance_sec:
        raise SignatureError("timestamp outside the tolerance window")

    expected = sign_payload(body, timestamp, secret)
    if not hmac.compare_digest(expected, signature or ""):
        raise SignatureError("signature mismatch")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_signing.py -v`
Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/security/signing.py backend/tests/test_signing.py
git commit -m "feat(backend): add HMAC signing and replay-safe verification for webhooks"
```

---

### Task 8: CV service client

The internal boundary, spec §4.

**Files:**
- Create: `backend/app/services/cv_client.py`
- Create: `backend/tests/test_cv_client.py`
- Modify: `backend/app/api/deps.py` (add `get_cv_client`, `get_storage`)

**Interfaces:**
- Consumes: `JobAccepted`, `JobStatus`, `Settings`.
- Produces:
  - `app.services.cv_client.CVClient(base_url: str, api_key: str, http: httpx.AsyncClient)`
  - `await client.submit_job(video: BinaryIO, filename: str, exercise_type: str, callback_url: str) -> JobAccepted`
  - `await client.get_job(job_id: str) -> JobStatus`
  - `await client.delete_job(job_id: str) -> None` — idempotent, tolerates 404
  - `app.services.cv_client.CVServiceError(Exception)` with `.status_code: int | None`
  - `app.api.deps.get_cv_client` and `app.api.deps.get_storage` FastAPI dependencies.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_cv_client.py`:

```python
import io

import httpx
import pytest
import respx

from app.schemas.contract import AttemptStatus, FailureCode
from app.services.cv_client import CVClient, CVServiceError

BASE = "http://cv.test"
API_KEY = "secret-api-key"

RESULT = {
    "exercise_type": "squat",
    "overall_score": 82,
    "summary": "Good depth.",
    "rep_count": 1,
    "reps": [
        {
            "rep_index": 1,
            "start_time_sec": 0.0,
            "end_time_sec": 2.0,
            "min_knee_angle_deg": 78,
            "score": 90,
            "errors": [],
        }
    ],
    "annotated_video_url": "https://cv-storage/x/annotated.mp4",
    "algorithm_version": "squat-rules-v1",
}


@pytest.fixture
async def cv_client():
    async with httpx.AsyncClient() as http:
        yield CVClient(base_url=BASE, api_key=API_KEY, http=http)


@respx.mock
async def test_submit_job_posts_multipart_with_the_api_key(cv_client):
    route = respx.post(f"{BASE}/v1/jobs").mock(
        return_value=httpx.Response(202, json={"job_id": "job-1", "status": "queued"})
    )

    accepted = await cv_client.submit_job(
        video=io.BytesIO(b"bytes"),
        filename="squat.mp4",
        exercise_type="squat",
        callback_url="http://backend/v1/cv-callback/xyz",
    )

    assert accepted.job_id == "job-1"
    assert accepted.status is AttemptStatus.QUEUED
    request = route.calls.last.request
    assert request.headers["X-API-Key"] == API_KEY
    body = request.content
    assert b"squat.mp4" in body
    assert b"http://backend/v1/cv-callback/xyz" in body


@respx.mock
async def test_submit_job_raises_on_a_server_error(cv_client):
    respx.post(f"{BASE}/v1/jobs").mock(return_value=httpx.Response(503, text="down"))

    with pytest.raises(CVServiceError) as excinfo:
        await cv_client.submit_job(
            video=io.BytesIO(b"bytes"),
            filename="squat.mp4",
            exercise_type="squat",
            callback_url="http://backend/cb",
        )

    assert excinfo.value.status_code == 503


@respx.mock
async def test_submit_job_raises_when_the_service_is_unreachable(cv_client):
    respx.post(f"{BASE}/v1/jobs").mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(CVServiceError):
        await cv_client.submit_job(
            video=io.BytesIO(b"bytes"),
            filename="squat.mp4",
            exercise_type="squat",
            callback_url="http://backend/cb",
        )


@respx.mock
async def test_get_job_parses_a_completed_result(cv_client):
    respx.get(f"{BASE}/v1/jobs/job-1").mock(
        return_value=httpx.Response(200, json={"status": "completed", "result": RESULT})
    )

    status = await cv_client.get_job("job-1")

    assert status.status is AttemptStatus.COMPLETED
    assert status.result is not None
    assert status.result.overall_score == 82


@respx.mock
async def test_get_job_parses_a_failure(cv_client):
    respx.get(f"{BASE}/v1/jobs/job-2").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "failed",
                "error": {"code": "no_pose_detected", "message": "empty frame"},
            },
        )
    )

    status = await cv_client.get_job("job-2")

    assert status.status is AttemptStatus.FAILED
    assert status.error is not None
    assert status.error.code is FailureCode.NO_POSE_DETECTED


@respx.mock
async def test_delete_job_sends_delete(cv_client):
    route = respx.delete(f"{BASE}/v1/jobs/job-1").mock(return_value=httpx.Response(204))

    await cv_client.delete_job("job-1")

    assert route.called
    assert route.calls.last.request.headers["X-API-Key"] == API_KEY


@respx.mock
async def test_delete_job_tolerates_an_already_deleted_job(cv_client):
    respx.delete(f"{BASE}/v1/jobs/gone").mock(return_value=httpx.Response(404))

    await cv_client.delete_job("gone")  # must not raise


@respx.mock
async def test_delete_job_raises_on_a_server_error(cv_client):
    respx.delete(f"{BASE}/v1/jobs/job-1").mock(return_value=httpx.Response(500))

    with pytest.raises(CVServiceError):
        await cv_client.delete_job("job-1")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_cv_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.cv_client'`.

- [ ] **Step 3: Write the implementation**

Create `backend/app/services/cv_client.py`:

```python
"""Client for the internal boundary: backend -> CV service (spec §4)."""

from typing import BinaryIO

import httpx

from app.schemas.contract import JobAccepted, JobStatus

TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=120.0, pool=5.0)


class CVServiceError(Exception):
    """The CV service was unreachable or answered with an unexpected status."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CVClient:
    def __init__(self, base_url: str, api_key: str, http: httpx.AsyncClient) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.http = http

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key}

    async def submit_job(
        self,
        video: BinaryIO,
        filename: str,
        exercise_type: str,
        callback_url: str,
    ) -> JobAccepted:
        try:
            response = await self.http.post(
                f"{self.base_url}/v1/jobs",
                headers=self._headers,
                files={"video": (filename, video, "video/mp4")},
                data={"exercise_type": exercise_type, "callback_url": callback_url},
                timeout=TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise CVServiceError(f"could not reach the CV service: {exc}") from exc

        if response.status_code not in (200, 201, 202):
            raise CVServiceError(
                f"CV service rejected the job: {response.text}", response.status_code
            )
        return JobAccepted.model_validate(response.json())

    async def get_job(self, job_id: str) -> JobStatus:
        try:
            response = await self.http.get(
                f"{self.base_url}/v1/jobs/{job_id}", headers=self._headers, timeout=TIMEOUT
            )
        except httpx.HTTPError as exc:
            raise CVServiceError(f"could not reach the CV service: {exc}") from exc

        if response.status_code != 200:
            raise CVServiceError(
                f"unexpected status for job {job_id}: {response.text}", response.status_code
            )
        return JobStatus.model_validate(response.json())

    async def delete_job(self, job_id: str) -> None:
        """Idempotent (spec §4): an already-deleted job is a success."""
        try:
            response = await self.http.delete(
                f"{self.base_url}/v1/jobs/{job_id}", headers=self._headers, timeout=TIMEOUT
            )
        except httpx.HTTPError as exc:
            raise CVServiceError(f"could not reach the CV service: {exc}") from exc

        if response.status_code not in (200, 202, 204, 404):
            raise CVServiceError(
                f"unexpected status deleting job {job_id}: {response.text}", response.status_code
            )
```

- [ ] **Step 4: Add the dependencies**

Add `import httpx` to the import block at the top of `backend/app/api/deps.py`, then append to the file (`AsyncIterator`, `Annotated`, and `Depends` are already imported from Task 4):

```python
from app.services.cv_client import CVClient
from app.services.storage import LocalFilesystemStorage, Storage


def get_storage(settings: SettingsDep) -> Storage:
    return LocalFilesystemStorage(root=settings.storage_dir)


async def get_cv_client(settings: SettingsDep) -> AsyncIterator[CVClient]:
    async with httpx.AsyncClient() as http:
        yield CVClient(
            base_url=settings.cv_service_url, api_key=settings.cv_api_key, http=http
        )


StorageDep = Annotated[Storage, Depends(get_storage)]
CVClientDep = Annotated[CVClient, Depends(get_cv_client)]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_cv_client.py -v`
Expected: 8 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/cv_client.py backend/app/api/deps.py backend/tests/test_cv_client.py
git commit -m "feat(backend): add CV service client for the internal boundary"
```

---

### Task 9: Create an attempt (POST /v1/attempts)

**Files:**
- Create: `backend/app/services/attempts.py`
- Create: `backend/app/schemas/attempt.py`
- Create: `backend/app/api/attempts.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_create_attempt.py`
- Modify: `backend/tests/conftest.py` (add the `isolated_storage` fixture)

**Interfaces:**
- Consumes: `Storage`, `CVClient`, `validate_upload`, `UploadValidationError`, `Attempt`, `CurrentUser`.
- Produces:
  - `app.services.attempts.create_attempt(db, user, video_path, filename, exercise_type, size_bytes, storage, cv_client, settings) -> Attempt`
  - `app.services.attempts.callback_url_for(attempt_id, settings) -> str`
  - `app.schemas.attempt.AttemptCreated`, `AttemptDetail`, `AttemptSummary`, `AttemptPage` (the latter three are consumed in Task 10).
  - `app.api.attempts.router` — mounted at `/v1/attempts`.
  - conftest fixture `isolated_storage` — an autouse `LocalFilesystemStorage` rooted in `tmp_path`, overriding `get_storage`. Tasks 12 and 13 use it to assert on stored files.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_create_attempt.py`:

```python
import uuid
from pathlib import Path

import httpx
import respx
import sqlalchemy as sa

from app.models import Attempt
from app.schemas.contract import AttemptStatus, UploadErrorCode

SQUAT = Path(__file__).parent / "fixtures" / "squat.mp4"


def _upload(filename: str = "squat.mp4", exercise: str = "squat", content: bytes | None = None):
    data = content if content is not None else SQUAT.read_bytes()
    return {"files": {"video": (filename, data, "video/mp4")}, "data": {"exercise_type": exercise}}


@respx.mock
async def test_creates_a_queued_attempt_and_submits_it_to_the_cv_service(
    client, auth_headers, session, user, settings
):
    route = respx.post(f"{settings.cv_service_url}/v1/jobs").mock(
        return_value=httpx.Response(202, json={"job_id": "job-42", "status": "queued"})
    )

    response = await client.post("/v1/attempts", headers=auth_headers, **_upload())

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"

    attempt = await session.get(Attempt, uuid.UUID(body["attempt_id"]))
    assert attempt is not None
    assert attempt.user_id == user.id
    assert attempt.exercise_type == "squat"
    assert attempt.status == AttemptStatus.QUEUED
    assert attempt.cv_job_id == "job-42"
    assert attempt.original_video_ref
    assert route.called


@respx.mock
async def test_records_consent_and_a_thirty_day_expiry(client, auth_headers, session, settings):
    respx.post(f"{settings.cv_service_url}/v1/jobs").mock(
        return_value=httpx.Response(202, json={"job_id": "job-43", "status": "queued"})
    )

    response = await client.post("/v1/attempts", headers=auth_headers, **_upload())
    attempt = await session.get(Attempt, uuid.UUID(response.json()["attempt_id"]))

    assert attempt.consent_at is not None
    retention_days = (attempt.expires_at - attempt.consent_at).days
    assert retention_days == settings.retention_days


@respx.mock
async def test_sends_a_callback_url_pointing_back_at_this_attempt(
    client, auth_headers, settings
):
    route = respx.post(f"{settings.cv_service_url}/v1/jobs").mock(
        return_value=httpx.Response(202, json={"job_id": "job-44", "status": "queued"})
    )

    response = await client.post("/v1/attempts", headers=auth_headers, **_upload())
    attempt_id = response.json()["attempt_id"]

    assert f"/v1/cv-callback/{attempt_id}".encode() in route.calls.last.request.content


async def test_requires_authentication(client):
    response = await client.post("/v1/attempts", **_upload())

    assert response.status_code == 401


async def test_rejects_an_unknown_exercise_type(client, auth_headers):
    response = await client.post(
        "/v1/attempts", headers=auth_headers, **_upload(exercise="backflip")
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == UploadErrorCode.UNKNOWN_EXERCISE_TYPE


async def test_rejects_an_unsupported_format(client, auth_headers):
    response = await client.post(
        "/v1/attempts", headers=auth_headers, **_upload(filename="clip.avi")
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == UploadErrorCode.UNSUPPORTED_FORMAT


async def test_rejects_a_file_that_is_not_a_video(client, auth_headers):
    response = await client.post(
        "/v1/attempts", headers=auth_headers, **_upload(content=b"nope")
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == UploadErrorCode.UNSUPPORTED_FORMAT


@respx.mock
async def test_no_attempt_row_survives_a_rejected_upload(client, auth_headers, session):
    before = await session.scalar(sa.select(sa.func.count()).select_from(Attempt))

    await client.post("/v1/attempts", headers=auth_headers, **_upload(exercise="backflip"))

    after = await session.scalar(sa.select(sa.func.count()).select_from(Attempt))
    assert after == before


@respx.mock
async def test_returns_502_and_stores_no_attempt_when_the_cv_service_is_down(
    client, auth_headers, session, settings
):
    respx.post(f"{settings.cv_service_url}/v1/jobs").mock(
        return_value=httpx.Response(503, text="down")
    )
    before = await session.scalar(sa.select(sa.func.count()).select_from(Attempt))

    response = await client.post("/v1/attempts", headers=auth_headers, **_upload())

    assert response.status_code == 502
    after = await session.scalar(sa.select(sa.func.count()).select_from(Attempt))
    assert after == before
```

- [ ] **Step 2: Point storage at a temp directory during tests**

Append to `backend/tests/conftest.py`:

```python
@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    """Keep uploaded test videos out of the developer's real storage directory."""
    from app.api.deps import get_storage
    from app.services.storage import LocalFilesystemStorage

    storage = LocalFilesystemStorage(root=tmp_path / "videos")
    fastapi_app.dependency_overrides[get_storage] = lambda: storage
    yield storage
    fastapi_app.dependency_overrides.pop(get_storage, None)
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/test_create_attempt.py -v`
Expected: FAIL — every test 404s, because `/v1/attempts` does not exist.

- [ ] **Step 4: Write the public response schemas**

Create `backend/app/schemas/attempt.py`:

```python
"""Public-boundary response shapes (spec §3)."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.contract import AnalysisResult, AttemptStatus, ErrorPayload


class AttemptCreated(BaseModel):
    attempt_id: uuid.UUID
    status: AttemptStatus


class AttemptDetail(BaseModel):
    attempt_id: uuid.UUID
    exercise_type: str
    status: AttemptStatus
    created_at: datetime
    completed_at: datetime | None = None
    result: AnalysisResult | None = None
    error: ErrorPayload | None = None


class AttemptSummary(BaseModel):
    """The light shape the progress view lists."""

    attempt_id: uuid.UUID
    exercise_type: str
    status: AttemptStatus
    overall_score: int | None = None
    created_at: datetime


class AttemptPage(BaseModel):
    items: list[AttemptSummary]
    next_cursor: str | None = None
```

- [ ] **Step 5: Write the orchestration service**

Create `backend/app/services/attempts.py`:

```python
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Attempt, User
from app.schemas.contract import AttemptStatus
from app.services.cv_client import CVClient
from app.services.storage import Storage
from app.services.validation import validate_upload


def callback_url_for(attempt_id: uuid.UUID, settings: Settings) -> str:
    return f"{settings.backend_public_url.rstrip('/')}/v1/cv-callback/{attempt_id}"


async def create_attempt(
    db: AsyncSession,
    user: User,
    video_path: Path,
    filename: str,
    exercise_type: str,
    size_bytes: int,
    storage: Storage,
    cv_client: CVClient,
    settings: Settings,
) -> Attempt:
    """Validate, store, submit, persist.

    Raises UploadValidationError (-> 400) or CVServiceError (-> 502). Nothing is
    persisted unless the CV service accepted the job, so a failed submission never
    leaves an orphan row for the reconciler to chew on.
    """
    exercise = validate_upload(video_path, filename, exercise_type, size_bytes, settings)

    with video_path.open("rb") as handle:
        video_ref = storage.save(handle, key=filename)

    attempt_id = uuid.uuid4()
    try:
        with storage.open(video_ref) as handle:
            accepted = await cv_client.submit_job(
                video=handle,
                filename=filename,
                exercise_type=exercise.value,
                callback_url=callback_url_for(attempt_id, settings),
            )
    except Exception:
        storage.delete(video_ref)
        raise

    now = datetime.now(UTC)
    attempt = Attempt(
        id=attempt_id,
        user_id=user.id,
        exercise_type=exercise.value,
        status=AttemptStatus.QUEUED.value,
        cv_job_id=accepted.job_id,
        original_video_ref=video_ref,
        created_at=now,
        expires_at=now + timedelta(days=settings.retention_days),
        consent_at=now,
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return attempt
```

- [ ] **Step 6: Write the router**

Create `backend/app/api/attempts.py`:

```python
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from app.api.deps import CVClientDep, CurrentUser, DbDep, SettingsDep, StorageDep
from app.schemas.attempt import AttemptCreated
from app.schemas.contract import AttemptStatus
from app.services.attempts import create_attempt
from app.services.cv_client import CVServiceError
from app.services.validation import UploadValidationError

router = APIRouter(prefix="/v1/attempts", tags=["attempts"])


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=AttemptCreated)
async def create(
    user: CurrentUser,
    db: DbDep,
    storage: StorageDep,
    cv_client: CVClientDep,
    settings: SettingsDep,
    video: UploadFile = File(...),
    exercise_type: str = Form(...),
):
    """Spool to a temp file first: validation needs to seek, and a stream cannot."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(video.filename or "").suffix) as tmp:
        temp_path = Path(tmp.name)
        size_bytes = 0
        while chunk := await video.read(1024 * 1024):
            size_bytes += len(chunk)
            tmp.write(chunk)

    try:
        attempt = await create_attempt(
            db=db,
            user=user,
            video_path=temp_path,
            filename=video.filename or "upload.mp4",
            exercise_type=exercise_type,
            size_bytes=size_bytes,
            storage=storage,
            cv_client=cv_client,
            settings=settings,
        )
    except UploadValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"code": exc.code.value, "message": exc.message}},
        )
    except CVServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"the analysis service is unavailable: {exc}",
        ) from exc
    finally:
        temp_path.unlink(missing_ok=True)

    return AttemptCreated(attempt_id=attempt.id, status=AttemptStatus(attempt.status))
```

- [ ] **Step 7: Wire the router into the app**

In `backend/app/main.py`, add the import and the include:

```python
from app.api import attempts, auth_dev

app.include_router(auth_dev.router)
app.include_router(attempts.router)
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `uv run pytest tests/test_create_attempt.py -v`
Expected: 9 PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/attempts.py backend/app/schemas/attempt.py \
        backend/app/api/attempts.py backend/app/main.py \
        backend/tests/conftest.py backend/tests/test_create_attempt.py
git commit -m "feat(backend): add POST /v1/attempts upload and CV job submission"
```

---

### Task 10: Read attempts (GET detail and paginated history)

**Files:**
- Modify: `backend/app/api/attempts.py`
- Create: `backend/tests/test_read_attempts.py`
- Modify: `backend/tests/conftest.py` (add the `make_attempt` factory)
- Modify: `backend/tests/test_auth.py` (remove the two `xfail` markers)

**Interfaces:**
- Consumes: `AttemptDetail`, `AttemptSummary`, `AttemptPage`, `CurrentUser`.
- Produces:
  - `GET /v1/attempts/{id}` → `AttemptDetail`, 404 for a stranger's attempt.
  - `GET /v1/attempts?limit=&cursor=` → `AttemptPage`, newest first, cursor = the ISO timestamp of the last item.
  - conftest factory fixture `make_attempt(user, **overrides) -> Attempt`, used by Tasks 10–13.

- [ ] **Step 1: Add the attempt factory fixture**

Append to `backend/tests/conftest.py`:

```python
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

    record = User(id=uuid.uuid4(), email=f"{uuid.uuid4().hex}@example.com")
    session.add(record)
    await session.flush()
    return record
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_read_attempts.py`:

```python
import uuid
from datetime import UTC, datetime, timedelta

RESULT = {
    "exercise_type": "squat",
    "overall_score": 82,
    "summary": "Good depth.",
    "rep_count": 1,
    "reps": [
        {
            "rep_index": 1,
            "start_time_sec": 0.0,
            "end_time_sec": 2.0,
            "min_knee_angle_deg": 78,
            "score": 90,
            "errors": [],
        }
    ],
    "annotated_video_url": "https://cv-storage/x/annotated.mp4",
    "algorithm_version": "squat-rules-v1",
}


async def test_returns_a_queued_attempt_with_no_result(client, auth_headers, user, make_attempt):
    attempt = await make_attempt(user)

    response = await client.get(f"/v1/attempts/{attempt.id}", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert body["result"] is None
    assert body["error"] is None
    assert body["completed_at"] is None


async def test_returns_the_result_of_a_completed_attempt(
    client, auth_headers, user, make_attempt
):
    attempt = await make_attempt(
        user,
        status="completed",
        result=RESULT,
        overall_score=82,
        annotated_video_url=RESULT["annotated_video_url"],
        completed_at=datetime.now(UTC),
    )

    response = await client.get(f"/v1/attempts/{attempt.id}", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["overall_score"] == 82
    assert body["result"]["reps"][0]["rep_index"] == 1
    assert body["completed_at"] is not None


async def test_returns_the_error_of_a_failed_attempt(client, auth_headers, user, make_attempt):
    attempt = await make_attempt(
        user, status="failed", error_code="no_pose_detected", completed_at=datetime.now(UTC)
    )

    response = await client.get(f"/v1/attempts/{attempt.id}", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error"]["code"] == "no_pose_detected"
    assert body["result"] is None


async def test_hides_another_users_attempt(client, auth_headers, other_user, make_attempt):
    attempt = await make_attempt(other_user)

    response = await client.get(f"/v1/attempts/{attempt.id}", headers=auth_headers)

    assert response.status_code == 404


async def test_returns_404_for_an_unknown_id(client, auth_headers):
    response = await client.get(f"/v1/attempts/{uuid.uuid4()}", headers=auth_headers)

    assert response.status_code == 404


async def test_history_lists_only_the_callers_attempts_newest_first(
    client, auth_headers, user, other_user, make_attempt
):
    base = datetime.now(UTC)
    await make_attempt(user, created_at=base - timedelta(hours=2), overall_score=50)
    newest = await make_attempt(user, created_at=base, overall_score=90)
    await make_attempt(other_user, created_at=base - timedelta(hours=1))

    response = await client.get("/v1/attempts", headers=auth_headers)

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert items[0]["attempt_id"] == str(newest.id)
    assert items[0]["overall_score"] == 90


async def test_history_paginates_with_a_cursor(client, auth_headers, user, make_attempt):
    base = datetime.now(UTC)
    for offset in range(5):
        await make_attempt(user, created_at=base - timedelta(minutes=offset))

    first = await client.get("/v1/attempts?limit=2", headers=auth_headers)
    first_body = first.json()
    assert len(first_body["items"]) == 2
    assert first_body["next_cursor"]

    second = await client.get(
        f"/v1/attempts?limit=2&cursor={first_body['next_cursor']}", headers=auth_headers
    )
    second_body = second.json()

    assert len(second_body["items"]) == 2
    first_ids = {item["attempt_id"] for item in first_body["items"]}
    second_ids = {item["attempt_id"] for item in second_body["items"]}
    assert first_ids.isdisjoint(second_ids)


async def test_history_reports_no_cursor_on_the_last_page(client, auth_headers, user, make_attempt):
    await make_attempt(user)

    response = await client.get("/v1/attempts?limit=10", headers=auth_headers)

    assert response.json()["next_cursor"] is None


async def test_history_requires_authentication(client):
    response = await client.get("/v1/attempts")

    assert response.status_code == 401
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/test_read_attempts.py -v`
Expected: FAIL — 405/404 on both routes, which do not exist yet.

- [ ] **Step 4: Write the read endpoints**

Append to `backend/app/api/attempts.py` (and extend the imports at the top of the file):

```python
import uuid
from datetime import datetime

import sqlalchemy as sa
from fastapi import Query

from app.models import Attempt
from app.schemas.attempt import AttemptDetail, AttemptPage, AttemptSummary
from app.schemas.contract import AnalysisResult, ErrorPayload, FailureCode


async def _load_owned_attempt(db, attempt_id: uuid.UUID, user) -> Attempt:
    """404 rather than 403 for a stranger's attempt — do not leak that it exists."""
    result = await db.execute(
        sa.select(Attempt).where(Attempt.id == attempt_id, Attempt.user_id == user.id)
    )
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="attempt not found")
    return attempt


@router.get("/{attempt_id}", response_model=AttemptDetail)
async def get_attempt(attempt_id: uuid.UUID, user: CurrentUser, db: DbDep) -> AttemptDetail:
    attempt = await _load_owned_attempt(db, attempt_id, user)

    error = None
    if attempt.error_code:
        error = ErrorPayload(
            code=FailureCode(attempt.error_code), message="see the CV service logs"
        )

    return AttemptDetail(
        attempt_id=attempt.id,
        exercise_type=attempt.exercise_type,
        status=AttemptStatus(attempt.status),
        created_at=attempt.created_at,
        completed_at=attempt.completed_at,
        result=AnalysisResult.model_validate(attempt.result) if attempt.result else None,
        error=error,
    )


@router.get("", response_model=AttemptPage)
async def list_attempts(
    user: CurrentUser,
    db: DbDep,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> AttemptPage:
    """Keyset pagination on created_at descending; the cursor is an ISO timestamp.

    Two attempts sharing an exact created_at would straddle a page boundary. Postgres
    timestamps are microsecond-precision and one user cannot upload twice in the same
    microsecond, so a compound (created_at, id) cursor is not worth the complexity yet.
    """
    query = sa.select(Attempt).where(Attempt.user_id == user.id)
    if cursor:
        try:
            query = query.where(Attempt.created_at < datetime.fromisoformat(cursor))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="malformed cursor"
            ) from None

    query = query.order_by(Attempt.created_at.desc()).limit(limit + 1)
    rows = list((await db.execute(query)).scalars())

    has_more = len(rows) > limit
    page = rows[:limit]
    return AttemptPage(
        items=[
            AttemptSummary(
                attempt_id=row.id,
                exercise_type=row.exercise_type,
                status=AttemptStatus(row.status),
                overall_score=row.overall_score,
                created_at=row.created_at,
            )
            for row in page
        ],
        next_cursor=page[-1].created_at.isoformat() if has_more and page else None,
    )
```

FastAPI matches routes in declaration order, and `/{attempt_id}` is declared before `""` — that is fine because the paths do not overlap. Keep `POST ""` first in the file for readability.

- [ ] **Step 5: Un-xfail the auth tests**

In `backend/tests/test_auth.py`, remove the `@pytest.mark.xfail(...)` decorators from `test_protected_route_rejects_a_missing_token` and `test_protected_route_rejects_a_bad_token`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_read_attempts.py tests/test_auth.py -v`
Expected: 9 + 7 PASS, no xfails.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/attempts.py backend/tests/conftest.py \
        backend/tests/test_read_attempts.py backend/tests/test_auth.py
git commit -m "feat(backend): add attempt detail and paginated history endpoints"
```

---

### Task 11: Webhook receiver

**Files:**
- Create: `backend/app/api/webhooks.py`
- Modify: `backend/app/services/attempts.py` (add `apply_job_status`)
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_webhook.py`

**Interfaces:**
- Consumes: `verify_signature`, `SignatureError`, `JobStatus`, `Attempt`.
- Produces:
  - `app.services.attempts.apply_job_status(db, attempt: Attempt, job_status: JobStatus) -> bool` — writes the result onto the attempt and commits; returns `False` (a no-op) if the attempt is already terminal. Task 13's reconciler calls the same function, which is what makes webhook and polling agree.
  - `POST /v1/cv-callback/{attempt_id}` — HMAC-verified, unauthenticated by JWT (the CV service has no user session).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_webhook.py`:

```python
import json
import time
from datetime import UTC, datetime

from app.models import Attempt
from app.security.signing import sign_payload

RESULT = {
    "exercise_type": "squat",
    "overall_score": 82,
    "summary": "Good depth.",
    "rep_count": 1,
    "reps": [
        {
            "rep_index": 1,
            "start_time_sec": 0.0,
            "end_time_sec": 2.0,
            "min_knee_angle_deg": 78,
            "score": 90,
            "errors": [],
        }
    ],
    "annotated_video_url": "https://cv-storage/x/annotated.mp4",
    "algorithm_version": "squat-rules-v1",
}

COMPLETED = {"status": "completed", "result": RESULT}
FAILED = {"status": "failed", "error": {"code": "no_pose_detected", "message": "empty frame"}}


def signed(payload: dict, secret: str, timestamp: str | None = None) -> tuple[bytes, dict]:
    body = json.dumps(payload).encode()
    stamp = timestamp or str(int(time.time()))
    return body, {
        "X-CV-Signature": sign_payload(body, stamp, secret),
        "X-CV-Timestamp": stamp,
        "Content-Type": "application/json",
    }


async def test_applies_a_completed_result(client, session, user, make_attempt, settings):
    attempt = await make_attempt(user, status="processing")
    body, headers = signed(COMPLETED, settings.cv_webhook_secret)

    response = await client.post(
        f"/v1/cv-callback/{attempt.id}", content=body, headers=headers
    )

    assert response.status_code == 204
    await session.refresh(attempt)
    assert attempt.status == "completed"
    assert attempt.overall_score == 82
    assert attempt.annotated_video_url == RESULT["annotated_video_url"]
    assert attempt.result["algorithm_version"] == "squat-rules-v1"
    assert attempt.completed_at is not None
    assert attempt.error_code is None


async def test_applies_a_failure(client, session, user, make_attempt, settings):
    attempt = await make_attempt(user, status="processing")
    body, headers = signed(FAILED, settings.cv_webhook_secret)

    response = await client.post(
        f"/v1/cv-callback/{attempt.id}", content=body, headers=headers
    )

    assert response.status_code == 204
    await session.refresh(attempt)
    assert attempt.status == "failed"
    assert attempt.error_code == "no_pose_detected"
    assert attempt.result is None
    assert attempt.completed_at is not None


async def test_rejects_a_wrong_signature(client, session, user, make_attempt, settings):
    attempt = await make_attempt(user, status="processing")
    body, headers = signed(COMPLETED, "the-wrong-secret")

    response = await client.post(
        f"/v1/cv-callback/{attempt.id}", content=body, headers=headers
    )

    assert response.status_code == 401
    await session.refresh(attempt)
    assert attempt.status == "processing"


async def test_rejects_a_missing_signature(client, user, make_attempt):
    attempt = await make_attempt(user, status="processing")

    response = await client.post(
        f"/v1/cv-callback/{attempt.id}",
        content=json.dumps(COMPLETED).encode(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 401


async def test_rejects_a_replayed_old_timestamp(client, user, make_attempt, settings):
    attempt = await make_attempt(user, status="processing")
    stale = str(int(time.time()) - 10_000)
    body, headers = signed(COMPLETED, settings.cv_webhook_secret, timestamp=stale)

    response = await client.post(
        f"/v1/cv-callback/{attempt.id}", content=body, headers=headers
    )

    assert response.status_code == 401


async def test_double_delivery_is_idempotent(client, session, user, make_attempt, settings):
    attempt = await make_attempt(user, status="processing")
    body, headers = signed(COMPLETED, settings.cv_webhook_secret)

    first = await client.post(f"/v1/cv-callback/{attempt.id}", content=body, headers=headers)
    await session.refresh(attempt)
    completed_at = attempt.completed_at

    second = await client.post(f"/v1/cv-callback/{attempt.id}", content=body, headers=headers)

    assert first.status_code == 204
    assert second.status_code == 204
    await session.refresh(attempt)
    assert attempt.completed_at == completed_at


async def test_a_late_webhook_cannot_overwrite_a_terminal_attempt(
    client, session, user, make_attempt, settings
):
    """The poller may have already written a failure; a stale webhook must not undo it."""
    attempt = await make_attempt(
        user, status="failed", error_code="worker_error", completed_at=datetime.now(UTC)
    )
    body, headers = signed(COMPLETED, settings.cv_webhook_secret)

    response = await client.post(f"/v1/cv-callback/{attempt.id}", content=body, headers=headers)

    assert response.status_code == 204
    await session.refresh(attempt)
    assert attempt.status == "failed"
    assert attempt.error_code == "worker_error"


async def test_returns_404_for_an_unknown_attempt(client, settings):
    import uuid

    body, headers = signed(COMPLETED, settings.cv_webhook_secret)

    response = await client.post(f"/v1/cv-callback/{uuid.uuid4()}", content=body, headers=headers)

    assert response.status_code == 404


async def test_rejects_a_payload_that_violates_the_contract(client, user, make_attempt, settings):
    attempt = await make_attempt(user, status="processing")
    body, headers = signed({"status": "completed", "result": None}, settings.cv_webhook_secret)

    response = await client.post(f"/v1/cv-callback/{attempt.id}", content=body, headers=headers)

    assert response.status_code == 422
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_webhook.py -v`
Expected: FAIL — 404 on every call; the route does not exist.

- [ ] **Step 3: Write the result-application service**

Append to `backend/app/services/attempts.py`:

```python
from app.schemas.contract import JobStatus


async def apply_job_status(db: AsyncSession, attempt: Attempt, job_status: JobStatus) -> bool:
    """Write a CV result onto an attempt. Returns False if it was already terminal.

    Both the webhook (Task 11) and the polling reconciler (Task 13) call this, so a
    result delivered twice — or by both paths — lands exactly once (spec §8).
    """
    if AttemptStatus(attempt.status).is_terminal:
        return False

    if job_status.status is AttemptStatus.COMPLETED and job_status.result is not None:
        attempt.status = AttemptStatus.COMPLETED.value
        attempt.result = job_status.result.model_dump(mode="json")
        attempt.overall_score = job_status.result.overall_score
        attempt.annotated_video_url = job_status.result.annotated_video_url
        attempt.error_code = None
        attempt.completed_at = datetime.now(UTC)
    elif job_status.status is AttemptStatus.FAILED and job_status.error is not None:
        attempt.status = AttemptStatus.FAILED.value
        attempt.error_code = job_status.error.code.value
        attempt.completed_at = datetime.now(UTC)
    else:
        # queued / processing — record the progress, stay non-terminal
        attempt.status = job_status.status.value

    await db.commit()
    return True
```

- [ ] **Step 4: Write the webhook router**

Create `backend/app/api/webhooks.py`:

```python
"""CV service -> backend callback (spec §4).

Not JWT-authenticated: the CV service has no user session. Trust comes entirely
from the HMAC signature, which is verified over the RAW body before parsing.
"""

import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import ValidationError

from app.api.deps import DbDep, SettingsDep
from app.models import Attempt
from app.schemas.contract import JobStatus
from app.security.signing import SignatureError, verify_signature
from app.services.attempts import apply_job_status

router = APIRouter(prefix="/v1/cv-callback", tags=["cv webhook"])


@router.post("/{attempt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def receive_result(
    attempt_id: uuid.UUID,
    request: Request,
    db: DbDep,
    settings: SettingsDep,
    x_cv_signature: str | None = Header(default=None),
    x_cv_timestamp: str | None = Header(default=None),
) -> Response:
    body = await request.body()

    try:
        verify_signature(
            body=body,
            timestamp=x_cv_timestamp or "",
            signature=x_cv_signature or "",
            secret=settings.cv_webhook_secret,
            tolerance_sec=settings.webhook_tolerance_sec,
        )
    except SignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"invalid webhook: {exc}"
        ) from exc

    try:
        job_status = JobStatus.model_validate_json(body)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()
        ) from exc

    result = await db.execute(sa.select(Attempt).where(Attempt.id == attempt_id))
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="attempt not found")

    await apply_job_status(db, attempt, job_status)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

Signature verification runs before the attempt lookup on purpose: an unauthenticated caller must not be able to probe which attempt IDs exist.

- [ ] **Step 5: Wire the router into the app**

In `backend/app/main.py`:

```python
from app.api import attempts, auth_dev, webhooks

app.include_router(auth_dev.router)
app.include_router(attempts.router)
app.include_router(webhooks.router)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_webhook.py -v`
Expected: 9 PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/webhooks.py backend/app/services/attempts.py backend/app/main.py \
        backend/tests/test_webhook.py
git commit -m "feat(backend): receive HMAC-verified CV result webhooks idempotently"
```

---

### Task 12: Erasure (DELETE /v1/attempts/{id})

Spec §7, the GDPR contract.

**Files:**
- Modify: `backend/app/services/attempts.py` (add `delete_attempt`)
- Modify: `backend/app/api/attempts.py`
- Create: `backend/tests/test_delete_attempt.py`

**Interfaces:**
- Consumes: `Storage`, `CVClient`, `Attempt`, and `_load_owned_attempt` (defined in Task 10's edit to the same router file).
- Produces:
  - `app.services.attempts.delete_attempt(db, attempt: Attempt, storage: Storage, cv_client: CVClient) -> None` — deletes the original video, then the CV-side artifacts, then the row. Task 13's purge job calls the same function.
  - `DELETE /v1/attempts/{id}` → 204; 404 for a stranger's or unknown attempt.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_delete_attempt.py`:

```python
import io
import uuid

import httpx
import respx

from app.models import Attempt


@respx.mock
async def test_deletes_the_row_the_video_and_the_cv_artifacts(
    client, auth_headers, session, user, make_attempt, isolated_storage, settings
):
    ref = isolated_storage.save(io.BytesIO(b"video"), key="orig.mp4")
    attempt = await make_attempt(
        user, status="completed", cv_job_id="job-99", original_video_ref=ref
    )
    cv_delete = respx.delete(f"{settings.cv_service_url}/v1/jobs/job-99").mock(
        return_value=httpx.Response(204)
    )

    response = await client.delete(f"/v1/attempts/{attempt.id}", headers=auth_headers)

    assert response.status_code == 204
    assert cv_delete.called
    assert await session.get(Attempt, attempt.id) is None
    try:
        isolated_storage.open(ref)
    except FileNotFoundError:
        return
    raise AssertionError("the original video should have been deleted")


@respx.mock
async def test_deleting_twice_returns_404_the_second_time(
    client, auth_headers, user, make_attempt, settings
):
    attempt = await make_attempt(user, cv_job_id="job-98")
    respx.delete(f"{settings.cv_service_url}/v1/jobs/job-98").mock(
        return_value=httpx.Response(204)
    )

    first = await client.delete(f"/v1/attempts/{attempt.id}", headers=auth_headers)
    second = await client.delete(f"/v1/attempts/{attempt.id}", headers=auth_headers)

    assert first.status_code == 204
    assert second.status_code == 404


@respx.mock
async def test_tolerates_a_cv_job_already_gone(
    client, auth_headers, session, user, make_attempt, settings
):
    attempt = await make_attempt(user, cv_job_id="job-97")
    respx.delete(f"{settings.cv_service_url}/v1/jobs/job-97").mock(
        return_value=httpx.Response(404)
    )

    response = await client.delete(f"/v1/attempts/{attempt.id}", headers=auth_headers)

    assert response.status_code == 204
    assert await session.get(Attempt, attempt.id) is None


@respx.mock
async def test_keeps_the_row_when_the_cv_service_cannot_confirm_erasure(
    client, auth_headers, session, user, make_attempt, settings
):
    """Never report erasure we could not carry out — the user must be able to retry."""
    attempt = await make_attempt(user, cv_job_id="job-96")
    respx.delete(f"{settings.cv_service_url}/v1/jobs/job-96").mock(
        return_value=httpx.Response(500)
    )

    response = await client.delete(f"/v1/attempts/{attempt.id}", headers=auth_headers)

    assert response.status_code == 502
    assert await session.get(Attempt, attempt.id) is not None


@respx.mock
async def test_deletes_an_attempt_that_never_reached_the_cv_service(
    client, auth_headers, session, user, make_attempt
):
    attempt = await make_attempt(user, cv_job_id=None)

    response = await client.delete(f"/v1/attempts/{attempt.id}", headers=auth_headers)

    assert response.status_code == 204
    assert await session.get(Attempt, attempt.id) is None


async def test_cannot_delete_another_users_attempt(
    client, auth_headers, session, other_user, make_attempt
):
    attempt = await make_attempt(other_user)

    response = await client.delete(f"/v1/attempts/{attempt.id}", headers=auth_headers)

    assert response.status_code == 404
    assert await session.get(Attempt, attempt.id) is not None


async def test_returns_404_for_an_unknown_id(client, auth_headers):
    response = await client.delete(f"/v1/attempts/{uuid.uuid4()}", headers=auth_headers)

    assert response.status_code == 404


async def test_requires_authentication(client, user, make_attempt):
    attempt = await make_attempt(user)

    response = await client.delete(f"/v1/attempts/{attempt.id}")

    assert response.status_code == 401
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_delete_attempt.py -v`
Expected: FAIL — 405 Method Not Allowed; `DELETE` is not routed.

- [ ] **Step 3: Write the erasure service**

Append to `backend/app/services/attempts.py`:

```python
async def delete_attempt(
    db: AsyncSession,
    attempt: Attempt,
    storage: Storage,
    cv_client: CVClient,
) -> None:
    """One user action, one sweep across both services (spec §7).

    The CV call comes before the row delete on purpose: if the CV service cannot
    confirm erasure, CVServiceError propagates, the row survives, and the user can
    retry. Reporting success we could not deliver would break the GDPR promise.
    """
    storage.delete(attempt.original_video_ref)

    if attempt.cv_job_id:
        await cv_client.delete_job(attempt.cv_job_id)

    await db.delete(attempt)
    await db.commit()
```

- [ ] **Step 4: Write the endpoint**

Append to `backend/app/api/attempts.py`:

```python
from app.services.attempts import delete_attempt


@router.delete("/{attempt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def erase_attempt(
    attempt_id: uuid.UUID,
    user: CurrentUser,
    db: DbDep,
    storage: StorageDep,
    cv_client: CVClientDep,
) -> Response:
    attempt = await _load_owned_attempt(db, attempt_id, user)

    try:
        await delete_attempt(db, attempt, storage, cv_client)
    except CVServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"could not confirm erasure with the analysis service: {exc}",
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

Add `Response` to the `fastapi` import line at the top of the file.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_delete_attempt.py -v`
Expected: 8 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/attempts.py backend/app/api/attempts.py \
        backend/tests/test_delete_attempt.py
git commit -m "feat(backend): implement end-to-end erasure per the GDPR contract"
```

---

### Task 13: Background jobs — polling fallback and retention purge

**Files:**
- Create: `backend/app/services/jobs.py`
- Modify: `backend/app/main.py` (lifespan + scheduler)
- Create: `backend/tests/test_jobs.py`

**Interfaces:**
- Consumes: `CVClient`, `Storage`, `apply_job_status`, `delete_attempt`.
- Produces:
  - `app.services.jobs.reconcile_stale_attempts(db, cv_client, settings, now: datetime) -> int` — polls every non-terminal attempt older than `cv_poll_after_sec`, applies whatever the CV service reports, returns how many it moved to terminal.
  - `app.services.jobs.purge_expired_attempts(db, storage, cv_client, now: datetime) -> int` — erases every attempt past `expires_at`, returns how many.
  - Both are plain async functions taking `now` explicitly so tests control time without mocking the clock.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_jobs.py`:

```python
import io
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from app.models import Attempt
from app.services.cv_client import CVClient
from app.services.jobs import purge_expired_attempts, reconcile_stale_attempts

RESULT = {
    "exercise_type": "squat",
    "overall_score": 70,
    "summary": "Reconciled by polling.",
    "rep_count": 1,
    "reps": [
        {
            "rep_index": 1,
            "start_time_sec": 0.0,
            "end_time_sec": 2.0,
            "min_knee_angle_deg": 80,
            "score": 70,
            "errors": [],
        }
    ],
    "annotated_video_url": "https://cv-storage/x/annotated.mp4",
    "algorithm_version": "squat-rules-v1",
}


@pytest.fixture
async def cv_client(settings):
    async with httpx.AsyncClient() as http:
        yield CVClient(base_url=settings.cv_service_url, api_key=settings.cv_api_key, http=http)


@respx.mock
async def test_poller_completes_an_attempt_whose_webhook_never_arrived(
    session, user, make_attempt, cv_client, settings
):
    now = datetime.now(UTC)
    attempt = await make_attempt(
        user,
        status="queued",
        cv_job_id="job-stale",
        created_at=now - timedelta(seconds=settings.cv_poll_after_sec + 60),
    )
    respx.get(f"{settings.cv_service_url}/v1/jobs/job-stale").mock(
        return_value=httpx.Response(200, json={"status": "completed", "result": RESULT})
    )

    moved = await reconcile_stale_attempts(session, cv_client, settings, now=now)

    assert moved == 1
    await session.refresh(attempt)
    assert attempt.status == "completed"
    assert attempt.overall_score == 70


@respx.mock
async def test_poller_ignores_attempts_that_are_still_fresh(
    session, user, make_attempt, cv_client, settings
):
    now = datetime.now(UTC)
    await make_attempt(user, status="queued", cv_job_id="job-fresh", created_at=now)
    route = respx.get(f"{settings.cv_service_url}/v1/jobs/job-fresh").mock(
        return_value=httpx.Response(200, json={"status": "completed", "result": RESULT})
    )

    moved = await reconcile_stale_attempts(session, cv_client, settings, now=now)

    assert moved == 0
    assert not route.called


@respx.mock
async def test_poller_ignores_already_terminal_attempts(
    session, user, make_attempt, cv_client, settings
):
    now = datetime.now(UTC)
    await make_attempt(
        user,
        status="completed",
        cv_job_id="job-done",
        created_at=now - timedelta(hours=1),
        completed_at=now - timedelta(minutes=30),
    )
    route = respx.get(f"{settings.cv_service_url}/v1/jobs/job-done")

    moved = await reconcile_stale_attempts(session, cv_client, settings, now=now)

    assert moved == 0
    assert not route.called


@respx.mock
async def test_poller_survives_one_unreachable_job_and_still_processes_the_rest(
    session, user, make_attempt, cv_client, settings
):
    now = datetime.now(UTC)
    stale = now - timedelta(seconds=settings.cv_poll_after_sec + 60)
    await make_attempt(user, status="queued", cv_job_id="job-broken", created_at=stale)
    await make_attempt(user, status="queued", cv_job_id="job-ok", created_at=stale)
    respx.get(f"{settings.cv_service_url}/v1/jobs/job-broken").mock(
        return_value=httpx.Response(500)
    )
    respx.get(f"{settings.cv_service_url}/v1/jobs/job-ok").mock(
        return_value=httpx.Response(200, json={"status": "completed", "result": RESULT})
    )

    moved = await reconcile_stale_attempts(session, cv_client, settings, now=now)

    assert moved == 1


@respx.mock
async def test_purge_erases_expired_attempts_everywhere(
    session, user, make_attempt, cv_client, isolated_storage, settings
):
    now = datetime.now(UTC)
    ref = isolated_storage.save(io.BytesIO(b"old video"), key="old.mp4")
    attempt = await make_attempt(
        user,
        status="completed",
        cv_job_id="job-expired",
        original_video_ref=ref,
        created_at=now - timedelta(days=31),
        expires_at=now - timedelta(days=1),
    )
    cv_delete = respx.delete(f"{settings.cv_service_url}/v1/jobs/job-expired").mock(
        return_value=httpx.Response(204)
    )

    purged = await purge_expired_attempts(session, isolated_storage, cv_client, now=now)

    assert purged == 1
    assert cv_delete.called
    assert await session.get(Attempt, attempt.id) is None


@respx.mock
async def test_purge_leaves_unexpired_attempts_alone(
    session, user, make_attempt, cv_client, isolated_storage
):
    now = datetime.now(UTC)
    attempt = await make_attempt(user, expires_at=now + timedelta(days=10))

    purged = await purge_expired_attempts(session, isolated_storage, cv_client, now=now)

    assert purged == 0
    assert await session.get(Attempt, attempt.id) is not None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_jobs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.jobs'`.

- [ ] **Step 3: Write the jobs module**

Create `backend/app/services/jobs.py`:

```python
"""Scheduled reconciliation (spec §4 polling fallback) and retention purge (spec §7).

Both take `now` explicitly so tests can place attempts in the past without patching
the clock, and both swallow per-attempt failures so one bad row cannot stall the sweep.
"""

import logging
from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Attempt
from app.schemas.contract import AttemptStatus
from app.services.attempts import apply_job_status, delete_attempt
from app.services.cv_client import CVClient, CVServiceError
from app.services.storage import Storage

logger = logging.getLogger(__name__)

NON_TERMINAL = [AttemptStatus.QUEUED.value, AttemptStatus.PROCESSING.value]


async def reconcile_stale_attempts(
    db: AsyncSession,
    cv_client: CVClient,
    settings: Settings,
    now: datetime,
) -> int:
    """Ask the CV service directly about attempts whose webhook never arrived."""
    cutoff = now - timedelta(seconds=settings.cv_poll_after_sec)
    query = sa.select(Attempt).where(
        Attempt.status.in_(NON_TERMINAL),
        Attempt.cv_job_id.is_not(None),
        Attempt.created_at < cutoff,
    )
    stale = list((await db.execute(query)).scalars())

    moved = 0
    for attempt in stale:
        try:
            job_status = await cv_client.get_job(attempt.cv_job_id)
        except CVServiceError as exc:
            logger.warning("could not poll job %s: %s", attempt.cv_job_id, exc)
            continue

        await apply_job_status(db, attempt, job_status)
        if AttemptStatus(attempt.status).is_terminal:
            moved += 1

    return moved


async def purge_expired_attempts(
    db: AsyncSession,
    storage: Storage,
    cv_client: CVClient,
    now: datetime,
) -> int:
    """TTL fallback so nothing lingers past the retention period."""
    query = sa.select(Attempt).where(Attempt.expires_at < now)
    expired = list((await db.execute(query)).scalars())

    purged = 0
    for attempt in expired:
        try:
            await delete_attempt(db, attempt, storage, cv_client)
            purged += 1
        except CVServiceError as exc:
            logger.warning("could not purge attempt %s: %s", attempt.id, exc)

    return purged
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_jobs.py -v`
Expected: 6 PASS.

- [ ] **Step 5: Schedule the jobs in the app lifespan**

Replace `backend/app/main.py` with:

```python
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from app.api import attempts, auth_dev, webhooks
from app.config import get_settings
from app.db import session_factory
from app.services.cv_client import CVClient
from app.services.jobs import purge_expired_attempts, reconcile_stale_attempts
from app.services.storage import LocalFilesystemStorage

logger = logging.getLogger(__name__)


async def _run_reconcile() -> None:
    settings = get_settings()
    maker = session_factory(settings.database_url)
    async with maker() as db, httpx.AsyncClient() as http:
        cv_client = CVClient(settings.cv_service_url, settings.cv_api_key, http)
        moved = await reconcile_stale_attempts(db, cv_client, settings, now=datetime.now(UTC))
    if moved:
        logger.info("reconciled %s stale attempt(s) by polling", moved)


async def _run_purge() -> None:
    settings = get_settings()
    maker = session_factory(settings.database_url)
    storage = LocalFilesystemStorage(root=settings.storage_dir)
    async with maker() as db, httpx.AsyncClient() as http:
        cv_client = CVClient(settings.cv_service_url, settings.cv_api_key, http)
        purged = await purge_expired_attempts(db, storage, cv_client, now=datetime.now(UTC))
    if purged:
        logger.info("purged %s expired attempt(s)", purged)


@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_run_reconcile, "interval", seconds=30, id="reconcile")
    scheduler.add_job(_run_purge, "interval", hours=6, id="purge")
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="AI Fitness Trainer Backend", version="0.1.0", lifespan=lifespan)
app.include_router(auth_dev.router)
app.include_router(attempts.router)
app.include_router(webhooks.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

`httpx.ASGITransport` in the tests does not run lifespan, so the scheduler stays off during tests — which is what you want.

- [ ] **Step 6: Run the whole suite**

Run: `uv run pytest -v`
Expected: every test PASSES.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/jobs.py backend/app/main.py backend/tests/test_jobs.py
git commit -m "feat(backend): add polling reconciler and retention purge jobs"
```

---

### Task 14: Runnable fake CV service and end-to-end demo

Gives you a working loop before Alejandro's service exists — and hands him a reference implementation of the contract he wrote.

**Files:**
- Create: `fake-cv-service/main.py`
- Create: `fake-cv-service/Dockerfile`
- Create: `fake-cv-service/README.md`
- Modify: `backend/docker-compose.yml`
- Create: `backend/README.md`
- Create: `backend/tests/test_end_to_end.py`

**Interfaces:**
- Consumes: every endpoint built in Tasks 9–12. The fake service deliberately has **no** import from `backend/` — it is a separate deployable that only knows the contract, exactly like Alejandro's real service. Its `_sign` must therefore reproduce `app.security.signing.sign_payload` byte-for-byte; the end-to-end test in Step 7 is what proves it does.
- Produces: a service implementing `POST /v1/jobs`, `GET /v1/jobs/{id}`, `DELETE /v1/jobs/{id}` and firing a signed webhook.

- [ ] **Step 1: Write the failing end-to-end test**

Create `backend/tests/test_end_to_end.py`. It exercises upload → webhook → read → delete in one flow, entirely in-process:

```python
import json
import time
import uuid
from pathlib import Path

import httpx
import respx

from app.security.signing import sign_payload

SQUAT = Path(__file__).parent / "fixtures" / "squat.mp4"

RESULT = {
    "exercise_type": "squat",
    "overall_score": 82,
    "summary": "Good depth overall.",
    "rep_count": 1,
    "reps": [
        {
            "rep_index": 1,
            "start_time_sec": 0.0,
            "end_time_sec": 2.0,
            "min_knee_angle_deg": 78,
            "score": 90,
            "errors": [],
        }
    ],
    "annotated_video_url": "https://cv-storage/x/annotated.mp4",
    "algorithm_version": "squat-rules-v1",
}


@respx.mock
async def test_full_lifecycle_upload_webhook_read_delete(client, auth_headers, settings):
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    respx.post(f"{settings.cv_service_url}/v1/jobs").mock(
        return_value=httpx.Response(202, json={"job_id": job_id, "status": "queued"})
    )
    respx.delete(f"{settings.cv_service_url}/v1/jobs/{job_id}").mock(
        return_value=httpx.Response(204)
    )

    # 1. Upload
    created = await client.post(
        "/v1/attempts",
        headers=auth_headers,
        files={"video": ("squat.mp4", SQUAT.read_bytes(), "video/mp4")},
        data={"exercise_type": "squat"},
    )
    assert created.status_code == 202
    attempt_id = created.json()["attempt_id"]

    # 2. The frontend polls and sees it queued
    pending = await client.get(f"/v1/attempts/{attempt_id}", headers=auth_headers)
    assert pending.json()["status"] == "queued"

    # 3. The CV service calls back with a signed result
    body = json.dumps({"status": "completed", "result": RESULT}).encode()
    stamp = str(int(time.time()))
    callback = await client.post(
        f"/v1/cv-callback/{attempt_id}",
        content=body,
        headers={
            "X-CV-Signature": sign_payload(body, stamp, settings.cv_webhook_secret),
            "X-CV-Timestamp": stamp,
            "Content-Type": "application/json",
        },
    )
    assert callback.status_code == 204

    # 4. The frontend polls again and sees the result
    done = await client.get(f"/v1/attempts/{attempt_id}", headers=auth_headers)
    body = done.json()
    assert body["status"] == "completed"
    assert body["result"]["overall_score"] == 82

    # 5. It shows up in history
    history = await client.get("/v1/attempts", headers=auth_headers)
    assert any(item["attempt_id"] == attempt_id for item in history.json()["items"])

    # 6. The user erases it
    erased = await client.delete(f"/v1/attempts/{attempt_id}", headers=auth_headers)
    assert erased.status_code == 204

    gone = await client.get(f"/v1/attempts/{attempt_id}", headers=auth_headers)
    assert gone.status_code == 404
```

- [ ] **Step 2: Run it to verify it passes**

Run: `uv run pytest tests/test_end_to_end.py -v`
Expected: PASS — every piece already exists; this test proves they compose.

- [ ] **Step 3: Write the fake CV service**

Create `fake-cv-service/main.py`:

```python
"""A fake CV service implementing the internal contract (spec §4).

Accepts a job, waits, then fires a signed webhook with a canned result. Lets the
backend's full loop be demoed before the real pipeline is ready — and doubles as a
reference implementation of the contract for the CV service author.

Run: uvicorn main:app --port 9000
"""

import asyncio
import hashlib
import hmac
import json
import os
import time
import uuid

import httpx
from fastapi import FastAPI, File, Form, Header, HTTPException, Response, UploadFile, status

API_KEY = os.environ.get("CV_API_KEY", "dev-cv-api-key")
WEBHOOK_SECRET = os.environ.get("CV_WEBHOOK_SECRET", "dev-webhook-secret")
PROCESSING_DELAY_SEC = float(os.environ.get("FAKE_PROCESSING_DELAY_SEC", "5"))
# Set to a failure code (e.g. "no_pose_detected") to exercise the failure path.
FORCE_FAILURE = os.environ.get("FAKE_FORCE_FAILURE", "")

app = FastAPI(title="Fake CV Service", version="0.1.0")

JOBS: dict[str, dict] = {}
# asyncio only holds a weak reference to running tasks; without this set the
# background "analysis" can be garbage-collected mid-flight.
BACKGROUND: set[asyncio.Task] = set()


def _canned_result() -> dict:
    return {
        "exercise_type": "squat",
        "overall_score": 82,
        "summary": "Good depth overall, but knees collapse inward on 2 of 5 reps.",
        "rep_count": 2,
        "reps": [
            {
                "rep_index": 1,
                "start_time_sec": 2.1,
                "end_time_sec": 5.4,
                "min_knee_angle_deg": 78,
                "score": 90,
                "errors": [],
            },
            {
                "rep_index": 2,
                "start_time_sec": 6.0,
                "end_time_sec": 9.1,
                "min_knee_angle_deg": 65,
                "score": 60,
                "errors": ["knee_valgus", "insufficient_depth"],
            },
        ],
        "annotated_video_url": "https://fake-cv-storage.local/annotated.mp4",
        "algorithm_version": "fake-v0",
    }


def _terminal_payload() -> dict:
    if FORCE_FAILURE:
        return {
            "status": "failed",
            "error": {"code": FORCE_FAILURE, "message": "forced by FAKE_FORCE_FAILURE"},
        }
    return {"status": "completed", "result": _canned_result()}


def _sign(body: bytes, timestamp: str) -> str:
    message = f"{timestamp}.".encode() + body
    return hmac.new(WEBHOOK_SECRET.encode(), message, hashlib.sha256).hexdigest()


def _require_api_key(provided: str | None) -> None:
    if provided != API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad API key")


async def _process(job_id: str, callback_url: str) -> None:
    await asyncio.sleep(PROCESSING_DELAY_SEC)
    payload = _terminal_payload()
    JOBS[job_id] = payload

    body = json.dumps(payload).encode()
    timestamp = str(int(time.time()))
    async with httpx.AsyncClient() as http:
        try:
            await http.post(
                callback_url,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-CV-Signature": _sign(body, timestamp),
                    "X-CV-Timestamp": timestamp,
                },
                timeout=10.0,
            )
        except httpx.HTTPError as exc:
            print(f"[fake-cv] webhook to {callback_url} failed: {exc} (backend will poll)")


@app.post("/v1/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    video: UploadFile = File(...),
    exercise_type: str = Form(...),
    callback_url: str = Form(...),
    x_api_key: str | None = Header(default=None),
) -> dict:
    _require_api_key(x_api_key)
    await video.read()  # drain the upload; the fake does not keep it

    job_id = f"fake-{uuid.uuid4().hex[:8]}"
    JOBS[job_id] = {"status": "processing"}
    task = asyncio.create_task(_process(job_id, callback_url))
    BACKGROUND.add(task)
    task.add_done_callback(BACKGROUND.discard)
    print(f"[fake-cv] accepted {job_id} for {exercise_type}, callback -> {callback_url}")
    return {"job_id": job_id, "status": "queued"}


@app.get("/v1/jobs/{job_id}")
async def get_job(job_id: str, x_api_key: str | None = Header(default=None)) -> dict:
    _require_api_key(x_api_key)
    if job_id not in JOBS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown job")
    return JOBS[job_id]


@app.delete("/v1/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: str, x_api_key: str | None = Header(default=None)) -> Response:
    _require_api_key(x_api_key)
    JOBS.pop(job_id, None)  # idempotent by contract
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Containerize it**

Create `fake-cv-service/Dockerfile`:

```dockerfile
FROM python:3.12-slim
WORKDIR /srv
RUN pip install --no-cache-dir "fastapi>=0.115" "uvicorn[standard]>=0.32" \
    "httpx>=0.28" "python-multipart>=0.0.12"
COPY main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
```

Create `fake-cv-service/README.md`:

```markdown
# Fake CV Service

A stand-in for the real CV pipeline that implements the internal contract from
`docs/superpowers/specs/2026-07-27-api-contract-design.md` §4: `POST /v1/jobs`,
`GET /v1/jobs/{id}`, `DELETE /v1/jobs/{id}`, and an HMAC-signed webhook callback.

It ignores the video and returns a canned result after a delay. Its only job is to
let the backend's full loop run before the real service is ready.

## Run

```bash
uvicorn main:app --port 9000
```

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `CV_API_KEY` | `dev-cv-api-key` | must match the backend's `CV_API_KEY` |
| `CV_WEBHOOK_SECRET` | `dev-webhook-secret` | must match the backend's `CV_WEBHOOK_SECRET` |
| `FAKE_PROCESSING_DELAY_SEC` | `5` | how long to "analyze" before calling back |
| `FAKE_FORCE_FAILURE` | *(empty)* | set to a failure code to exercise the failure path |

Set `FAKE_PROCESSING_DELAY_SEC=120` to let the webhook lag past the backend's
`CV_POLL_AFTER_SEC` and watch the polling fallback reconcile the attempt instead.
```

- [ ] **Step 5: Add it to docker-compose**

Append to the `services:` block in `backend/docker-compose.yml`:

```yaml
  fake-cv:
    build: ../fake-cv-service
    environment:
      CV_API_KEY: dev-cv-api-key
      CV_WEBHOOK_SECRET: dev-webhook-secret
      FAKE_PROCESSING_DELAY_SEC: "5"
    ports:
      - "9000:9000"
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

The backend runs on the host during development, so the fake service must reach it at
`host.docker.internal`. Set `BACKEND_PUBLIC_URL=http://host.docker.internal:8000` in `.env`
when using the containerized fake.

- [ ] **Step 6: Write the backend README**

Create `backend/README.md`:

````markdown
# AI Fitness Trainer — Backend

FastAPI service implementing the public (frontend ↔ backend) and internal
(backend ↔ CV service) contracts from
[`docs/superpowers/specs/2026-07-27-api-contract-design.md`](../docs/superpowers/specs/2026-07-27-api-contract-design.md).

## Setup

```bash
cd backend
uv venv
uv pip install -e ".[dev]"
cp .env.example .env
docker compose up -d db
docker compose exec db psql -U fitness -c "CREATE DATABASE fitness_test;"
uv run alembic upgrade head
```

## Test

```bash
uv run pytest -v
```

Tests need the Postgres container running. They apply migrations to `fitness_test`
once per session and roll back after every test.

## Run the whole loop locally

```bash
docker compose up -d db fake-cv
BACKEND_PUBLIC_URL=http://host.docker.internal:8000 uv run uvicorn app.main:app --reload
```

Then:

```bash
TOKEN=$(curl -s -X POST localhost:8000/v1/auth/dev-login \
  -H 'Content-Type: application/json' -d '{"email":"me@example.com"}' | jq -r .access_token)

ATTEMPT=$(curl -s -X POST localhost:8000/v1/attempts \
  -H "Authorization: Bearer $TOKEN" \
  -F video=@tests/fixtures/squat.mp4 -F exercise_type=squat | jq -r .attempt_id)

# poll until status flips to completed (the fake service calls back after ~5s)
curl -s localhost:8000/v1/attempts/$ATTEMPT -H "Authorization: Bearer $TOKEN" | jq
```

## Endpoints

| Method | Path | Boundary | Notes |
|---|---|---|---|
| `POST` | `/v1/auth/dev-login` | public | **dev only**, no password; replaced by the auth plan |
| `POST` | `/v1/attempts` | public | multipart upload, 202 |
| `GET` | `/v1/attempts/{id}` | public | poll this for the result |
| `GET` | `/v1/attempts` | public | paginated history |
| `DELETE` | `/v1/attempts/{id}` | public | end-to-end erasure (GDPR) |
| `POST` | `/v1/cv-callback/{id}` | internal | HMAC-verified webhook from the CV service |

## Background jobs

Two APScheduler jobs run inside the app process:

- **reconcile** (every 30s) — polls the CV service for non-terminal attempts older than
  `CV_POLL_AFTER_SEC`, so a dropped webhook cannot strand an attempt.
- **purge** (every 6h) — erases attempts past `expires_at` (30-day retention).

## Not yet built

- Real authentication (registration, passwords, refresh tokens) — dev-login is a placeholder.
- S3/MinIO storage — `LocalFilesystemStorage` is the only `Storage` implementation.
- Frontend.
````

- [ ] **Step 7: Verify the loop by hand**

Run the commands in the README's "Run the whole loop locally" section.
Expected: the attempt starts `queued`, and within ~5 seconds `GET /v1/attempts/{id}` reports `completed` with `overall_score: 82`. The uvicorn log shows the callback arriving; the fake-cv log shows the job accepted.

Then verify the polling fallback: stop the backend, restart the fake service with `FAKE_PROCESSING_DELAY_SEC=120`, upload again, and confirm the reconciler completes the attempt from the `GET /v1/jobs/{id}` poll even though the webhook is late.

- [ ] **Step 8: Run the entire suite one last time**

Run: `uv run pytest -v`
Expected: every test PASSES. Record the count.

- [ ] **Step 9: Commit**

```bash
git add fake-cv-service backend/docker-compose.yml backend/README.md \
        backend/tests/test_end_to_end.py
git commit -m "feat: add runnable fake CV service and end-to-end lifecycle test"
```

---

## Deliberately out of scope

Named here so nobody assumes they were forgotten.

- **Thumbnails in the history list.** Spec §3 describes the history item as "score, date, exercise, thumbnail". This plan ships the first three. A thumbnail needs frame extraction on upload *and* an endpoint that serves media back to the browser — and no endpoint in this plan serves the original or annotated video either. Media serving is one coherent follow-up task, not a field to bolt onto `AttemptSummary`.
- **Real authentication.** `app/api/auth_dev.py` issues tokens with no password. Its own docstring says so and the README lists it under "Not yet built". A separate plan replaces that module; nothing else depends on how tokens are issued.
- **Object storage (S3 / MinIO).** The spec defers it. `Storage` is a protocol precisely so this becomes one new class and zero caller changes.
- **Retry policy for retryable failures.** `FailureCode.is_retryable` encodes the spec §6b distinction and is tested, but nothing consumes it yet — the CV service owns worker-side retries. It exists so the backend-side policy, when written, has the catalog already right.
- **Frontend.** Separate project, separate plan.

## Follow-up with Alejandro

**Sync the limits:** MP4/MOV, ≤100 MB, ≤60 s, 30-day retention. The backend now enforces all four; his pipeline and storage need to agree. `fake-cv-service/main.py` is a working reference implementation of his own §4 contract — worth sending him along with the numbers.
