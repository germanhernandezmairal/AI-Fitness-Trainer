# Servicio CV (MVP) — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir una API FastAPI de un solo proceso que envuelva la lógica de detección de
postura de `script.py`, cumpliendo el contrato `/v1` acordado con backend (POST/GET/DELETE jobs,
webhook firmado, límites de subida) sin cola de tareas ni almacenamiento externo.

**Architecture:** Cuatro archivos con un propósito cada uno (`security.py`, `pipeline.py`,
`jobs.py`, `main.py`) dentro de `cv-service/`, con un diccionario en memoria como estado y
`storage/` en disco local para los videos. `main.py` recibe el video y delega el análisis a una
`BackgroundTask` de FastAPI (mismo proceso, sin Redis/Celery) que ejecuta `pipeline.py` y, si
hay `callback_url`, dispara un webhook firmado con HMAC.

**Tech Stack:** Python 3.10, FastAPI + Uvicorn, OpenCV (`opencv-python`), MediaPipe, NumPy,
httpx (cliente HTTP para el webhook y para el script de prueba manual), pytest.

## Global Constraints

- Prefijo `/v1` en todos los endpoints del contrato.
- Auth: header `X-API-Key` en cada request entrante; env var `CV_API_KEY` (default de
  desarrollo `dev-cv-api-key`, igual que `fake-cv-service`).
- Webhook firmado: header `X-CV-Signature` = `HMAC-SHA256(timestamp + "." + body,
  CV_WEBHOOK_SECRET)` en hex, más `X-CV-Timestamp`; env var `CV_WEBHOOK_SECRET` (default de
  desarrollo `dev-webhook-secret-change-me-in-production`, igual que `fake-cv-service`).
- El payload del webhook (y de `GET /v1/jobs/{id}`) lleva `job_id` en el nivel superior.
- Límites de subida: contenedor MP4/MOV, ≤100 MB, ≤60 s. Códec real validado abriendo el video
  con OpenCV (no se confía en `Content-Type`); HEVC queda fuera de alcance (se rechaza si
  OpenCV no puede abrirlo — no hay whitelist de códecs explícita).
- Sin Celery/Redis/S3/MinIO: `BackgroundTasks` de FastAPI + diccionario en memoria + disco
  local (`cv-service/storage/`, en `.gitignore`).
- `errors: []` en cada rep por ahora (sin detección de `knee_valgus` / `insufficient_depth` /
  `excessive_forward_lean` en este MVP).
- Umbrales de ángulo de rodilla (heredados de `script.py`): de pie ≥160°, profundidad buena en
  `[70°, 100°]`.
- `algorithm_version`: `"squat-rules-v0"`.
- `exercise_type` soportado en este MVP: solo `"squat"` — cualquier otro valor es
  `400 unknown_exercise_type`.

---

### Task 1: Andamiaje del proyecto + `security.py`

**Files:**
- Create: `cv-service/requirements.txt`
- Create: `cv-service/security.py`
- Create: `cv-service/tests/conftest.py`
- Test: `cv-service/tests/test_security.py`
- Modify: `.gitignore` (raíz del repo)

**Interfaces:**
- Produces: `security.check_api_key(provided: str | None) -> bool`,
  `security.sign_webhook(body: bytes, timestamp: str) -> str`, constantes
  `security.API_KEY: str`, `security.WEBHOOK_SECRET: str`.

- [ ] **Step 1: Crear la estructura de carpetas y `requirements.txt`**

```bash
mkdir -p cv-service/tests
```

Contenido de `cv-service/requirements.txt`:

```
fastapi>=0.111
uvicorn[standard]>=0.30
python-multipart>=0.0.9
httpx>=0.27
opencv-python==5.0.0.93
mediapipe==0.10.14
numpy==2.2.6
pytest>=8.2
```

(Las tres últimas versiones son las que ya tienes instaladas en `.venv` para `script.py` — se
fijan tal cual para no romper lo que ya funciona.)

- [ ] **Step 2: Añadir `cv-service/storage/` al `.gitignore` de la raíz**

Añade esta línea al final de `.gitignore`:

```
cv-service/storage/
```

- [ ] **Step 3: Instalar las dependencias nuevas**

```bash
.venv/Scripts/python.exe -m pip install fastapi "uvicorn[standard]" python-multipart httpx pytest
```

