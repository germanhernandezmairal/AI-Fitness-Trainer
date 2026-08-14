# Free-Tier Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce the configuration, Dockerfiles, CI workflow, and a human-executed runbook needed
to deploy this project on free-tier infrastructure (Vercel for the frontend, one Oracle
Always-Free ARM VM for backend/cv-service/Postgres) — verified locally wherever verification is
possible without real cloud accounts, since no infrastructure is provisioned as part of this plan.

**Architecture:** Two new services get containerized for the first time (`backend/Dockerfile` is
new; `cv-service/Dockerfile` already exists but has never been built for ARM64), then wired
together with a production-shaped Docker Compose overlay + Caddy reverse proxy, a DB backup
script, a GitHub Actions deploy workflow, and a runbook a human follows to actually provision the
account-level resources (cloud accounts, DNS, secrets) this plan cannot create unattended.

**Tech Stack:** Docker + Docker Buildx (via Colima on this Mac), Docker Compose, Caddy (reverse
proxy + automatic Let's Encrypt TLS), GitHub Actions, DuckDNS, Oracle Cloud Always-Free (Ampere A1
ARM VM), Vercel.

**Spec:** `docs/superpowers/specs/2026-08-14-free-tier-deployment-design.md`

## Global Constraints

- No infrastructure is provisioned by this plan's tasks — every task produces
  configuration/code/docs verified locally; actual cloud provisioning is a human-executed step
  documented in Task 6, not run by an implementer (spec §0).
- Backend + cv-service + Postgres deploy together on one Oracle Always-Free VM via Docker Compose;
  frontend deploys separately to Vercel (spec §2).
- Database stays self-hosted Postgres 16 in Docker Compose — no Oracle Autonomous DB, no new
  connection-string abstraction (spec §3).
- Video storage stays on local disk via the backend's existing storage abstraction — no new
  object-storage adapter code (spec §4).
- `mediapipe`/`opencv-python` ARM64 compatibility must be verified by an actual
  `docker buildx build --platform linux/arm64` run, not assumed (spec §9).
- This Mac has no Docker installed — Task 1 installs it via Colima (CLI-only, no GUI app), per an
  explicit decision already made for this plan.
- Secrets: deploy-time secrets (SSH key, VM host) as GitHub Actions repo secrets; app-runtime
  secrets (JWT key, webhook secret, `CV_API_KEY`, DB password) live only in a `.env` file placed
  directly on the VM, never committed and never passed through CI (spec §6).

---

### Task 1: Install Docker via Colima, verify `cv-service` builds and runs on ARM64

**Files:**
- Create: `deploy/arm64-verification.md`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: a working local Docker/Buildx environment (Colima) that every later task's build
  verification steps rely on. Produces no code interfaces — this task is a risk-gate plus a
  written record of its result.

- [ ] **Step 1: Install Colima and the Docker CLI**

Run:
```bash
brew install colima docker docker-buildx
mkdir -p ~/.docker/cli-plugins
ln -sfn "$(brew --prefix)/opt/docker-buildx/bin/docker-buildx" ~/.docker/cli-plugins/docker-buildx
```
Expected: both `brew install` commands complete without error. The `ln` makes `docker buildx`
available as a CLI subcommand (Homebrew's `docker-buildx` formula installs the binary but doesn't
wire it into `~/.docker/cli-plugins/` automatically).

- [ ] **Step 2: Start Colima and verify Docker works**

Run:
```bash
colima start --cpu 2 --memory 4
docker run --rm hello-world
```
Expected: `colima start` reports a running VM (this Mac is Apple Silicon, so Colima's default VM
architecture is already `aarch64` — no cross-architecture emulation needed for this step).
`docker run --rm hello-world` prints Docker's "Hello from Docker!" message. If `colima start`
fails, stop here — every later task depends on this environment.

- [ ] **Step 3: Build `cv-service` for `linux/arm64`**

