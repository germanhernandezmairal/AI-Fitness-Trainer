# Design: Free-Tier Deployment

**Date:** 2026-08-14
**Author:** Fullstack role (compiled with Claude)
**Status:** APPROVED (2026-08-14)
**Related:** `backend/docker-compose.yml` (the existing local containerization this design extends,
not replaces), `backend/README.md` / `cv-service/README.md` (current local-loop docs),
`memoria-ada-outline.md` §6/§12 (name AWS as the intended deployment target — this design departs
from that, see §7 below).

---

## 0. Context and goal

Nothing is deployed anywhere yet — this repo runs entirely locally (Docker Compose for
`db`/`fake-cv`/`cv-service`, `npm run dev` / `uvicorn` directly for frontend/backend). This is the
third of three follow-up tasks decided after the 2026-08-12 frontend-design-polish pass (see
[[project-backend-status]] in project memory): design (not yet deploy) a real, working deployment.

**Hard constraint, decided with Alejandro before this design started:** the deployment must be
free — no paid hosting yet. This is not a soft preference; it drove every choice below, including
overriding the task's original "AWS" framing (see §7).

**Scope of this document:** design only. No infrastructure is provisioned as part of writing this
spec or its implementation plan — the plan's tasks produce configuration/docs/CI workflows that a
human then runs by hand (creating cloud accounts, clicking through provisioning UIs, and running
`terraform`/`ssh` commands isn't something an agent should do unattended for a personal AWS-adjacent
account). This mirrors how the cv-service integration work was handled: Claude designs and drafts,
the human executes the account-level actions.

## 1. Why not AWS

The task was originally framed as "AWS deployment design" (memoria §6/§12 already name AWS). Two
facts surfaced during brainstorming changed that:

- **AWS's real free tier no longer applies to new accounts.** EC2's 12-month free tier (t2/t3.micro,
  1 vCPU, 1GB RAM) is grandfathered to accounts created before 2025-07-15. A new account (the
  relevant case here) gets a $200 credit valid for 6 months, not an ongoing free tier — this
  contradicts "must stay free," not just "free for now."
- **`cv-service` needs real headroom.** It runs full `opencv-python` (non-headless) + `mediapipe` +
  `ffmpeg` for actual pose-detection inference — meaningfully heavier than a typical free-tier
  micro instance's ~512MB-1GB RAM comfortably handles alongside Postgres and the backend.

Given those two constraints together, **Oracle Cloud's Always Free tier** is the best fit found:
an Ampere A1 ARM VM at **2 OCPUs / 12GB RAM**, genuinely free indefinitely (no account-age gate,
no time limit), plus 200GB block storage, 20GB object storage, and 10TB/month egress, all free.
(Note: Oracle halved this shape's ceiling from 24GB to 12GB RAM on 2026-06-15 with no public
announcement — still comfortably the most RAM of any free option surveyed, but confirms free-tier
terms can shift without notice; §8 tracks this as an ongoing risk, not a one-time fact.)

Two other options were surveyed and rejected:
- **Fly.io** — free tier discontinued for new accounts since October 2024. Not available.
- **GCP e2-micro** — genuinely permanent and free, but only 1GB RAM: real inference risk under
  load, no more headroom than the AWS option this design is explicitly avoiding.
- **Render free web service** — permanent and free, but 512MB RAM and sleeps after 15 minutes
  idle; too tight for `cv-service`'s real inference and a cold-start UX regression for a small demo
  audience.

## 2. Architecture

Split hosting, matching each component to the free tier that fits it best rather than forcing
everything onto one box:

```
┌─────────────────────┐         HTTPS          ┌──────────────────────────────────────┐
│   Vercel (free)      │ ───────────────────────▶│  Oracle Always-Free VM (Ampere A1)   │
│   Next.js frontend   │  api.<subdomain>        │  2 OCPU / 12GB RAM                    │
│   auto HTTPS + CDN   │  .duckdns.org            │                                        │
└─────────────────────┘                          │  ┌────────────────────────────────┐  │
                                                   │  │ Caddy (reverse proxy, auto TLS) │  │
                                                   │  └───────────────┬────────────────┘  │
                                                   │                  │                    │
                                                   │  ┌───────────────▼────────────────┐  │
                                                   │  │ backend (FastAPI, uvicorn)      │  │
                                                   │  └───────────────┬────────────────┘  │
                                                   │      ┌───────────┼──────────┐         │
                                                   │  ┌───▼───┐  ┌────▼─────┐   │         │
                                                   │  │  db   │  │cv-service│   │         │
                                                   │  │(pg 16)│  │(real-cv) │   │         │
                                                   │  └───────┘  └──────────┘   │         │
                                                   │  local disk: uploaded/annotated videos │
                                                   └──────────────────────────────────────┘
```