- [ ] **Step 4: Crear `cv-service/tests/conftest.py` para que los tests encuentren los módulos**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

(Sin esto, `import security` desde `tests/test_security.py` falla porque `security.py` vive un
nivel por encima, en `cv-service/`, no dentro de `tests/`.)

- [ ] **Step 5: Escribir los tests que fallan, para `check_api_key` y `sign_webhook`**

`cv-service/tests/test_security.py`:

```python
import security


def test_check_api_key_accepts_the_configured_key():
    assert security.check_api_key(security.API_KEY) is True


def test_check_api_key_rejects_wrong_or_missing_key():
    assert security.check_api_key("wrong-key") is False
    assert security.check_api_key(None) is False


def test_sign_webhook_matches_hand_computed_hmac():
    import hashlib
    import hmac

    body = b'{"job_id": "abc123", "status": "completed"}'
    timestamp = "1700000000"
    expected = hmac.new(
        security.WEBHOOK_SECRET.encode(),
        f"{timestamp}.".encode() + body,
        hashlib.sha256,
    ).hexdigest()

    assert security.sign_webhook(body, timestamp) == expected
```

- [ ] **Step 6: Ejecutar los tests y confirmar que fallan**

```bash
cd cv-service && ../.venv/Scripts/python.exe -m pytest tests/test_security.py -v
```

Esperado: `FAIL` — `ModuleNotFoundError: No module named 'security'` (todavía no existe el
archivo).

- [ ] **Step 7: Implementar `cv-service/security.py`**

```python
"""Autenticación del servicio CV: valida la API key de las peticiones entrantes
y firma los webhooks salientes para que el backend pueda verificar su origen.
"""

import hashlib
import hmac
import os

API_KEY = os.environ.get("CV_API_KEY", "dev-cv-api-key")
WEBHOOK_SECRET = os.environ.get(
    "CV_WEBHOOK_SECRET", "dev-webhook-secret-change-me-in-production"
)


def check_api_key(provided: str | None) -> bool:
    """Compara la API key recibida en el header X-API-Key contra la configurada."""
    return provided == API_KEY


def sign_webhook(body: bytes, timestamp: str) -> str:
    """Firma el cuerpo del webhook con HMAC-SHA256, igual que espera el backend.

    La firma cubre "timestamp + '.' + body" para que el backend pueda rechazar
    mensajes reenviados fuera de su ventana de tolerancia (protección anti-replay).
    """
    message = f"{timestamp}.".encode() + body
    return hmac.new(WEBHOOK_SECRET.encode(), message, hashlib.sha256).hexdigest()
```

- [ ] **Step 8: Ejecutar los tests y confirmar que pasan**

```bash
cd cv-service && ../.venv/Scripts/python.exe -m pytest tests/test_security.py -v
```

Esperado: `3 passed`.

- [ ] **Step 9: Commit**

```bash
git add cv-service/requirements.txt cv-service/security.py cv-service/tests/conftest.py cv-service/tests/test_security.py .gitignore
git commit -m "feat(cv-service): add API key check and webhook HMAC signing"
```

---

### Task 2: `pipeline.py` — funciones puras (ángulo, score, segmentación de reps)

**Files:**
- Create: `cv-service/pipeline.py`
- Test: `cv-service/tests/test_pipeline.py`

**Interfaces:**
- Consumes: nada de tareas anteriores.
- Produces: `pipeline.STANDING_THRESHOLD: float` (160), `pipeline.GOOD_DEPTH_MIN: float` (70),
  `pipeline.GOOD_DEPTH_MAX: float` (100), `pipeline.calculate_angle(a: list[float], b:
  list[float], c: list[float]) -> float`, `pipeline.score_from_angle(min_angle: float) -> int`,
  `pipeline.build_rep(rep_index: int, start_frame: int, end_frame: int, fps: float, min_angle:
  float) -> dict` (claves: `rep_index`, `start_time_sec`, `end_time_sec`, `min_knee_angle_deg`,
  `score`, `errors`), `pipeline.segment_reps(detections: list[tuple[int, float]], fps: float) ->
  list[dict]` (lista de dicts con la forma de `build_rep`).

- [ ] **Step 1: Escribir los tests que fallan**

`cv-service/tests/test_pipeline.py`:

