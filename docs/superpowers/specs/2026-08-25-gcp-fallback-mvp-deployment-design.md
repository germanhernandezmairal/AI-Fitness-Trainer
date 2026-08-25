# Design: GCP `e2-micro` Fallback MVP Deployment

**Date:** 2026-08-25
**Author:** Compiled with Claude (via `superpowers:brainstorming`)
**Status:** APPROVED (2026-08-25)
**Related:** `docs/superpowers/specs/2026-08-14-free-tier-deployment-design.md` (the primary Oracle
Always-Free design this fallback temporarily sits alongside — everything decided there still
holds as the real target), `deploy/README.md` (the Oracle runbook this design adds a section to,
not replaces).

---

## 0. Context and goal

Oracle Cloud's Ampere A1 VM creation has been retrying since 2026-08-21 (48+ attempts as of this
design, an unattended `launchd`-scheduled loop, see `project_aws_deployment_constraints` memory)
against a genuine capacity shortage in `eu-madrid-1`'s single availability domain — not a
misconfiguration, just no free ARM capacity yet. With the frontend already live on Vercel and the
whole backend/`cv-service`/Postgres stack fully built and locally verified, the only missing piece
for a real, live MVP is *any* VM to run it on.

**Goal:** ship a real, live, clickable MVP now, on GCP's `e2-micro` Always-Free tier (confirmed
current as of 2026-08-25 — still genuinely free and unchanged, unlike Fly.io's and AWS's free
tiers, both of which this project already found discontinued/gutted for new accounts), without
waiting on Oracle. The Oracle retry script keeps running unattended regardless; this is a parallel
stopgap, not a replacement plan.

**Explicitly out of scope:**
- Any change to the Oracle-targeted design or its runbook sections (`deploy/README.md` §1-7) —
  this design only adds alongside them.
- Any backend code change. Postgres and FastAPI stay exactly as they are — see §2 for why a
  database/framework swap (raised as a space-saving idea) doesn't actually address the real
  constraint and was explicitly decided against.
- Running real `cv-service` on this fallback — see §1.
- A permanent dual-environment CI/CD setup — see §3.

## 1. Why `fake-cv-service`, not real `cv-service`

`e2-micro`'s free tier is 1GB RAM total, and this fallback colocates Postgres + backend +
`cv-service` on that one VM (the same single-VM pattern as the Oracle design). Nobody has ever
measured real `cv-service`'s actual memory footprint — the 2026-08-14 research's rejection of
`e2-micro` for it was a reasonable judgment call (MediaPipe + OpenCV + Python typically want
several hundred MB to 1GB+), not a demonstrated failure, and the memoria's own benchmarks
(RNF-2/RNF-3) only measured latency and concurrency on a 16-core dev machine, never RAM.

Real `cv-service` was considered directly for this fallback and decided against: stacked with
Postgres and the backend on a machine with roughly ~950MB usable, an out-of-memory crash under
real load is a genuine risk, not a hypothetical, and testing it empirically would cost real time
against the actual goal (shipping fast). **Decided: `fake-cv-service`** — near-zero memory
footprint (no MediaPipe/OpenCV at all), so backend + Postgres + `fake-cv` fitting comfortably on
1GB is a near-certainty, not a gamble.

Trade-off: `fake-cv-service` returns canned, deterministic scores — not real AI form analysis. See
§4 for how this MVP stays honest about that.

## 2. Why Postgres and FastAPI stay unchanged

Raised during brainstorming (relayed from Alejandro): could a smaller database or web framework
shrink the footprint further? Checked against where the actual weight sits, not assumed:

- **Disk space was never the constraint.** `e2-micro` includes 30GB of free disk; one test user's
  attempt history is a few KB of data. A smaller database doesn't address a problem that doesn't
  exist here.
- **RAM is the real constraint, and Postgres isn't the dominant cost there.** A default Postgres
  container idles around 50-100MB — real, but small next to the actual heavy consumer.
- **FastAPI is not a heavy runtime.** It's a thin routing layer over Python/Pydantic; swapping to
  a smaller framework wouldn't move memory usage meaningfully, because FastAPI was never where the
  weight comes from.
- **MediaPipe/OpenCV are the actual RAM cost** (§1) — but this fallback doesn't run them at all
  (`fake-cv-service` has zero ML dependencies), so the question is moot for this specific design
  regardless.

**Decided: keep Postgres and FastAPI exactly as they are.** A Postgres → SQLite swap would be a
real backend code change (async driver swap, Alembic migration re-verification) for a RAM saving
that doesn't target the actual constraint — pure added risk against the goal of shipping fast. The
one genuinely useful lever raised in this conversation was a smaller MediaPipe pose-model variant
(MediaPipe ships "lite" tiers) — that's for Alejandro to pursue on his own timeline on the
`cv-service` side, not something this deployment design should build around.

## 3. Deployment mechanics — reuse and repoint, don't duplicate

