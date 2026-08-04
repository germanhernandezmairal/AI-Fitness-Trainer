# Design: Frontend (v1)

**Date:** 2026-08-04
**Author:** Fullstack role (compiled with Claude)
**Status:** APPROVED (2026-08-04)
**Related:** `ai-fitness-trainer-concept.md` (original stack intent), `docs/2026-07-27-market-research.md`
(async upload-based MVP model), `docs/superpowers/specs/2026-07-27-api-contract-design.md` (public
boundary the frontend consumes), `docs/superpowers/plans/2026-08-04-real-auth.md` (the auth API this
design integrates with), `memoria-ada-outline.md` §4–5 (functional requirements, wireframe scope,
WCAG requirement).

---

## 0. Context and goal

No frontend code exists yet. The backend's public boundary (`/v1/attempts`, `/v1/auth/*`) is
complete and tested: upload a squat video, poll for CV analysis results, list history, delete an
attempt (GDPR erasure), and now real password-based authentication alongside the existing dev-login
stub. This design covers the first frontend version — enough to exercise every endpoint the backend
already supports, no more.

**Explicitly out of scope for v1** (per the original concept doc's own "Possible Extensions" list
and the market-research doc's MVP framing): live webcam recording/real-time analysis (MVP is
pre-recorded upload only), a progress dashboard with trend charts across attempts, multiple exercise
types (backend only supports `squat` today).

## 1. Platform and stack

Next.js 15, **App Router**, TypeScript. Chosen over a plain Vite+React SPA or the older Pages Router
because it matches the concept doc's stated intent exactly and is the current standard for new
Next.js projects — accepting the trade-off that React Server Components add a real learning curve
around client/server component boundaries, which matters here since auth-token handling and
attempt-status polling are both inherently client-side.

- **Styling/components:** Tailwind CSS + shadcn/ui — accessible-by-default primitives, which matters
  given the memoria's explicit WCAG requirement (§4 Requisitos no funcionales).
- **Data fetching/polling:** TanStack Query.
- **Location:** `frontend/`, sibling to `backend/`, `cv-service/`, `fake-cv-service/` at the repo
  root, matching the existing per-service layout convention.

## 2. Auth token storage

Two options were weighed: (a) the browser calling the FastAPI backend directly, with the access
token in memory and the refresh token in `localStorage`; or (b) a backend-for-frontend layer of
Next.js Route Handlers proxying every auth call and setting the refresh token as an httpOnly cookie
(invisible to JS, immune to XSS token theft, but meaningfully more code — proxy routes for every
auth call plus middleware to attach `Authorization` on server-rendered requests).

**Chosen: (a), direct calls.** Simpler to build, and for a portfolio/TFG-scoped project the
localStorage XSS exposure is an accepted, explicitly-named trade-off rather than an oversight. The
backend needs one small addition it doesn't have today: CORS middleware (`app/main.py` currently has
none — see `docs/superpowers/plans/2026-08-04-real-auth.md` for backend context).

## 3. Pages and components

| Route | Purpose |
|---|---|
| `/register`, `/login` | Auth forms — `POST /v1/auth/register` / `/login`, store the returned token pair |
| `/` | Protected home: `AttemptHistoryList` (paginated `GET /v1/attempts`) + entry point to upload |
| `/attempts/[id]` | Detail/results view — polls while non-terminal, renders the result once `completed`, delete action |

- **`AuthProvider`** — holds the access token in memory (React context), exposes
  login/register/logout, and drives the refresh flow.
- **`apiClient`** — a shared `fetch` wrapper that attaches `Authorization: Bearer <token>`; on a 401
  it attempts exactly one refresh-and-retry (matching the backend's rotate-on-refresh semantics —
  see `docs/superpowers/plans/2026-08-04-real-auth.md`), and on a second failure clears tokens and
  redirects to `/login`.
- **`VideoUploadForm`** — file picker with a client-side pre-check mirroring the backend's limits
  (format, ≤100MB, exercise type fixed to `squat`), `POST /v1/attempts`, redirect to
  `/attempts/[id]`.
- **`AttemptStatusPoller`** — TanStack Query `refetchInterval` while `status` is `queued`/
  `processing`; stops once terminal.
- **`AttemptResult`** — renders score, summary, per-rep breakdown, and the annotated video.
- **`AttemptHistoryList`** — paginated list, links to detail, delete action.

## 4. The video-auth wrinkle

`GET /v1/attempts/{id}/video` is JWT-protected via the `Authorization` header — deliberately, so the
CV service's internal API key never reaches the browser (see the real-auth-adjacent backend work in
`docs/superpowers/plans/2026-08-04-real-auth.md`'s related session). A plain `<video src="...">` tag
can only send cookies automatically, not custom headers, and §2 already chose header-based auth over
cookies. **Resolution:** `AttemptResult` fetches the video with the header via `fetch()`, wraps the
response in a blob, and sets `URL.createObjectURL(blob)` as the `<video>` `src`. This needs no
backend change and works today. Trade-off, accepted for v1: the whole file downloads before playback
starts — no HTTP range-request seeking mid-download. Worth revisiting (e.g. a short-lived signed
query-param token on that one route) if seeking UX becomes a priority later.

## 5. Error handling

| Case | Handling |
|---|---|
| 401 on any authenticated call | One silent refresh-and-retry via `apiClient`; second failure clears tokens, redirects to `/login` |
| 422 (register/login validation) | Inline field errors |
| 400 upload rejection (`unsupported_format`, `file_too_large`, `video_too_long`, `unknown_exercise_type`) | Inline on the upload form. The backend has no user-facing copy for these yet (unlike CV-failure codes, which already have a Spanish `USER_MESSAGES` map server-side) — the frontend owns its own copy table for these four codes; no backend change needed |
| 502 (CV service unreachable) | Retry banner on the upload/detail view |
| Network/offline | Generic retry, same banner |

## 6. Testing

Vitest + React Testing Library for components/hooks (form validation, the polling hook, `apiClient`'s
refresh-and-retry logic). Playwright for one end-to-end path — register → login → upload → poll to a
result → delete — run against the real backend + `fake-cv-service` (already deterministic and fast;
`FAKE_FORCE_FAILURE` lets the same e2e setup exercise the failure path too, no extra infra needed).

## 7. Explicitly out of scope

- Webcam recording / real-time analysis.
- Progress dashboard with trend charts across attempts.
- Multiple exercise types (backend only supports `squat`).
- A more secure (httpOnly-cookie, BFF) auth token storage model — named as a viable alternative in
  §2, not chosen for v1.
- HTTP range-request video seeking (§4) — accepted limitation of the blob-URL approach.
