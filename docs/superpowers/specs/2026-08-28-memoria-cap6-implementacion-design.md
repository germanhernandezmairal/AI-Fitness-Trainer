# Design: Memoria — Chapter 6 (Implementación)

**Date:** 2026-08-28
**Author:** Fullstack role (compiled with Claude)
**Status:** APPROVED (2026-08-28)
**Related:** `memoria-ada-outline.md` §6 (scaffolding this chapter expands); `memoria/03-planificacion.md`,
`memoria/04-requisitos.md`, `memoria/05-diseno.md` (the three existing chapters — set the
per-chapter-spec, file-location and Spanish-language precedent; §5 in particular already owns the
architecture diagram, the video-proxy pattern, HMAC signing, the class model and the persistence
design, so this chapter cross-references §5 rather than repeating them); the real
`cv-service/pipeline.py` + `cv-service/GLOSARIO.md` + `backend/app/` source (the chapter's actual
source of truth, not the outline).

---

## 0. Context and goal

Same per-chapter approach as Ch.3/Ch.4/Ch.5: the memoria's 12 chapters are largely independent, so
each is its own sub-project (brainstorm → spec → plan → SDD). This design covers only **Chapter 6
(Implementación)**.

Per `memoria-ada-outline.md` §6, this chapter is about **"technology details and specific algorithms
— not the code itself"**. Concretely: how the movement-analysis pipeline works (pose → joint angle →
rep segmentation → score), how the two services talk, which technologies were chosen and why
(including what was deliberately left out), and how the system is packaged. It is **not** a
re-statement of §5's architecture, and it does **not** contain the step-by-step deployment runbook —
that is §12 Anexos (decided with the user, 2026-08-28).

**Scope decisions made with the user during brainstorming (2026-08-28):**

1. **Deployment mechanics → §12 only.** §6 covers containerization (Dockerfiles, Compose profiles)
   and describes the free-tier split-hosting *strategy* in ~1 paragraph, pointing to §12 for the
   provisioning/CI/CD runbook.
2. **CV algorithm → full detail, from the code, with Alejandro review.** The pose/angle/segmentation/
   scoring algorithm is documented in full technical detail from `cv-service/pipeline.py` and
   `cv-service/GLOSARIO.md`. Prose states plainly that the CV pipeline is Alejandro's work,
   integrated into this repository. A review-request message covering §6.1 will be drafted for the
   user to send Alejandro; his corrections, if any, land as a follow-up commit — **not a merge
   blocker**, matching every prior cv-service touch-point (`docs/2026-08-11-…`, `docs/2026-08-20-…`).
3. **Structure = two-part (CV / App), prose + math + diagrams.** Keeps the outline's AI/App split.
   Formulas shown as display math, the rep state machine as a small Mermaid `stateDiagram`, the CV
   constants as a short table. **No source-code blocks** — the outline is explicit that the code
   itself is out of scope.

**Outline-vs-reality corrections this chapter makes** (same posture as Ch.3–5, which corrected the
pre-code outline rather than transcribing it):

- Not "PyTorch/TensorFlow keypoint extraction" + a trained model — MediaPipe Pose (a pre-trained,
  off-the-shelf detector) feeds a **deterministic rules pipeline**. No model was trained; no
  accuracy/precision/recall metric applies (consistent with §4 RNF-4).
- Not "FastAPI vs. Express" — **FastAPI for both** services.
- Not "tip-generation method" — the "tips" are a static code→message lookup table in the frontend
  (`frontend/src/lib/form-error-messages.ts`), not generated natural language.
- Not "AWS services used" — free-tier split hosting (Vercel + one always-free VM); §12 has the detail.

The chapter is written **in Spanish**. New file `memoria/06-implementacion.md`, `NN-nombre.md`
pattern. `memoria-ada-outline.md` stays untouched.

---

## 1. Section 1 — Pipeline de análisis de movimiento (cv-service)

Documents `cv-service/pipeline.py` and its constants (`cv-service/GLOSARIO.md`). Opening sentence
attributes the pipeline to Alejandro (Datos/IA track), integrated into this repo.

### 1.1 Extracción de pose

- **MediaPipe Pose** (`mp.solutions.pose`, `mediapipe==0.10.14`), one `Pose` instance per job,
  `min_detection_confidence=0.5`, `min_tracking_confidence=0.5`.
