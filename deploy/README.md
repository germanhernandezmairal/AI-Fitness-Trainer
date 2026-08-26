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

## Local verification notes (this session, 2026-08-20)

Everything above that doesn't need real cloud accounts was verified locally on this Mac via
Colima (`brew install colima docker docker-buildx docker-compose`, native ARM64, no
cross-architecture emulation — see `deploy/arm64-verification.md`). Two local-environment gotchas
worth knowing if you're setting up Docker/Colima fresh on a machine like this one:

- **This project's exFAT-formatted drive writes AppleDouble `._*` shadow files** that break
  `docker buildx`'s build-context sender (`error from sender: failed to xattr ...: operation not
  permitted`). Both `backend/.dockerignore` and `cv-service/.dockerignore` exclude `._*` to work
  around this — if you still hit it, delete stray `._*` files under the affected directory
  (`find <dir> -name '._*' -delete`) before rebuilding.
- **Colima does not mount external volumes by default** (only `$HOME`) — bind-mounting a file
  from a path like `/Volumes/Expansion/...` (this repo's location) silently creates a phantom
  empty directory inside the VM instead of failing clearly, which breaks anything relying on
  `docker run -v`/Compose bind mounts (e.g. the Caddyfile mount). Fix: start Colima with
  `colima start --mount "/Volumes/<your-volume>:w"` (or add the equivalent to
  `~/.colima/default/colima.yaml`'s `mounts:` list) if the repo lives outside `$HOME`.

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
