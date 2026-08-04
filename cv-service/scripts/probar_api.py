"""Sube squat.mp4 al servicio CV local y espera el resultado por polling.

Uso: arranca el servidor en otra terminal (ver README) y luego:
    ../.venv/Scripts/python.exe scripts/probar_api.py
"""

import time
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000"
API_KEY = "dev-cv-api-key"
VIDEO_PATH = (
    Path(__file__).resolve().parent.parent.parent / "backend" / "tests" / "fixtures" / "squat.mp4"
)


def main() -> None:
    """Sube squat.mp4, y luego hace polling a GET /v1/jobs/{id} cada 2s hasta
    ver 'completed' o 'failed' — el mismo mecanismo de respaldo que usaría
    el backend si el webhook no le llegara.
    """
    with open(VIDEO_PATH, "rb") as video_file:
        response = httpx.post(
            f"{BASE_URL}/v1/jobs",
            headers={"X-API-Key": API_KEY},
            data={"exercise_type": "squat"},
            files={"video": ("squat.mp4", video_file, "video/mp4")},
            timeout=30.0,
        )

    response.raise_for_status()
    job_id = response.json()["job_id"]
    print(f"Job creado: {job_id}, esperando resultado...")

    while True:
        time.sleep(2)
        status_response = httpx.get(f"{BASE_URL}/v1/jobs/{job_id}", headers={"X-API-Key": API_KEY})
        status_response.raise_for_status()
        job = status_response.json()
        print(f"  status: {job['status']}")

        if job["status"] in ("completed", "failed"):
            print(job)
            break


if __name__ == "__main__":
    main()