Confirmed against the actual files (not assumed) before designing around them:
`deploy/docker-compose.prod.yml`'s `cv-service` service hardcodes `build: ../cv-service` (the real
service) with no existing fake-cv path in the prod compose file (unlike the dev compose file,
which already has both behind a profile switch); `.github/workflows/deploy-backend.yml`'s deploy
script runs a single `docker compose -f docker-compose.prod.yml up -d --build ...` command against
`secrets.DEPLOY_HOST`/`DEPLOY_USER`/`DEPLOY_SSH_KEY`.

**New file: `deploy/docker-compose.prod.fake-cv.yml`** — a Compose override defining only the
`cv-service` service, with `build: ../fake-cv-service` in place of `../cv-service`. Same service
name (`cv-service`), same port (9000), so `backend`'s `CV_SERVICE_URL: http://cv-service:9000`
environment variable needs zero changes — the network alias is identical either way. Deployed as:

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.prod.fake-cv.yml up -d --build
```

**`.github/workflows/deploy-backend.yml`: one-line temporary edit** — the deploy script's existing
`docker compose` line gains the extra `-f docker-compose.prod.fake-cv.yml` flag. Reverting this
single line is the entire "switch back to real `cv-service`" step at cutover (§6).

**DNS and secrets: repoint, don't duplicate.** The existing DuckDNS subdomain
(`ai-fitness-trainer-api.duckdns.org`) and the same three GitHub secrets
(`DEPLOY_HOST`/`DEPLOY_USER`/`DEPLOY_SSH_KEY`) point at the GCP VM now, and get repointed at Oracle
once it's ready. No second DNS name, no parallel CI environment, no dual-target workflow logic —
this fallback is explicitly temporary (confirmed with the user), so building permanent
infrastructure for a stopgap is the wrong trade.

**Architecture note:** Oracle's Ampere A1 is ARM64; `e2-micro` is x86-64. This matters less than it
sounds — the 2026-08-20 ARM64 verification work was necessary specifically because MediaPipe/
OpenCV needed real ARM64 wheel confirmation, a concern that doesn't apply here since
`fake-cv-service` has no such dependencies. `backend`'s Dockerfile is a standard Python/`uv` build
with no ARM-specific pinning, and images build natively on whatever platform `docker compose build`
runs on (the target VM itself, via the existing SSH-deploy step) — no cross-compilation or
`--platform` flag needed, unlike Oracle's case. Still worth a one-time smoke test (build +
`/health` check for `backend`/`fake-cv-service`/`db`/`caddy` on the actual GCP VM) before calling
this live, the same spirit as the original plan's Task 1 risk-gate, but expected to be
low-risk — these are the two least architecture-sensitive of the four images involved.

## 4. Demo-honesty banner

Since `fake-cv-service` returns canned scores, the live MVP must say so visibly — decided
explicitly rather than shipped silently, since this could be shown to Alejandro, a professor, or
early testers. A small, visible note (e.g. on the attempt-result page, near the score) stating
scoring is a placeholder while the real analysis engine is being deployed.

**Built separately from the in-flight frontend redesign.** `worktree-frontend-redesign` (a
different plan, `docs/superpowers/plans/2026-08-25-frontend-redesign.md`) is mid-flight and
unmerged as of this design. This banner is small and time-sensitive enough not to wait on that
work landing — it's built in its own worktree, off current `main` (the pre-redesign visual state),
independent of the redesign. Whichever of the two merges to `main` first, the other rebases
trivially — this is a one-paragraph addition to one existing component, not a structural change
either could conflict on.

## 5. GCP VM provisioning — new runbook section

New section appended to `deploy/README.md` (not a new file — follows the existing runbook's
established pattern, its own numbered §1-7 for Oracle stay untouched), covering the
human-executed steps: GCP billing account + project creation, enabling the Compute Engine API,
creating the `e2-micro` instance in an allowed free region (`us-central1`), firewall rules for
22/80/443, and an SSH key (a fresh dedicated one, same reuse-avoidance principle the Oracle runbook
already follows for its own VM-access and deploy keys).

**Unlike Oracle, no retry-loop script is needed.** `e2-micro` creation isn't capacity-constrained
the way Oracle's single-AD ARM capacity is — a plain `gcloud compute instances create` is expected
to succeed on the first attempt.

## 6. Cutover (documented now, executed later)

Whenever Oracle succeeds or a decision is made to move to real `cv-service` on this same GCP VM
instead: revert the workflow's extra `-f` flag (§3), repoint the DuckDNS record and the three
GitHub secrets at the new target, redeploy, and remove the demo-honesty banner (§4). Whether the
GCP VM itself gets decommissioned or kept as a spare at that point is a decision for whenever
cutover actually happens, not now.

## 7. Testing

No new automated test suite — this is infrastructure, not application code (mirrors the original
free-tier-deployment plan's own testing approach). Verification is the same kind the Oracle plan
used: local `docker compose config` validation of the new override file, a real smoke test of the
built images once the GCP VM exists (§3), and the existing `deploy/README.md` §7-style live
verification checklist (health endpoints, a real upload-to-result round trip through the actual
deployed stack) adapted for the GCP target. The banner (§4) is a small React component change and
gets ordinary component-level test coverage in its own worktree, following that codebase's
existing test conventions.
