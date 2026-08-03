"""A fake CV service implementing the internal contract (spec §4).

Accepts a job, waits, then fires a signed webhook with a canned result. Lets the
backend's full loop be demoed before the real pipeline is ready — and doubles as a
reference implementation of the contract for the CV service author.

Run: uvicorn main:app --port 9000
"""

import asyncio
import hashlib
import hmac
import json
import os
import time
import uuid

import httpx
from fastapi import FastAPI, File, Form, Header, HTTPException, Response, UploadFile, status

API_KEY = os.environ.get("CV_API_KEY", "dev-cv-api-key")
WEBHOOK_SECRET = os.environ.get("CV_WEBHOOK_SECRET", "dev-webhook-secret")
PROCESSING_DELAY_SEC = float(os.environ.get("FAKE_PROCESSING_DELAY_SEC", "5"))
# Set to a failure code (e.g. "no_pose_detected") to exercise the failure path.
FORCE_FAILURE = os.environ.get("FAKE_FORCE_FAILURE", "")

app = FastAPI(title="Fake CV Service", version="0.1.0")

JOBS: dict[str, dict] = {}
# asyncio only holds a weak reference to running tasks; without this set the
# background "analysis" can be garbage-collected mid-flight.
BACKGROUND: set[asyncio.Task] = set()


def _canned_result() -> dict:
    return {
        "exercise_type": "squat",
        "overall_score": 82,
        "summary": "Good depth overall, but knees collapse inward on 2 of 5 reps.",
        "rep_count": 2,
        "reps": [
            {
                "rep_index": 1,
                "start_time_sec": 2.1,
                "end_time_sec": 5.4,
                "min_knee_angle_deg": 78,
                "score": 90,
                "errors": [],
            },
            {
                "rep_index": 2,
                "start_time_sec": 6.0,
                "end_time_sec": 9.1,
                "min_knee_angle_deg": 65,
                "score": 60,
                "errors": ["knee_valgus", "insufficient_depth"],
            },
        ],
        "annotated_video_url": "https://fake-cv-storage.local/annotated.mp4",
        "algorithm_version": "fake-v0",
    }


def _terminal_payload() -> dict:
    if FORCE_FAILURE:
        return {
            "status": "failed",
            "error": {"code": FORCE_FAILURE, "message": "forced by FAKE_FORCE_FAILURE"},
        }
    return {"status": "completed", "result": _canned_result()}


def _sign(body: bytes, timestamp: str) -> str:
    message = f"{timestamp}.".encode() + body
    return hmac.new(WEBHOOK_SECRET.encode(), message, hashlib.sha256).hexdigest()


def _require_api_key(provided: str | None) -> None:
    if provided != API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad API key")


async def _process(job_id: str, callback_url: str) -> None:
    await asyncio.sleep(PROCESSING_DELAY_SEC)
    payload = _terminal_payload()
    JOBS[job_id] = payload

    body = json.dumps(payload).encode()
    timestamp = str(int(time.time()))
    async with httpx.AsyncClient() as http:
        try:
            await http.post(
                callback_url,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-CV-Signature": _sign(body, timestamp),
                    "X-CV-Timestamp": timestamp,
                },
                timeout=10.0,
            )
        except httpx.HTTPError as exc:
            print(f"[fake-cv] webhook to {callback_url} failed: {exc} (backend will poll)")


@app.post("/v1/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    video: UploadFile = File(...),
    exercise_type: str = Form(...),
    callback_url: str = Form(...),
    x_api_key: str | None = Header(default=None),
) -> dict:
    _require_api_key(x_api_key)
    await video.read()  # drain the upload; the fake does not keep it

    job_id = f"fake-{uuid.uuid4().hex[:8]}"
    JOBS[job_id] = {"status": "processing"}
    task = asyncio.create_task(_process(job_id, callback_url))
    BACKGROUND.add(task)
    task.add_done_callback(BACKGROUND.discard)
    print(f"[fake-cv] accepted {job_id} for {exercise_type}, callback -> {callback_url}")
    return {"job_id": job_id, "status": "queued"}


@app.get("/v1/jobs/{job_id}")
async def get_job(job_id: str, x_api_key: str | None = Header(default=None)) -> dict:
    _require_api_key(x_api_key)
    if job_id not in JOBS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown job")
    return JOBS[job_id]


@app.delete("/v1/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: str, x_api_key: str | None = Header(default=None)) -> Response:
    _require_api_key(x_api_key)
    JOBS.pop(job_id, None)  # idempotent by contract
    return Response(status_code=status.HTTP_204_NO_CONTENT)
