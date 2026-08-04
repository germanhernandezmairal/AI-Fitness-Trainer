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
