"""Lógica de análisis de sentadilla.

Dos partes con distinto grado de testeo: las funciones puras (ángulo, score,
`segment_reps`) no tocan video ni MediaPipe, así que se prueban con datos
sintéticos (`tests/test_pipeline.py`). `analizar_video` sí usa MediaPipe/
OpenCV de verdad sobre el archivo de video — esa parte se verifica a mano,
viendo el video anotado que produce, en vez de con pytest.
"""

from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

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