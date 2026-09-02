# Privacy Compliance (Consent + Account Deletion) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add registration-time explicit consent (backend-enforced) and a real account-deletion
endpoint + UI, closing the two real data-protection gaps found while scoping memoria Ch.9.

**Architecture:** Two independent backend additions (a new NOT NULL column threaded through every
`User`-creation path; a new `DELETE /v1/users/me` route that reuses `delete_attempt`'s per-attempt
external-cleanup pattern before deleting the user row) plus three frontend additions (a static
privacy-policy page, a consent checkbox on the register form, and a delete-account control in the
shared header). No new dependencies, no new routes beyond the two named above.

**Tech Stack:** FastAPI / SQLAlchemy / Alembic / pytest / respx (backend); Next.js App Router /
React / Vitest / Testing Library / Playwright (frontend). Same stack as every existing route this
touches — nothing new.

**Spec:** `docs/superpowers/specs/2026-09-02-privacy-compliance-design.md`

## Global Constraints

- Consent is captured **once, at registration**, not per upload (spec §1).
- Consent is **backend-enforced**: `POST /v1/auth/register` 422s without it (spec §1, §2.3-2.4).
- `User.privacy_consent_at` is `NOT NULL` — every `User`-creation code path (real registration,
  `dev-login`, test fixtures) must set it in the same change that adds the column (spec §1).
- Account deletion must clean up **storage + cv-service** for every owned attempt, the same way
  `delete_attempt` does, before the `User` row is deleted — the DB's `ON DELETE CASCADE` on
  `attempts.user_id`/`refresh_tokens.user_id` only removes Postgres rows, never the video file on
  disk or the cv-service job (spec §1, §2.6).
- No re-authentication (password re-entry) required to delete an account — a valid JWT plus a
  client-side type-to-confirm step is sufficient (spec §1).
- "Delete account" lives in the existing `AppShell` header, next to Logout — no new route/page
  (spec §1, §3.3).
- Out of scope, do not build: data export/portability, account-info editing (change email), app-level
  at-rest encryption, a DPO contact page, per-upload consent (spec §0, §5).
- Real behavior in tests, not mocks, matching every existing test in this repo — `respx` for the
  cv-service boundary (already the pattern in `test_delete_attempt.py`), a real (test) Postgres DB,
  real `LocalFilesystemStorage` writes/reads.

---

### Task 1: Backend — `privacy_consent_at` column + registration consent enforcement

