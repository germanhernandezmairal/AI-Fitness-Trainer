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

# Ángulo de rodilla (cadera-rodilla-tobillo) a partir del cual una rep cuenta como "buena
# profundidad". Aproxima la sentadilla paralela (~90° de flexión de rodilla en la convención
# de la literatura, que mide desde la extensión completa -- el ángulo que calculamos aquí es
# el complementario, así que ~90° de flexión ≈ 90-100° de ángulo interior). Por debajo o igual
# a este valor, la rep no se penaliza por profundidad ni se marca `insufficient_depth`: la NSCA
# no encuentra base para tratar la sentadilla completa (mayor flexión) como más riesgosa para
# la rodilla que la paralela, así que solo se penaliza quedarse corto, nunca pasarse. Fuentes y
# discusión completa en GLOSARIO.md.
GOOD_DEPTH_ANGLE_DEG = 100.0
PENALTY_PER_DEGREE = 3  # puntos que se restan del score por cada grado por encima del umbral

# Umbral de inclinación de torso (`torso_lean_from_vertical`) a partir del cual se marca
# `excessive_forward_lean`. A diferencia de GOOD_DEPTH_ANGLE_DEG, este valor es un punto de
# partida heurístico, no derivado de una fuente concreta -- a ajustar contra videos reales
# (ver GLOSARIO.md).
EXCESSIVE_LEAN_DEG = 45.0

# Norma mínima (en píxeles) que debe tener un vector cadera->hombro o tobillo->rodilla
# para confiar en su dirección. Por debajo de esto, los landmarks están tan juntos que
# el vector es ruido de tracking de sub-píxel, no una medición real -- ver GLOSARIO.md.
MIN_TORSO_VECTOR_NORM_PX = 1.0

# 'mp4v' (MPEG-4 Part 2) es lo que probaría cualquiera primero, pero los navegadores no lo
# decodifican en <video> -- solo H.264/AVC, VP8/VP9 o AV1. 'avc1' sí produce H.264 real con este
# build de OpenCV (confirmado: writer.isOpened() y el fourcc leído de vuelta es 'h264'), sin
# necesitar un post-proceso con ffmpeg.
ANNOTATED_VIDEO_FOURCC = cv2.VideoWriter_fourcc(*"avc1")


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


def torso_lean_from_vertical(hip, shoulder) -> float:
    """Ángulo entre el vector cadera->hombro y la vertical, en grados.

    0° = torso perfectamente vertical. Es solo la magnitud de la inclinación --
    no distingue adelante de atrás, ver `is_excessive_forward_lean` para eso.
    Usado para `excessive_forward_lean` (ver fuentes de umbral en GLOSARIO.md).
    """
    # Vértice sintético "arriba" de la cadera para reusar calculate_angle en vez de
    # reimplementar el mismo dot/norma/arccos/clip a mano.
    vertical_point = [hip[0], hip[1] - 1]
    return calculate_angle(shoulder, hip, vertical_point)


def is_excessive_forward_lean(hip, knee, ankle, shoulder) -> bool:
    """True si el torso está inclinado más de `EXCESSIVE_LEAN_DEG` hacia ADELANTE.

    "Adelante" se define a partir de la posición horizontal de la rodilla respecto
    al tobillo, no de un lado fijo de la pantalla: durante el descenso de una
    sentadilla la rodilla avanza hacia adelante del tobillo sin importar hacia qué
    lado mire la cámara, así que esa dirección sirve de referencia estable. Una
    inclinación hacia atrás (p. ej. más bisagra de cadera) no cuenta como error,
    aunque su magnitud supere el umbral.

    Devuelve False -- en vez de adivinar -- cuando el vector cadera->hombro o el
    vector tobillo->rodilla son demasiado cortos en píxeles para confiar en su
    dirección (`MIN_TORSO_VECTOR_NORM_PX`), incluyendo el caso borde en el que la
    rodilla queda justo encima del tobillo (dirección de "adelante" ambigua).
    """
    torso_vector = np.array(shoulder) - np.array(hip)
    forward_vector = np.array(knee) - np.array(ankle)

    if np.linalg.norm(torso_vector) < MIN_TORSO_VECTOR_NORM_PX:
        return False
    if np.linalg.norm(forward_vector) < MIN_TORSO_VECTOR_NORM_PX:
        return False

    forward_sign = np.sign(forward_vector[0])
    if forward_sign == 0 or np.sign(torso_vector[0]) != forward_sign:
        return False

    return torso_lean_from_vertical(hip, shoulder) > EXCESSIVE_LEAN_DEG