Run (from the repo root):
```bash
docker buildx build --platform linux/arm64 -t cv-service-arm64-test --load cv-service/
```
Expected: PASS — the build completes without error. This is the step that actually answers spec
§9's open risk question: do `opencv-python==5.0.0.93` and `mediapipe==0.10.14` (both pinned in
`cv-service/requirements.txt`) have installable ARM64 wheels? If `pip install` fails inside the
build for either package, note the exact error in `deploy/arm64-verification.md` (Step 6) — this
would be a real spec-level finding, not something to silently work around.

- [ ] **Step 4: Run the built image and smoke-test it with a real video**

Run:
```bash
docker run -d --name cv-service-arm64-test -p 9000:9000 \
  -e CV_API_KEY=dev-cv-api-key \
  -e CV_WEBHOOK_SECRET=dev-webhook-secret-change-me-in-production \
  -e CV_SERVICE_BASE_URL=http://localhost:9000 \
  cv-service-arm64-test

sleep 3

curl -sf -X POST http://localhost:9000/v1/jobs \
  -H "X-API-Key: dev-cv-api-key" \
  -F "exercise_type=squat" \
  -F "video=@backend/tests/fixtures/squat.mp4;type=video/mp4" | tee /tmp/cv-arm64-job.json

JOB_ID=$(python3 -c "import json; print(json.load(open('/tmp/cv-arm64-job.json'))['job_id'])")

for i in $(seq 1 30); do
  STATUS_JSON=$(curl -sf "http://localhost:9000/v1/jobs/$JOB_ID" -H "X-API-Key: dev-cv-api-key")
  echo "$STATUS_JSON"
  STATUS=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['status'])" "$STATUS_JSON")
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  sleep 2
done
```
Expected: the final polled response has `"status": "completed"` with a real `result` object
(reps detected, scores, `annotated_video_url`) — the same shape confirmed working on this Mac's
native architecture earlier in this project (6 reps correctly detected on `squat.mp4`). A
`"status": "failed"` result, or the loop timing out still `"queued"`/`"processing"` after 30
tries, is a real finding to record, not to explain away.

- [ ] **Step 5: Tear down the test container**

Run:
```bash
docker rm -f cv-service-arm64-test
```

- [ ] **Step 6: Write the verification record**

Create `deploy/arm64-verification.md`:

```markdown
# ARM64 Build Verification

Verifies spec §9's open risk: does `cv-service` (full `opencv-python` + `mediapipe`, non-headless)
actually build and run correctly on `linux/arm64` — the architecture of Oracle's Always-Free
Ampere A1 VM — before any deployment work depends on it.

**Environment:** Colima (Docker CLI via Homebrew), native `aarch64` VM on this Apple Silicon Mac —
no cross-architecture emulation involved, so this closely matches what the real Oracle VM will run.

**Build:** `docker buildx build --platform linux/arm64 -t cv-service-arm64-test --load cv-service/`
— [PASS/FAIL — fill in from Step 3's real output, including the exact error text if it failed].

**Smoke test:** uploaded `backend/tests/fixtures/squat.mp4` to the running ARM64 container via
`POST /v1/jobs`, polled `GET /v1/jobs/{id}` until terminal — [PASS/FAIL — fill in from Step 4's
real output: final status, rep count, whether it matches the known-good 6-rep result from prior
native-architecture testing on this project].

**Conclusion:** [state plainly whether ARM64 deployment is viable for `cv-service` based on the
above, or what specifically needs to change if it isn't].
```

Fill in the bracketed parts with the actual Step 3/4 output — this file is a real record, not a
template to leave as-is.

- [ ] **Step 7: Commit**

```bash
cd "/Volumes/Expansion/Software Builder/Web-App Projects/AI Fitness Trainer"
git add deploy/arm64-verification.md
git commit -m "docs(deploy): verify cv-service builds and runs on linux/arm64"
```

---

