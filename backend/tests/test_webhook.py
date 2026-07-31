import json
import time
import uuid
from datetime import UTC, datetime

import httpx

from app.security.signing import sign_payload

RESULT = {
    "exercise_type": "squat",
    "overall_score": 82,
    "summary": "Good depth.",
    "rep_count": 1,
    "reps": [
        {
            "rep_index": 1,
            "start_time_sec": 0.0,
            "end_time_sec": 2.0,
            "min_knee_angle_deg": 78,
            "score": 90,
            "errors": [],
        }
    ],
    "annotated_video_url": "https://cv-storage/x/annotated.mp4",
    "algorithm_version": "squat-rules-v1",
}

COMPLETED = {"status": "completed", "result": RESULT}
FAILED = {"status": "failed", "error": {"code": "no_pose_detected", "message": "empty frame"}}


def signed(payload: dict, secret: str, timestamp: str | None = None) -> tuple[bytes, dict]:
    body = json.dumps(payload).encode()
    stamp = timestamp or str(int(time.time()))
    return body, {
        "X-CV-Signature": sign_payload(body, stamp, secret),
        "X-CV-Timestamp": stamp,
        "Content-Type": "application/json",
    }


async def test_applies_a_completed_result(client, session, user, make_attempt, settings):
    attempt = await make_attempt(user, status="processing")
    body, headers = signed(COMPLETED, settings.cv_webhook_secret)

    response = await client.post(
        f"/v1/cv-callback/{attempt.id}", content=body, headers=headers
    )

    assert response.status_code == 204
    await session.refresh(attempt)
    assert attempt.status == "completed"
    assert attempt.overall_score == 82
    assert attempt.annotated_video_url == RESULT["annotated_video_url"]
    assert attempt.result["algorithm_version"] == "squat-rules-v1"
    assert attempt.completed_at is not None
    assert attempt.error_code is None


async def test_applies_a_failure(client, session, user, make_attempt, settings):
    attempt = await make_attempt(user, status="processing")
    body, headers = signed(FAILED, settings.cv_webhook_secret)

    response = await client.post(
        f"/v1/cv-callback/{attempt.id}", content=body, headers=headers
    )

    assert response.status_code == 204
    await session.refresh(attempt)
    assert attempt.status == "failed"
    assert attempt.error_code == "no_pose_detected"
    assert attempt.result is None
    assert attempt.completed_at is not None


async def test_rejects_a_wrong_signature(client, session, user, make_attempt, settings):
    attempt = await make_attempt(user, status="processing")
    body, headers = signed(COMPLETED, "the-wrong-secret")

    response = await client.post(
        f"/v1/cv-callback/{attempt.id}", content=body, headers=headers
    )

    assert response.status_code == 401
    await session.refresh(attempt)
    assert attempt.status == "processing"


async def test_rejects_a_missing_signature(client, user, make_attempt):
    attempt = await make_attempt(user, status="processing")

    response = await client.post(
        f"/v1/cv-callback/{attempt.id}",
        content=json.dumps(COMPLETED).encode(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 401


async def test_rejects_a_replayed_old_timestamp(client, user, make_attempt, settings):
    attempt = await make_attempt(user, status="processing")
    stale = str(int(time.time()) - 10_000)
    body, headers = signed(COMPLETED, settings.cv_webhook_secret, timestamp=stale)

    response = await client.post(
        f"/v1/cv-callback/{attempt.id}", content=body, headers=headers
    )

    assert response.status_code == 401


async def test_double_delivery_is_idempotent(client, session, user, make_attempt, settings):
    attempt = await make_attempt(user, status="processing")
    body, headers = signed(COMPLETED, settings.cv_webhook_secret)

    first = await client.post(f"/v1/cv-callback/{attempt.id}", content=body, headers=headers)
    await session.refresh(attempt)
    completed_at = attempt.completed_at

    second = await client.post(f"/v1/cv-callback/{attempt.id}", content=body, headers=headers)

    assert first.status_code == 204
    assert second.status_code == 204
    await session.refresh(attempt)
    assert attempt.completed_at == completed_at


async def test_a_late_webhook_cannot_overwrite_a_terminal_attempt(
    client, session, user, make_attempt, settings
):
    """The poller may have already written a failure; a stale webhook must not undo it."""
    attempt = await make_attempt(
        user, status="failed", error_code="worker_error", completed_at=datetime.now(UTC)
    )
    body, headers = signed(COMPLETED, settings.cv_webhook_secret)

    response = await client.post(f"/v1/cv-callback/{attempt.id}", content=body, headers=headers)

    assert response.status_code == 204
    await session.refresh(attempt)
    assert attempt.status == "failed"
    assert attempt.error_code == "worker_error"


async def test_returns_404_for_an_unknown_attempt(client, settings):
    body, headers = signed(COMPLETED, settings.cv_webhook_secret)

    response = await client.post(f"/v1/cv-callback/{uuid.uuid4()}", content=body, headers=headers)

    assert response.status_code == 404


async def test_rejects_a_payload_that_violates_the_contract(client, user, make_attempt, settings):
    attempt = await make_attempt(user, status="processing")
    body, headers = signed({"status": "completed", "result": None}, settings.cv_webhook_secret)

    response = await client.post(f"/v1/cv-callback/{attempt.id}", content=body, headers=headers)

    assert response.status_code == 422


async def test_rejects_a_non_ascii_signature(client, session, user, make_attempt, settings):
    """A byte > 0x7F in the signature header must fail cleanly, not raise.

    Starlette decodes header bytes as latin-1, so any caller can send a non-ASCII
    X-CV-Signature. hmac.compare_digest raises TypeError on two `str` arguments when
    either is non-ASCII; this must not escape as an unhandled error on the one
    unauthenticated route in the app.
    """
    attempt = await make_attempt(user, status="processing")
    body = json.dumps(COMPLETED).encode()
    stamp = str(int(time.time()))
    headers = httpx.Headers(
        [
            (b"X-CV-Signature", "\xe9".encode("latin-1")),
            (b"X-CV-Timestamp", stamp.encode()),
            (b"Content-Type", b"application/json"),
        ]
    )

    response = await client.post(f"/v1/cv-callback/{attempt.id}", content=body, headers=headers)

    assert response.status_code == 401
    await session.refresh(attempt)
    assert attempt.status == "processing"


async def test_a_bad_signature_against_an_unknown_attempt_still_returns_401(client, settings):
    """Pins verify-before-lookup: an unauthenticated caller gets no attempt-ID oracle."""
    body, headers = signed(COMPLETED, "the-wrong-secret")

    response = await client.post(f"/v1/cv-callback/{uuid.uuid4()}", content=body, headers=headers)

    assert response.status_code == 401


async def test_applies_a_processing_update(client, session, user, make_attempt, settings):
    attempt = await make_attempt(user, status="queued")
    body, headers = signed({"status": "processing"}, settings.cv_webhook_secret)

    response = await client.post(f"/v1/cv-callback/{attempt.id}", content=body, headers=headers)

    assert response.status_code == 204
    await session.refresh(attempt)
    assert attempt.status == "processing"
    assert attempt.completed_at is None