def score_from_angle(min_angle: float) -> int:
    """Puntúa una repetición según qué tan lejos quedó su ángulo mínimo de GOOD_DEPTH_ANGLE_DEG.

    100 si el ángulo mínimo llegó a GOOD_DEPTH_ANGLE_DEG o más profundo (ángulo menor);
    por encima, penaliza PENALTY_PER_DEGREE puntos por cada grado de distancia, sin
    bajar de 0. No hay penalización por pasarse de profundo (ver GOOD_DEPTH_ANGLE_DEG).
    """
    if min_angle <= GOOD_DEPTH_ANGLE_DEG:
        return 100

    distance = min_angle - GOOD_DEPTH_ANGLE_DEG
    return max(0, round(100 - distance * PENALTY_PER_DEGREE))


def build_rep(
    rep_index: int,
    start_frame: int,
    end_frame: int,
    fps: float,
    min_angle: float,
    hip=None,
    knee=None,
    ankle=None,
    shoulder=None,
) -> dict:
    """Construye el diccionario de una repetición con la forma que espera el contrato.

    `hip`/`knee`/`ankle`/`shoulder` son las coordenadas de esos landmarks en el frame
    donde ocurrió `min_angle` (ver `segment_reps`); si falta alguno, no se evalúa
    `excessive_forward_lean` (ver `is_excessive_forward_lean`). `knee_valgus` no se
    evalúa: requiere una cámara frontal, y `pipeline.py` asume una sola cámara lateral.
    Queda documentado como limitación conocida (ver GLOSARIO.md), no como código
    pendiente.
    """
    errors = []
    if min_angle > GOOD_DEPTH_ANGLE_DEG:
        errors.append("insufficient_depth")
    if hip is not None and knee is not None and ankle is not None and shoulder is not None:
        if is_excessive_forward_lean(hip, knee, ankle, shoulder):
            errors.append("excessive_forward_lean")

    return {
        "rep_index": rep_index,
        "start_time_sec": round(start_frame / fps, 2),
        "end_time_sec": round(end_frame / fps, 2),
        "min_knee_angle_deg": round(min_angle, 1),
        "score": score_from_angle(min_angle),
        "errors": errors,
    }


def segment_reps(detections: list[tuple[int, float, list, list, list, list]], fps: float) -> list[dict]:
    """Agrupa una secuencia de ángulos de rodilla en repeticiones completas.

    `detections` es una lista de (número_de_frame, ángulo, hip, knee, ankle, shoulder),
    solo para los frames donde sí se detectó a la persona. Esos cuatro landmarks son
    las coordenadas en ese frame -- se necesitan para evaluar `excessive_forward_lean`
    en el frame exacto del ángulo mínimo de cada rep, no en cualquier otro. Usa una
    máquina de estados simple: de pie -> bajando/abajo/subiendo -> de pie de nuevo
    cierra una repetición. Una repetición que empieza pero nunca vuelve a "de pie"
    (video cortado a mitad de rep) no se cuenta.
    """
    state = "standing"
    rep_start_frame = None
    min_angle_in_rep = None
    min_angle_landmarks = None
    reps = []

    for frame_index, angle, hip, knee, ankle, shoulder in detections:
        if state == "standing" and angle < STANDING_THRESHOLD:
            state = "descending"
            rep_start_frame = frame_index
            min_angle_in_rep = angle
            min_angle_landmarks = (hip, knee, ankle, shoulder)
        elif state != "standing":
            if angle < min_angle_in_rep:
                min_angle_in_rep = angle
                min_angle_landmarks = (hip, knee, ankle, shoulder)
            if angle >= STANDING_THRESHOLD:
                min_hip, min_knee, min_ankle, min_shoulder = min_angle_landmarks
                reps.append(
                    build_rep(
                        len(reps) + 1, rep_start_frame, frame_index, fps, min_angle_in_rep,
                        hip=min_hip, knee=min_knee, ankle=min_ankle, shoulder=min_shoulder,
                    )
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
    writer = cv2.VideoWriter(str(output_path), ANNOTATED_VIDEO_FOURCC, fps, (width, height))

    pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

    detections: list[tuple[int, float, list, list, list, list]] = []
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
                shoulder = [
                    landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x * width,
                    landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y * height,
                ]
                angle = calculate_angle(hip, knee, ankle)
                detections.append((frame_index, angle, hip, knee, ankle, shoulder))

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
        "algorithm_version": "squat-rules-v1",
    }