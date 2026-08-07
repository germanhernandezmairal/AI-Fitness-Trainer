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

See `.env.example` for all variables — including `CORS_ALLOWED_ORIGINS`, the JSON list of
origins allowed to call the API (e.g. the Next.js dev server at `http://localhost:3000`).

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

This uses `fake-cv-service`, which ignores the video and returns a canned result — fast, no
MediaPipe/OpenCV build, and supports deterministic failure injection (see its README). To exercise
the real analysis pipeline instead:

```bash
docker compose --profile real-cv up -d db cv-service
```

(`cv-service` and `fake-cv` both listen on 9000 and are drop-in replacements for each other —
don't run both at once.)

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
| `POST` | `/v1/auth/dev-login` | public | **dev only**, no password; kept alongside real auth for the local dev loop |
| `POST` | `/v1/auth/register` | public | email + password, returns an access/refresh token pair |
| `POST` | `/v1/auth/login` | public | email + password, returns an access/refresh token pair |
| `POST` | `/v1/auth/refresh` | public | rotates a refresh token; reuse of an already-rotated token revokes the whole session family |
| `POST` | `/v1/auth/logout` | public | revokes a refresh token, idempotent |
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

- Rate limiting on `/v1/auth/login` and `/v1/auth/refresh`.
- Email verification / password reset — no email-sending infrastructure exists yet.
- S3/MinIO storage — `LocalFilesystemStorage` is the only `Storage` implementation.
- Frontend.
