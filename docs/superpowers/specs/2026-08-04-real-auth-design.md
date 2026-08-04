# Design: Real Authentication (register / login / refresh / logout)

**Date:** 2026-08-04
**Author:** Fullstack role (compiled with Claude)
**Status:** APPROVED and IMPLEMENTED (2026-08-04) — see `docs/superpowers/plans/2026-08-04-real-auth.md`
for the task-by-task build record.
**Related:** `docs/superpowers/specs/2026-07-27-api-contract-design.md` (the public boundary this
extends), `backend/app/api/auth_dev.py` (the dev-only stub this lives alongside, untouched).

---

## 0. Context and goal

Before this work, `POST /v1/auth/dev-login` (`backend/app/api/auth_dev.py`) was the only way to get
a session: it takes just an email, upserts a `User` row with no password, and issues a JWT.
`backend/README.md`'s "Not yet built" list called out real authentication explicitly, and
`auth_dev.py`'s own docstring says it's meant to be "replaced by the auth plan."

**Goal:** add real, password-based authentication — registration, login, refresh-token rotation, and
logout — without touching the dev-login stub.

**Explicitly out of scope:** email verification and password reset (both need email-sending
infrastructure that doesn't exist), and replacing `auth_dev.py` (kept deliberately, see §1).

## 1. Decisions made (and why)

**`/v1/auth/dev-login` stays completely unchanged, living alongside the new real routes.** It's used
by the local docker-compose dev loop (`backend/README.md`) and by test fixtures
(`backend/tests/conftest.py`'s `user`/`auth_headers`). This overrides `auth_dev.py`'s own docstring
intent — a deliberate choice, not an oversight.

**`User.hashed_password` is nullable, not `NOT NULL`.** `auth_dev.py` creates users with no password
at all and had to stay untouched — a non-nullable column would break every dev-login insert. `NULL`
means "this account has no password credential." `authenticate_user` treats a `NULL` hash the same
as a wrong password: a generic 401, so a caller can't learn from the response that an account exists
but has no password. This also means the existing `user`/`other_user` test fixtures needed **zero
changes** — they already omit the field.

**Refresh tokens are opaque random strings, not JWTs.** Each is `secrets.token_urlsafe(32)` (256
bits of entropy); only its SHA-256 hex digest is ever stored — the raw token never touches the
database, the same principle as not storing raw passwords. Revocation requires a database check
regardless of token format, so a signed JWT refresh token would buy nothing while adding a second
signing secret to manage. SHA-256 (not bcrypt) is correct here: the token already has enough entropy
that a fast, deterministic hash isn't a weakness, and determinism is what makes an indexed equality
lookup possible — bcrypt's per-hash random salt would rule that out.

**Access tokens are unchanged in mechanism.** Real login/register/refresh issue access tokens through
the exact same `create_access_token`/`decode_access_token` (`app/security/tokens.py`) dev-login
already used. `app/api/deps.py`'s `get_current_user` — and therefore every protected route — needed
**zero changes**. The only new setting is `access_token_ttl_seconds` (15 minutes), separate from
dev-login's existing `jwt_ttl_seconds` (24 hours), left untouched.

**Refresh-token reuse triggers a bulk revoke, not a `replaced_by` chain.** If a refresh token that
has already been rotated (`revoked_at` set) is presented again, every currently-active refresh token
for that user is revoked in one query, and the caller gets the same generic 401 as any other
invalid-token case. This treats replay as "assume the token was stolen, kill every session for this
user" — simpler than tracking a rotation chain, and needs no extra column.

**Password hashing uses `bcrypt` directly, not `passlib`** (unmaintained, has broken against recent
bcrypt releases). bcrypt truncates input at 72 bytes, so request schemas enforce `max_length=72`
rather than silently discarding part of a longer password.

## 2. Data model

- `User.hashed_password: str | None` — `String(60)` (bcrypt hashes are always exactly 60 ASCII
  chars), nullable.
- `RefreshToken` (new table): `id` (UUID PK), `user_id` (FK → `users.id`, `ondelete="CASCADE"`),
  `token_hash` (`String(64)`, unique — SHA-256 hex digest), `issued_at` (server-default now),
  `expires_at`, `revoked_at` (nullable — `NULL` = active). Indexed on `user_id` and `expires_at`.

## 3. Token design

| | Access token | Refresh token |
|---|---|---|
| Format | JWT (unchanged `create_access_token`) | Opaque `secrets.token_urlsafe(32)` |
| Storage | Not persisted (self-contained) | SHA-256 hash persisted in `refresh_tokens` |
| TTL | `access_token_ttl_seconds` = 900s (15 min) | `refresh_token_ttl_seconds` = 2,592,000s (30 days) |
| Secret | Same `jwt_secret` as dev-login | None — DB row is authoritative |
| Revocation | Not possible (short-lived by design) | `revoked_at` column |

**Flow:** Register/Login → create/verify user → issue one access token + one new `refresh_tokens`
row → return both. Refresh → hash presented token → look up by `token_hash`. Not found → 401.
`revoked_at` set (reuse) → revoke *all* active tokens for that `user_id`, then 401. `expires_at` past
→ 401. Otherwise: rotate (mark this row revoked, insert a new one), issue a new access token, return
both. Logout → hash presented token → if found and active, set `revoked_at`. Always 204 — idempotent,
no enumeration signal.

## 4. Endpoints

| Method | Path | Status codes | Notes |
|---|---|---|---|
| `POST` | `/v1/auth/register` | 201, 409 (duplicate email), 422 (validation) | Returns a token pair |
| `POST` | `/v1/auth/login` | 200, 401 | Wrong password, unknown email, and a passwordless (dev-login-only) account all return the *same* generic message — no enumeration |
| `POST` | `/v1/auth/refresh` | 200, 401 | Unknown, expired, or reused token — same generic message |
| `POST` | `/v1/auth/logout` | 204 always | Idempotent |

## 5. Explicitly out of scope

- Rate limiting on `/login`/`/refresh` — no such library exists in the project yet.
- `auth_dev.py` remains a live, unauthenticated account-takeover primitive for any email,
  unconditionally mounted. Pre-existing behavior, deliberately left untouched — worth revisiting
  before any production deployment decision.
- No `GET /v1/auth/me` endpoint — a natural small follow-up once the frontend needs to know who's
  logged in (see `docs/superpowers/specs/2026-08-04-frontend-design.md`).
- Email verification, password reset — need email-sending infrastructure that doesn't exist.