```python
import pipeline


def test_calculate_angle_of_a_right_angle():
    # cadera y tobillo alineados en el mismo eje, rodilla en el vértice: 90°
    hip = [0, 0]
    knee = [0, 1]
    ankle = [1, 1]

    assert pipeline.calculate_angle(hip, knee, ankle) == pytest.approx(90.0, abs=0.1)


def test_score_from_angle_within_good_depth_is_100():
    assert pipeline.score_from_angle(85) == 100
    assert pipeline.score_from_angle(70) == 100
    assert pipeline.score_from_angle(100) == 100


def test_score_from_angle_outside_good_depth_is_penalized():
    # 10 grados por debajo del mínimo (70): 100 - 10*3 = 70
    assert pipeline.score_from_angle(60) == 70
    # 15 grados por encima del máximo (100): 100 - 15*3 = 55
    assert pipeline.score_from_angle(115) == 55
    # penalización nunca baja de 0
    assert pipeline.score_from_angle(0) == 0


def test_segment_reps_counts_two_full_repetitions():
    # de pie -> bajando -> abajo -> subiendo -> de pie, dos veces
    detections = [
        (0, 170), (1, 150), (2, 90), (3, 80), (4, 170),
        (5, 170), (6, 140), (7, 65), (8, 175),
    ]

    reps = pipeline.segment_reps(detections, fps=30.0)

    assert len(reps) == 2
    assert reps[0]["rep_index"] == 1
    assert reps[0]["min_knee_angle_deg"] == 80
    assert reps[1]["rep_index"] == 2
    assert reps[1]["min_knee_angle_deg"] == 65


def test_segment_reps_ignores_an_incomplete_repetition():
    # empieza a bajar pero el video se corta antes de volver a "de pie"
    detections = [(0, 170), (1, 150), (2, 90)]

    reps = pipeline.segment_reps(detections, fps=30.0)

    assert reps == []
```

Añade `import pytest` al principio del archivo (se usa `pytest.approx`).

- [ ] **Step 2: Ejecutar los tests y confirmar que fallan**

```bash
cd cv-service && ../.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v
```

Esperado: `FAIL` — `ModuleNotFoundError: No module named 'pipeline'`.

- [ ] **Step 3: Implementar las funciones puras en `cv-service/pipeline.py`**

```python
"""Lógica de análisis de sentadilla.

Dos partes con distinto grado de testeo: las funciones puras (ángulo, score,
`segment_reps`) no tocan video ni MediaPipe, así que se prueban con datos
sintéticos (`tests/test_pipeline.py`). `analizar_video` sí usa MediaPipe/
OpenCV de verdad sobre el archivo de video — esa parte se verifica a mano,
viendo el video anotado que produce, en vez de con pytest.
"""

import numpy as np

STANDING_THRESHOLD = 160.0  # ángulo de rodilla a partir del cual se considera "de pie"
GOOD_DEPTH_MIN = 70.0  # rango de profundidad considerado buena sentadilla
GOOD_DEPTH_MAX = 100.0
PENALTY_PER_DEGREE = 3  # puntos que se restan del score por cada grado fuera del rango bueno


class NoPoseDetectedError(Exception):
    """No se detectó a ninguna persona en ningún frame del video."""


def calculate_angle(a, b, c) -> float:
    """Calcula el ángulo en grados formado por los puntos a-b-c, con vértice en b.

    Pensado para (cadera, rodilla, tobillo): el ángulo resultante es el ángulo
    de la rodilla.
    """
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    ba = a - b
    bc = c - b

    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0)

    return float(np.degrees(np.arccos(cosine_angle)))


def score_from_angle(min_angle: float) -> int:
    """Puntúa una repetición según lo cerca que quedó su ángulo mínimo del rango bueno.

    100 si el ángulo mínimo cae dentro de [GOOD_DEPTH_MIN, GOOD_DEPTH_MAX];
    fuera de ese rango, penaliza PENALTY_PER_DEGREE puntos por cada grado de
    distancia al límite más cercano, sin bajar de 0.
    """
    if GOOD_DEPTH_MIN <= min_angle <= GOOD_DEPTH_MAX:
        return 100

    if min_angle < GOOD_DEPTH_MIN:
        distance = GOOD_DEPTH_MIN - min_angle
    else:
        distance = min_angle - GOOD_DEPTH_MAX

    return max(0, round(100 - distance * PENALTY_PER_DEGREE))


def build_rep(rep_index: int, start_frame: int, end_frame: int, fps: float, min_angle: float) -> dict:
    """Construye el diccionario de una repetición con la forma que espera el contrato."""
    return {
        "rep_index": rep_index,
        "start_time_sec": round(start_frame / fps, 2),
        "end_time_sec": round(end_frame / fps, 2),
        "min_knee_angle_deg": round(min_angle, 1),
        "score": score_from_angle(min_angle),
        "errors": [],
    }


def segment_reps(detections: list[tuple[int, float]], fps: float) -> list[dict]:
    """Agrupa una secuencia de ángulos de rodilla en repeticiones completas.

    `detections` es una lista de (número_de_frame, ángulo), solo para los
    frames donde sí se detectó a la persona. Usa una máquina de estados
    simple: de pie -> bajando/abajo/subiendo -> de pie de nuevo cierra una
    repetición. Una repetición que empieza pero nunca vuelve a "de pie"
    (video cortado a mitad de rep) no se cuenta.
    """
    state = "standing"
    rep_start_frame = None
    min_angle_in_rep = None
    reps = []

    for frame_index, angle in detections:
        if state == "standing" and angle < STANDING_THRESHOLD:
            state = "descending"
            rep_start_frame = frame_index
            min_angle_in_rep = angle
        elif state != "standing":
            min_angle_in_rep = min(min_angle_in_rep, angle)
            if angle >= STANDING_THRESHOLD:
                reps.append(
                    build_rep(len(reps) + 1, rep_start_frame, frame_index, fps, min_angle_in_rep)
                )
                state = "standing"

    return reps
```

