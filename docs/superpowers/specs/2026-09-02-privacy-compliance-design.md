# Design: Privacy Compliance (explicit consent + account deletion)

**Date:** 2026-09-02
**Author:** Fullstack role (compiled with Claude)
**Status:** APPROVED, not yet implemented.
**Related:** `docs/superpowers/specs/2026-08-04-real-auth-design.md` (the auth flow this extends),
`memoria/04-requisitos.md` CU-7 (existing per-attempt GDPR erasure, the pattern this reuses), the
upcoming memoria Ch.9 (Legislación y protección de datos) spec, which documents the result of this
work — this spec has to land first, since that chapter's SDD tasks grep-verify real code before
writing prose, same as every prior chapter.

---

## 0. Context and goal

Scoping memoria Ch.9 surfaced two real, fixable gaps in the app's data-protection posture:

1. **No explicit consent.** `Attempt.consent_at` already exists and is set automatically at upload
   time — but nothing the user ever affirmatively agreed to. There's no checkbox, no privacy policy
   page, nothing a court or a supervisor could point to as a lawful basis under GDPR Art. 6(1)(a).
2. **No account-level erasure.** `DELETE /v1/attempts/{id}` (CU-7) deletes one video/analysis
   completely (video file, cv-service job, DB row) — but there's no way to delete the *account*
   (the `User` row itself, with its email). A user's right to erasure is only half-implemented.

**Goal:** add registration-time explicit consent (backend-enforced) and a real account-deletion
endpoint + UI, so the upcoming Ch.9 chapter can honestly document a materially better legal posture
instead of just disclosing these as gaps.

