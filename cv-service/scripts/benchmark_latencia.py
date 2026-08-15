"""Mide latencia end-to-end y degradación bajo concurrencia de cv-service.

Pensado para rellenar RNF-2 (latencia) y RNF-3 (capacidad concurrente) de
`memoria/04-requisitos.md` con datos reales, y para poder re-correrlo cuando
cambie el pipeline o el video de prueba.

Uso: arranca el servidor en otra terminal (ver README) y luego:
    ../.venv/Scripts/python.exe scripts/benchmark_latencia.py

Solo mide `POST /v1/jobs` -> polling hasta `completed`/`failed`, igual que
`probar_api.py`, pero repetido en secuencia (línea base) y en paralelo
(concurrencia) con `concurrent.futures`. No mide uso de CPU/RAM del proceso
-- ver la sección "Cómo leer estos números" en el docstring de `_run_job`.
"""

import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000"
API_KEY = "dev-cv-api-key"
VIDEO_PATH = (
    Path(__file__).resolve().parent.parent.parent / "backend" / "tests" / "fixtures" / "squat.mp4"
)
POLL_INTERVAL_SEC = 0.5
CONCURRENCY_LEVELS = (1, 2, 3, 4)
RUNS_PER_LEVEL = 3


def _run_job() -> float:
    """Sube VIDEO_PATH, espera a que el job termine, y devuelve la latencia
    total en segundos (subida incluida). Borra el job al terminar para no
    dejar basura en `storage/`.

    Cómo leer estos números: esta latencia es específica del video de prueba
    (~13s de squat.mp4, el único video de referencia del repo) y de esta
    máquina -- sirve para comparar concurrencia=1 contra concurrencia=N en
    el mismo hardware, no como cifra absoluta portable a otro entorno.
    """
    start = time.perf_counter()

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

    while True:
        time.sleep(POLL_INTERVAL_SEC)
        status_response = httpx.get(f"{BASE_URL}/v1/jobs/{job_id}", headers={"X-API-Key": API_KEY})
        status_response.raise_for_status()
        job = status_response.json()
        if job["status"] in ("completed", "failed"):
            if job["status"] == "failed":
                print(f"  ADVERTENCIA: job {job_id} falló: {job.get('error')}")
            break

    elapsed = time.perf_counter() - start
    httpx.delete(f"{BASE_URL}/v1/jobs/{job_id}", headers={"X-API-Key": API_KEY})
    return elapsed


def _run_level(concurrency: int) -> list[float]:
    """Lanza `concurrency` jobs a la vez (uno por hilo) y devuelve sus latencias.

    Repetido RUNS_PER_LEVEL veces por nivel para suavizar ruido (cache de
    disco, jitter del SO, etc.).
    """
    latencies = []
    for _ in range(RUNS_PER_LEVEL):
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            latencies.extend(pool.map(lambda _: _run_job(), range(concurrency)))
    return latencies


def main() -> None:
    print(f"Video de prueba: {VIDEO_PATH.name}\n")
    baseline_mean = None

    for concurrency in CONCURRENCY_LEVELS:
        print(f"Concurrencia={concurrency} ({RUNS_PER_LEVEL} tandas)...")
        latencies = _run_level(concurrency)
        mean = statistics.mean(latencies)
        if baseline_mean is None:
            baseline_mean = mean

        print(
            f"  latencia por job: media={mean:.1f}s  mediana={statistics.median(latencies):.1f}s "
            f"min={min(latencies):.1f}s  max={max(latencies):.1f}s  "
            f"(vs. concurrencia=1: {mean / baseline_mean:.2f}x)\n"
        )


if __name__ == "__main__":
    main()