- [ ] **Step 4: Ejecutar los tests y confirmar que pasan**

```bash
cd cv-service && ../.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v
```

Esperado: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add cv-service/pipeline.py cv-service/tests/test_pipeline.py
git commit -m "feat(cv-service): add pure scoring and rep-segmentation logic"
```

---

### Task 3: `pipeline.py` — `analizar_video` y `probe_duration_sec` (I/O real con MediaPipe)

Esta parte reutiliza MediaPipe/OpenCV para procesar el video de verdad. Tal como acordamos en el
diseño, no lleva tests automatizados (la corrección visual se revisa a ojo con el video anotado);
en su lugar, este task termina con una verificación manual explícita.

**Files:**
- Modify: `cv-service/pipeline.py` (añade `analizar_video` y `probe_duration_sec` al archivo del
  Task 2)

**Interfaces:**
- Consumes: `calculate_angle`, `segment_reps`, `NoPoseDetectedError` (Task 2).
- Produces: `pipeline.probe_duration_sec(path: Path) -> float | None` (None si el archivo no se
  puede abrir como video), `pipeline.analizar_video(input_path: Path, output_path: Path) ->
  dict` (claves: `exercise_type`, `overall_score`, `summary`, `rep_count`, `reps`,
  `algorithm_version` — **sin** `annotated_video_url`, eso lo añade `jobs.py` en el Task 4 con
  la URL pública). Lanza `NoPoseDetectedError` si no se detecta a la persona en ningún frame.

- [ ] **Step 1: Añadir los imports de video y las dos funciones a `cv-service/pipeline.py`**

Al principio del archivo, junto a `import numpy as np`:

```python
from pathlib import Path

import cv2
import mediapipe as mp

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
```

Al final del archivo:

```python
def probe_duration_sec(path: Path) -> float | None:
    """Devuelve la duración del video en segundos, o None si OpenCV no puede
    abrirlo (contenedor/códec no soportado — así se detecta 'formato no
    soportado' sin fiarnos del Content-Type que manda el backend).
    """
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        return None

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()

    if not fps:
        return None

    return frame_count / fps


