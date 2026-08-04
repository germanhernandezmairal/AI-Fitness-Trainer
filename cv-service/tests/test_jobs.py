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