### Task 2: Add `backend/Dockerfile`, verify it builds and runs on ARM64

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/.dockerignore`

**Interfaces:**
- Consumes: the working Colima/Buildx environment from Task 1.
- Produces: `backend/Dockerfile`, an image that Task 3's production Compose file references by
  build context `../backend`. The image's `/health` endpoint (already implemented at
  `backend/app/main.py:67-69`, returns `{"status": "ok"}`) is what Task 3's verification and any
  later container-orchestration health check rely on.

- [ ] **Step 1: Create `backend/.dockerignore`**

Create `backend/.dockerignore`:
```
.venv
__pycache__
*.pyc
.pytest_cache
var/
.env
.env.local
```
This keeps the local dev virtualenv, cached bytecode, and any real `.env` file (which must never
end up baked into an image layer) out of the build context.

- [ ] **Step 2: Create `backend/Dockerfile`**

Create `backend/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /srv

# uv is how this project manages Python dependencies locally (see pyproject.toml/uv.lock) —
# installing it here keeps the container's dependency resolution identical to local dev instead
# of introducing a second, divergent pip-based install path.
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /usr/local/bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN mkdir -p /srv/var/videos

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```
Migrations are deliberately NOT run automatically in the image's `CMD` — Task 3's production
Compose file runs `alembic upgrade head` as an explicit one-shot step before starting the backend
service, so a bad migration fails loudly during deploy instead of silently inside a
restart-looping container.

- [ ] **Step 3: Build the image for `linux/arm64`**

Run (from the repo root):
```bash
docker buildx build --platform linux/arm64 -t backend-arm64-test --load backend/
```
Expected: PASS. `sqlalchemy[asyncio]`, `asyncpg`, `bcrypt`, `av`, and every other dependency in
`backend/pyproject.toml` publish ARM64 wheels for Python 3.11 — this build is lower-risk than
Task 1's (no OpenCV/MediaPipe), but must still actually be run, not assumed.

- [ ] **Step 4: Run it against a real Postgres and confirm `/health`**

Run:
```bash
docker network create fitness-arm64-test-net

docker run -d --name pg-arm64-test --network fitness-arm64-test-net \
  -e POSTGRES_USER=fitness -e POSTGRES_PASSWORD=fitness -e POSTGRES_DB=fitness \
  postgres:16

sleep 5

docker run --rm --network fitness-arm64-test-net \
  -e DATABASE_URL=postgresql+asyncpg://fitness:fitness@pg-arm64-test:5432/fitness \
  backend-arm64-test uv run alembic upgrade head

docker run -d --name backend-arm64-test --network fitness-arm64-test-net -p 8001:8000 \
  -e DATABASE_URL=postgresql+asyncpg://fitness:fitness@pg-arm64-test:5432/fitness \
  backend-arm64-test

sleep 3

curl -sf http://localhost:8001/health
```
Expected: the final `curl` prints `{"status":"ok"}`. If `alembic upgrade head` fails, that's a
real finding (check the error against `backend/alembic/versions/` — every migration in this repo
has already run successfully against Postgres 16 in CI-equivalent local testing, so a failure here
would point at something ARM64/container-specific, not a migration bug).

- [ ] **Step 5: Tear down the test containers**

Run:
```bash
docker rm -f backend-arm64-test pg-arm64-test
docker network rm fitness-arm64-test-net
```

- [ ] **Step 6: Commit**

```bash
cd "/Volumes/Expansion/Software Builder/Web-App Projects/AI Fitness Trainer"
git add backend/Dockerfile backend/.dockerignore
git commit -m "feat(backend): add Dockerfile, verified on linux/arm64"
```

---

### Task 3: Production Docker Compose overlay + Caddy reverse proxy

**Files:**
- Create: `deploy/docker-compose.prod.yml`
- Create: `deploy/Caddyfile`
- Create: `deploy/.env.example`

**Interfaces:**
- Consumes: `backend/Dockerfile` (Task 2) and `cv-service/Dockerfile` (pre-existing, ARM64-verified
  by Task 1) as build contexts.
- Produces: the Compose stack Task 6's runbook tells a human to run on the actual Oracle VM, and
  the `.env.example` Task 6 tells them to copy and fill in with real secrets.

- [ ] **Step 1: Create `deploy/.env.example`**

Create `deploy/.env.example`:
```
# Copy to deploy/.env on the VM and fill in real values. Never commit deploy/.env.

# --- Domain (set up via DuckDNS, see deploy/README.md) ---
DOMAIN=ai-fitness-trainer-api.duckdns.org