def analizar_video(input_path: Path, output_path: Path) -> dict:
    """Analiza un video de sentadilla de principio a fin: recorre cada frame
    con MediaPipe, calcula el ángulo de rodilla, dibuja el esqueleto sobre el
    frame y lo escribe en `output_path`, y al terminar agrupa los ángulos en
    repeticiones (ver `segment_reps`).

    Lanza `NoPoseDetectedError` si no se detectó a la persona en ningún
    frame. `output_path` no incluye la URL pública del video — eso lo añade
    quien llame a esta función (jobs.py), que es quien conoce esa URL.
    """
    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise ValueError(f"No se pudo abrir el video: {input_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

    pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

    detections: list[tuple[int, float]] = []
    frame_index = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb_frame)

            if results.pose_landmarks:
                landmarks = results.pose_landmarks.landmark
                hip = [
                    landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x * width,
                    landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y * height,
                ]
                knee = [
                    landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].x * width,
                    landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].y * height,
                ]
                ankle = [
                    landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].x * width,
                    landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].y * height,
                ]
                angle = calculate_angle(hip, knee, ankle)
                detections.append((frame_index, angle))

                mp_drawing.draw_landmarks(frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
                cv2.putText(
                    frame, f"{int(angle)} deg",
                    (int(knee[0]) + 20, int(knee[1])),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2, cv2.LINE_AA,
                )

            writer.write(frame)
            frame_index += 1
    finally:
        cap.release()
        writer.release()
        pose.close()

    if not detections:
        raise NoPoseDetectedError("No se detectó a la persona en ningún frame del video.")

    reps = segment_reps(detections, fps)
    overall_score = round(sum(rep["score"] for rep in reps) / len(reps)) if reps else 0

    return {
        "exercise_type": "squat",
        "overall_score": overall_score,
        "summary": f"{len(reps)} repetición(es) detectada(s).",
        "rep_count": len(reps),
        "reps": reps,
        "algorithm_version": "squat-rules-v0",
    }
```

- [ ] **Step 2: Verificación manual — correr el análisis sobre `squat.mp4`**

Desde la raíz del repo:

```bash
.venv/Scripts/python.exe -c "
from pathlib import Path
import sys
sys.path.insert(0, 'cv-service')
import pipeline

result = pipeline.analizar_video(Path('squat.mp4'), Path('cv-service/storage/_manual_test/annotated.mp4'))
print(result)
"
```

Esperado: imprime un diccionario con `rep_count >= 1`, una lista `reps` con `min_knee_angle_deg`
y `score` por repetición, y `algorithm_version: "squat-rules-v0"`. Además, comprueba que se ha
creado `cv-service/storage/_manual_test/annotated.mp4` y ábrelo — debe verse el mismo video con
el esqueleto y el ángulo dibujados encima (igual que la ventana que abría `script.py`, pero
guardado a archivo en vez de mostrado en pantalla).

Borra la carpeta de prueba después de verificarlo:

```bash
rm -rf cv-service/storage/_manual_test
```

- [ ] **Step 3: Commit**

```bash
git add cv-service/pipeline.py
git commit -m "feat(cv-service): add real video analysis wired to MediaPipe"
```

---

### Task 4: `jobs.py` — estado en memoria y orquestación del análisis en segundo plano

**Files:**
- Create: `cv-service/jobs.py`
- Test: `cv-service/tests/test_jobs.py`

**Interfaces:**
- Consumes: `pipeline.analizar_video(input_path, output_path) -> dict`,
  `pipeline.NoPoseDetectedError`, `security.sign_webhook(body, timestamp) -> str`.
- Produces: `jobs.STORAGE_DIR: Path`, `jobs.BASE_URL: str`, `jobs.JOBS: dict[str, dict]`,
  `jobs.new_job_id() -> str`, `jobs.job_dir(job_id: str) -> Path`, `jobs.create_job(job_id: str)
  -> None`, `jobs.get_job(job_id: str) -> dict | None`, `jobs.delete_job(job_id: str) -> None`
  (nunca lanza excepción, exista o no el job), `jobs.run_job(job_id: str, input_path: Path,
  callback_url: str | None) -> None`.

- [ ] **Step 1: Escribir los tests que fallan**

`cv-service/tests/test_jobs.py`:

```python
from pathlib import Path

import pipeline


def test_new_job_id_are_unique():
    import jobs

    assert jobs.new_job_id() != jobs.new_job_id()


def test_delete_job_is_idempotent(tmp_path, monkeypatch):
    import jobs

    monkeypatch.setattr(jobs, "STORAGE_DIR", tmp_path)
    job_id = "job-test1"
    jobs.create_job(job_id)
    jobs.job_dir(job_id).mkdir(parents=True)

    jobs.delete_job(job_id)
    assert jobs.get_job(job_id) is None
    assert not jobs.job_dir(job_id).exists()

    # borrar dos veces, o un job que nunca existió, no debe lanzar excepción
    jobs.delete_job(job_id)
    jobs.delete_job("job-que-no-existe")


def test_run_job_stores_completed_result_with_job_id(tmp_path, monkeypatch):
    import jobs

    monkeypatch.setattr(jobs, "STORAGE_DIR", tmp_path)
    monkeypatch.setattr(jobs, "BASE_URL", "http://localhost:8000")

    def fake_analizar_video(input_path, output_path):
        return {
            "exercise_type": "squat",
            "overall_score": 90,
            "summary": "1 repetición(es) detectada(s).",
            "rep_count": 1,
            "reps": [],
            "algorithm_version": "squat-rules-v0",
        }

    monkeypatch.setattr(pipeline, "analizar_video", fake_analizar_video)

    job_id = "job-test2"
    jobs.create_job(job_id)
    jobs.run_job(job_id, tmp_path / "input.mp4", callback_url=None)

    stored = jobs.get_job(job_id)
    assert stored["job_id"] == job_id
    assert stored["status"] == "completed"
    assert stored["result"]["annotated_video_url"] == f"http://localhost:8000/v1/jobs/{job_id}/video"


def test_run_job_maps_no_pose_detected_to_failed(tmp_path, monkeypatch):
    import jobs

    monkeypatch.setattr(jobs, "STORAGE_DIR", tmp_path)

    def raise_no_pose(input_path, output_path):
        raise pipeline.NoPoseDetectedError("nadie en el video")

    monkeypatch.setattr(pipeline, "analizar_video", raise_no_pose)

    job_id = "job-test3"
    jobs.create_job(job_id)
    jobs.run_job(job_id, tmp_path / "input.mp4", callback_url=None)

    stored = jobs.get_job(job_id)
    assert stored["job_id"] == job_id
    assert stored["status"] == "failed"
    assert stored["error"]["code"] == "no_pose_detected"


def test_run_job_sends_signed_webhook_when_callback_url_given(tmp_path, monkeypatch):
    import jobs

    monkeypatch.setattr(jobs, "STORAGE_DIR", tmp_path)
    monkeypatch.setattr(jobs, "BASE_URL", "http://localhost:8000")

    def fake_analizar_video(input_path, output_path):
        return {
            "exercise_type": "squat", "overall_score": 100, "summary": "",
            "rep_count": 0, "reps": [], "algorithm_version": "squat-rules-v0",
        }

    monkeypatch.setattr(pipeline, "analizar_video", fake_analizar_video)

    sent = {}

    def fake_post(url, content, headers, timeout):
        sent["url"] = url
        sent["headers"] = headers
        sent["body"] = content

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)

    job_id = "job-test4"
    jobs.create_job(job_id)
    jobs.run_job(job_id, tmp_path / "input.mp4", callback_url="http://backend.local/callback")

    assert sent["url"] == "http://backend.local/callback"
    assert "X-CV-Signature" in sent["headers"]
    assert "X-CV-Timestamp" in sent["headers"]
    assert f'"job_id": "{job_id}"'.encode() in sent["body"] or f'"job_id":"{job_id}"'.encode() in sent["body"]
