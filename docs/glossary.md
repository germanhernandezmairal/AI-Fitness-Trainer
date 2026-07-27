# Glossary — AI Fitness Trainer

Plain-language definitions of the terms that come up around this project, each grounded in how
it actually applies to *our* app. Useful for the *memoria* and for staying in sync between the
fullstack and Data/AI roles.

---

## Core concepts

### Artifact
A file or output the system produces or stores (as opposed to the code that makes it). One squat
analysis produces three artifacts:
- **Original video** — the raw clip the user uploaded (stored by our backend).
- **Annotated video** — the clip with skeleton / angles / feedback drawn on it (stored by the CV service).
- **Result JSON** — the scores, per-rep breakdown, and error codes (stored by our backend in Postgres).

"The CV service stores the artifacts, the backend stores references" means Alejandro's service
keeps the heavy media files and our backend keeps a **URL pointing to them** plus the JSON.

### Boundary
A line where two separate parts of the system talk to each other through a defined **contract**
(an agreed set of requests and responses). Neither side needs to know *how* the other works
internally — only how to talk across the line. An **API contract** is the rulebook for a boundary.

Our app has two:
- **Public boundary** — Frontend ↔ Backend. Faces the outside world (the user's browser), so it's
  protected by **user login**; each user only sees their own data.
- **Internal boundary** (a.k.a. private) — Backend ↔ CV service. Server-to-server, behind the
  scenes; the browser never touches it. Protected by a **shared secret key**, not user logins.

Drawing boundaries deliberately lets us change or replace the CV service without the frontend
ever noticing, as long as the backend keeps honoring the public contract.

### API contract
The precise, agreed definition of a boundary: which requests are allowed, what data they carry,
and what responses come back. It lets two people (or services) build independently and still fit
together. Ours is written in `docs/superpowers/specs/2026-07-27-api-contract-design.md`.

### Microservice
An independently built, deployed, and run piece of the system that does one job and talks to the
rest over an API. Alejandro's CV service is a microservice: it can be updated or redeployed on its
own schedule without touching our backend.

---

## Legal & data protection

### GDPR (General Data Protection Regulation)
The EU law governing how you may collect, store, and use **personal data** about people. In Spain
its local implementation is **LOPDGDD**. It applies to us because we handle data about real people.

It matters *a lot* here because we process **video of people's bodies**, likely **biometric data**
— one of the most protected categories. Key obligations:
- **Consent** — the user must clearly agree before we process their video.
- **Right to erasure** ("right to be forgotten") — a user can demand full deletion, and we must be
  able to do it. This is why we designed a `DELETE` endpoint plus a 30-day auto-expiry that wipes
  data from *both* the backend and the CV service.
- **Data minimization & retention** — keep data only as long as genuinely needed (our 30-day limit).
- **Security** — encrypt data at rest and in transit.

Covered in *memoria* §9, and (per our market research) a genuine differentiator since most
competitors don't lead with privacy.

### Biometric data
Data about a person's physical characteristics that can identify them — here, the body pose /
movement extracted from their video. Treated as a special, extra-protected category under GDPR.

---

## How the pipeline works

### Asynchronous ("async") processing
Instead of making the user wait on one long request while a video is analyzed, the backend accepts
the upload, immediately returns a job id, and the analysis happens in the background. The result is
fetched later. Prevents timeouts on long videos and keeps the app responsive.

### Job
A single unit of background work — one video to analyze. It moves through states:
`queued → processing → completed | failed`. Our backend mirrors each CV job as an `Attempt` row.

### Webhook (callback)
A way for the CV service to notify our backend the moment a job finishes, by sending an HTTP
request *to us* (a "callback"). Faster than us repeatedly asking. Secured with a signature so we
know it genuinely came from the CV service.

### Polling
Repeatedly asking "is it done yet?" on an interval. We use it two ways: the frontend polls our
backend for a result, and our backend polls the CV service as a **fallback** in case a webhook is
ever missed.

### Pose estimation
The computer-vision technique of detecting a person's body position in an image/video by locating
skeletal keypoints (joints). Alejandro's prototype uses **MediaPipe** for this.

### Landmarks / keypoints
The specific points on the body that pose estimation finds (hip, knee, ankle, shoulder, …). Joint
**angles** are computed from these to judge technique (e.g. knee angle for squat depth).

### Rep (repetition)
One full execution of the exercise (one squat down-and-up). The pipeline segments the video into
reps and scores each one individually.

### Annotated video
The user's clip with the detected skeleton, joint angles, and feedback drawn on top — the visual
version of the result.

---

## Security & engineering terms

### Shared secret / API key
A private value known only to our backend and the CV service, used to prove requests between them
are legitimate. Sent as a header (e.g. `X-API-Key`). Because it's server-to-server, this replaces
user logins on the internal boundary.

### HMAC signature
A tamper-proof fingerprint attached to the webhook, computed from the message body plus the shared
secret. Our backend recomputes it to confirm the webhook is authentic and unmodified before
trusting it. A timestamp is included to reject old, replayed requests.

### Closed catalog (of codes)
A fixed, agreed list of allowed values — e.g. our error codes (`knee_valgus`,
`insufficient_depth`, `no_pose_detected`, …) — rather than free-form text. It lets the frontend
control the wording, translations, and icons, and keeps the two services in agreement.

### Idempotent / idempotency
An operation that's safe to run more than once with the same effect as running it once. Our webhook
and polling can both deliver the same result, so the backend saves it idempotently (keyed by the
CV job id) — no duplicates.

### Schema (Pydantic)
The formal definition of the *shape* of a piece of data (which fields exist and their types).
Because both our backend and the CV service use FastAPI/**Pydantic** (Python), we can share one
schema definition across the boundary — the biggest defense against integration bugs.

### Reference (URL / pointer)
A small piece of data that points to where something big lives, instead of the big thing itself.
Our backend stores a **URL reference** to the annotated video rather than a copy of the video.