**Explicitly out of scope** (staying MVP-frozen per the 2026-08-31 decision — these become
Ch.9 §9.6 "Limitaciones" disclosures, not this session's work):
- Data portability / export (no "download my data" endpoint).
- Account rectification (no "change my email" flow).
- App-level encryption at rest (relying on GCP/Vercel platform defaults only).
- A formal DPO/contact designation.
- Per-upload (as opposed to per-account) consent granularity.

## 1. Decisions made (and why)

**Consent is captured once, at registration — not per upload.** The account's only purpose is
uploading exercise videos for analysis; there is no second, separate processing purpose a user
could consent to independently. One checkbox at signup, referencing the privacy policy, covers
every future upload under that same stated purpose. Confirmed with the user (see brainstorm).

**Consent is backend-enforced, not just a UI checkbox.** `RegisterRequest.consent` is a required
field; the API 422s if it's not exactly `true`. A client that skips the checkbox cannot register —
mirrors how every other contract-level constraint in this app is enforced server-side, not trusted
to the frontend.

**New column `User.privacy_consent_at: datetime`, NOT NULL.** Mirrors the existing
`Attempt.consent_at` pattern exactly (same column shape, same "record *when* someone agreed, not
just *that* they did" rationale). NOT NULL is safe: every `User`-creation path is being updated in
this same change (see below), so there is no path left that can insert a user without it.

**`auth_dev.py`'s dev-login also sets `privacy_consent_at`.** It's the one other place a `User` row
gets created (`backend/app/api/auth_dev.py`, used by the local docker-compose dev loop and test
fixtures) — the NOT NULL column means it must set the field too. It sets it to "now" on first
creation, with no separate consent UI of its own. This is a deliberate, disclosed MVP simplification
(dev-login is a local-dev/test-only shortcut, not a path a real end user reaches), not a silent
gap — Ch.9 §9.6 names it explicitly.

**Account deletion reuses `delete_attempt`'s per-attempt cleanup, not just a DB cascade.**
`attempts.user_id` and `refresh_tokens.user_id` already have `ON DELETE CASCADE` — deleting the
`User` row alone would silently wipe those Postgres rows. But it would **not** delete the attempt's
video file on disk or its cv-service job, since `delete_attempt` (`backend/app/services/attempts.py:145`)
handles those with explicit calls (`storage.delete`, `cv_client.delete_job`), not a DB trigger. So
account deletion must loop every attempt the user owns, run the same cleanup `delete_attempt` does
for each one, and only then delete the `User` row (which cascades the now-empty attempt rows and
all refresh tokens for free). Getting this wrong would silently leave orphaned video files on disk
and orphaned jobs on the cv-service — a real erasure-guarantee violation, not just an untidy delete.

**No re-authentication (password re-entry) required to delete the account.** The endpoint requires
a valid JWT (the existing `get_current_user` dependency) plus a client-side type-to-confirm modal.
Given this is a school-project MVP, not a production consumer app handling payment data, requiring
an already-authenticated session plus a deliberate confirm step is proportionate. Documented as a
scope decision, not silently assumed.

**"Delete account" lives in the existing `AppShell` header, next to Logout — no new route.** A
dedicated `/account` settings page would be more conventional but is more surface area (new route,
new nav entry, new tests) than a single destructive action needs. Confirmed with the user.

## 2. Backend changes

### 2.1 Migration

New Alembic revision (there are two existing: `0001_initial`, `0002_auth` — this is `0003`):
`users.privacy_consent_at TIMESTAMPTZ NOT NULL`. No existing migration in this repo backfills a
new NOT NULL column, so there's no established idiom to match — implementer picks the standard
Alembic approach (add nullable, backfill any existing rows with `now()`, then `alter_column` to
NOT NULL in the same migration) or, simpler, add it `NOT NULL` with a one-time `server_default=
sa.func.now()` and drop the server default immediately after in the same `upgrade()` — either
works, since either way any pre-existing row (including the interview-demo account on production,
if any real registrations exist there) ends up with a real, if retroactive, `privacy_consent_at`
timestamp rather than a crash or a silently wrong value. Confirmed: `alembic upgrade head` already
runs automatically as its own service in `deploy/docker-compose.prod.yml` on every deploy, so this
migration reaches production the same way `0001`/`0002` did — no manual step needed.

### 2.2 `backend/app/models/user.py`

Add:
```python
privacy_consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

### 2.3 `backend/app/schemas/auth.py`

`RegisterRequest` gains `consent: bool`. Validate `consent is True` (not just truthy) — reject
`False` and reject a missing field (Pydantic already does the latter since there's no default).

### 2.4 `backend/app/services/auth.py` — `register_user`

Takes the new `consent: bool` (or just reads it from the caller-validated request — implementer's
call which is cleaner). Raises a new `ConsentRequired` exception if `not consent`; the route maps
it to `422`. Sets `privacy_consent_at=datetime.now(UTC)` on the created `User`.

### 2.5 `backend/app/api/auth_dev.py`

`dev_login`'s user-creation branch sets `privacy_consent_at=datetime.now(UTC)` alongside the
existing `User(id=..., email=...)` construction. No consent field on `DevLoginRequest` — this stays
a dev-only shortcut, per the decision above.

### 2.6 New endpoint: `DELETE /v1/users/me`

`backend/app/api/users.py` (new file — mirrors `attempts.py`'s router shape), registered in
`backend/app/main.py` alongside the other routers.

```python
@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(user: CurrentUser, db: DbDep, storage: StorageDep, cv_client: CVClientDep) -> None:
    attempts = (await db.execute(sa.select(Attempt).where(Attempt.user_id == user.id))).scalars().all()
    for attempt in attempts:
        storage.delete(attempt.original_video_ref)
        if attempt.cv_job_id:
            await cv_client.delete_job(attempt.cv_job_id)
    await db.delete(user)  # cascades attempts + refresh_tokens
    await db.commit()
```

Note the deliberate ordering, same rationale as `delete_attempt`'s own docstring: external cleanup
(storage, cv-service) happens *before* the DB delete. Unlike `delete_attempt`, a `CVServiceError`
mid-loop here is a real edge case worth an explicit decision — implementer flags it in the task
report rather than picking silently: either (a) let it propagate and abort (some attempts cleaned,
user row survives, matching `delete_attempt`'s existing "fail safe, let them retry" philosophy), or
(b) log-and-continue so one bad cv-service job doesn't block the rest of a real erasure request. **(a)
is the recommended default** — consistent with the existing per-attempt behavior — but flag it for a
ruling if the implementer sees a reason to prefer (b).

### 2.7 New service module `backend/app/services/users.py` (optional split)

Implementer's call whether the loop above lives directly in the route (matching `attempts.py`'s own
mix of thin-route/route-with-logic) or gets extracted to a `delete_account(db, user, storage,
cv_client)` service function (matching `delete_attempt`'s placement in `services/attempts.py`) for
testability. Recommend the latter — keeps the route thin like every other route in this API and
makes the function unit-testable without going through FastAPI's dependency injection.

## 3. Frontend changes

### 3.1 Privacy policy page — `frontend/src/app/privacy/page.tsx` (new)

Plain static page, matching the existing page style (`Card`-based, no new dependencies). Plain-
language content covering: what's collected (account email; uploaded video; derived exercise
scores/angles/error codes; an annotated copy of the video), why (to analyze exercise technique,
the account's sole purpose), how long (30 days, then automatically deleted), and the two erasure
options (delete one analysis, or delete the whole account) with the pointer to Delete Account in the
header. No new route guard needed — a privacy policy is public, unauthenticated pages should reach
it too (link it from `/register` before login exists).

### 3.2 Register form — `frontend/src/app/register/page.tsx`

Add a required checkbox: *"I agree that videos I upload will be processed to analyze my exercise
technique, per the [Privacy Policy](/privacy)."* (English, matching the rest of the UI's English
copy per README precedent.) Submit button stays disabled until checked (client-side UX nicety); the
real enforcement is the backend 422. `useAuth().register(email, password)` gains a third `consent:
boolean` argument, threaded through to the `apiFetch` call in `auth-context.tsx`.

### 3.3 Account deletion — `AppShell` (`frontend/src/components/app-shell.tsx`)

A "Delete account" text button next to the existing "Log out" button. Click opens a confirm modal
(new small component, or an inline conditional render — implementer's call given the scope) with:
a warning that this permanently deletes the account and all attempts, a text input that must exactly
match `DELETE` before the confirm button enables, Cancel/Confirm actions. On confirm: call
`DELETE /v1/users/me` via `apiFetch`, then clear stored tokens and redirect to `/login` — reuse
`auth-context.tsx`'s existing token-clearing logic (the same path `logout()` already exercises)
rather than duplicating it.

## 4. Testing

Follows this repo's existing pattern (real behavior, not mocks, per every prior chapter/task in
this project):
- Backend: `test_register_login.py` gains cases for missing/false `consent` (422), and a new
  `test_users.py` (or extend an existing file) covers account deletion — attempts' videos really
  gone from storage, cv-service `delete_job` really called for each, refresh tokens really gone,
  re-login with the same credentials really fails post-deletion.
- Frontend: `video-upload-form`-adjacent test conventions apply — a new `register` test case for
  the disabled-until-checked behavior and the consent field reaching the API call; a new test
  (component or e2e) for the delete-account confirm flow (`DELETE` typed → button enabled → API
  called → redirect).
- The existing Playwright `full-flow.spec.ts` registers a throwaway account already — it will need
  the new checkbox checked to keep passing; implementer updates it as part of this work, not as an
  afterthought.

## 5. Out of scope (see §0) — reiterated for the implementer

Do not build data export, account-info editing, app-level at-rest encryption, or a DPO contact
page. These become disclosed limitations in Ch.9 §9.6, matching this project's established honesty
pattern (Ch.7 §7.6, Ch.4/Ch.5's disclosed gaps) rather than new work.
