"""Estado de los jobs de análisis y orquestación del trabajo en segundo plano.

Guarda el estado de cada job en un diccionario en memoria (se pierde si se
reinicia el proceso — aceptable para el MVP, el backend hace polling de
respaldo). `run_job` es la función que corre en background: llama al
pipeline de CV, guarda el resultado, y si hay `callback_url` avisa al
backend con un webhook firmado.
"""

import json
import os
import shutil
import time
import uuid
from pathlib import Path

import httpx

import pipeline
import security

STORAGE_DIR = Path(__file__).resolve().parent / "storage"  # carpeta local con los videos de cada job
BASE_URL = os.environ.get("CV_SERVICE_BASE_URL", "http://localhost:8000")  # prefijo para construir annotated_video_url

JOBS: dict[str, dict] = {}  # job_id -> payload de estado/resultado (ver contrato en el diseño)


def new_job_id() -> str:
    """Genera un identificador de job corto y único (p. ej. 'job-a1b2c3d4')."""
    return f"job-{uuid.uuid4().hex[:8]}"


def job_dir(job_id: str) -> Path:
    """Ruta de la carpeta donde viven el video de entrada y el anotado de un job."""
    return STORAGE_DIR / job_id


def create_job(job_id: str) -> None:
    """Registra un job nuevo en estado 'queued', antes de lanzar el análisis."""
    JOBS[job_id] = {"job_id": job_id, "status": "queued"}


def get_job(job_id: str) -> dict | None:
    """Devuelve el estado actual del job, o None si no existe."""
    return JOBS.get(job_id)


def delete_job(job_id: str) -> None:
    """Borra el job y su carpeta de almacenamiento. Idempotente: nunca falla,
    exista o no el job (requisito del contrato de borrado GDPR).
    """
    JOBS.pop(job_id, None)
    shutil.rmtree(job_dir(job_id), ignore_errors=True)


def run_job(job_id: str, input_path: Path, callback_url: str | None) -> None:
    """Ejecuta el análisis de un job y guarda el resultado (pensada para
    correr en un BackgroundTask de FastAPI, fuera del ciclo request/response).

    Traduce las dos formas de fallo del pipeline (nadie detectado / error
    inesperado) al catálogo cerrado de códigos del contrato, y dispara el
    webhook si el backend pidió que le avisáramos con `callback_url`.
    """
    JOBS[job_id] = {"job_id": job_id, "status": "processing"}

    try:
        output_path = job_dir(job_id) / "annotated.mp4"
        result = pipeline.analizar_video(input_path, output_path)
        result["annotated_video_url"] = f"{BASE_URL}/v1/jobs/{job_id}/video"
        payload = {"job_id": job_id, "status": "completed", "result": result}
    except pipeline.NoPoseDetectedError as exc:
        payload = {
            "job_id": job_id,
            "status": "failed",
            "error": {"code": "no_pose_detected", "message": str(exc)},
        }
    except Exception as exc:  # cualquier fallo inesperado del análisis
        payload = {
            "job_id": job_id,
            "status": "failed",
            "error": {"code": "worker_error", "message": str(exc)},
        }

    JOBS[job_id] = payload

    if callback_url:
        _send_webhook(callback_url, payload)


def _send_webhook(callback_url: str, payload: dict) -> None:
    """Envía el resultado firmado a callback_url. Si falla (red caída, etc.)
    no reintenta aquí: el polling del backend (GET /v1/jobs/{id}) es el
    respaldo, así que un webhook perdido no bloquea nada.
    """
    body = json.dumps(payload).encode()
    timestamp = str(int(time.time()))
    signature = security.sign_webhook(body, timestamp)

    try:
        httpx.post(
            callback_url,
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-CV-Signature": signature,
                "X-CV-Timestamp": timestamp,
            },
            timeout=10.0,
        )
    except httpx.HTTPError:
        pass  # el backend hace polling de respaldo si el webhook falla