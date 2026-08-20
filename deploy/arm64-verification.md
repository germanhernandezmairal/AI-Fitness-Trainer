# ARM64 Build Verification

Verifies spec §9's open risk: does `cv-service` (full `opencv-python` + `mediapipe`, non-headless)
actually build and run correctly on `linux/arm64` — the architecture of Oracle's Always-Free
Ampere A1 VM — before any deployment work depends on it.

**Environment:** Colima (Docker CLI via Homebrew), native `aarch64` VM on this Apple Silicon Mac —
no cross-architecture emulation involved, so this closely matches what the real Oracle VM will run.

**Build:** `docker buildx build --platform linux/arm64 -t cv-service-arm64-test --load cv-service/`
— **PASS**. Both `opencv-python==5.0.0.93` and `mediapipe==0.10.14` (pinned in
`cv-service/requirements.txt`) installed cleanly from PyPI's ARM64 wheels, no build-from-source
fallback needed. Full image built (including model download/exporting layers) in under a minute.

One real (non-ARM64) build blocker hit and fixed along the way: `docker buildx`'s build-context
sender failed with `error from sender: failed to xattr cv-service/._GLOSARIO.md: operation not
permitted` — the same exFAT AppleDouble shadow-file issue documented elsewhere in this project
(e.g. the `**/._*` vitest exclude). Fixed by adding `cv-service/.dockerignore` (excludes `._*`,
`__pycache__`, `*.pyc`, `.pytest_cache`) and deleting the AppleDouble files that already existed
on disk before the build ran — the ignore rules alone weren't enough because the build-context
sender walks the tree looking for the Dockerfile/`.dockerignore` themselves before ignore rules
apply, and hit a freshly-created `._.dockerignore` on the first retry. Unrelated to ARM64/wheel
availability.

**Smoke test:** uploaded `backend/tests/fixtures/squat.mp4` to the running ARM64 container via
`POST /v1/jobs`, polled `GET /v1/jobs/{id}` until terminal — **PASS**. Final status `completed`,
6 reps detected (matches the known-good 6-rep result from prior native-architecture testing on
this project). All 6 reps scored 100/100 (`min_knee_angle_deg` 38.8-44.1°), confirming the
`GOOD_DEPTH_ANGLE_DEG` scoring-curve fix (merged from `cv-form-error-detection`, 2026-08-20) also
works correctly on ARM64 — no error codes fired (`errors: []` on all reps, as expected for a clean
deep squat with no forward-lean signal), `algorithm_version: "squat-rules-v1"`.

**Conclusion:** ARM64 deployment is viable for `cv-service` — both MediaPipe and OpenCV have real
ARM64 wheels, the built image runs and produces correct results identical to native-architecture
testing. No workaround needed beyond the `.dockerignore` fix above, which is now committed
alongside this file.
