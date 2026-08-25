# GCP Fallback MVP Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce the Compose override, CI workflow edit, frontend honesty banner, and human-executed
runbook needed to run backend + Postgres + `fake-cv-service` on a GCP `e2-micro` Always-Free VM as a
temporary stopgap MVP, while Oracle's Ampere A1 VM creation keeps retrying — verified locally
wherever verification is possible without a real GCP account, since no infrastructure is
provisioned as part of this plan.

**Architecture:** Reuses the existing Oracle-targeted deploy pipeline almost entirely — a small
Docker Compose override file swaps only the `cv-service` build context to `../fake-cv-service`
(same service name and port, so `backend`'s env vars need zero changes), the GitHub Actions deploy
workflow gets one line added to pick up that override, and the existing DuckDNS name/deploy
secrets get repointed at the GCP VM instead of a new parallel setup. A separate, small frontend
change adds a visible "placeholder scoring" notice, built in its own worktree off current `main`
— independent of the in-flight `docs/superpowers/plans/2026-08-25-frontend-redesign.md` work, per
the spec's explicit decision not to block on it.

**Tech Stack:** Docker Compose (override-file layering), GitHub Actions, GCP Compute Engine
(`e2-micro`), DuckDNS (reused, not new), Next.js/shadcn `Alert` component (already in the
codebase).

**Spec:** `docs/superpowers/specs/2026-08-25-gcp-fallback-mvp-deployment-design.md`

## Global Constraints

- No infrastructure is provisioned by this plan's tasks — every task produces
  configuration/code/docs verified locally; actual GCP account/VM provisioning is a human-executed
  step documented in Task 4, not run by an implementer (spec §5).
- **No backend code change.** Postgres and FastAPI stay exactly as they are — checked against
  where the real memory constraint sits (MediaPipe/OpenCV, not Postgres/FastAPI) and decided
  against a database/framework swap (spec §2).
- **This fallback does not run real `cv-service`.** Only `fake-cv-service` (spec §1).
- **Reuse and repoint, never duplicate:** the existing DuckDNS subdomain
  (`ai-fitness-trainer-api.duckdns.org`) and the existing three GitHub secrets
  (`DEPLOY_HOST`/`DEPLOY_USER`/`DEPLOY_SSH_KEY`) get repointed at the GCP VM, not replaced with a
  second parallel DNS name or a dual-target CI setup (spec §3).
- **Task 3 (the frontend banner) must be built in its own worktree off current `main`, never
  inside `.claude/worktrees/frontend-redesign`** — that worktree belongs to a different,
  independent plan (spec §4).
- This is an explicitly temporary stopgap, not a permanent second environment — optimize each task
  for reuse of what already exists over building anything new-and-parallel (spec §0, "Temporary
  stopgap" decision).

---

### Task 1: `fake-cv-service` Compose override, verified locally

**Files:**
- Create: `deploy/docker-compose.prod.fake-cv.yml`

**Interfaces:**
- Consumes: `deploy/docker-compose.prod.yml`'s existing `cv-service` service definition (build
  context `../cv-service`, port 9000, `CV_API_KEY`/`CV_WEBHOOK_SECRET`/`CV_SERVICE_BASE_URL` env
  vars) as the base layer this file overrides via Compose's `-f`/`-f` merge.
- Produces: `deploy/docker-compose.prod.fake-cv.yml`, which Task 2's CI workflow edit and Task 4's
  runbook both reference by this exact path.

Docker Compose merges multi-file configs per-service, per-key — a key not specified in the
override file is inherited unchanged from the base file. So this override only needs to state the
one key that actually changes (`build:`); `restart: unless-stopped`, the `cv-service` service name
(and therefore its network alias, which `backend`'s `CV_SERVICE_URL: http://cv-service:9000` env
var depends on), and every existing environment variable are inherited from
`docker-compose.prod.yml` unchanged.

- [ ] **Step 1: Create `deploy/docker-compose.prod.fake-cv.yml`**

Create `deploy/docker-compose.prod.fake-cv.yml`:
```yaml
services:
  cv-service:
    build: ../fake-cv-service
```

- [ ] **Step 2: Validate the merged Compose config resolves cleanly**

Run (from the repo root, with dummy values since real secrets don't exist yet — same pattern the
original Oracle plan's Task 3 Step 4 used):
```bash
DOMAIN=test.example.com POSTGRES_USER=fitness POSTGRES_PASSWORD=fitness POSTGRES_DB=fitness \
  JWT_SECRET=test-secret-at-least-32-bytes-long-xxxxxxxxx CV_API_KEY=test CV_WEBHOOK_SECRET=test \
  CORS_ALLOWED_ORIGINS='["http://localhost:3000"]' \
  docker compose -f deploy/docker-compose.prod.yml -f deploy/docker-compose.prod.fake-cv.yml config
```
Expected: PASS — prints the fully-resolved config, and in it the `cv-service` service's `build`
key shows `context: ../fake-cv-service` (not `../cv-service`), while its `environment` still lists
`CV_API_KEY`/`CV_WEBHOOK_SECRET`/`CV_SERVICE_BASE_URL` unchanged from the base file — confirms the
per-key merge worked as expected, not a full-service replacement that would have silently dropped
those env vars.

- [ ] **Step 3: Bring up the full stack locally with `fake-cv-service` and confirm the wiring works**

Run (from the repo root — reuses the Colima/Docker environment already set up for this project's
earlier ARM64 deployment work):
```bash
cd deploy
DOMAIN=localhost POSTGRES_USER=fitness POSTGRES_PASSWORD=fitness POSTGRES_DB=fitness \
  JWT_SECRET=test-secret-at-least-32-bytes-long-xxxxxxxxx \
  CV_API_KEY=test-cv-key CV_WEBHOOK_SECRET=test-webhook-secret \
  CORS_ALLOWED_ORIGINS='["http://localhost:3000"]' \
  docker compose -f docker-compose.prod.yml -f docker-compose.prod.fake-cv.yml \
  up -d --build db migrate backend cv-service

sleep 10
docker compose -f docker-compose.prod.yml -f docker-compose.prod.fake-cv.yml ps
docker compose -f docker-compose.prod.yml -f docker-compose.prod.fake-cv.yml logs backend | tail -20
```
Expected: `ps` shows `db`, `backend`, and `cv-service` (now built from `../fake-cv-service`, no
MediaPipe/OpenCV dependency to slow the build) as `running`/`healthy`, `migrate` as `exited (0)`.
`backend`'s logs show a clean `Application startup complete`, no crash loop.

Then confirm `backend` can actually reach `cv-service` over the Compose network (this is the one
thing this task exists to prove — that the `http://cv-service:9000` alias still resolves to the
now-fake service):
```bash
NETWORK=$(docker compose -f docker-compose.prod.yml -f docker-compose.prod.fake-cv.yml ps --format '{{.Networks}}' backend | head -1)
docker run --rm --network "${NETWORK}" curlimages/curl:latest -sf \
  -H "X-API-Key: test-cv-key" http://cv-service:9000/health
```
Expected: prints a `200`-shaped health response from `fake-cv-service` (its own `/health` route,
same contract as the real service) — confirms the override's build-context swap didn't break the
service-name/network wiring `backend` depends on.

Run `docker compose -f docker-compose.prod.yml -f docker-compose.prod.fake-cv.yml down -v`
afterward to tear down.

- [ ] **Step 4: Commit**

```bash
cd "/Volumes/Expansion/Software Builder/Web-App Projects/AI Fitness Trainer"
git add deploy/docker-compose.prod.fake-cv.yml
git commit -m "feat(deploy): add fake-cv-service Compose override for the GCP fallback"
```

---

### Task 2: GitHub Actions workflow — pick up the fake-cv override

**Files:**
- Modify: `.github/workflows/deploy-backend.yml`

**Interfaces:**
- Consumes: `deploy/docker-compose.prod.fake-cv.yml` (Task 1) — the workflow's remote deploy
  command adds this file to its existing `-f` chain.
- Produces: nothing new consumed by later tasks — Task 4's runbook documents reverting this same
  line at cutover time, but doesn't depend on any code interface from it.

- [ ] **Step 1: Edit the deploy script's `docker compose` line**

In `.github/workflows/deploy-backend.yml`, change:
```yaml
            docker compose -f docker-compose.prod.yml up -d --build db migrate backend cv-service caddy
```
to:
```yaml
            docker compose -f docker-compose.prod.yml -f docker-compose.prod.fake-cv.yml up -d --build db migrate backend cv-service caddy
```
This is the entire code change this task makes. Reverting this one line back to the original
(dropping the `-f docker-compose.prod.fake-cv.yml`) is the entire "switch back to real
`cv-service`" step at cutover — see Task 4's new runbook section.

- [ ] **Step 2: Validate the workflow YAML is still well-formed**

Run:
```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-backend.yml'))" && echo "YAML valid"
```
Expected: `YAML valid` prints, no exception.

- [ ] **Step 3: Commit**

```bash
cd "/Volumes/Expansion/Software Builder/Web-App Projects/AI Fitness Trainer"
git add .github/workflows/deploy-backend.yml
git commit -m "ci(deploy): point the backend deploy workflow at the fake-cv override"
```

---

### Task 3: Demo-honesty banner on the attempt result

**Files:**
- Modify: `frontend/src/components/attempt-result.tsx`
- Modify: `frontend/tests/unit/components/attempt-result.test.tsx`

**Interfaces:**
- Consumes: `Alert`/`AlertDescription` from `@/components/ui/alert` (already used elsewhere in
  this file for the video-load error, and in `AttemptDetailContent` for delete/failure errors —
  same component, default variant instead of `variant="destructive"`).
- Produces: nothing new consumed by later tasks.

**Must be implemented in its own worktree, off current `main` — never inside
`.claude/worktrees/frontend-redesign`** (Global Constraints). Current `main`'s
`frontend/src/components/attempt-result.tsx` is the exact file this task's steps below are written
against; if the frontend-redesign plan has merged to `main` by the time this task runs, re-read the
file first and adapt the line numbers/surrounding classes accordingly — the banner text and test
assertion below are what matters, not the exact surrounding `className` strings.

- [ ] **Step 1: Write the failing test**

Add this test to the existing `describe("AttemptResult", ...)` block in
`frontend/tests/unit/components/attempt-result.test.tsx` (after the last existing `it(...)`,
before the closing `});`):
```tsx
  it("shows a notice that scoring is a placeholder", () => {
    render(<AttemptResult result={RESULT} />);

    expect(screen.getByText(/placeholder/i)).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run tests/unit/components/attempt-result.test.tsx`
Expected: FAIL — the new test, since no such notice exists in the component yet.

- [ ] **Step 3: Add the banner**

In `frontend/src/components/attempt-result.tsx`, add the import alongside the existing ones:
```tsx
import { Alert, AlertDescription } from "@/components/ui/alert";
```

Then add the banner as the first child of the outer `<div className="space-y-4">`, immediately
before the existing `<Card className="p-4">` score card:
```tsx
      <Alert>
        <AlertDescription>
          Scoring shown here is a placeholder while the real AI analysis engine is being deployed.
        </AlertDescription>
      </Alert>
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run tests/unit/components/attempt-result.test.tsx`
Expected: PASS (7 tests, including the new one — 6 pre-existing per current `main`, adjust the
expected count if the frontend-redesign plan's Task 5 has merged and added its own by the time
this runs).

- [ ] **Step 5: Run the full unit suite to confirm no regressions**

Run: `cd frontend && npm test`
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
cd frontend
git add src/components/attempt-result.tsx tests/unit/components/attempt-result.test.tsx
git commit -m "feat(frontend): add placeholder-scoring notice for the fake-cv fallback MVP"
```

---

### Task 4: GCP VM provisioning runbook

**Files:**
- Modify: `deploy/README.md`

**Interfaces:**
- Consumes: `deploy/docker-compose.prod.fake-cv.yml` (Task 1), the edited
  `.github/workflows/deploy-backend.yml` (Task 2), and the banner (Task 3) — this task's whole job
  is documenting how a human strings them together against a real GCP account. Also consumes the
  already-existing DuckDNS hostname and GitHub secret names from `deploy/README.md`'s existing §2
  and §6 (this task repoints them, per Global Constraints, rather than inventing new ones).
- Produces: nothing later tasks depend on (this is the final task).

- [ ] **Step 1: Add a new section to `deploy/README.md`**

Add this new section at the end of `deploy/README.md`, after the existing "Local verification
notes" section:

```markdown
## Temporary fallback: GCP `e2-micro` with `fake-cv-service`

While Oracle's Ampere A1 capacity retry keeps running (see §1 above), this fallback ships a real,
live MVP now on GCP's `e2-micro` Always-Free tier — same domain, same deploy pipeline, `cv-service`
swapped for `fake-cv-service` (canned scoring, not real AI analysis — the running app says so via
a visible banner). Full rationale:
`docs/superpowers/specs/2026-08-25-gcp-fallback-mvp-deployment-design.md`.

**This is a human-executed runbook, not something to automate end-to-end** — same reasoning as §1.

### A. Provision the GCP `e2-micro` VM

1. Create a GCP account/project at <https://console.cloud.google.com/> if you don't have one (a
   billing account with a card on file is required even for the Always Free tier — it will not be
   charged unless usage exceeds the free quota).
2. Enable the Compute Engine API for the project (the console prompts for this automatically the
   first time you visit **Compute Engine → VM instances**).
3. Create the instance:
   - **Region:** one of `us-west1`, `us-central1`, or `us-east1` — these are the *only* regions
     where the `e2-micro` Always-Free quota applies; any other region bills at standard rates.
   - **Machine type:** `e2-micro`.
   - **Boot disk:** a recent Ubuntu LTS image, up to 30GB standard persistent disk (within the
     Always-Free disk quota).
   - **Firewall:** allow HTTP (80) and HTTPS (443) traffic (checkboxes in the instance-creation
     form); SSH (22) is open by default via GCP's default firewall rules.
4. Unlike Oracle's Ampere A1 shape, `e2-micro` creation is not capacity-constrained — this should
   succeed on the first attempt, no retry loop needed.
5. Note the VM's public IP.

### B. Repoint DNS and deploy secrets at the GCP VM

1. In DuckDNS (already set up per §2 above), update the existing
   `ai-fitness-trainer-api.duckdns.org` record to point at the GCP VM's IP from step A.5 — do not
   create a second subdomain.
2. In the GitHub repo's **Settings → Secrets and variables → Actions**, update the existing
   `DEPLOY_HOST` secret to the GCP VM's IP (or the same DuckDNS hostname), and generate/attach a
   fresh dedicated SSH deploy key the same way §6 above describes (never reuse the Oracle VM's
   key) — update `DEPLOY_USER`/`DEPLOY_SSH_KEY` accordingly. Do not add new secret names; these
   three are repointed, not duplicated.

### C. Initial VM setup

SSH into the VM, then follow §3 above exactly (`curl -fsSL https://get.docker.com | sudo sh`,
clone the repo, `cp .env.example .env` and fill in real values) — the only difference from §3 is
the final command, which includes the fake-cv override:

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.prod.fake-cv.yml up -d --build
```

### D. Verify

Same checklist as §7 above, with one line adjusted: the attempt will reach `completed` with a
**canned, deterministic** score (not real form analysis) — confirm the placeholder-scoring banner
from Task 3 is visible on the result page, in addition to §7's other checks.

### E. Cutover back to Oracle / real `cv-service` (whenever that's ready)

1. Revert `.github/workflows/deploy-backend.yml`'s deploy line to drop
   `-f docker-compose.prod.fake-cv.yml` (Task 2 of the implementation plan made this a one-line
   change; reverting it is the same one line).
2. Repoint the DuckDNS record and the three `DEPLOY_*` GitHub secrets at the real target (Oracle's
   VM, or wherever real `cv-service` ends up running) — same repoint pattern as step B above, just
   aimed the other direction.
3. Redeploy (push to `main`, or trigger the workflow manually).
4. Remove the placeholder-scoring banner added in Task 3 (a follow-up change, not part of this
   plan).
5. Whether the GCP VM gets decommissioned or kept as a spare at this point is a decision for
   whenever cutover actually happens, not now.
```

- [ ] **Step 2: Re-read the new section against every file Tasks 1-3 actually created**

Check, and fix anything that doesn't match:
- The Compose command in step C matches Task 1's actual file name
  (`docker-compose.prod.fake-cv.yml`) exactly.
- Step E.1's description of what to revert matches Task 2's actual one-line edit exactly.
- No new DuckDNS subdomain or GitHub secret name was invented anywhere in the new section — every
  reference reuses the existing names already documented in §2/§6 above it.

- [ ] **Step 3: Commit**

```bash
cd "/Volumes/Expansion/Software Builder/Web-App Projects/AI Fitness Trainer"
git add deploy/README.md
git commit -m "docs(deploy): add GCP e2-micro fallback runbook"
```