- Per frame: OpenCV reads BGR → converted to RGB → `pose.process(...)`. Frames with no detected
  person are skipped (not counted, not written with a skeleton). If **no** frame yields a pose, the
  job fails with `no_pose_detected` (`NoPoseDetectedError`).
- Only **four landmarks** are used, all right-side: `RIGHT_HIP`, `RIGHT_KNEE`, `RIGHT_ANKLE`,
  `RIGHT_SHOULDER`, de-normalised to pixel coordinates. State the assumption this encodes: **a
  single lateral (sagittal) camera** with the athlete's right side toward it — the same assumption
  that makes `knee_valgus` (a frontal-plane fault) undetectable by design (§4 CU-5, §5).

### 1.2 Ángulo de rodilla

The knee angle is the vertex angle at `b` of the points `a-b-c` = (hip, knee, ankle), i.e.

$$\theta = \arccos\!\left(\frac{\vec{ba}\cdot\vec{bc}}{\lVert\vec{ba}\rVert\,\lVert\vec{bc}\rVert}\right)$$

computed in 2D image coordinates (`calculate_angle`), clipped to `[-1, 1]` before `arccos`, result
in degrees. Note the convention: this **interior** hip-knee-ankle angle is ~180° at full extension
(standing) and decreases as the knee flexes, so it is roughly the *complement* of the "flexion
angle" used in the biomechanics literature — ~90° of flexion ≈ a ~90–100° interior angle here. This
convention matters for reading §1.4's thresholds.

Torso lean (`torso_lean_from_vertical`) is the angle between the hip→shoulder vector and image-space
vertical `[0, -1]`; 0° = perfectly upright. Used only in §1.4.

### 1.3 Segmentación en repeticiones

A simple state machine over the per-frame angle sequence (`segment_reps`), shown as a Mermaid
`stateDiagram-v2`:

- Start in **`de pie`** (standing). When the angle drops below `STANDING_THRESHOLD = 160°`, a rep
  opens (**`bajando`** / in-rep) and the current frame is its start.
- While in-rep, track the running **minimum** angle and the hip/shoulder coordinates *at that
  minimum frame* (needed so `excessive_forward_lean` is evaluated at the bottom of the rep, not an
  arbitrary frame).
- When the angle returns to ≥ `STANDING_THRESHOLD`, the rep closes and is appended.
- A rep that opens but never returns to standing (video cut mid-rep) is **discarded**, not counted.

`fps` comes from OpenCV (`CAP_PROP_FPS`, default 30 if unavailable); rep start/end times are
`frame / fps` rounded to 2 decimals.

### 1.4 Puntuación y errores de forma

Per-rep score (`score_from_angle`), a **one-sided** curve:

$$\text{score}(a_{\min}) = \begin{cases} 100 & a_{\min} \le \text{GOOD\_DEPTH\_ANGLE\_DEG} \\[4pt] \max\!\big(0,\ \operatorname{round}(100 - (a_{\min} - \text{GOOD\_DEPTH\_ANGLE\_DEG}) \cdot \text{PENALTY\_PER\_DEGREE})\big) & \text{en otro caso} \end{cases}$$

- `GOOD_DEPTH_ANGLE_DEG = 100°`, `PENALTY_PER_DEGREE = 3`. Going *deeper* than the threshold is
  never penalised — only stopping short is. Cited rationale from `GLOSARIO.md`: **Schoenfeld (2010)**,
  *Squatting Kinematics and Kinetics…*, and the **NSCA**'s position that evidence does not support
  treating a full-depth squat as inherently riskier to the knee than a parallel one. (Note the
  history: an earlier two-sided `GOOD_DEPTH_MIN`/`GOOD_DEPTH_MAX` band that also penalised going too
  deep was collapsed to this single threshold — commit `aefbc6f`.)
- **Overall score** = mean of the per-rep scores, rounded; 0 if no reps were segmented.

Per-rep form-error codes (`build_rep`), from the closed catalogue in
`backend/app/schemas/contract.py::FormErrorCode`:

- `insufficient_depth` — `min_angle > GOOD_DEPTH_ANGLE_DEG`.
- `excessive_forward_lean` — `torso_lean_from_vertical(hip, shoulder) > EXCESSIVE_LEAN_DEG` at the
  minimum-angle frame. `EXCESSIVE_LEAN_DEG = 45°` is an explicit **heuristic starting point**, not
  from a cited source (GLOSARIO.md says so; also note the direction-agnostic limitation flagged in
  `docs/2026-08-20-…-followup-message.md`).