**Files:**
- Create: `backend/alembic/versions/0003_privacy_consent.py`
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/services/auth.py`
- Modify: `backend/app/api/auth.py`
- Modify: `backend/app/api/auth_dev.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_register_login.py`

**Interfaces:**
- Consumes: nothing from other tasks (this is the first task).
- Produces: `User.privacy_consent_at: datetime` (non-null column, every codebase `User`-creation
  path sets it); `app.services.auth.ConsentRequired` exception; `RegisterRequest.consent: bool`
  (required field). Task 2 does not depend on any of these. Tasks 3-5 (frontend) depend on the
  contract shape only: `POST /v1/auth/register` now requires a JSON body with `consent: true`, and
  returns `422` if `consent` is missing or `false`.

- [ ] **Step 1: Update `test_register_login.py` — add `consent: True` to every existing register
  call, and add two new tests for the not-yet-built enforcement**

  Rewrite `backend/tests/test_register_login.py` to this exact content (every existing
  `/v1/auth/register` JSON body gains `"consent": True`; two new test functions are added at the
  end):

  ```python
  import uuid
  from datetime import UTC, datetime, timedelta

  from app.models import RefreshToken
  from app.services.auth import hash_refresh_token

  EMAIL = "athlete@example.com"
  PASSWORD = "correct-horse-battery-staple"


  async def test_register_creates_a_user_and_returns_a_token_pair(client):
      response = await client.post(
          "/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "consent": True}
      )

      assert response.status_code == 201
      body = response.json()
      assert body["access_token"]
      assert body["refresh_token"]
      assert body["token_type"] == "bearer"


  async def test_register_rejects_a_duplicate_email(client):
      await client.post(
          "/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "consent": True}
      )

      response = await client.post(
          "/v1/auth/register",
          json={"email": EMAIL, "password": "a-different-password", "consent": True},
      )

      assert response.status_code == 409


  async def test_register_rejects_a_too_short_password(client):
      response = await client.post(
          "/v1/auth/register", json={"email": EMAIL, "password": "short", "consent": True}
      )

      assert response.status_code == 422


  async def test_register_requires_consent(client):
      response = await client.post(
          "/v1/auth/register", json={"email": EMAIL, "password": PASSWORD}
      )

      assert response.status_code == 422


  async def test_register_rejects_explicit_false_consent(client):
      response = await client.post(
          "/v1/auth/register",
          json={"email": EMAIL, "password": PASSWORD, "consent": False},
      )

      assert response.status_code == 422


  async def test_login_succeeds_with_correct_credentials(client):
      await client.post(
          "/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "consent": True}
      )

      response = await client.post(
          "/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
      )

      assert response.status_code == 200
      body = response.json()
      assert body["access_token"]
      assert body["refresh_token"]


  async def test_login_rejects_wrong_password(client):
      await client.post(
          "/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "consent": True}
      )

      response = await client.post(
          "/v1/auth/login", json={"email": EMAIL, "password": "wrong-password"}
      )

      assert response.status_code == 401


  async def test_login_rejects_unknown_email(client):
      unknown = await client.post(
          "/v1/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
      )
      wrong_password = await client.post(
          "/v1/auth/login", json={"email": EMAIL, "password": "wrong-password"}
      )

      assert unknown.status_code == 401
      assert wrong_password.status_code == 401
      assert unknown.json() == wrong_password.json()  # no enumeration signal


  async def test_login_rejects_a_dev_login_created_account(client):
      await client.post("/v1/auth/dev-login", json={"email": "devonly@example.com"})

      response = await client.post(
          "/v1/auth/login", json={"email": "devonly@example.com", "password": "anything-at-all"}
      )

      assert response.status_code == 401


  async def test_refresh_rotates_and_invalidates_the_old_token(client):
      registered = await client.post(
          "/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "consent": True}
      )
      old_refresh_token = registered.json()["refresh_token"]

      refreshed = await client.post(
          "/v1/auth/refresh", json={"refresh_token": old_refresh_token}
      )
      assert refreshed.status_code == 200
      new_refresh_token = refreshed.json()["refresh_token"]
      assert new_refresh_token != old_refresh_token

      reuse_attempt = await client.post(
          "/v1/auth/refresh", json={"refresh_token": old_refresh_token}
      )
      assert reuse_attempt.status_code == 401


  async def test_refresh_can_be_chained_when_each_new_token_is_used_in_turn(client):
      registered = await client.post(
          "/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "consent": True}
      )
      token = registered.json()["refresh_token"]

      for _ in range(3):
          response = await client.post("/v1/auth/refresh", json={"refresh_token": token})
          assert response.status_code == 200
          token = response.json()["refresh_token"]


  async def test_refresh_rejects_an_expired_token(client, session, user):
      raw_token = "expired-raw-token"
      session.add(
          RefreshToken(
              id=uuid.uuid4(),
              user_id=user.id,
              token_hash=hash_refresh_token(raw_token),
              expires_at=datetime.now(UTC) - timedelta(days=1),
          )
      )
      await session.flush()

      response = await client.post("/v1/auth/refresh", json={"refresh_token": raw_token})

      assert response.status_code == 401


  async def test_refresh_detects_reuse_and_revokes_the_whole_session_family(client):
      registered = await client.post(
          "/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "consent": True}
      )
      token_a = registered.json()["refresh_token"]

      first_refresh = await client.post("/v1/auth/refresh", json={"refresh_token": token_a})
      token_b = first_refresh.json()["refresh_token"]

      reuse = await client.post("/v1/auth/refresh", json={"refresh_token": token_a})
      assert reuse.status_code == 401

      token_b_now = await client.post("/v1/auth/refresh", json={"refresh_token": token_b})
      assert token_b_now.status_code == 401


  async def test_logout_revokes_the_refresh_token(client):
      registered = await client.post(
          "/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "consent": True}
      )
      refresh_token = registered.json()["refresh_token"]

      logout = await client.post("/v1/auth/logout", json={"refresh_token": refresh_token})
      assert logout.status_code == 204

      response = await client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
      assert response.status_code == 401


  async def test_logout_is_idempotent_for_an_unknown_token(client):
      response = await client.post(
          "/v1/auth/logout", json={"refresh_token": "not-a-real-token"}
      )

      assert response.status_code == 204


  async def test_access_token_from_login_still_authorizes_protected_routes(client):
      await client.post(
          "/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "consent": True}
      )
      logged_in = await client.post(
          "/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
      )
      access_token = logged_in.json()["access_token"]

      response = await client.get(
          "/v1/attempts", headers={"Authorization": f"Bearer {access_token}"}
      )

      assert response.status_code == 200
  ```

- [ ] **Step 2: Run the tests to confirm the two new ones fail, everything else still passes**

  Run: `cd backend && uv run --extra dev pytest tests/test_register_login.py -v`
  Expected: `test_register_requires_consent` and `test_register_rejects_explicit_false_consent`
  FAIL (register currently succeeds either way, returning 201 not 422 — `consent` isn't a field on
  `RegisterRequest` yet, so Pydantic silently ignores the extra key). Every other test in the file
  PASSES (the added `"consent": True` key is likewise ignored today, harmlessly).

- [ ] **Step 3: Add the migration**

  Create `backend/alembic/versions/0003_privacy_consent.py`:

  ```python
  """privacy: explicit consent timestamp on users

  Revision ID: 0003
  Revises: 0002
  """
  import sqlalchemy as sa
  from alembic import op

  revision = "0003"
  down_revision = "0002"
  branch_labels = None
  depends_on = None


  def upgrade() -> None:
      # NOT NULL from the start: a temporary server_default backfills any pre-existing
      # row in the same statement, then gets dropped so every future insert must supply
      # the value explicitly in application code — matching Attempt.consent_at, which
      # has no server default either.
      op.add_column(
          "users",
          sa.Column(
              "privacy_consent_at",
              sa.DateTime(timezone=True),
              server_default=sa.func.now(),
              nullable=False,
          ),
      )
      op.alter_column("users", "privacy_consent_at", server_default=None)


  def downgrade() -> None:
      op.drop_column("users", "privacy_consent_at")
  ```

- [ ] **Step 4: Add the column to the `User` model**

  In `backend/app/models/user.py`, add the import and the column:

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
      # NULL means no password credential (e.g. a dev-login-created account) — never
      # NOT NULL, since app/api/auth_dev.py creates users with no password at all.
      hashed_password: Mapped[str | None] = mapped_column(String(60), nullable=True)
      created_at: Mapped[datetime] = mapped_column(
          DateTime(timezone=True), server_default=func.now(), nullable=False
      )
      # Set explicitly by every User-creation path (register_user, dev_login, test
      # fixtures) — no server default, so a code path that forgets it fails loudly at
      # insert time rather than silently recording a fabricated consent moment.
      privacy_consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  ```