```

- [ ] **Step 2: Ejecutar los tests y confirmar que fallan**

```bash
cd cv-service && ../.venv/Scripts/python.exe -m pytest tests/test_jobs.py -v
```

Esperado: `FAIL` — `ModuleNotFoundError: No module named 'jobs'`.

- [ ] **Step 3: Implementar `cv-service/jobs.py`**

```python
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
```

- [ ] **Step 4: Ejecutar los tests y confirmar que pasan**

```bash
cd cv-service && ../.venv/Scripts/python.exe -m pytest tests/test_jobs.py -v
```

Esperado: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add cv-service/jobs.py cv-service/tests/test_jobs.py
git commit -m "feat(cv-service): add in-memory job store and background job orchestration"
```

---

### Task 5: `main.py` — la API FastAPI

**Files:**
- Create: `cv-service/main.py`
- Test: `cv-service/tests/test_main.py`

**Interfaces:**
- Consumes: `security.check_api_key`, `jobs.new_job_id`, `jobs.job_dir`, `jobs.create_job`,
  `jobs.get_job`, `jobs.delete_job`, `jobs.run_job`, `jobs.JOBS`, `pipeline.probe_duration_sec`.
- Produces: `main.app` (instancia de `FastAPI`), rutas `POST /v1/jobs`, `GET /v1/jobs/{job_id}`,
  `DELETE /v1/jobs/{job_id}`, `GET /v1/jobs/{job_id}/video`.