- `knee_valgus` — in the contract and the frontend label map, but **not evaluated, by design**
  (frontal-plane fault, single sagittal camera). Cross-reference §4 CU-5 / §5.

Short **table** of the CV constants: name · value · role · source.

### 1.5 Video anotado

For every frame with a detected pose, the skeleton (`mp_drawing.draw_landmarks`,
`POSE_CONNECTIONS`) and the integer knee angle (`cv2.putText`, near the knee) are drawn onto the
frame, and every frame (annotated or not) is written to the output video.

**Codec:** `ANNOTATED_VIDEO_FOURCC = cv2.VideoWriter_fourcc(*"avc1")`. Explain *why this is not the
obvious `mp4v`*: browsers' `<video>` decode only H.264/AVC, VP8/VP9 or AV1, not MPEG-4 Part 2, so an
`mp4v` file plays as a blank frame in the results page. `avc1` produces real H.264 with this OpenCV
build, no `ffmpeg` post-process. This was a real bug found the first time the *real* (not fake)
pipeline output was played in a browser — commit `eeae94a`; also referenced in §3's Fase 6.

### 1.6 Naturaleza del pipeline (nota)

One short paragraph: MediaPipe Pose is a pre-trained detector used off the shelf; everything
downstream (angles, state machine, thresholds, scoring) is **deterministic rules**, tuned by
constants, not learned. There is no training set and no accuracy/precision/recall figure — the
meaningful reliability question (correctly counting reps on real footage) is framed in §4 RNF-4 and
evaluated in §7. `algorithm_version` in the result payload is the literal string `"squat-rules-v1"`.

---

## 2. Section 2 — Aplicación web

### 2.1 Contrato e integración entre servicios

The internal contract lives in one module, validated by **both** sides
(`backend/app/schemas/contract.py`; the cv-service has its own equivalent). Result flow:

1. `POST /v1/attempts` (multipart: `video`, `exercise_type`) → backend validates
   (`backend/app/services/validation.py`: extension `.mp4`/`.mov`, ≤100 MB, H.264 only, ≤60 s,
   known exercise), stores the original video via the `Storage` protocol, creates the `Attempt`
   row (`status = queued`), then forwards the video to the cv-service.
2. Backend → cv-service `POST /v1/jobs` (`backend/app/services/cv_client.py`), multipart + form
   field `exercise_type`, header `X-API-Key`.
3. cv-service processes the job **asynchronously via FastAPI `BackgroundTasks`** (`cv-service/main.py`,
   `cv-service/jobs.py`) — **no task queue**; state is in-process and lost on restart, which is
   acceptable precisely because of step 5.
4. On completion the cv-service `POST`s the result back to
   `/v1/webhooks/cv-results/{attempt_id}` with an **HMAC-SHA256 signature** (`X-CV-Signature` /
   `X-CV-Timestamp` over `timestamp + "." + body`; verified in `backend/app/api/webhooks.py` via
   `verify_signature`, replay window `WEBHOOK_TOLERANCE_SEC`). Design rationale of the signature is
   §5's; here it is just named as part of the flow.
5. **Polling reconciler** (`reconcile_stale_attempts`, `backend/app/services/jobs.py`, APScheduler):
   any attempt still non-terminal `CV_POLL_AFTER_SEC` after creation is polled directly
   (`GET /v1/jobs/{id}` on the cv-service). This is the real fallback when a webhook is lost — the
   webhook is an optimisation, not the system of record.
6. **Exactly-once application:** both the webhook and the reconciler call `apply_job_status`
   (`backend/app/services/attempts.py`), which does `SELECT … FOR UPDATE` on the attempt and
   returns early if it is already terminal — so a result delivered twice, or by both paths, lands
   once. When a result is applied, the cv-service's own `annotated_video_url` is rewritten to the
   backend's authenticated proxy route before it is ever persisted (design in §5).
- A separate scheduled job purges attempts past their retention window (`expires_at`); named, not
  re-explained (that's §5's persistence design).

A compact numbered list or a small sequence-style description — not a full re-draw of §5's
architecture diagram.

### 2.2 Decisiones tecnológicas