- [ ] **Step 5: Add `consent` to `RegisterRequest`**

  In `backend/app/schemas/auth.py`, change:

  ```python
  class RegisterRequest(BaseModel):
      email: EmailStr
      password: str = Field(min_length=8, max_length=72)
  ```

  to:

  ```python
  class RegisterRequest(BaseModel):
      email: EmailStr
      password: str = Field(min_length=8, max_length=72)
      consent: bool
  ```

  (No default — a request with no `consent` key at all fails Pydantic validation automatically
  with a 422, which is `test_register_requires_consent`'s path. `consent: False` is a valid bool,
  so it reaches `register_user`, which is `test_register_rejects_explicit_false_consent`'s path.)

- [ ] **Step 6: Add `ConsentRequired` and update `register_user`**

  In `backend/app/services/auth.py`, add the exception next to the existing ones:

  ```python
  class ConsentRequired(Exception):
      """Registration attempted with consent missing or explicitly false."""
  ```

  and change `register_user`:

  ```python
  async def register_user(db: AsyncSession, email: str, password: str, consent: bool) -> User:
      if not consent:
          raise ConsentRequired(email)

      existing = await db.execute(sa.select(User).where(User.email == email))
      if existing.scalar_one_or_none() is not None:
          raise EmailAlreadyRegistered(email)

      user = User(
          id=uuid.uuid4(),
          email=email,
          hashed_password=hash_password(password),
          privacy_consent_at=datetime.now(UTC),
      )
      db.add(user)
      try:
          await db.commit()
      except sa.exc.IntegrityError:
          await db.rollback()
          raise EmailAlreadyRegistered(email) from None
      return user
  ```

- [ ] **Step 7: Wire the route**

  In `backend/app/api/auth.py`, add `ConsentRequired` to the import from `app.services.auth` and
  update the `register` route:

  ```python
  from app.services.auth import (
      ConsentRequired,
      EmailAlreadyRegistered,
      InvalidCredentials,
      InvalidRefreshToken,
      authenticate_user,
      issue_token_pair,
      register_user,
      revoke_refresh_token,
      rotate_refresh_token,
  )

  router = APIRouter(prefix="/v1/auth", tags=["auth"])


  @router.post("/register", status_code=status.HTTP_201_CREATED, response_model=TokenPair)
  async def register(payload: RegisterRequest, db: DbDep, settings: SettingsDep) -> TokenPair:
      try:
          user = await register_user(db, payload.email, payload.password, payload.consent)
      except ConsentRequired:
          raise HTTPException(
              status.HTTP_422_UNPROCESSABLE_ENTITY, "consent is required to register"
          ) from None
      except EmailAlreadyRegistered:
          raise HTTPException(status.HTTP_409_CONFLICT, "email already registered") from None

      access_token, refresh_token = await issue_token_pair(db, user, settings)
      return TokenPair(access_token=access_token, refresh_token=refresh_token)
  ```

- [ ] **Step 8: Fix `dev_login`**

  In `backend/app/api/auth_dev.py`, the user-creation branch needs `privacy_consent_at` too — add
  the import and the field:

  ```python
  import uuid
  from datetime import UTC, datetime

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
          user = User(id=uuid.uuid4(), email=payload.email, privacy_consent_at=datetime.now(UTC))
          db.add(user)
          await db.commit()

      token = create_access_token(user.id, settings.jwt_secret, settings.jwt_ttl_seconds)
      return TokenResponse(access_token=token)
  ```

- [ ] **Step 9: Fix the `user`/`other_user` test fixtures**

  In `backend/tests/conftest.py`, both direct `User(...)` constructions need the new field. The
  file's top-level imports are currently `import os`, `subprocess`, `sys`, `uuid`, `httpx`,
  `pytest`, `pytest_asyncio`, plus `from sqlalchemy...`/`from app...` imports — no top-level
  `datetime` import exists yet (the `make_attempt` fixture imports it locally, inside its own
  function body). Add `from datetime import UTC, datetime` as a new top-level import line. Change:

  ```python
  @pytest_asyncio.fixture
  async def user(session) -> User:
      record = User(id=uuid.uuid4(), email=f"{uuid.uuid4().hex}@example.com")
      session.add(record)
      await session.flush()
      return record
  ```

  to:

  ```python
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
  ```

  and the same change to `other_user`:

  ```python
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
  ```

- [ ] **Step 10: Run the full backend suite**

  Run: `cd backend && uv run --extra dev pytest -v`
  Expected: PASS, all tests (the two new ones from Step 1 now pass; nothing else regresses).

- [ ] **Step 11: Commit**

  ```bash
  git add backend/alembic/versions/0003_privacy_consent.py backend/app/models/user.py \
    backend/app/schemas/auth.py backend/app/services/auth.py backend/app/api/auth.py \
    backend/app/api/auth_dev.py backend/tests/conftest.py backend/tests/test_register_login.py
  git commit -m "feat(backend): explicit consent required to register (privacy compliance)"
  ```

---

### Task 2: Backend — account deletion (`DELETE /v1/users/me`)

**Files:**
- Create: `backend/app/services/users.py`
- Create: `backend/app/api/users.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_users.py`

**Interfaces:**
- Consumes: nothing from Task 1 (independent — this task's `User` rows come from the `user`/
  `other_user` fixtures, already fixed in Task 1). Reuses `CurrentUser`, `DbDep`, `StorageDep`,
  `CVClientDep` from `app.api.deps` (all exist already, unchanged) and `CVServiceError` from
  `app.services.cv_client` (exists already, unchanged).
- Produces: `app.services.users.delete_account(db, user, storage, cv_client) -> None` (raises
  `CVServiceError` if the cv-service can't confirm a job deletion — propagates, nothing is
  deleted from the DB in that case); route `DELETE /v1/users/me` (204 on success, 401 unauthenticated,
  502 if the cv-service can't confirm erasure). Task 5 (frontend account-deletion UI) depends on
  this exact route existing with this exact status-code contract.

- [ ] **Step 1: Write the failing tests**

  Create `backend/tests/test_users.py`:

  ```python
  import io
  import uuid
  from datetime import UTC, datetime, timedelta

  import httpx
  import respx
  import sqlalchemy as sa

  from app.models import Attempt, RefreshToken, User
  from app.services.auth import hash_refresh_token


  @respx.mock
  async def test_deletes_the_user_their_attempts_and_their_refresh_tokens(
      client, auth_headers, session, user, make_attempt, isolated_storage, settings
  ):
      ref = isolated_storage.save(io.BytesIO(b"video"), key="orig.mp4")
      attempt = await make_attempt(
          user, status="completed", cv_job_id="job-77", original_video_ref=ref
      )
      session.add(
          RefreshToken(
              id=uuid.uuid4(),
              user_id=user.id,
              token_hash=hash_refresh_token("some-raw-refresh-token"),
              expires_at=datetime.now(UTC) + timedelta(days=1),
          )
      )
      await session.flush()
      cv_delete = respx.delete(f"{settings.cv_service_url}/v1/jobs/job-77").mock(
          return_value=httpx.Response(204)
      )

      response = await client.delete("/v1/users/me", headers=auth_headers)

      assert response.status_code == 204
      assert cv_delete.called
      assert await session.get(User, user.id) is None
      assert await session.get(Attempt, attempt.id) is None
      remaining_tokens = (
          await session.execute(sa.select(RefreshToken).where(RefreshToken.user_id == user.id))
      ).scalars().all()
      assert remaining_tokens == []
      try:
          isolated_storage.open(ref)
      except FileNotFoundError:
          return
      raise AssertionError("the original video should have been deleted")


  async def test_deletes_an_account_with_no_attempts(client, auth_headers, session, user):
      response = await client.delete("/v1/users/me", headers=auth_headers)

      assert response.status_code == 204
      assert await session.get(User, user.id) is None


  @respx.mock
  async def test_keeps_the_account_when_the_cv_service_cannot_confirm_erasure(
      client, auth_headers, session, user, make_attempt, settings
  ):
      attempt = await make_attempt(user, cv_job_id="job-76")
      respx.delete(f"{settings.cv_service_url}/v1/jobs/job-76").mock(
          return_value=httpx.Response(500)
      )

      response = await client.delete("/v1/users/me", headers=auth_headers)

      assert response.status_code == 502
      assert await session.get(User, user.id) is not None
      assert await session.get(Attempt, attempt.id) is not None


  @respx.mock
  async def test_tolerates_a_cv_job_already_gone(
      client, auth_headers, session, user, make_attempt, settings
  ):
      attempt = await make_attempt(user, cv_job_id="job-75")
      respx.delete(f"{settings.cv_service_url}/v1/jobs/job-75").mock(
          return_value=httpx.Response(404)
      )

      response = await client.delete("/v1/users/me", headers=auth_headers)

      assert response.status_code == 204
      assert await session.get(User, user.id) is None
      assert await session.get(Attempt, attempt.id) is None


  async def test_does_not_touch_another_users_data(
      client, auth_headers, session, user, other_user, make_attempt
  ):
      other_attempt = await make_attempt(other_user)

      response = await client.delete("/v1/users/me", headers=auth_headers)

      assert response.status_code == 204
      assert await session.get(User, other_user.id) is not None
      assert await session.get(Attempt, other_attempt.id) is not None


  async def test_requires_authentication(client):
      response = await client.delete("/v1/users/me")

      assert response.status_code == 401
  ```

- [ ] **Step 2: Run the tests to confirm they fail**

  Run: `cd backend && uv run --extra dev pytest tests/test_users.py -v`
  Expected: FAIL with 404 (no route registered yet at `/v1/users/me`).

- [ ] **Step 3: Write the service function**

  Create `backend/app/services/users.py`:

  ```python
  """Business logic for account-level erasure (spec: 2026-09-02-privacy-compliance-design.md §2.6-2.7)."""

  import sqlalchemy as sa
  from sqlalchemy.ext.asyncio import AsyncSession

  from app.models import Attempt, User
  from app.services.cv_client import CVClient
  from app.services.storage import Storage


  async def delete_account(
      db: AsyncSession,
      user: User,
      storage: Storage,
      cv_client: CVClient,
  ) -> None:
      """Erase a user and everything they own.

      Mirrors delete_attempt's ordering and rationale: `attempts.user_id` and
      `refresh_tokens.user_id` both have ON DELETE CASCADE, so deleting the `User` row
      alone would silently wipe those Postgres rows — but it would never touch the
      video file on disk or the cv-service job, since those only ever get cleaned up
      by explicit Python calls (storage.delete, cv_client.delete_job), never a DB
      trigger. So every owned attempt gets that same external cleanup first; only then
      does the user row go. If a CVServiceError propagates mid-loop, it aborts here —
      some attempts may already be cleaned, the user row survives, and the request can
      be retried. Reporting success we could not fully deliver would break the GDPR
      promise, same as delete_attempt's own docstring.
      """
      attempts = (
          await db.execute(sa.select(Attempt).where(Attempt.user_id == user.id))
      ).scalars().all()
      for attempt in attempts:
          storage.delete(attempt.original_video_ref)
          if attempt.cv_job_id:
              await cv_client.delete_job(attempt.cv_job_id)

      await db.delete(user)
      await db.commit()
  ```

- [ ] **Step 4: Write the route**

  Create `backend/app/api/users.py`:

  ```python
  """Account-level operations (spec: 2026-09-02-privacy-compliance-design.md §2.6)."""

  from fastapi import APIRouter, HTTPException, status

  from app.api.deps import CurrentUser, CVClientDep, DbDep, StorageDep
  from app.services.cv_client import CVServiceError
  from app.services.users import delete_account

  router = APIRouter(prefix="/v1/users", tags=["users"])


  @router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
  async def delete_my_account(
      user: CurrentUser, db: DbDep, storage: StorageDep, cv_client: CVClientDep
  ) -> None:
      try:
          await delete_account(db, user, storage, cv_client)
      except CVServiceError as exc:
          raise HTTPException(
              status_code=status.HTTP_502_BAD_GATEWAY,
              detail=f"could not confirm erasure with the analysis service: {exc}",
          ) from exc
  ```

- [ ] **Step 5: Register the router**

  In `backend/app/main.py`, change:

  ```python
  from app.api import attempts, auth, auth_dev, webhooks
  ```

  to:

  ```python
  from app.api import attempts, auth, auth_dev, users, webhooks
  ```

  and add, alongside the other `app.include_router(...)` calls:

  ```python
  app.include_router(users.router)
  ```

- [ ] **Step 6: Run the tests to confirm they pass**

  Run: `cd backend && uv run --extra dev pytest tests/test_users.py -v`
  Expected: PASS, all 6 tests.

- [ ] **Step 7: Run the full backend suite**

  Run: `cd backend && uv run --extra dev pytest -v`
  Expected: PASS, no regressions.

- [ ] **Step 8: Commit**

  ```bash
  git add backend/app/services/users.py backend/app/api/users.py backend/app/main.py \
    backend/tests/test_users.py
  git commit -m "feat(backend): DELETE /v1/users/me — real account-level erasure (privacy compliance)"
  ```

---

### Task 3: Frontend — privacy policy page

**Files:**
- Create: `frontend/src/app/privacy/page.tsx`
- Create: `frontend/tests/unit/app/privacy-page.test.tsx`

**Interfaces:**
- Consumes: nothing from other tasks (static content, no data fetching).
- Produces: a public route at `/privacy`. Task 4 links to it by that exact path.

- [ ] **Step 1: Write the failing test**

  Create `frontend/tests/unit/app/privacy-page.test.tsx`:

  ```tsx
  import { render, screen } from "@testing-library/react";
  import { describe, expect, it } from "vitest";
  import PrivacyPage from "@/app/privacy/page";

  describe("PrivacyPage", () => {
    it("renders the policy heading", () => {
      render(<PrivacyPage />);

      expect(screen.getByRole("heading", { name: /privacy policy/i })).toBeInTheDocument();
    });

    it("states the 30-day retention period", () => {
      render(<PrivacyPage />);

      expect(screen.getByText(/30 days/i)).toBeInTheDocument();
    });

    it("names both erasure options", () => {
      render(<PrivacyPage />);

      expect(screen.getByText(/delete a single analysis/i)).toBeInTheDocument();
      expect(screen.getByText(/delete your entire account/i)).toBeInTheDocument();
    });
  });
  ```

- [ ] **Step 2: Run the test to verify it fails**

  Run: `cd frontend && npx vitest run tests/unit/app/privacy-page.test.tsx`
  Expected: FAIL — `Cannot find module '@/app/privacy/page'`.

- [ ] **Step 3: Write the page**

  Create `frontend/src/app/privacy/page.tsx`:

  ```tsx
  import Link from "next/link";
  import { Card } from "@/components/ui/card";

  export default function PrivacyPage() {
    return (
      <Card className="mx-auto mt-16 max-w-2xl space-y-4 p-6">
        <h1 className="text-2xl font-semibold">Privacy Policy</h1>

        <section className="space-y-1">
          <h2 className="text-lg font-medium">What we collect</h2>
          <p className="text-sm text-muted-foreground">
            Your account email and password (stored as a salted hash, never in plain text). Any
            video you upload, the exercise scores and joint-angle measurements our analysis
            derives from it, and an annotated copy of the video showing that analysis.
          </p>
        </section>

        <section className="space-y-1">
          <h2 className="text-lg font-medium">Why</h2>
          <p className="text-sm text-muted-foreground">
            Solely to analyze your exercise technique and show you the result — the only purpose
            this account exists for. We do not sell or share this data with third parties.
          </p>
        </section>

        <section className="space-y-1">
          <h2 className="text-lg font-medium">How long</h2>
          <p className="text-sm text-muted-foreground">
            Every video and its analysis are automatically and permanently deleted 30 days after
            upload.
          </p>
        </section>

        <section className="space-y-1">
          <h2 className="text-lg font-medium">Your rights</h2>
          <p className="text-sm text-muted-foreground">
            You can delete a single analysis at any time from your history, or delete your entire
            account (and everything in it) from the header menu — both take effect immediately.
          </p>
        </section>

        <p className="text-center text-sm text-muted-foreground">
          <Link href="/register" className="underline underline-offset-2">
            Back to registration
          </Link>
        </p>
      </Card>
    );
  }
  ```

- [ ] **Step 4: Run the test to verify it passes**

  Run: `cd frontend && npx vitest run tests/unit/app/privacy-page.test.tsx`
  Expected: PASS, all 3 tests.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/app/privacy/page.tsx frontend/tests/unit/app/privacy-page.test.tsx
  git commit -m "feat(frontend): add the privacy policy page (privacy compliance)"
  ```

---

### Task 4: Frontend — consent checkbox on registration

**Files:**
- Modify: `frontend/src/lib/auth-context.tsx`
- Modify: `frontend/src/app/register/page.tsx`
- Modify: `frontend/tests/unit/lib/auth-context.test.tsx`
- Modify: `frontend/tests/unit/app/register-page.test.tsx`
- Modify: `frontend/tests/e2e/full-flow.spec.ts`

**Interfaces:**
- Consumes: `POST /v1/auth/register` now requiring `consent: true` in its JSON body (Task 1); the
  `/privacy` route (Task 3).
- Produces: `useAuth().register(email: string, password: string, consent: boolean): Promise<void>`
  — the third parameter is new; every existing caller of `register(...)` must be updated to pass it.
  Task 5 does not call `register`, so nothing outside this task's own files needs updating besides
  what's listed here.

- [ ] **Step 1: Write the failing tests**

  In `frontend/tests/unit/lib/auth-context.test.tsx`, change the existing register test's call
  site:

  ```tsx
    it("becomes authenticated after a successful register", async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        jsonResponse(201, { access_token: "a1", refresh_token: "r1", token_type: "bearer" }),
      );
      const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      await act(async () => {
        await result.current.register("me@example.com", "correct-horse-battery-staple", true);
      });

      expect(result.current.isAuthenticated).toBe(true);
    });
  ```

  and add a new test right after it, asserting the consent flag actually reaches the request body:

  ```tsx
    it("sends the consent flag in the register request body", async () => {
      const fetchMock = vi.mocked(fetch).mockResolvedValueOnce(
        jsonResponse(201, { access_token: "a1", refresh_token: "r1", token_type: "bearer" }),
      );
      const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      await act(async () => {
        await result.current.register("me@example.com", "correct-horse-battery-staple", true);
      });

      const [, init] = fetchMock.mock.calls[0];
      const body = JSON.parse(init!.body as string);
      expect(body.consent).toBe(true);
    });
  ```

  In `frontend/tests/unit/app/register-page.test.tsx`, update the two existing tests that call
  `register` to expect the new third argument, and add a new test for the checkbox gate. Replace
  the whole file's content with:

  ```tsx
  import { render, screen, waitFor, cleanup } from "@testing-library/react";
  import userEvent from "@testing-library/user-event";
  import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

  const mockPush = vi.fn();
  vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mockPush }) }));

  const mockRegister = vi.fn();
  vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ register: mockRegister }) }));

  import RegisterPage from "@/app/register/page";

  describe("RegisterPage", () => {
    beforeEach(() => {
      mockRegister.mockReset();
      mockPush.mockReset();
    });

    afterEach(() => {
      cleanup();
    });

    it("rejects a password shorter than 8 characters before calling register", async () => {
      render(<RegisterPage />);
      const user = userEvent.setup();

      await user.type(screen.getByLabelText(/email/i), "me@example.com");
      await user.type(screen.getByLabelText(/password/i), "short");
      await user.click(screen.getByLabelText(/i agree/i));
      await user.click(screen.getByRole("button", { name: /create account/i }));

      expect(await screen.findByText(/at least 8 characters/i)).toBeInTheDocument();
      expect(mockRegister).not.toHaveBeenCalled();
    });

    it("disables submit until the consent checkbox is checked", async () => {
      render(<RegisterPage />);
      const user = userEvent.setup();

      await user.type(screen.getByLabelText(/email/i), "me@example.com");
      await user.type(screen.getByLabelText(/password/i), "correct-horse-battery-staple");

      expect(screen.getByRole("button", { name: /create account/i })).toBeDisabled();

      await user.click(screen.getByLabelText(/i agree/i));

      expect(screen.getByRole("button", { name: /create account/i })).toBeEnabled();
    });

    it("submits with consent true and redirects home on success", async () => {
      mockRegister.mockResolvedValueOnce(undefined);
      render(<RegisterPage />);
      const user = userEvent.setup();

      await user.type(screen.getByLabelText(/email/i), "me@example.com");
      await user.type(screen.getByLabelText(/password/i), "correct-horse-battery-staple");
      await user.click(screen.getByLabelText(/i agree/i));
      await user.click(screen.getByRole("button", { name: /create account/i }));

      await waitFor(() =>
        expect(mockRegister).toHaveBeenCalledWith(
          "me@example.com",
          "correct-horse-battery-staple",
          true,
        ),
      );
      expect(mockPush).toHaveBeenCalledWith("/");
    });

    it("shows an error message when the email is already registered", async () => {
      mockRegister.mockRejectedValueOnce(new Error("request to /v1/auth/register failed with status 409"));
      render(<RegisterPage />);
      const user = userEvent.setup();

      await user.type(screen.getByLabelText(/email/i), "me@example.com");
      await user.type(screen.getByLabelText(/password/i), "correct-horse-battery-staple");
      await user.click(screen.getByLabelText(/i agree/i));
      await user.click(screen.getByRole("button", { name: /create account/i }));

      expect(await screen.findByText(/already registered/i)).toBeInTheDocument();
    });
  });
  ```

- [ ] **Step 2: Run the tests to verify they fail**

  Run: `cd frontend && npx vitest run tests/unit/lib/auth-context.test.tsx tests/unit/app/register-page.test.tsx`
  Expected: FAIL — `register` still takes 2 arguments, no consent checkbox exists yet
  (`getByLabelText(/i agree/i)` finds nothing).

- [ ] **Step 3: Update `auth-context.tsx`**

  Change `requestTokenPair` and `register` in `frontend/src/lib/auth-context.tsx`:

  ```tsx
  interface AuthContextValue {
    isAuthenticated: boolean;
    isLoading: boolean;
    login(email: string, password: string): Promise<void>;
    register(email: string, password: string, consent: boolean): Promise<void>;
    logout(): Promise<void>;
  }

  const AuthContext = createContext<AuthContextValue | null>(null);

  async function requestTokenPair(
    path: string,
    body: Record<string, unknown>,
  ): Promise<TokenPair> {
    let response: Response;
    try {
      response = await apiFetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } catch (error) {
      if (error instanceof AuthError) {
        // On login/register endpoints, a 401 means bad credentials, not session expiration.
        // Don't let the global auth-failure signal treat it as session invalidation.
        throw new Error("Invalid email or password");
      }
      throw error; // Network errors, etc. propagate as-is
    }
    if (!response.ok) {
      throw new Error(`request to ${path} failed with status ${response.status}`);
    }
    return (await response.json()) as TokenPair;
  }
  ```

  and further down:

  ```tsx
    async function login(email: string, password: string) {
      const tokens = await requestTokenPair("/v1/auth/login", { email, password });
      setTokens(tokens);
      setIsAuthenticated(true);
    }

    async function register(email: string, password: string, consent: boolean) {
      const tokens = await requestTokenPair("/v1/auth/register", { email, password, consent });
      setTokens(tokens);
      setIsAuthenticated(true);
    }
  ```

  (`requestTokenPair` changed from `(path, email, password)` to `(path, body)` — a small
  refactor so it stays reusable for a request shape `login` doesn't share. `login`'s call site
  above is updated in the same edit; nothing else calls `requestTokenPair`.)

- [ ] **Step 4: Update the register page**

  Replace `frontend/src/app/register/page.tsx` with:

  ```tsx
  "use client";

  import { useState, type FormEvent } from "react";
  import { useRouter } from "next/navigation";
  import Link from "next/link";
  import { useAuth } from "@/lib/auth-context";
  import { Button } from "@/components/ui/button";
  import { Input } from "@/components/ui/input";
  import { Label } from "@/components/ui/label";
  import { Card } from "@/components/ui/card";
  import { Alert, AlertDescription } from "@/components/ui/alert";

  const MIN_PASSWORD_LENGTH = 8;

  export default function RegisterPage() {
    const { register } = useAuth();
    const router = useRouter();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [consent, setConsent] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    async function handleSubmit(event: FormEvent) {
      event.preventDefault();
      if (password.length < MIN_PASSWORD_LENGTH) {
        setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
        return;
      }
      setError(null);
      setIsSubmitting(true);
      try {
        await register(email, password, consent);
        router.push("/");
      } catch (err) {
        const message = err instanceof Error ? err.message : "";
        if (message.includes("409")) {
          setError("That email is already registered.");
        } else {
          setError("Could not create the account. Try again.");
        }
      } finally {
        setIsSubmitting(false);
      }
    }

    return (
      <Card className="mx-auto mt-16 max-w-sm p-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <h1 className="text-2xl font-semibold">Create account</h1>
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <div className="space-y-1">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <div className="flex items-start gap-2">
            <input
              id="consent"
              type="checkbox"
              className="mt-1"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
            />
            <Label htmlFor="consent" className="text-sm font-normal text-muted-foreground">
              I agree that videos I upload will be processed to analyze my exercise technique,
              per the{" "}
              <Link href="/privacy" className="underline underline-offset-2">
                Privacy Policy
              </Link>
              .
            </Label>
          </div>
          <Button type="submit" disabled={isSubmitting || !consent} className="w-full">
            Create account
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link href="/login" className="underline underline-offset-2">
              Log in
            </Link>
          </p>
        </form>
      </Card>
    );
  }
  ```

- [ ] **Step 5: Run the tests to verify they pass**

  Run: `cd frontend && npx vitest run tests/unit/lib/auth-context.test.tsx tests/unit/app/register-page.test.tsx`
  Expected: PASS, all tests.

- [ ] **Step 6: Update the Playwright e2e test**

  In `frontend/tests/e2e/full-flow.spec.ts`, the register step needs the checkbox checked before
  the submit click. Change:

  ```ts
    await page.goto("/register");
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/password/i).fill(password);
    await page.getByRole("button", { name: /create account/i }).click();
  ```

  to:

  ```ts
    await page.goto("/register");
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/password/i).fill(password);
    await page.getByLabel(/i agree/i).check();
    await page.getByRole("button", { name: /create account/i }).click();
  ```

- [ ] **Step 7: Run the full frontend unit suite**

  Run: `cd frontend && npm test`
  Expected: PASS, no regressions — the total test count vitest reports should be higher than
  before this task (this task alone adds 1 new register-page test and 1 new auth-context test on
  top of whatever Task 3 already added; don't hardcode an exact number, read it off the run).

- [ ] **Step 8: Commit**

  ```bash
  git add frontend/src/lib/auth-context.tsx frontend/src/app/register/page.tsx \
    frontend/tests/unit/lib/auth-context.test.tsx frontend/tests/unit/app/register-page.test.tsx \
    frontend/tests/e2e/full-flow.spec.ts
  git commit -m "feat(frontend): consent checkbox on registration (privacy compliance)"
  ```

---

### Task 5: Frontend — account deletion in `AppShell`

**Files:**
- Modify: `frontend/src/lib/auth-context.tsx`
- Modify: `frontend/src/components/app-shell.tsx`
- Modify: `frontend/tests/unit/lib/auth-context.test.tsx`
- Modify: `frontend/tests/unit/components/app-shell.test.tsx`

**Interfaces:**
- Consumes: `DELETE /v1/users/me` (Task 2) — 204 on success.
- Produces: `useAuth().deleteAccount(): Promise<void>` — calls the endpoint, then reuses the
  existing `logout()` for token-clearing (best-effort revoke of the now-cascaded refresh token,
  `setTokens(null)`, `setIsAuthenticated(false)`). Nothing else consumes this.

- [ ] **Step 1: Write the failing tests**

  In `frontend/tests/unit/lib/auth-context.test.tsx`, add a new test after the existing logout
  test:

  ```tsx
    it("deletes the account, then clears tokens and flips to unauthenticated", async () => {
      vi.mocked(fetch)
        .mockResolvedValueOnce(jsonResponse(200, { access_token: "a1", refresh_token: "r1", token_type: "bearer" }))
        .mockResolvedValueOnce(new Response(null, { status: 204 })) // DELETE /v1/users/me
        .mockResolvedValueOnce(jsonResponse(204, {})); // best-effort POST /v1/auth/logout
      const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
      await waitFor(() => expect(result.current.isLoading).toBe(false));
      await act(async () => {
        await result.current.login("me@example.com", "correct-horse-battery-staple");
      });

      await act(async () => {
        await result.current.deleteAccount();
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(apiClient.getAccessToken()).toBeNull();
      expect(localStorage.getItem("refresh_token")).toBeNull();
      const deleteCall = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === "DELETE");
      expect(deleteCall?.[0]).toContain("/v1/users/me");
    });
  ```

  In `frontend/tests/unit/components/app-shell.test.tsx`, add the mock for `deleteAccount` to the
  existing `vi.mock("@/lib/auth-context", ...)` call and add new tests. Replace the file's content
  with:

  ```tsx
  import { cleanup, render, screen } from "@testing-library/react";
  import userEvent from "@testing-library/user-event";
  import { afterEach, describe, expect, it, vi } from "vitest";

  const mockLogout = vi.fn();
  const mockDeleteAccount = vi.fn();
  vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({ logout: mockLogout, deleteAccount: mockDeleteAccount }),
  }));

  const mockPush = vi.fn();
  vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mockPush }) }));

  const mockSetTheme = vi.fn();
  let mockResolvedTheme = "light";
  vi.mock("next-themes", () => ({
    useTheme: () => ({ resolvedTheme: mockResolvedTheme, setTheme: mockSetTheme }),
  }));

  import { AppShell } from "@/components/app-shell";

  describe("AppShell", () => {
    afterEach(() => {
      cleanup();
      mockLogout.mockReset();
      mockDeleteAccount.mockReset();
      mockPush.mockReset();
      mockSetTheme.mockReset();
      mockResolvedTheme = "light";
    });

    it("renders the wordmark and its children", () => {
      render(
        <AppShell>
          <p>page content</p>
        </AppShell>,
      );

      expect(screen.getByText("AI Fitness Trainer")).toBeInTheDocument();
      expect(screen.getByText("page content")).toBeInTheDocument();
    });

    it("links the wordmark back to /", () => {
      render(
        <AppShell>
          <p>page content</p>
        </AppShell>,
      );

      expect(screen.getByRole("link", { name: "AI Fitness Trainer" })).toHaveAttribute(
        "href",
        "/",
      );
    });

    it("calls logout when the Log out button is clicked", async () => {
      mockLogout.mockResolvedValueOnce(undefined);
      render(
        <AppShell>
          <p>page content</p>
        </AppShell>,
      );
      const user = userEvent.setup();

      await user.click(screen.getByRole("button", { name: /log out/i }));

      expect(mockLogout).toHaveBeenCalled();
    });

    it("renders a theme toggle button", () => {
      render(
        <AppShell>
          <p>page content</p>
        </AppShell>,
      );

      expect(screen.getByRole("button", { name: /toggle theme/i })).toBeInTheDocument();
    });

    it("switches to dark when toggled while the resolved theme is light", async () => {
      mockResolvedTheme = "light";
      render(
        <AppShell>
          <p>page content</p>
        </AppShell>,
      );
      const user = userEvent.setup();

      await user.click(screen.getByRole("button", { name: /toggle theme/i }));

      expect(mockSetTheme).toHaveBeenCalledWith("dark");
    });

    it("switches to light when toggled while the resolved theme is dark", async () => {
      mockResolvedTheme = "dark";
      render(
        <AppShell>
          <p>page content</p>
        </AppShell>,
      );
      const user = userEvent.setup();

      await user.click(screen.getByRole("button", { name: /toggle theme/i }));

      expect(mockSetTheme).toHaveBeenCalledWith("light");
    });

    it("does not call deleteAccount until DELETE is typed to confirm", async () => {
      render(
        <AppShell>
          <p>page content</p>
        </AppShell>,
      );
      const user = userEvent.setup();

      await user.click(screen.getByRole("button", { name: /delete account/i }));
      await user.click(screen.getByRole("button", { name: /confirm/i }));

      expect(mockDeleteAccount).not.toHaveBeenCalled();
    });

    it("deletes the account and redirects to /login once DELETE is typed", async () => {
      mockDeleteAccount.mockResolvedValueOnce(undefined);
      render(
        <AppShell>
          <p>page content</p>
        </AppShell>,
      );
      const user = userEvent.setup();

      await user.click(screen.getByRole("button", { name: /delete account/i }));
      await user.type(screen.getByLabelText(/type delete to confirm/i), "DELETE");
      await user.click(screen.getByRole("button", { name: /confirm/i }));

      expect(mockDeleteAccount).toHaveBeenCalled();
      await vi.waitFor(() => expect(mockPush).toHaveBeenCalledWith("/login"));
    });

    it("cancels the confirmation without deleting", async () => {
      render(
        <AppShell>
          <p>page content</p>
        </AppShell>,
      );
      const user = userEvent.setup();

      await user.click(screen.getByRole("button", { name: /delete account/i }));
      await user.click(screen.getByRole("button", { name: /cancel/i }));

      expect(screen.queryByLabelText(/type delete to confirm/i)).not.toBeInTheDocument();
      expect(mockDeleteAccount).not.toHaveBeenCalled();
    });
  });
  ```

- [ ] **Step 2: Run the tests to verify they fail**

  Run: `cd frontend && npx vitest run tests/unit/lib/auth-context.test.tsx tests/unit/components/app-shell.test.tsx`
  Expected: FAIL — `deleteAccount` doesn't exist on the auth context; no "Delete account" button
  exists in `AppShell`.

- [ ] **Step 3: Add `deleteAccount` to `auth-context.tsx`**

  In `frontend/src/lib/auth-context.tsx`, add to the interface:

  ```tsx
  interface AuthContextValue {
    isAuthenticated: boolean;
    isLoading: boolean;
    login(email: string, password: string): Promise<void>;
    register(email: string, password: string, consent: boolean): Promise<void>;
    logout(): Promise<void>;
    deleteAccount(): Promise<void>;
  }
  ```

  add the function after `logout`:

  ```tsx
    async function deleteAccount() {
      await apiFetch("/v1/users/me", { method: "DELETE" });
      await logout(); // best-effort refresh-token revoke (harmless — it's already gone via
                       // cascade) + the same local token-clearing logout() always does
    }
  ```

  and add it to the provider value:

  ```tsx
    return (
      <AuthContext.Provider value={{ isAuthenticated, isLoading, login, register, logout, deleteAccount }}>
        {children}
      </AuthContext.Provider>
    );
  ```

- [ ] **Step 4: Add the UI to `AppShell`**

  Replace `frontend/src/components/app-shell.tsx` with:

  ```tsx
  "use client";

  import { useEffect, useState, type ReactNode } from "react";
  import Link from "next/link";
  import { useRouter } from "next/navigation";
  import { useTheme } from "next-themes";
  import { Moon, Sun } from "lucide-react";
  import { useAuth } from "@/lib/auth-context";
  import { Button } from "@/components/ui/button";
  import { Input } from "@/components/ui/input";
  import { Label } from "@/components/ui/label";
  import { Alert, AlertDescription } from "@/components/ui/alert";

  function ThemeToggle() {
    const { resolvedTheme, setTheme } = useTheme();
    const [mounted, setMounted] = useState(false);

    // next-themes' documented pattern for detecting client-mount to avoid an SSR/hydration mismatch
    // on resolvedTheme; the effect fires once and only affects this small leaf component, not a
    // cascading-render risk here.
    useEffect(() => {
      setMounted(true); // eslint-disable-line react-hooks/set-state-in-effect
    }, []);

    // Until mounted, resolvedTheme reflects the server render (no system-preference
    // read yet) — render a disabled placeholder rather than guess and risk a
    // hydration mismatch between server and client icon.
    if (!mounted) {
      return <Button variant="ghost" size="icon-sm" aria-label="Toggle theme" disabled />;
    }

    const isDark = resolvedTheme === "dark";

    return (
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label="Toggle theme"
        onClick={() => setTheme(isDark ? "light" : "dark")}
      >
        {isDark ? <Sun className="size-4" /> : <Moon className="size-4" />}
      </Button>
    );
  }

  function DeleteAccountControl() {
    const { deleteAccount } = useAuth();
    const router = useRouter();
    const [confirming, setConfirming] = useState(false);
    const [confirmText, setConfirmText] = useState("");
    const [isDeleting, setIsDeleting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    function cancel() {
      setConfirming(false);
      setConfirmText("");
      setError(null);
    }

    async function confirm() {
      setIsDeleting(true);
      setError(null);
      try {
        await deleteAccount();
        router.push("/login");
      } catch {
        setError("Could not delete the account. Try again.");
        setIsDeleting(false);
      }
    }

    if (!confirming) {
      return (
        <Button variant="ghost" size="sm" onClick={() => setConfirming(true)}>
          Delete account
        </Button>
      );
    }

    return (
      <div className="absolute right-6 top-14 z-10 w-72 space-y-3 rounded-md border border-border bg-card p-4 shadow-md">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <p className="text-sm text-muted-foreground">
          This permanently deletes your account and every video/analysis in it. This cannot be
          undone.
        </p>
        <div className="space-y-1">
          <Label htmlFor="delete-confirm">Type DELETE to confirm</Label>
          <Input
            id="delete-confirm"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={cancel}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            size="sm"
            disabled={confirmText !== "DELETE" || isDeleting}
            onClick={confirm}
          >
            Confirm
          </Button>
        </div>
      </div>
    );
  }

  export function AppShell({ children }: { children: ReactNode }) {
    const { logout } = useAuth();

    return (
      <div className="min-h-full">
        <header className="relative border-b border-border bg-card px-6 py-3">
          <div className="mx-auto flex max-w-2xl items-center justify-between">
            <Link href="/" className="text-base font-semibold">
              AI Fitness Trainer
            </Link>
            <div className="flex items-center gap-1">
              <ThemeToggle />
              <DeleteAccountControl />
              <Button variant="ghost" size="sm" onClick={() => logout()}>
                Log out
              </Button>
            </div>
          </div>
        </header>
        {children}
      </div>
    );
  }
  ```

  (`Button`'s `variant="destructive"` is already defined in `frontend/src/components/ui/button.tsx`
  — confirmed, no new variant needed.)

- [ ] **Step 5: Run the tests to verify they pass**

  Run: `cd frontend && npx vitest run tests/unit/lib/auth-context.test.tsx tests/unit/components/app-shell.test.tsx`
  Expected: PASS, all tests.

- [ ] **Step 6: Run the full frontend unit suite, lint, and build**

  Run: `cd frontend && npm test && npm run lint && npm run build`
  Expected: PASS — no regressions, no lint errors, clean production build.

- [ ] **Step 7: Commit**

  ```bash
  git add frontend/src/lib/auth-context.tsx frontend/src/components/app-shell.tsx \
    frontend/tests/unit/lib/auth-context.test.tsx frontend/tests/unit/components/app-shell.test.tsx
  git commit -m "feat(frontend): account deletion control in AppShell (privacy compliance)"
  ```

---

## After all 5 tasks

Run the full stack's tests one more time end to end (`cd backend && uv run --extra dev pytest`,
`cd frontend && npm test && npm run lint && npm run build`) before handing off to
`finishing-a-development-branch`. The Playwright e2e (`npx playwright test`) needs the real local
stack up (Postgres + backend + `fake-cv-service` or `cv-service` + frontend) — run it if that stack
is available; if not, note it as unverified in the final report rather than skipping silently.