- [ ] **Step 1: Escribir los tests que fallan**

`cv-service/tests/test_main.py`:

```python
import jobs
import security
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
HEADERS = {"X-API-Key": security.API_KEY}


def test_missing_api_key_is_rejected():
    response = client.get("/v1/jobs/does-not-matter")
    assert response.status_code == 401


def test_wrong_api_key_is_rejected():
    response = client.get("/v1/jobs/does-not-matter", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


def test_upload_over_size_limit_is_rejected(monkeypatch):
    import main

    monkeypatch.setattr(main, "MAX_FILE_SIZE_BYTES", 10)  # cualquier archivo de prueba lo supera

    response = client.post(
        "/v1/jobs",
        headers=HEADERS,
        data={"exercise_type": "squat"},
        files={"video": ("clip.mp4", b"contenido de mas de diez bytes", "video/mp4")},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "file_too_large"


def test_upload_with_unreadable_content_is_rejected():
    response = client.post(
        "/v1/jobs",
        headers=HEADERS,
        data={"exercise_type": "squat"},
        files={"video": ("clip.mp4", b"esto no es un video valido", "video/mp4")},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "unsupported_format"


def test_upload_with_unknown_exercise_type_is_rejected():
    response = client.post(
        "/v1/jobs",
        headers=HEADERS,
        data={"exercise_type": "flexiones"},
        files={"video": ("clip.mp4", b"contenido", "video/mp4")},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "unknown_exercise_type"


def test_upload_over_duration_limit_is_rejected(monkeypatch):
    import pipeline

    monkeypatch.setattr(pipeline, "probe_duration_sec", lambda path: 61.0)

    response = client.post(
        "/v1/jobs",
        headers=HEADERS,
        data={"exercise_type": "squat"},
        files={"video": ("clip.mp4", b"contenido", "video/mp4")},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "video_too_long"


def test_get_unknown_job_is_404():
    response = client.get("/v1/jobs/no-existe", headers=HEADERS)
    assert response.status_code == 404


def test_get_job_returns_the_stored_state():
    jobs.JOBS["job-seeded"] = {"job_id": "job-seeded", "status": "completed", "result": {}}

    response = client.get("/v1/jobs/job-seeded", headers=HEADERS)

    assert response.status_code == 200
    assert response.json() == {"job_id": "job-seeded", "status": "completed", "result": {}}


def test_delete_existing_job_removes_it():
    jobs.JOBS["job-to-delete"] = {"job_id": "job-to-delete", "status": "completed"}

    response = client.delete("/v1/jobs/job-to-delete", headers=HEADERS)

    assert response.status_code == 204
    assert jobs.get_job("job-to-delete") is None


def test_delete_unknown_job_is_idempotent():
    response = client.delete("/v1/jobs/nunca-existio", headers=HEADERS)
    assert response.status_code == 204
```

- [ ] **Step 2: Ejecutar los tests y confirmar que fallan**

```bash
cd cv-service && ../.venv/Scripts/python.exe -m pytest tests/test_main.py -v
```

Esperado: `FAIL` — `ModuleNotFoundError: No module named 'main'`.

- [ ] **Step 3: Implementar `cv-service/main.py`**

```python
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
```

- [ ] **Step 4: Ejecutar los tests y confirmar que pasan**

```bash
cd cv-service && ../.venv/Scripts/python.exe -m pytest tests/test_main.py -v
```

Esperado: `10 passed`.

- [ ] **Step 5: Ejecutar toda la suite junta**

```bash
cd cv-service && ../.venv/Scripts/python.exe -m pytest -v
```

Esperado: todos los tests de `test_security.py`, `test_pipeline.py`, `test_jobs.py` y
`test_main.py` en verde (23 en total).

- [ ] **Step 6: Commit**