- **FastAPI for both services.** cv-service *must* be Python (MediaPipe/OpenCV). The backend is
  FastAPI too — one language across the project, native async for the CV round-trip, Pydantic
  models that double as the validated contract (`contract.py`). SQLAlchemy (async) + Alembic;
  Postgres.
- **Next.js (App Router)** for the frontend; browser talks to the backend directly, access token in
  memory + refresh token in `localStorage` (no BFF — decision recorded in §5 /
  `docs/superpowers/specs/2026-08-04-frontend-design.md`).
- **Deliberate omissions**, each with its one-line reason:
  - *No task queue* (Celery/RQ/Arq) — `BackgroundTasks` + the polling reconciler cover the single-VM
    MVP; a queue is operational weight the free-tier target can't spend.
  - *No object storage* (S3/GCS) — original videos on local disk behind the `Storage` protocol
    (`backend/app/services/storage.py`, one impl `LocalFilesystemStorage`); swappable later without
    touching callers.
  - *No cache layer* (Redis) — the outline assumed one; nothing in the real workload needs it.
  - *"Tips" are static* — `form-error-messages.ts` maps each error code to a fixed English string;
    no NLG.

### 2.3 Empaquetado y despliegue (resumen)

- `backend/Dockerfile` (uv, `--frozen` install) and `cv-service/Dockerfile`; both build for
  `linux/arm64` (verified, `deploy/arm64-verification.md`).
- `backend/docker-compose.yml` for local dev: `db` + `fake-cv` by default; the real `cv-service`
  behind a `real-cv` profile. `fake-cv-service` (no MediaPipe/OpenCV, canned deterministic result)
  is kept for fast local runs and failure-path testing.
- `deploy/docker-compose.prod.yml` (+ a fake-cv variant) + `deploy/Caddyfile` for production.
- ~1 paragraph on the **free-tier split-hosting strategy**: Next.js frontend on Vercel; backend +
  cv-service + Postgres on a single always-free VM (Oracle Ampere A1 target; a smaller GCP
  `e2-micro` running `fake-cv-service` is the current live fallback), Caddy for automatic TLS behind
  a DuckDNS subdomain. **Full provisioning steps, CI/CD and the fallback rationale are §12 Anexos** —
  this chapter only states the shape and the constraint (must be free — decided with Alejandro, see
  `docs/superpowers/specs/2026-08-14-free-tier-deployment-design.md`).

---

## 3. Diagrams and tables

- **1 Mermaid `stateDiagram-v2`** — the rep-segmentation state machine (§1.3).
- **1 display-math block** for the knee-angle formula (§1.2) and **1** for the score curve (§1.4).
- **1 small table** — CV constants: name · value · role · source (§1.4).
- No architecture diagram (that's §5). No source-code blocks anywhere.

---

## 4. Out of scope (explicit)

- §5's architecture diagram, video-proxy design rationale, HMAC design rationale, class model,
  persistence/erasure design — cross-referenced, not repeated.
- The deployment runbook (provisioning, GitHub Actions, DuckDNS cron, backup job, live-verification
  checklist) — §12 Anexos.
- Test design and results — §7 Evaluación.
- Costs — §8. Legal/data-protection — §9.

---

## 5. Testing / verification approach

Documentation chapter — "testing" means factual accuracy, same bar as Ch.3/Ch.4/Ch.5:

- Every constant value, function name, threshold, route and `file` citation re-checked against the
  current source immediately before writing (the citations in this design doc were pulled from a
  fresh `read`/`grep` pass on 2026-08-28).
- Every formula matches `calculate_angle` / `score_from_angle` exactly; the state diagram matches
  `segment_reps`'s real transitions.
- The outline-correction claims (no trained model, FastAPI ×2, static tips, no AWS) each verified
  against the repo, not asserted from the outline.
- Whole-chapter review (opus, matching Ch.3–5's final-review step) before merge, checking every
  claim against the source it cites — with specific attention to §1.x, since that section documents
  code owned by the other track.
- **After merge:** a review-request message for §6.1 drafted for the user to send Alejandro; any
  corrections applied as a follow-up commit.

---

## 6. Open questions

None — the three real decisions (deployment placement, CV-section depth + authorship, structure/
code-detail level) were resolved with the user during brainstorming (2026-08-28) before this doc was
written.