# --- Database ---
POSTGRES_USER=fitness
POSTGRES_PASSWORD=change-me-generate-a-real-password
POSTGRES_DB=fitness

# --- Backend secrets (generate real random values, do not reuse the dev defaults below) ---
JWT_SECRET=change-me-generate-a-real-secret-at-least-32-bytes
CV_API_KEY=change-me-generate-a-real-key
CV_WEBHOOK_SECRET=change-me-generate-a-real-secret

# --- CORS: the Vercel frontend's real production URL ---
CORS_ALLOWED_ORIGINS=["https://ai-fitness-trainer.vercel.app"]
```

- [ ] **Step 2: Create `deploy/docker-compose.prod.yml`**

Create `deploy/docker-compose.prod.yml`:
```yaml
services:
  db:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      retries: 10

  migrate:
    build: ../backend
    restart: "no"
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
    command: ["uv", "run", "alembic", "upgrade", "head"]

  backend:
    build: ../backend
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
      migrate:
        condition: service_completed_successfully
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      JWT_SECRET: ${JWT_SECRET}
      CV_SERVICE_URL: http://cv-service:9000
      CV_API_KEY: ${CV_API_KEY}
      CV_WEBHOOK_SECRET: ${CV_WEBHOOK_SECRET}
      BACKEND_PUBLIC_URL: https://${DOMAIN}
      CORS_ALLOWED_ORIGINS: ${CORS_ALLOWED_ORIGINS}
    volumes:
      - videos:/srv/var/videos

  cv-service:
    build: ../cv-service
    restart: unless-stopped
    environment:
      CV_API_KEY: ${CV_API_KEY}
      CV_WEBHOOK_SECRET: ${CV_WEBHOOK_SECRET}
      CV_SERVICE_BASE_URL: http://cv-service:9000

  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    depends_on:
      - backend
    ports:
      - "80:80"
      - "443:443"
    environment:
      DOMAIN: ${DOMAIN}
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config

volumes:
  pgdata:
  videos:
  caddy_data:
  caddy_config:
```
Note this file is standalone (not a Compose "override" layered on `backend/docker-compose.yml`
via `-f`) — the dev compose file targets a laptop (bind-mounted `fake-cv`/`cv-service` source,
host-exposed Postgres port for local `psql`), while this one targets the VM (named volumes, no
host port exposure except through Caddy, real secrets via `${VAR}` substitution from `deploy/.env`).
Keeping them separate avoids fighting Compose's override-merge semantics for genuinely different
deployment shapes.

- [ ] **Step 3: Create `deploy/Caddyfile`**

Create `deploy/Caddyfile`:
```
{$DOMAIN} {
	reverse_proxy backend:8000
}
```
Caddy reads `{$DOMAIN}` from the `DOMAIN` environment variable (wired in Step 2's `caddy` service)
and automatically obtains/renews a Let's Encrypt certificate for it — no manual `certbot` step.

- [ ] **Step 4: Validate the Compose file's syntax**

Run (from the repo root, with dummy values since real secrets don't exist yet):
```bash
DOMAIN=test.example.com POSTGRES_USER=fitness POSTGRES_PASSWORD=fitness POSTGRES_DB=fitness \
  JWT_SECRET=test-secret-at-least-32-bytes-long-xxxxxxxxx CV_API_KEY=test CV_WEBHOOK_SECRET=test \
  CORS_ALLOWED_ORIGINS='["http://localhost:3000"]' \
  docker compose -f deploy/docker-compose.prod.yml config
```
Expected: PASS — prints the fully-resolved Compose configuration with no errors. This confirms
the YAML is valid and every `${VAR}` substitution resolves.

- [ ] **Step 5: Validate the Caddyfile's syntax**

Run:
```bash
docker run --rm -v "$(pwd)/deploy/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2-alpine \
  caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
