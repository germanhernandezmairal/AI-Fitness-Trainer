# Design: Memoria — Chapter 5 (Diseño)

**Date:** 2026-08-24
**Author:** Fullstack role (compiled with Claude)
**Status:** APPROVED (2026-08-24)
**Related:** `memoria-ada-outline.md` §5 (scaffolding this chapter expands), `memoria/03-planificacion.md`
and `memoria/04-requisitos.md` (the two existing chapters, set the file-location and per-chapter-spec
precedent — Ch.4's CU-1..CU-7 are this chapter's direct input for the use-case diagram), the real
backend/frontend/cv-service source (the chapter's actual source of truth, not the outline).

---

## 0. Context and goal

Same per-chapter approach as Ch.3/Ch.4: the memoria's 12 chapters are largely independent, so each
is its own sub-project. This design covers only **Chapter 5 (Diseño)**: architecture, use-case
diagram, class design, UI design, and data persistence design.

**Scope: grounded in the real shipped system, not the outline's speculative stack.** The outline's
§5 scaffolding (`Presentacion_TFG_2024.pdf`-derived, written before any code existed) names Redis
caching, PyTorch, and Express — none of which exist. The real stack is Next.js (frontend) → FastAPI
(backend, attempts API) → FastAPI + MediaPipe/OpenCV (cv-service) + Postgres, no caching layer. Like
Ch.3/Ch.4, this chapter corrects the outline rather than transcribing it — decided explicitly with
the user (2026-08-24), not assumed.

The chapter is written **in Spanish**, matching Ch.3/Ch.4. New file `memoria/05-diseno.md`,
following the `NN-nombre.md` pattern. `memoria-ada-outline.md` stays untouched.

**Deployment topology is out of scope for this chapter.** Vercel/Oracle-VM/Caddy hosting belongs to
a deployment chapter/anexo (§6 or §12 per the outline), not "Diseño" — mentioned here only as a
one-line pointer to `deploy/README.md`.

## 1. Section 1 — Arquitectura

One Mermaid `graph` diagram of the real component architecture:

- **Next.js frontend** (App Router) — calls the backend directly from the browser; refresh token in
  `localStorage`, access token in memory (no BFF layer — decision recorded in
  [[project-real-auth-design]] / `docs/superpowers/specs/2026-08-04-frontend-design.md`).
- **FastAPI backend** (`backend/app/`) — attempts API, auth, the only component with a browser-facing
  contract.
- **FastAPI cv-service** (`cv-service/`) — MediaPipe/OpenCV pose analysis, internal-only (never
  called from the browser).
- **Postgres** — backend's only datastore (`User`, `Attempt`, `RefreshToken`).
- **Local disk storage** — original video files, behind the `Storage` protocol
  (`backend/app/services/storage.py`), not S3.

One design point gets called out in prose (not just the diagram): the **authenticated video-proxy
pattern**. The cv-service's `annotated_video_url` is never given to the browser directly — the
backend rewrites it to `GET /v1/attempts/{attempt_id}/video` (`backend/app/api/attempts.py:183`),
a JWT-protected route that proxies the video using the cv-service's internal `X-API-Key`. This is a
real architectural decision (documented in `project-backend-status` memory as a gap Alejandro found
and the user had fixed), worth explaining *why* — the CV service's internal key must never reach a
user's browser.

Also named: HMAC-SHA256 webhook signing between backend and cv-service (`X-CV-Signature`/
`X-CV-Timestamp`, `timestamp + "." + body`), since it's part of how the two services actually talk,
not just an implementation detail.

## 2. Section 2 — Diagramas de uso

One Mermaid diagram (flowchart-style — Mermaid has no native UML use-case notation, so an actor node
connected to rounded-rectangle use-case nodes is the standard workaround) derived directly from
Ch.4's CU-1..CU-7, no new use cases invented:

Actor **Usuario** → Registrarse (CU-1), Iniciar sesión (CU-2), Cerrar sesión (CU-3), Subir video de
un intento (CU-4), Consultar resultado de un intento (CU-5), Ver historial de intentos (CU-6),
Eliminar un intento — GDPR (CU-7).

No new actors (no admin role exists in the real system) and no new use cases beyond Ch.4's seven —
this diagram visualizes Ch.4's requirements, it doesn't add scope.

## 3. Section 3 — Diseño de clases

One Mermaid `classDiagram` with the three real SQLAlchemy models, fields taken directly from
`backend/app/models/`:

- **User** (`user.py`): `id`, `email`, `hashed_password` (nullable — dev-login users have none, per
  [[project-real-auth-design]]), `created_at`.
- **Attempt** (`attempt.py`): `id`, `user_id`, `exercise_type`, `status`, `cv_job_id`,
  `original_video_ref`, `annotated_video_url`, `result` (JSONB), `overall_score`, `error_code`,
  `created_at`, `completed_at`, `expires_at`, `consent_at`.
- **RefreshToken** (`refresh_token.py`): `id`, `user_id`, `token_hash` (opaque, hashed — never the
  raw token), `issued_at`, `expires_at`, `revoked_at`.

Relationships: `User 1—* Attempt`, `User 1—* RefreshToken`.

Explicit callout (not just a diagram label): the outline's §5 imagined `Exercise`, `Score`,
`Feedback/Tip`, and `VideoAsset` as separate classes. In the real system, per-rep scores, error
codes (`knee_valgus`/`insufficient_depth`/`excessive_forward_lean`), and feedback tips all live as
**nested JSON inside `Attempt.result`** (shaped by the cv-service's contract response), not as
separate tables or ORM classes — `exercise_type` is a plain string field, not a normalized
`Exercise` entity, since only one exercise (squat) exists today. This is a real, deliberate
simplicity choice worth stating plainly, not smoothing over.

## 4. Section 4 — Diseño de interfaz

Real screenshots of the actually-implemented screens, not wireframes — captured via `claude-in-chrome`
against the app running locally (production backend doesn't exist yet — VM still pending). Screens,
one figure each, matching `frontend/src/app/`'s real routes:

1. **Login** (`/login`) and **Registro** (`/register`) — auth entry points (CU-1/CU-2).
2. **Subida de video** (home page, authenticated) — the upload form (CU-4).
3. **Resultado de un intento** (`/attempts/[id]`) — score card, annotated video player (via the
   blob-URL fetch pattern, not a direct `<video src>`), per-rep breakdown with error labels (CU-5).
4. **Historial de intentos** (`/attempts`) — list with status pills (CU-6).

Each figure gets 2-3 sentences of caption/prose on what it shows and which use case(s) it serves —
not just a dropped-in image.

**Local run needed to capture these:** Postgres (Homebrew service) + backend (uvicorn) + a CV
service (real `cv-service`, so a genuine result/score renders rather than `fake-cv-service`'s canned
502) + frontend (`next dev`) — the same loop `backend/README.md`'s "Run the whole loop locally"
section already documents. Register a throwaway account, upload `backend/tests/fixtures/squat.mp4`,
capture screens as the flow progresses.

## 5. Section 5 — Diseño de persistencia de datos

Not a separate outline bullet but named in §5's own intro sentence ("...diseño de persistencia de
datos") — added as its own subsection rather than folded into Section 3, since it covers behavior,
not just schema:

- **Schema management:** Alembic migrations (`backend/alembic/`), current head noted by revision ID.
- **Erasure design (GDPR, CU-7):** `delete_attempt` (`backend/app/services/attempts.py:145`)'s real
  ordering — local video file deleted first, then the cv-service job (if one exists), then the DB
  row, committed last. The ordering is deliberate, not incidental: if the cv-service erasure call
  fails, the exception propagates *before* the row is deleted, so the user can retry rather than the
  app falsely reporting success on a promise it couldn't keep. Named explicitly in Ch.4's CU-7 already
  (per `project-backend-status` memory, Ch.4's final review caught this step order stated backwards
  once already) — this chapter's diagram/prose must match the same real order, not repeat that
  earlier mistake.
- **Retention:** `expires_at` on `Attempt` + the polling reconciler / retention-purge background
  jobs (named, not re-explained in depth — that's implementation, covered in the backend plan doc,
  not this design chapter).
- **Video storage:** local disk via the `Storage` protocol (`backend/app/services/storage.py`), one
  concrete implementation (`LocalFilesystemStorage`) — explicitly not S3, matching the free-tier
  deployment decision in [[project-aws-deployment-constraints]].

## Testing / verification approach

This is a documentation chapter, not code — "testing" means factual accuracy, the same bar Ch.3/Ch.4
were held to:
- Every model field, route, and file:line citation re-checked against the actual current source
  right before writing (not from memory) — this design doc's own citations above were pulled from a
  fresh `grep`/`read` pass this session.
- Every diagram traceable to real code or to Ch.4's existing CU-1..CU-7 — no invented entities,
  actors, or use cases.
- Screenshots are of the real running app, not mockups — captured from an actual local session, not
  described from imagination.
- Whole-chapter review (opus, matching Ch.3/Ch.4's final-review step) before merge, specifically
  checking every claim against the real source it cites.

## Open questions

None — all three real ambiguities (outline-vs-reality grounding, screenshots vs. wireframes, class
diagram scope) were resolved with the user during brainstorming (2026-08-24) before this doc was
written.
