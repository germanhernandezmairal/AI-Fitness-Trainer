import json
import time
import uuid
from pathlib import Path

import httpx
import respx

from app.security.signing import sign_payload

SQUAT = Path(__file__).parent / "fixtures" / "squat.mp4"

RESULT = {
    "exercise_type": "squat",
    "overall_score": 82,
    "summary": "Good depth overall.",
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


@respx.mock
async def test_full_lifecycle_upload_webhook_read_delete(client, auth_headers, settings):
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    respx.post(f"{settings.cv_service_url}/v1/jobs").mock(
        return_value=httpx.Response(202, json={"job_id": job_id, "status": "queued"})
    )
    respx.delete(f"{settings.cv_service_url}/v1/jobs/{job_id}").mock(
        return_value=httpx.Response(204)
    )

    # 1. Upload
    created = await client.post(
        "/v1/attempts",
        headers=auth_headers,
        files={"video": ("squat.mp4", SQUAT.read_bytes(), "video/mp4")},
        data={"exercise_type": "squat"},
    )
    assert created.status_code == 202
    attempt_id = created.json()["attempt_id"]

    # 2. The frontend polls and sees it queued
    pending = await client.get(f"/v1/attempts/{attempt_id}", headers=auth_headers)
    assert pending.json()["status"] == "queued"

    # 3. The CV service calls back with a signed result
    body = json.dumps({"status": "completed", "result": RESULT}).encode()
    stamp = str(int(time.time()))
    callback = await client.post(
        f"/v1/cv-callback/{attempt_id}",
        content=body,
        headers={
            "X-CV-Signature": sign_payload(body, stamp, settings.cv_webhook_secret),
            "X-CV-Timestamp": stamp,
            "Content-Type": "application/json",
        },
    )
    assert callback.status_code == 204

    # 4. The frontend polls again and sees the result
    done = await client.get(f"/v1/attempts/{attempt_id}", headers=auth_headers)
    body = done.json()
    assert body["status"] == "completed"
    assert body["result"]["overall_score"] == 82

    # 4b. The annotated_video_url points at our own proxy, not the CV service's
    # X-API-Key-gated URL, and fetching it streams the video through
    video_url = body["result"]["annotated_video_url"]
    assert video_url == f"{settings.backend_public_url}/v1/attempts/{attempt_id}/video"
    respx.get(f"{settings.cv_service_url}/v1/jobs/{job_id}/video").mock(
        return_value=httpx.Response(200, content=b"fake-mp4-bytes", headers={"content-type": "video/mp4"})
    )
    video = await client.get(f"/v1/attempts/{attempt_id}/video", headers=auth_headers)
    assert video.status_code == 200
    assert video.content == b"fake-mp4-bytes"

    # 5. It shows up in history
    history = await client.get("/v1/attempts", headers=auth_headers)
    assert any(item["attempt_id"] == attempt_id for item in history.json()["items"])

    # 6. The user erases it
    erased = await client.delete(f"/v1/attempts/{attempt_id}", headers=auth_headers)
    assert erased.status_code == 204

    gone = await client.get(f"/v1/attempts/{attempt_id}", headers=auth_headers)
    assert gone.status_code == 404
