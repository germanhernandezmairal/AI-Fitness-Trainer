import pytest

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
