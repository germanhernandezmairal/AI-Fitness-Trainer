import uuid
from datetime import UTC, datetime, timedelta

RESULT = {
    "exercise_type": "squat",
    "overall_score": 82,
    "summary": "Good depth.",
    "rep_count": 1,
    "reps": [
        {
            "rep_index": 1,
            "start_time_sec": 0.0,
            "end_time_sec": 2.0,
            "min_knee_angle_deg": 78,
            "score": 90,
            "errors": [],
        }
    ],
    "annotated_video_url": "https://cv-storage/x/annotated.mp4",
    "algorithm_version": "squat-rules-v1",
}


async def test_returns_a_queued_attempt_with_no_result(client, auth_headers, user, make_attempt):
    attempt = await make_attempt(user)

    response = await client.get(f"/v1/attempts/{attempt.id}", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert body["result"] is None
    assert body["error"] is None
    assert body["completed_at"] is None


async def test_returns_the_result_of_a_completed_attempt(
    client, auth_headers, user, make_attempt
):
    attempt = await make_attempt(
        user,
        status="completed",
        result=RESULT,
        overall_score=82,
        annotated_video_url=RESULT["annotated_video_url"],
        completed_at=datetime.now(UTC),
    )

    response = await client.get(f"/v1/attempts/{attempt.id}", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["overall_score"] == 82
    assert body["result"]["reps"][0]["rep_index"] == 1
    assert body["completed_at"] is not None


async def test_returns_the_error_of_a_failed_attempt(client, auth_headers, user, make_attempt):
    attempt = await make_attempt(
        user, status="failed", error_code="no_pose_detected", completed_at=datetime.now(UTC)
    )

    response = await client.get(f"/v1/attempts/{attempt.id}", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error"]["code"] == "no_pose_detected"
    assert body["result"] is None


async def test_hides_another_users_attempt(client, auth_headers, other_user, make_attempt):
    attempt = await make_attempt(other_user)

    response = await client.get(f"/v1/attempts/{attempt.id}", headers=auth_headers)

    assert response.status_code == 404


async def test_returns_404_for_an_unknown_id(client, auth_headers):
    response = await client.get(f"/v1/attempts/{uuid.uuid4()}", headers=auth_headers)

    assert response.status_code == 404


async def test_history_lists_only_the_callers_attempts_newest_first(
    client, auth_headers, user, other_user, make_attempt
):
    base = datetime.now(UTC)
    await make_attempt(user, created_at=base - timedelta(hours=2), overall_score=50)
    newest = await make_attempt(user, created_at=base, overall_score=90)
    await make_attempt(other_user, created_at=base - timedelta(hours=1))

    response = await client.get("/v1/attempts", headers=auth_headers)

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert items[0]["attempt_id"] == str(newest.id)
    assert items[0]["overall_score"] == 90


async def test_history_paginates_with_a_cursor(client, auth_headers, user, make_attempt):
    base = datetime.now(UTC)
    for offset in range(5):
        await make_attempt(user, created_at=base - timedelta(minutes=offset))

    first = await client.get("/v1/attempts?limit=2", headers=auth_headers)
    first_body = first.json()
    assert len(first_body["items"]) == 2
    assert first_body["next_cursor"]

    second = await client.get(
        f"/v1/attempts?limit=2&cursor={first_body['next_cursor']}", headers=auth_headers
    )
    second_body = second.json()

    assert len(second_body["items"]) == 2
    first_ids = {item["attempt_id"] for item in first_body["items"]}
    second_ids = {item["attempt_id"] for item in second_body["items"]}
    assert first_ids.isdisjoint(second_ids)


async def test_history_pagination_visits_every_attempt_exactly_once_in_order(
    client, auth_headers, user, make_attempt
):
    """Disjoint pages alone would not catch a keyset off-by-one that skips a row."""
    base = datetime.now(UTC)
    seeded = [
        await make_attempt(user, created_at=base - timedelta(minutes=offset))
        for offset in range(5)
    ]
    expected_ids = [str(attempt.id) for attempt in seeded]  # newest (offset 0) first

    seen_ids: list[str] = []
    cursor = None
    for _ in range(10):  # generous upper bound so a bug can't hang the test
        url = "/v1/attempts?limit=2"
        if cursor:
            url += f"&cursor={cursor}"
        response = await client.get(url, headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        seen_ids.extend(item["attempt_id"] for item in body["items"])
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert seen_ids == expected_ids


async def test_history_reports_no_cursor_on_the_last_page(client, auth_headers, user, make_attempt):
    await make_attempt(user)

    response = await client.get("/v1/attempts?limit=10", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["next_cursor"] is None


async def test_history_is_empty_for_a_user_with_no_attempts(client, auth_headers):
    response = await client.get("/v1/attempts", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["next_cursor"] is None


async def test_history_rejects_a_malformed_cursor(client, auth_headers, user, make_attempt):
    await make_attempt(user)

    response = await client.get("/v1/attempts?cursor=not-a-date", headers=auth_headers)

    assert response.status_code == 400


async def test_history_rejects_a_non_base64_cursor(client, auth_headers, user, make_attempt):
    await make_attempt(user)

    response = await client.get("/v1/attempts?cursor=%24%24%24not-base64%24%24%24", headers=auth_headers)

    assert response.status_code == 400


async def test_history_rejects_a_limit_below_the_minimum(client, auth_headers):
    response = await client.get("/v1/attempts?limit=0", headers=auth_headers)

    assert response.status_code == 422


async def test_history_rejects_a_limit_above_the_maximum(client, auth_headers):
    response = await client.get("/v1/attempts?limit=101", headers=auth_headers)

    assert response.status_code == 422


async def test_history_requires_authentication(client):
    response = await client.get("/v1/attempts")

    assert response.status_code == 401
