import os
import tempfile

import cv2
import numpy as np
import pytest

import pipeline


def test_calculate_angle_of_a_right_angle():
    # cadera y tobillo alineados en el mismo eje, rodilla en el vértice: 90°
    hip = [0, 0]
    knee = [0, 1]
    ankle = [1, 1]

    assert pipeline.calculate_angle(hip, knee, ankle) == pytest.approx(90.0, abs=0.1)


def test_score_from_angle_at_or_below_threshold_is_100():
    # reptir a la profundidad buena o más allá no penaliza (ver GLOSARIO.md:
    # la NSCA no encuentra base para tratar la sentadilla completa como riesgosa)
    assert pipeline.score_from_angle(100) == 100
    assert pipeline.score_from_angle(85) == 100
    assert pipeline.score_from_angle(30) == 100


def test_score_from_angle_above_threshold_is_penalized():
    # 15 grados por encima del umbral (100): 100 - 15*3 = 55
    assert pipeline.score_from_angle(115) == 55
    # penalización nunca baja de 0
    assert pipeline.score_from_angle(180) == 0


def test_build_rep_flags_insufficient_depth_when_min_angle_above_threshold():
    rep = pipeline.build_rep(1, 0, 10, fps=30.0, min_angle=120.0)

    assert rep["errors"] == ["insufficient_depth"]


def test_build_rep_does_not_flag_insufficient_depth_at_or_below_threshold():
    rep = pipeline.build_rep(1, 0, 10, fps=30.0, min_angle=90.0)

    assert "insufficient_depth" not in rep["errors"]


def test_build_rep_flags_excessive_forward_lean_when_torso_leans_too_much():
    # cadera y hombro alineados horizontalmente: 90° de inclinación
    rep = pipeline.build_rep(
        1, 0, 10, fps=30.0, min_angle=90.0, hip=[0, 0], shoulder=[10, 0]
    )

    assert rep["errors"] == ["excessive_forward_lean"]


def test_build_rep_does_not_flag_excessive_forward_lean_when_torso_is_upright():
    rep = pipeline.build_rep(
        1, 0, 10, fps=30.0, min_angle=90.0, hip=[0, 10], shoulder=[0, 0]
    )

    assert rep["errors"] == []


def test_build_rep_can_flag_both_errors_at_once():
    rep = pipeline.build_rep(
        1, 0, 10, fps=30.0, min_angle=120.0, hip=[0, 0], shoulder=[10, 0]
    )

    assert set(rep["errors"]) == {"insufficient_depth", "excessive_forward_lean"}


UPRIGHT = ([0, 10], [0, 0])  # (hip, shoulder) sin inclinación, para detecciones de relleno


def test_segment_reps_counts_two_full_repetitions():
    # de pie -> bajando -> abajo -> subiendo -> de pie, dos veces
    detections = [
        (0, 170, *UPRIGHT), (1, 150, *UPRIGHT), (2, 90, *UPRIGHT), (3, 80, *UPRIGHT), (4, 170, *UPRIGHT),
        (5, 170, *UPRIGHT), (6, 140, *UPRIGHT), (7, 65, *UPRIGHT), (8, 175, *UPRIGHT),
    ]

    reps = pipeline.segment_reps(detections, fps=30.0)

    assert len(reps) == 2
    assert reps[0]["rep_index"] == 1
    assert reps[0]["min_knee_angle_deg"] == 80
    assert reps[1]["rep_index"] == 2
    assert reps[1]["min_knee_angle_deg"] == 65


def test_segment_reps_ignores_an_incomplete_repetition():
    # empieza a bajar pero el video se corta antes de volver a "de pie"
    detections = [(0, 170, *UPRIGHT), (1, 150, *UPRIGHT), (2, 90, *UPRIGHT)]

    reps = pipeline.segment_reps(detections, fps=30.0)

    assert reps == []


def test_segment_reps_uses_hip_and_shoulder_from_the_min_angle_frame():
    # la inclinación excesiva ocurre justo en el frame del ángulo mínimo (frame 2);
    # los demás frames están erguidos -- el error debe salir de ESE frame, no de otro
    leaning = ([0, 0], [10, 0])  # 90° de inclinación
    detections = [
        (0, 170, *UPRIGHT), (1, 150, *UPRIGHT), (2, 80, *leaning), (3, 170, *UPRIGHT),
    ]

    reps = pipeline.segment_reps(detections, fps=30.0)

    assert reps[0]["errors"] == ["excessive_forward_lean"]


def test_torso_lean_from_vertical_is_zero_for_upright_torso():
    # hombro justo encima de la cadera, sin inclinación
    hip = [0, 10]
    shoulder = [0, 0]

    assert pipeline.torso_lean_from_vertical(hip, shoulder) == pytest.approx(0.0, abs=0.1)


def test_torso_lean_from_vertical_is_45_degrees():
    hip = [0, 0]
    shoulder = [10, -10]

    assert pipeline.torso_lean_from_vertical(hip, shoulder) == pytest.approx(45.0, abs=0.1)


def test_torso_lean_from_vertical_is_90_degrees_for_horizontal_torso():
    hip = [0, 0]
    shoulder = [10, 0]

    assert pipeline.torso_lean_from_vertical(hip, shoulder) == pytest.approx(90.0, abs=0.1)


def test_annotated_video_fourcc_produces_a_browser_playable_codec():
    # No usa MediaPipe -- solo cv2.VideoWriter/VideoCapture con datos sintéticos, así
    # que sigue la misma regla que el resto de este archivo (funciones puras con datos
    # sintéticos). 'mp4v' (MPEG-4 Part 2) abre y "funciona" para OpenCV, pero los
    # navegadores no lo decodifican en <video> -- solo H.264/AVC, VP8/VP9 o AV1. Este
    # test existe para que un futuro cambio a un fourcc no reproducible en navegador
    # falle aquí, en vez de descubrirse a mano viendo un video que no reproduce.
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = os.path.join(tmp_dir, "annotated.mp4")

        writer = cv2.VideoWriter(output_path, pipeline.ANNOTATED_VIDEO_FOURCC, 25, (64, 48))
        assert writer.isOpened()
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        for _ in range(5):
            writer.write(frame)
        writer.release()

        cap = cv2.VideoCapture(output_path)
        fourcc_read_back = int(cap.get(cv2.CAP_PROP_FOURCC))
        codec = "".join(chr((fourcc_read_back >> (8 * i)) & 0xFF) for i in range(4))
        cap.release()

        assert codec.lower() in ("h264", "avc1"), (
            f"expected a browser-playable codec (h264/avc1), got {codec!r}"
        )
