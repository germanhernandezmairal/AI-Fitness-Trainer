# Fake CV Service

A stand-in for the real CV pipeline that implements the internal contract from
`docs/superpowers/specs/2026-07-27-api-contract-design.md` §4: `POST /v1/jobs`,
`GET /v1/jobs/{id}`, `DELETE /v1/jobs/{id}`, and an HMAC-signed webhook callback.

It ignores the video and returns a canned result after a delay. Its only job is to
let the backend's full loop run before the real service is ready.

## Run

```bash
uvicorn main:app --port 9000
```

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `CV_API_KEY` | `dev-cv-api-key` | must match the backend's `CV_API_KEY` |
| `CV_WEBHOOK_SECRET` | `dev-webhook-secret` | must match the backend's `CV_WEBHOOK_SECRET` |
| `FAKE_PROCESSING_DELAY_SEC` | `5` | how long to "analyze" before calling back |
| `FAKE_FORCE_FAILURE` | *(empty)* | set to a failure code to exercise the failure path |

Set `FAKE_PROCESSING_DELAY_SEC=120` to let the webhook lag past the backend's
`CV_POLL_AFTER_SEC` and watch the polling fallback reconcile the attempt instead.
