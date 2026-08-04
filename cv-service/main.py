"""La API HTTP del servicio CV: los cuatro endpoints del contrato /v1.

Capa fina a propósito — no hay lógica de análisis aquí. Cada ruta valida lo
mínimo que le corresponde a la capa HTTP (auth, tamaño/formato de subida) y
delega el resto en jobs.py y pipeline.py.
"""

import shutil
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, Header, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

import jobs
import pipeline
import security

app = FastAPI(title="CV Service", version="0.1.0")

MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB, límite del contrato
MAX_DURATION_SEC = 60  # límite del contrato
SUPPORTED_EXERCISE_TYPES = {"squat"}  # único ejercicio soportado en este MVP


def _require_api_key(x_api_key: str | None) -> None:
    """Corta la petición con 401 si la API key no es la esperada.

    Se llama al principio de cada ruta, antes de tocar nada más.
    """
    if not security.check_api_key(x_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad API key")


def _validate_exercise_type(exercise_type: str) -> None:
    """400 si el ejercicio no es uno de los soportados (solo 'squat' en este MVP)."""
    if exercise_type not in SUPPORTED_EXERCISE_TYPES:
        raise HTTPException(status_code=400, detail={"code": "unknown_exercise_type"})


def _validate_size(contents: bytes) -> None:
    """400 si el archivo pesa más que MAX_FILE_SIZE_BYTES."""
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail={"code": "file_too_large"})


def _save_upload(job_id: str, contents: bytes) -> Path:
    """Crea la carpeta del job y escribe ahí el video recibido."""
    job_folder = jobs.job_dir(job_id)
    job_folder.mkdir(parents=True, exist_ok=True)
    input_path = job_folder / "input.mp4"
    input_path.write_bytes(contents)
    return input_path


def _validate_format_and_duration(job_id: str, input_path: Path) -> None:
    """400 si el video no se puede abrir (formato/códec no soportado) o dura
    más de MAX_DURATION_SEC. Abrir el archivo con OpenCV es la comprobación
    real — no nos fiamos del Content-Type que manda el cliente.
    """
    duration = pipeline.probe_duration_sec(input_path)
    if duration is None:
        shutil.rmtree(jobs.job_dir(job_id), ignore_errors=True)
        raise HTTPException(status_code=400, detail={"code": "unsupported_format"})
    if duration > MAX_DURATION_SEC:
        shutil.rmtree(jobs.job_dir(job_id), ignore_errors=True)
        raise HTTPException(status_code=400, detail={"code": "video_too_long"})


@app.post("/v1/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    exercise_type: str = Form(...),
    callback_url: str | None = Form(default=None),
    x_api_key: str | None = Header(default=None),
) -> dict:
    """Recibe el video, lo valida y lo guarda, y lanza el análisis en segundo
    plano. Responde 202 de inmediato — no espera a que el análisis termine.

    El cuerpo de esta función es, a propósito, una lista de pasos en orden:
    autenticar, validar, guardar, validar de nuevo (ya con el archivo en
    disco), y lanzar el análisis. Cada paso vive en su propia función de
    arriba — si algo falla, se puede mirar solo esa función sin leer todo
    el resto.
    """
    _require_api_key(x_api_key)
    _validate_exercise_type(exercise_type)

    contents = await video.read()
    _validate_size(contents)

    job_id = jobs.new_job_id()
    input_path = _save_upload(job_id, contents)
    _validate_format_and_duration(job_id, input_path)

    jobs.create_job(job_id)
    background_tasks.add_task(jobs.run_job, job_id, input_path, callback_url)
    return {"job_id": job_id, "status": "queued"}


@app.get("/v1/jobs/{job_id}")
def get_job(job_id: str, x_api_key: str | None = Header(default=None)) -> dict:
    """Devuelve el estado/resultado actual de un job (para el polling del backend)."""
    _require_api_key(x_api_key)
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")
    return job


@app.delete("/v1/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: str, x_api_key: str | None = Header(default=None)) -> None:
    """Borra el job y sus artefactos. Siempre 204, exista o no el job."""
    _require_api_key(x_api_key)
    jobs.delete_job(job_id)


@app.get("/v1/jobs/{job_id}/video")
def get_annotated_video(job_id: str, x_api_key: str | None = Header(default=None)) -> FileResponse:
    """Sirve el archivo de video anotado — es la URL que se manda como annotated_video_url."""
    _require_api_key(x_api_key)
    video_path = jobs.job_dir(job_id) / "annotated.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="video not ready")
    return FileResponse(video_path, media_type="video/mp4")