```
Expected: PASS — Caddy reports the config is valid. This does not test real certificate issuance
(that needs a real public domain and inbound port 80/443, which don't exist until Task 6's
provisioning happens), only that the file itself is well-formed.

- [ ] **Step 6: Bring up the full stack locally and confirm the real wiring works**

Run (from the repo root — this reuses Task 1/2's now-installed Colima environment, and proves the
whole production-shaped stack works together, not just each image individually):
```bash
cd deploy
DOMAIN=localhost POSTGRES_USER=fitness POSTGRES_PASSWORD=fitness POSTGRES_DB=fitness \
  JWT_SECRET=test-secret-at-least-32-bytes-long-xxxxxxxxx \
  CV_API_KEY=test-cv-key CV_WEBHOOK_SECRET=test-webhook-secret \
  CORS_ALLOWED_ORIGINS='["http://localhost:3000"]' \
  docker compose -f docker-compose.prod.yml up -d --build db migrate backend cv-service

sleep 10
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs backend | tail -20
```
Expected: `docker compose ps` shows `db`, `backend`, and `cv-service` as `running`/`healthy`, and
`migrate` as `exited (0)` (a one-shot job that completes, not a long-running service — exit code 0
means the migration succeeded). `backend`'s logs show a clean `Application startup complete` with
no crash loop — this is what actually matters here: `backend`'s `CV_SERVICE_URL` points at
`http://cv-service:9000` (a real container, not `fake-cv`) and its `DATABASE_URL` points at `db`
over the Compose network for the first time, so a clean startup proves that wiring is correct. A
restart loop or an error in the logs means the service wiring is broken and must be fixed before
continuing.

Then confirm the backend is actually reachable over the network (its port is deliberately not
published to the host — only Caddy should be reachable in production — so reach it via a
throwaway container on the same Compose network instead of `localhost`):
```bash
NETWORK=$(docker compose -f docker-compose.prod.yml ps --format '{{.Networks}}' backend | head -1)
docker run --rm --network "${NETWORK}" curlimages/curl:latest -sf http://backend:8000/health
```
Expected: prints `{"status":"ok"}`.