```bash
git add cv-service/main.py cv-service/tests/test_main.py
git commit -m "feat(cv-service): add the FastAPI app implementing the /v1 jobs contract"
```

---

### Task 6: Script de prueba manual end-to-end + README

Con los cuatro archivos ya probados por separado, este último task conecta todo y te deja un
camino claro para verlo funcionar de principio a fin con el video real del repo.

**Files:**
- Create: `cv-service/scripts/probar_api.py`
- Create: `cv-service/README.md`

**Interfaces:**
- Consumes: la API completa levantada con `uvicorn main:app`.
- Produces: ninguna — es la verificación manual final, no código que otras partes importen.

- [ ] **Step 1: Crear `cv-service/scripts/probar_api.py`**

```python
"""Sube squat.mp4 al servicio CV local y espera el resultado por polling.

Uso: arranca el servidor en otra terminal (ver README) y luego:
    ../.venv/Scripts/python.exe scripts/probar_api.py
"""

import time
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000"
API_KEY = "dev-cv-api-key"
VIDEO_PATH = Path(__file__).resolve().parent.parent.parent / "squat.mp4"


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
```

- [ ] **Step 2: Crear `cv-service/README.md`**

```markdown
# CV Service (MVP)

Servicio de visión por computador que analiza videos de sentadilla y cumple el contrato `/v1`
acordado con backend. Ver `docs/superpowers/specs/2026-08-04-cv-service-mvp-design.md` para el
diseño completo y `docs/2026-07-27-cv-gym-exercise-design.md` para el contrato original.

## Instalar

Desde la raíz del repo, con el entorno virtual ya activo:

\`\`\`bash
.venv/Scripts/python.exe -m pip install -r cv-service/requirements.txt
\`\`\`

## Arrancar el servidor

\`\`\`bash
cd cv-service
../.venv/Scripts/python.exe -m uvicorn main:app --reload --port 8000
\`\`\`

## Probar de punta a punta

En otra terminal, con el servidor ya corriendo:

\`\`\`bash
cd cv-service
../.venv/Scripts/python.exe scripts/probar_api.py
\`\`\`

Sube `squat.mp4` (el video de prueba del repo), hace polling a `GET /v1/jobs/{id}` cada 2
segundos, e imprime el resultado final. El video anotado queda en
`cv-service/storage/<job_id>/annotated.mp4`.

## Variables de entorno

| Variable | Default | Para qué |
|---|---|---|
| `CV_API_KEY` | `dev-cv-api-key` | debe coincidir con lo que envíe el backend |
| `CV_WEBHOOK_SECRET` | `dev-webhook-secret-change-me-in-production` | firma HMAC del webhook |
| `CV_SERVICE_BASE_URL` | `http://localhost:8000` | prefijo con el que se construye `annotated_video_url` |

## Correr los tests

\`\`\`bash
cd cv-service
../.venv/Scripts/python.exe -m pytest -v
\`\`\`

## Fuera de alcance en este MVP

Ver la sección "Fuera de alcance" de
`docs/superpowers/specs/2026-08-04-cv-service-mvp-design.md`: sin detección de `knee_valgus` /
`insufficient_depth` / `excessive_forward_lean` todavía, sin cola de tareas ni S3, sin soporte
HEVC confirmado, sin purga automática por retención.
```

- [ ] **Step 3: Verificación manual — levantar el servidor y correr el script**

Terminal 1:

```bash
cd cv-service && ../.venv/Scripts/python.exe -m uvicorn main:app --port 8000
```

Terminal 2:

```bash
cd cv-service && ../.venv/Scripts/python.exe scripts/probar_api.py
```

Esperado: la terminal 2 imprime `Job creado: job-XXXXXXXX, esperando resultado...`, luego varias
líneas `status: processing`, y finalmente `status: completed` seguido del diccionario completo
del resultado (con `rep_count`, `reps`, `overall_score`, `annotated_video_url`). Abre la URL de
`annotated_video_url` en el navegador (o el archivo directamente en
`cv-service/storage/<job_id>/annotated.mp4`) y confirma que se ve el esqueleto dibujado sobre el
video.

- [ ] **Step 4: Commit**

```bash
git add cv-service/scripts/probar_api.py cv-service/README.md
git commit -m "docs(cv-service): add manual end-to-end verification script and README"
```
