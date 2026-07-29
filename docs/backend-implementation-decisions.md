# Backend implementation — decisions and deviations

Companion to [the backend implementation plan](superpowers/plans/2026-07-28-backend-attempts-api.md) and the [API contract design](superpowers/specs/2026-07-27-api-contract-design.md).

Those two documents say what we intended to build. This one records what we decided **while building it** — the points where following the plan literally would have produced something wrong, and what we chose instead. Git history records *what* changed; this records *why*, which the commits cannot.

Last updated 2026-07-29, after Task 7 of 14.

---

## 1. Decisions that override the plan

Each of these overrides text in the plan. They were raised by a code review, escalated because the plan itself mandated the behaviour, and decided deliberately.

### 1.1 Uploads must carry H.264 video; the audio codec is not checked

**The plan said:** probe the video and record its codec in `VideoInfo.video_codec`.

**The problem:** nothing ever read that field. The global constraint says "MP4 (H.264 / AAC) and MOV. Nothing else," but in practice an `.mp4` container carrying HEVC or AV1 passed validation — the codec half of the constraint was computed and thrown away.

**What we do instead:** `ALLOWED_VIDEO_CODECS = {"h264"}`. Anything else is rejected with `unsupported_format`. The **audio** codec is deliberately *not* checked: pose estimation never reads audio, so requiring AAC would reject silent clips and PCM exports for no benefit.

**Consequence we accepted:** iPhone `.mov` recordings default to HEVC, so they will be rejected. Failing fast at upload is better than storing the file, queueing a job, and failing minutes later as a `worker_error` — but this is a real user-facing limit. See the open questions in §4.

### 1.2 An unknown video duration fails closed

**The plan said:** `duration = float(container.duration) / 1_000_000 if container.duration else 0.0`.

**The problem:** a decodable but fragmented container that reports no duration scored **0 seconds**, which always passes the 60-second cap. The check was silently disabled for exactly the class of file most likely to need it.

**What we do instead:** fall back to the video stream's own duration (`stream.duration` × `time_base`), which is often present when the container's is not. If the duration is still unknown after that, reject with `unsupported_format`. An unknown duration is never scored as zero.

### 1.3 Weak dev-default secrets are fixed at the root, not suppressed

**The problem:** PyJWT emits `InsecureKeyLengthWarning` for HMAC keys under 32 bytes. The plan's test secrets were 11 and 18 bytes, and `Settings.jwt_secret` defaulted to `"dev-only-change-me"` (18) — so the warning also fired at runtime on every token the dev server issued.

**What we rejected:** silencing it with a `filterwarnings` entry in `pyproject.toml`. The warning was correctly reporting a too-short default; muting it would have hidden a real signal to make a test suite look tidy.

**What we do instead:** the dev defaults `jwt_secret` and `cv_webhook_secret` are both ≥32 characters, with `.env.example` kept in agreement, and the JWT tests use long secrets too. The signing tests keep their shorter test-local literal — it produces no warning and is not a default anyone can accidentally ship.

**Worth knowing:** PyJWT warns about short keys; Python's `hmac` does not. So the webhook secret had no test symptom at all — it was raised for consistency, not because anything complained.

### 1.4 The `squat.mp4` test fixture is tracked despite the `*.mp4` ignore rule

`.gitignore` excludes `*.mp4` repo-wide, sensible for user uploads and generated frames. But the validation suite needs a real ~470 KB H.264 clip (taken from the `cv-pipeline` branch), and `git add` was silently skipping it — which would have produced a suite that passes locally and fails on a fresh clone.

Fixed with a narrowly scoped negation for that one fixture path, rather than `git add -f`, so the intent is visible in the ignore file itself instead of living in one person's shell history.

---

## 2. Requirements carried into later tasks

Reviews surfaced these, but each belongs to a task that has not been written yet, so they are recorded here rather than fixed early.

| Task | Requirement | Why it matters |
|---|---|---|
| Task 9 — `POST /v1/attempts` | `size_bytes` must be derived from the bytes actually written to storage, never from a client-supplied `Content-Length` | Otherwise the 100 MB cap is bypassed by lying in a header |
| Task 11 — webhook receiver | A bad or absent signature must produce a rejection, not an unhandled exception | `verify_signature` raises `TypeError`/`AttributeError` on malformed input types; unhandled, that surfaces as a 500 where a 401/400 belongs |

---

## 3. Known gaps, deliberately deferred

Real but minor, and not worth interrupting the task flow for. To be triaged before the branch merges.

- The storage path-escape test covers `open` but not `delete` or `path_for`. They share one `_resolve` guard today, so a future refactor that split them would go uncaught.
- `Storage` is not `@runtime_checkable` — fine until something wants an `isinstance` check on an injected storage object.
- `except Exception` in `probe_video` is broad enough to report a genuine programming bug as `unsupported_format`.
- No test covers a container with **no video stream** (an audio-only file), though the code path exists.
- `_resolve_duration_sec` returns a literal `0.0` if a stream reports an explicit zero duration — indistinguishable from "unknown," though arguably correct for a zero-length stream.
- The order of the size check versus the extension check is arbitrary (both are O(1)); only *size before probe* is contractual.

---

## 4. Open questions for Alejandro

1. **Does the CV pipeline decode HEVC?** If yes, §1.1 relaxes to a one-line change and iPhone recordings work. If no, the current strictness is right and the frontend should say so at the file picker.
2. Confirm the four limits the backend now enforces: **MP4/MOV**, **≤100 MB**, **≤60 s**, **30-day retention**.

---

## 5. Environment deviations

The plan was written against a toolchain the development machine does not have. These are workarounds, not design changes — they revert cleanly if the real toolchain arrives.

| Plan assumes | Reality | What we do |
|---|---|---|
| Postgres via `docker compose` | Docker not installed | Native PostgreSQL 16 on `localhost:5432`, role `fitness`. The compose file still ships as a plan deliverable |
| Python 3.12 | Python 3.11.5 only | `requires-python = ">=3.11"`. Verified safe: `StrEnum`, `datetime.UTC` and `typing.Self` all landed in 3.11 |
| `uv` for dependencies and running | `uv` not installed | `python -m venv` + `pip install -e ".[dev]"`; tools invoked as `.venv/Scripts/python.exe -m <tool>` |

---

## 6. How the work is being executed

Each of the plan's 14 tasks is implemented by a fresh agent working only from that task's brief, then checked by a separate reviewer against both the brief and the project's global constraints. A task is not done when its tests pass — it is done when that review clears. Findings go back to the original implementer, and the fix gets its own scoped re-review.

Three of the four decisions in §1 exist because a reviewer flagged something the plan itself had mandated. That is the gate doing its job: passing tests only prove the code does *something*, not that it does what the spec requires.

Progress through Task 7: Tasks 1, 3, 5 and 7 passed review first time; Tasks 2, 4 and 6 needed fix rounds. Suite at 40 passed, 2 expected-fail (placeholders un-marked in Task 10).
