# Design: API Contract — Backend ↔ AI (CV) Service

**Date:** 2026-07-27
**Author:** Fullstack role (compiled with Claude)
**Status:** APPROVED (2026-07-27)
**Related:** `docs/2026-07-27-cv-gym-exercise-design.md` (Alejandro's CV service design),
`ai-fitness-trainer-concept.md`, `memoria-ada-outline.md` (§5 Diseño, §6 Implementación,
§7 Evaluación, §9 Legislación).

---

## 0. Decisions locked (during brainstorming)

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | How the video reaches the CV service | **Backend proxies everything** | Frontend only talks to our backend; we own auth, history, and the video lifecycle (GDPR). |
| 2 | Result delivery (CV → backend) | **Webhook + polling fallback** | Near-instant updates, resilient to a dropped webhook. Matches the CV service's design. |
| 3 | Artifact storage | **CV stores artifacts; backend stores references** + explicit erasure contract | Fewest moving parts for MVP; honors the microservice boundary. Erasure contract keeps GDPR answerable. |
| 4 | Backend stack | **FastAPI (Python)** | One language and one shared schema across the backend↔CV boundary — the biggest source of integration bugs between two people working separately. |
| — | Frontend notification | **Frontend polls the backend** | Simplest for MVP; SSE/WebSocket is a later optimization that does not change the contract. |

---

## 1. Architecture & the two boundaries

Because the backend proxies everything (decision 1), we are defining **two** contracts:

- **Public boundary** — Frontend ↔ Backend. User-facing, authenticated by user session/JWT.
- **Internal boundary** — Backend ↔ CV service. Service-to-service, authenticated by a shared secret.

```
                         PUBLIC boundary                    INTERNAL boundary
 ┌──────────┐   upload video   ┌───────────────┐   POST /v1/jobs   ┌──────────────┐
 │ Frontend │ ───────────────► │  Backend      │ ────(+callback)──►│  CV Service  │
 │ (React)  │ ◄─── poll ────── │  (FastAPI)    │ ◄── webhook ──────│  (FastAPI +  │
 └──────────┘  GET /attempts   │  owns:        │   result JSON     │   Celery)    │
                               │  - users      │                   │  owns:       │
                               │  - orig video │   GET /v1/jobs/{id}│  - annotated │
                               │  - job state  │ ─── (fallback) ───►│    video     │
                               │  - Postgres   │                   │  - landmarks │
                               └───────────────┘                   └──────────────┘
                                      │  references (URLs) only
                                      ▼
                          [Backend storage: original video]
```

The backend translates between the public contract and the internal one. The frontend never
sees the CV service.

---

## 2. Backend data model (Postgres)

One core entity, `Attempt`, is the backend's mirror of a CV job.

```
Attempt
  id                  UUID    public id, exposed to the frontend
  user_id             UUID    FK → users
  exercise_type       str     e.g. "squat"
  status              enum     queued | processing | completed | failed
  cv_job_id           str     the CV service's job id (internal only)
  original_video_ref  str     key/URL in backend storage
  annotated_video_url str?    reference into CV storage; null until done
  result              jsonb?  the CV result payload; null until done
  overall_score       int?    denormalized from result for cheap history queries
  error_code          str?    closed catalog; set when status = failed
  created_at          ts
  completed_at        ts?
  expires_at          ts      drives retention / erasure (see §7)
  consent_at          ts      recorded at creation (feeds memoria §9)
```

Notes:
- `overall_score` is denormalized so the history/progress views never parse JSON.
- `expires_at` and `consent_at` exist from day one to support the GDPR story even in the MVP.

---

## 3. Public API — Frontend ↔ Backend (prefix `/v1`)

### `POST /v1/attempts` — upload & create
```
Content-Type: multipart/form-data
Fields: video (file), exercise_type (string)
Auth:   user session / JWT

202 Accepted:
{ "attempt_id": "uuid", "status": "queued" }
```

### `GET /v1/attempts/{id}` — status / result (the frontend polls this)
```json
{
  "attempt_id": "uuid",
  "exercise_type": "squat",
  "status": "completed",
  "created_at": "2026-07-27T18:00:00Z",
  "completed_at": "2026-07-27T18:00:12Z",
  "result": { "...": "see §5 — passed through from the CV service" },
  "error": null
}
```

Polling: every 2–3s with backoff until `status` is `completed` or `failed`.

### `GET /v1/attempts?limit=&cursor=` — paginated history
Returns a light list (score, date, exercise, thumbnail) for the progress view.

### `DELETE /v1/attempts/{id}` — user erasure
See §7. Returns `204`.

---

## 4. Internal API — Backend ↔ CV Service (prefix `/v1`)

This **ratifies the CV service's draft** (`docs/2026-07-27-cv-gym-exercise-design.md` §4),
with one addition: `DELETE`.

### `POST /v1/jobs` — backend submits a job
```
Content-Type: multipart/form-data
Fields: video (file), exercise_type (string), callback_url (string)
Auth:   service API key (header: X-API-Key)

202 Accepted:
{ "job_id": "abc123", "status": "queued" }
```

### `GET /v1/jobs/{job_id}` — polling fallback
Same result schema as §5.

### `DELETE /v1/jobs/{job_id}` — erasure contract (NEW)
Deletes the annotated video and any retained landmarks / intermediate data.
Idempotent; returns `204` even if already gone.

### Webhook callback
When the worker finishes, the CV service `POST`s the §5 payload to `callback_url`.
Security:
- `X-CV-Signature`: HMAC-SHA256 over the raw body using the shared secret.
- `X-CV-Timestamp`: used to reject replays (reject if too old).
The backend verifies the signature before trusting the payload.

---

## 5. Result schema (shared: CV → backend → frontend)

Passed through essentially verbatim from the CV design — a single source of truth, expressed as
one Pydantic model both repos can share.

```json
{
  "exercise_type": "squat",
  "overall_score": 82,
  "summary": "Good depth overall, but knees collapse inward on 2 of 5 reps.",
  "rep_count": 5,
  "reps": [
    { "rep_index": 1, "start_time_sec": 2.1, "end_time_sec": 5.4,
      "min_knee_angle_deg": 78, "score": 90, "errors": [] },
    { "rep_index": 2, "start_time_sec": 6.0, "end_time_sec": 9.1,
      "min_knee_angle_deg": 65, "score": 60,
      "errors": ["knee_valgus", "insufficient_depth"] }
  ],
  "annotated_video_url": "https://cv-storage/.../annotated.mp4",
  "algorithm_version": "squat-rules-v1"
}
```

---

## 6. Status & error model (closed catalogs)

**Status** (identical on both boundaries): `queued` → `processing` → `completed` | `failed`.

Three **closed** code catalogs — no free text — so the frontend controls copy / i18n / icons:

**a. Form errors** (per rep, when `completed`)
`knee_valgus`, `insufficient_depth`, `excessive_forward_lean`, … (extensible per exercise).

**b. Failure codes** (when `status = failed`)
- *Content errors — user re-records, NOT retried:* `no_pose_detected`, `low_pose_confidence`,
  `no_movement_detected`.
- *System errors — retried with backoff:* `storage_error`, `worker_error`.

**c. Upload validation (400, backend rejects before creating a job)**
`unsupported_format`, `file_too_large`, `video_too_long`, `unknown_exercise_type`.

Concrete MVP limits (to confirm with Alejandro, since they bound his pipeline too):
- **Allowed formats:** MP4 (H.264 / AAC) and MOV.
- **Max file size:** 100 MB.
- **Max duration:** 60 seconds.

Failure shape (both boundaries):
```json
{ "status": "failed", "error": { "code": "no_pose_detected", "message": "human-readable, for logs" } }
```

---

## 7. Deletion / erasure contract (GDPR — memoria §9)

We process **potentially biometric body video** under GDPR / LOPDGDD, so "right to erasure"
must be answerable end-to-end.

- **User-triggered:** `DELETE /v1/attempts/{id}` →
  1. backend deletes the original video from its storage,
  2. backend calls `DELETE /v1/jobs/{cv_job_id}` on the CV service (annotated video + landmarks),
  3. backend removes the `Attempt` row.
  One user action → one guaranteed sweep across both services.
- **TTL fallback:** every artifact has an `expires_at`; both services auto-purge expired data on
  a schedule, so nothing lingers if an explicit delete is missed. **Retention period: 30 days**
  from creation for the original video, annotated video, and any retained landmarks.
- **Consent + retention:** recorded on the `Attempt` at creation (`consent_at`), feeding
  directly into memoria §9.

---

## 8. Security & robustness

- **Public boundary:** user session / JWT; users can only read or delete their own attempts.
- **Internal boundary:** `X-API-Key` on backend→CV requests; HMAC-signed + timestamped webhooks
  on CV→backend.
- **Idempotency:** the webhook and the polling fallback can both deliver the same result — the
  backend upserts by `cv_job_id`, so double-delivery is safe.
- **Versioning:** `/v1` path prefix on both APIs; `algorithm_version` in every result for
  comparability as the CV model evolves.

---

## 9. Contract testing (memoria §7)

- **Shared schema:** Pydantic models for request / result / error, validated on both sides.
- **Contract tests:** backend against a stubbed CV service (fixture responses for `completed`
  and for each `failed` code).
- **Webhook tests:** signature verification, replay rejection, idempotent double-delivery.
- **Fallback test:** webhook never arrives → the poller reconciles state.

---

## 10. Resolved decisions & remaining follow-ups

**Resolved:**
- **CV service author attribution:** Alejandro Hernández Mairal (Data/AI role,
  `github.com/Alherma7`).
- **Upload limits:** MP4 (H.264 / AAC) and MOV; ≤ 100 MB; ≤ 60 seconds (§6c).
- **Retention period:** 30 days from creation for all artifacts (§7).

**Remaining follow-ups:**
- Sync the upload limits and 30-day retention with Alejandro, since they bound his pipeline
  and storage too.
- Decide backend object storage for the original video (S3 / MinIO) — deferred, does not change
  this contract.