- **Frontend:** Vercel, deployed via Vercel's own GitHub integration (push to `main` → build →
  deploy). No new code — `frontend/` already builds cleanly with `npm run build` (verified working
  as part of routine verification throughout this project's frontend work).
- **Backend + cv-service + Postgres:** one Oracle Always-Free VM, running
  `backend/docker-compose.yml`'s existing services via the `real-cv` profile
  (`docker compose --profile real-cv up -d`) — the same command already documented in
  `backend/README.md` for local real-CV testing, now run on the VM instead of a laptop.
- **Reverse proxy / TLS:** Caddy, added as a new service in a deployment-specific compose overlay
  (not the base `docker-compose.yml`, which stays laptop-oriented). Caddy's built-in automatic
  HTTPS (Let's Encrypt) needs only a `Caddyfile` naming the DuckDNS hostname — no manual
  certificate handling.
- **Domain:** a free DuckDNS subdomain (e.g. `ai-fitness-trainer-api.duckdns.org`) pointed at the
  VM's public IP, kept current via DuckDNS's own lightweight cron-based update script (handles the
  case where Oracle's free-tier IP is reassigned on VM restart).

## 3. Database

Self-hosted Postgres 16 in Docker Compose on the VM — the same `postgres:16` image already used
locally, not Oracle's proprietary Autonomous DB. This avoids introducing a second
database-connection code path (Autonomous DB needs Oracle's own wallet-based TLS client config,
which the backend's SQLAlchemy setup doesn't support today) for no real benefit at this scale.

**Backups:** a nightly `pg_dump` cron job on the VM, writing a compressed dump to Oracle's free
Object Storage (20GB free, well beyond what a personal-project Postgres instance needs) via the
`oci` CLI. No point-in-time recovery, no multi-AZ, no automatic failover — explicitly out of scope
for a free-tier personal-project deployment; a nightly dump is the right amount of durability for
the actual stakes here.

## 4. Video storage

Stays on the VM's local disk via the backend's existing storage abstraction
(`backend/app/services/storage.py`'s local-filesystem implementation) — no new object-storage
adapter code. Oracle's 200GB free block storage is far more than this project's demo-scale video
volume needs. If usage ever outgrows local disk, Oracle Object Storage (20GB free, already used for
DB backups above) is the natural next step, but that's a future decision, not part of this design.

## 5. CI/CD

- **Frontend:** none needed beyond Vercel's own git integration — push to `main`, Vercel builds and
  deploys automatically. Already the simplest path for a Next.js app.
- **Backend/cv-service:** a new GitHub Actions workflow (`.github/workflows/deploy-backend.yml`)
  that, on push to `main` (paths-filtered to `backend/`, `cv-service/`,
  `backend/docker-compose.yml`, and the new deployment overlay), SSHs into the Oracle VM and runs
  `docker compose --profile real-cv pull && docker compose --profile real-cv up -d --build`. The
  SSH private key and VM host are stored as GitHub Actions repository secrets, never committed.

## 6. Secrets

Two tiers, matching the existing local-dev pattern rather than inventing a new one:
- **Deploy-time secrets** (SSH key, VM host/user): GitHub Actions repository secrets, used only by
  the deploy workflow.
- **App-runtime secrets** (JWT signing key, webhook HMAC secret, `CV_API_KEY`, DB password): a
  `.env` file placed directly on the VM by hand during initial setup, never committed to git and
  never passed through GitHub Actions — the deploy workflow only triggers `docker compose up`,
  which reads the VM's own `.env`. Identical trust model to how local dev already keeps secrets out
  of git via `.env`/`.env.local`.

## 7. Memoria note (not part of this design's scope)

`memoria-ada-outline.md` §6 and §12 currently name AWS as the intended deployment target. This
design deliberately departs from that (per §1's reasoning) — worth a one-line correction next time
those memoria sections are actually written, but editing the outline is out of scope for this spec
(same boundary [[project-frontend-followup-polish]] and the Chapter 4/Chapter 3 memoria work have
already established: outline edits happen only when that specific chapter is the active
sub-project).

## 8. Explicitly out of scope

- Load balancing, auto-scaling, multi-region, or any HA beyond "one VM, restart it if it dies."
- A monitoring/alerting stack (could be a future follow-up task, not named here).
- Any AWS service, despite the memoria's current wording (§7 above).
- Swapping video storage to an object-storage backend (§4) — local disk is sufficient at this
  scale.
- Actually provisioning any of this — the implementation plan produces configuration and docs; a
  human runs the account-creation and provisioning steps by hand (§0).

## 9. Known risks to carry into the implementation plan, not hide

- **ARM64 compatibility is unverified.** `cv-service`'s Dockerfile (`python:3.10-slim` base) has
  never been built for `linux/arm64` on this project — `opencv-python==5.0.0.93` and
  `mediapipe==0.10.14` both publish ARM64 wheels, so this should work, but "should" is not
  "verified." The plan must include an explicit `docker buildx build --platform linux/arm64` test
  step before deployment, not assume it from this design.
- **Oracle's free Ampere A1 shape has a well-documented "out of capacity" provisioning issue** —
  creating the free instance can fail with a capacity error and need multiple retries (sometimes
  over hours or days, per widely-reported community experience). The plan should document this as
  an expected retry loop, not treat a first-attempt failure as a design defect.
- **Free-tier terms can change without notice** — Oracle's own 24GB→12GB mid-tier cut (2026-06-15,
  no announcement) is the concrete precedent. This design is correct as of 2026-08-14; whoever
  executes the implementation plan should re-verify current free-tier terms at that time rather
  than trust this document's numbers indefinitely.

## 10. Testing / verification

Not applicable in the code-test sense — this is an infrastructure design. "Verification" for the
implementation plan means: the ARM64 build step above actually succeeds and the resulting image
actually starts and processes a real test video before the VM is considered "working," not just
that the Docker Compose files are syntactically valid.