Run `docker compose -f docker-compose.prod.yml down -v` afterward to tear down (the `-v` also
removes the test's named volumes, which is correct here since they hold only throwaway test data).

- [ ] **Step 7: Commit**

```bash
cd "/Volumes/Expansion/Software Builder/Web-App Projects/AI Fitness Trainer"
git add deploy/docker-compose.prod.yml deploy/Caddyfile deploy/.env.example
git commit -m "feat(deploy): add production Docker Compose stack with Caddy reverse proxy"
```

---

### Task 4: Nightly database backup script

**Files:**
- Create: `deploy/backup-db.sh`

**Interfaces:**
- Consumes: the `db` service name and `POSTGRES_*` env vars from Task 3's
  `deploy/docker-compose.prod.yml`.
- Produces: `deploy/backup-db.sh`, which Task 6's runbook tells the human to install as a cron job
  on the VM.

- [ ] **Step 1: Create `deploy/backup-db.sh`**

Create `deploy/backup-db.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail

# Nightly Postgres backup: dumps the `db` service (from deploy/docker-compose.prod.yml), gzips it,
# and uploads it to Oracle Object Storage. Run via cron on the VM — see deploy/README.md for the
# crontab line. Requires: this script's directory contains docker-compose.prod.yml and .env
# (loaded automatically by `docker compose`), and the `oci` CLI is installed and configured
# (`oci setup config`) with access to the free-tier Object Storage bucket named in
# OCI_BACKUP_BUCKET below.

cd "$(dirname "$0")"

TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
DUMP_FILE="/tmp/fitness-backup-${TIMESTAMP}.sql.gz"
OCI_BACKUP_BUCKET="${OCI_BACKUP_BUCKET:?Set OCI_BACKUP_BUCKET in the environment or crontab line}"

# Source POSTGRES_* from deploy/.env so this script works standalone (not only via `docker compose`).
set -a
# shellcheck disable=SC1091
source .env
set +a

docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" | gzip > "${DUMP_FILE}"

oci os object put \
  --bucket-name "${OCI_BACKUP_BUCKET}" \
  --file "${DUMP_FILE}" \
  --name "postgres/$(basename "${DUMP_FILE}")"

rm -f "${DUMP_FILE}"

echo "Backup complete: postgres/$(basename "${DUMP_FILE}") uploaded to ${OCI_BACKUP_BUCKET}"
```

- [ ] **Step 2: Make it executable**

Run:
```bash
chmod +x deploy/backup-db.sh
```

- [ ] **Step 3: Syntax-check the script**

Run:
```bash
bash -n deploy/backup-db.sh
```
Expected: PASS — no output means no syntax errors.

- [ ] **Step 4: Test the dump portion locally (the part that doesn't need real Oracle credentials)**

Run (using the same throwaway Postgres pattern as Task 2's verification — this tests the `pg_dump`
half of the script directly, since the `oci os object put` half genuinely cannot be tested until a
real Oracle bucket exists, which is out of scope per this plan's Global Constraints):
```bash
docker run -d --name pg-backup-test \
  -e POSTGRES_USER=fitness -e POSTGRES_PASSWORD=fitness -e POSTGRES_DB=fitness \
  -p 5434:5432 postgres:16

sleep 5

docker exec pg-backup-test pg_dump -U fitness fitness | gzip > /tmp/backup-test.sql.gz
gzip -t /tmp/backup-test.sql.gz && echo "gzip integrity OK"
zcat /tmp/backup-test.sql.gz | head -5

docker rm -f pg-backup-test
rm -f /tmp/backup-test.sql.gz
```
Expected: `gzip integrity OK` prints, and the `zcat` preview shows real `pg_dump` SQL header
comments (`-- PostgreSQL database dump`) — confirms the dump-and-compress logic this script relies
on genuinely works, independent of the Oracle-specific upload step.

- [ ] **Step 5: Commit**

```bash
cd "/Volumes/Expansion/Software Builder/Web-App Projects/AI Fitness Trainer"
git add deploy/backup-db.sh
git commit -m "feat(deploy): add nightly database backup script"
```

---

### Task 5: GitHub Actions backend deploy workflow

**Files:**
- Create: `.github/workflows/deploy-backend.yml`

**Interfaces:**
- Consumes: `deploy/docker-compose.prod.yml` (Task 3) — the workflow's remote command targets this
  file by its path on the VM.
- Produces: the workflow Task 6's runbook tells the human to enable (by adding the
  `DEPLOY_SSH_KEY`/`DEPLOY_HOST`/`DEPLOY_USER` repo secrets it references) once the VM exists.

- [ ] **Step 1: Create `.github/workflows/deploy-backend.yml`**

Create `.github/workflows/deploy-backend.yml`:
```yaml
name: Deploy backend

on:
  push:
    branches: [main]
    paths:
      - "backend/**"
      - "cv-service/**"
      - "deploy/docker-compose.prod.yml"
      - "deploy/Caddyfile"
      - ".github/workflows/deploy-backend.yml"
  workflow_dispatch: {}

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy over SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: ${{ secrets.DEPLOY_USER }}
          key: ${{ secrets.DEPLOY_SSH_KEY }}
          script: |
            cd ~/ai-fitness-trainer
            git pull origin main
            cd deploy
            docker compose -f docker-compose.prod.yml up -d --build db migrate backend cv-service caddy
```
`appleboy/ssh-action` is a widely-used, actively-maintained action for exactly this pattern (SSH in,
run a script) — pinned to a specific version tag (`v1.0.3`) rather than a floating `@master`, so
this workflow doesn't silently change behavior on a future action update.

- [ ] **Step 2: Validate the workflow YAML is well-formed**

Run:
```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-backend.yml'))" && echo "YAML valid"
```
Expected: `YAML valid` prints, no exception. This cannot verify the workflow actually deploys
successfully — that needs a real VM and real repo secrets, which don't exist until Task 6's
human-executed provisioning happens (Global Constraints).

- [ ] **Step 3: Commit**

```bash
cd "/Volumes/Expansion/Software Builder/Web-App Projects/AI Fitness Trainer"
git add .github/workflows/deploy-backend.yml
git commit -m "feat(deploy): add GitHub Actions backend deploy workflow"
```

---

### Task 6: Deployment runbook

**Files:**
- Create: `deploy/README.md`
- Modify: `backend/README.md` (add one cross-reference line)

**Interfaces:**
- Consumes: every file produced by Tasks 1-5 — this task's whole job is to document how a human
  strings them together against real cloud accounts.
- Produces: nothing later tasks depend on (this is the final task).

- [ ] **Step 1: Create `deploy/README.md`**

Create `deploy/README.md`:
```markdown
# Deployment Runbook

Free-tier deployment: Next.js frontend on Vercel, backend + cv-service + Postgres on one Oracle
Cloud Always-Free ARM VM. Full rationale: `docs/superpowers/specs/2026-08-14-free-tier-deployment-design.md`.

**This is a human-executed runbook, not something to automate end-to-end** — cloud account
creation and VM provisioning need a real person clicking through billing/identity screens.

## 1. Provision the Oracle Always-Free VM

1. Create an Oracle Cloud account at <https://www.oracle.com/cloud/free/> if you don't have one.
2. In the console: **Compute → Instances → Create Instance**.
3. Choose the **Ampere A1 (ARM)** shape, configured at **2 OCPUs / 12 GB RAM** (Oracle's current
   Always-Free ceiling as of 2026-08 — verify this hasn't changed again since Oracle has cut it
   before with no announcement; check the console's "Always Free eligible" badge before creating).
4. Choose a recent **Ubuntu** or **Oracle Linux** ARM image.
5. **Known issue:** creating the free Ampere A1 shape often fails with an "out of capacity" error
   on the first (or fifth) attempt — this is a widely-reported, expected friction point, not a
   sign anything is misconfigured. Retry; some people need to retry over hours or days. Don't
   switch to a paid shape to work around it — that violates the free-tier constraint this whole
   design exists to satisfy.
6. Once created, note the VM's public IP and open inbound ports **22** (SSH), **80**, and **443**
   in its attached Security List / Network Security Group — Oracle blocks these by default.

## 2. Set up the domain (DuckDNS)

1. Sign in at <https://www.duckdns.org/> (free, no cost) and create a subdomain, e.g.
   `ai-fitness-trainer-api.duckdns.org`, pointed at the VM's public IP from Step 1.
2. On the VM, install DuckDNS's update cron job (keeps the DNS record current if Oracle ever
   reassigns the free-tier IP on a VM restart) — DuckDNS's own site provides a copy-pasteable
   install script for this once you're signed in; follow it as given rather than reinventing it.

## 3. Initial VM setup

SSH into the VM (`ssh ubuntu@<VM public IP>`), then:

```bash
# Install Docker + Compose plugin (Ubuntu's official convenience script)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# log out and back in for the group change to take effect

# Clone the repo
git clone https://github.com/germanhernandezmairal/ai-fitness-trainer.git ~/ai-fitness-trainer
cd ~/ai-fitness-trainer/deploy

# Create the real secrets file — copy the template and fill in real values
cp .env.example .env
nano .env  # set DOMAIN to your DuckDNS hostname from step 2, generate real random
           # POSTGRES_PASSWORD / JWT_SECRET / CV_API_KEY / CV_WEBHOOK_SECRET values
           # (e.g. `openssl rand -hex 32` for each secret), and set CORS_ALLOWED_ORIGINS
           # to your real Vercel URL from step 5 below

docker compose -f docker-compose.prod.yml up -d --build
```

## 4. Set up the nightly backup

1. Create an Oracle Object Storage bucket for backups (**Storage → Buckets → Create Bucket**),
   note its name.
2. Install and configure the `oci` CLI on the VM: `bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)"`,
   then `oci setup config` (follow its prompts — needs an API key generated from your Oracle
   account's console, under **Profile → API Keys**).
3. Add a crontab entry to run the nightly backup:
   ```bash
   crontab -e
   # add this line (adjust the bucket name and path to match your setup):
   0 3 * * * OCI_BACKUP_BUCKET=your-backup-bucket-name /home/ubuntu/ai-fitness-trainer/deploy/backup-db.sh >> /home/ubuntu/backup.log 2>&1
   ```

## 5. Deploy the frontend to Vercel

1. Import the GitHub repo at <https://vercel.com/new>, set the **Root Directory** to `frontend`.
2. In the Vercel project's **Settings → Environment Variables**, add:
   `NEXT_PUBLIC_API_BASE_URL` = `https://<your-duckdns-hostname>` (the domain from step 2, with
   `https://` — this is the env var `frontend/src/lib/api-client.ts` reads for the backend's base
   URL).
3. Deploy. Note the resulting Vercel URL (e.g. `https://ai-fitness-trainer.vercel.app`).
4. Go back to the VM's `deploy/.env` (step 3) and set `CORS_ALLOWED_ORIGINS` to this real Vercel
   URL if you hadn't already, then `docker compose -f docker-compose.prod.yml up -d backend` to
   pick up the change.

## 6. Enable automatic backend deploys

In the GitHub repo's **Settings → Secrets and variables → Actions**, add:
- `DEPLOY_HOST` — the VM's public IP or DuckDNS hostname.
- `DEPLOY_USER` — the VM's SSH user (e.g. `ubuntu`).
- `DEPLOY_SSH_KEY` — a private key with access to the VM (generate a dedicated deploy key with
  `ssh-keygen -t ed25519 -f deploy_key -N ""`, add `deploy_key.pub` to the VM's
  `~/.ssh/authorized_keys`, and paste `deploy_key`'s contents as this secret — never reuse your
  personal SSH key here).

Once these three secrets exist, `.github/workflows/deploy-backend.yml` runs automatically on every
push to `main` that touches `backend/`, `cv-service/`, or the deploy Compose/Caddy files.

## 7. Verify the live deployment

- [ ] Visit the Vercel frontend URL, register a real account, log in.
- [ ] Upload `backend/tests/fixtures/squat.mp4` (or a real squat video) through the UI.
- [ ] Confirm the attempt reaches `completed` with a real score and rep breakdown (not stuck on
      `queued`/`processing`, and not `failed`).
- [ ] Confirm the annotated video plays back in the browser (proxied through the backend's
      `/v1/attempts/{id}/video` route — never a direct `cv-service` URL).
- [ ] Confirm `https://<duckdns-hostname>/health` returns `{"status":"ok"}` over real HTTPS (not
      a certificate warning) — proves Caddy's automatic TLS actually issued a certificate.
- [ ] Wait for (or manually trigger) the first nightly backup, confirm a real object appears in
      the Oracle Object Storage bucket from step 4.
```

- [ ] **Step 2: Add a cross-reference from `backend/README.md`**

Read `backend/README.md` first to find its "Not yet built" section (referenced in project memory
as the section that previously had a stale "Frontend" line, already corrected — find wherever that
list or an equivalent "what's not done yet" note currently lives) and add, near it:

```markdown
**Deployment:** see `deploy/README.md` for the free-tier deployment runbook (Vercel + Oracle
Always-Free VM).
```

- [ ] **Step 3: Re-read `deploy/README.md` against every file Tasks 1-5 actually created**

Check, and fix anything that doesn't match:
- Every env var named in step 3/5's instructions (`DOMAIN`, `POSTGRES_PASSWORD`, `JWT_SECRET`,
  `CV_API_KEY`, `CV_WEBHOOK_SECRET`, `CORS_ALLOWED_ORIGINS`, `NEXT_PUBLIC_API_BASE_URL`) matches
  exactly what `deploy/.env.example` (Task 3) and `frontend/src/lib/api-client.ts` actually read —
  no invented variable names.
- The `docker compose -f docker-compose.prod.yml up -d --build` command in step 3 matches Task 3's
  actual service names (`db`, `migrate`, `backend`, `cv-service`, `caddy`).
- The three GitHub secret names in step 6 (`DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`) match
  exactly what Task 5's workflow file references.
- The backup crontab line in step 4 matches Task 4's actual script path and its `OCI_BACKUP_BUCKET`
  environment variable name.

- [ ] **Step 4: Commit**

```bash
cd "/Volumes/Expansion/Software Builder/Web-App Projects/AI Fitness Trainer"
git add deploy/README.md backend/README.md
git commit -m "docs(deploy): add deployment runbook"
```
