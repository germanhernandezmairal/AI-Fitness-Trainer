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
