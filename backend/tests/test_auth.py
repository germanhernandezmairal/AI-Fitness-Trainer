import uuid

import pytest

from app.security.tokens import InvalidToken, create_access_token, decode_access_token

SECRET = "this-is-a-test-secret-that-is-long-enough"


def test_round_trips_a_user_id():
    user_id = uuid.uuid4()
    token = create_access_token(user_id, SECRET, ttl_seconds=60)

    assert decode_access_token(token, SECRET) == user_id


def test_rejects_a_token_signed_with_another_secret():
    token = create_access_token(uuid.uuid4(), SECRET, ttl_seconds=60)

    with pytest.raises(InvalidToken):
        decode_access_token(token, "a-completely-different-secret-value-here")


def test_rejects_an_expired_token():
    token = create_access_token(uuid.uuid4(), SECRET, ttl_seconds=-1)

    with pytest.raises(InvalidToken):
        decode_access_token(token, SECRET)


def test_rejects_a_garbage_token():
    with pytest.raises(InvalidToken):
        decode_access_token("not-a-jwt", SECRET)


async def test_dev_login_issues_a_token_for_a_new_email(client):
    response = await client.post("/v1/auth/dev-login", json={"email": "new@example.com"})

    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_protected_route_rejects_a_missing_token(client):
    response = await client.get("/v1/attempts")

    assert response.status_code == 401


async def test_protected_route_rejects_a_bad_token(client):
    response = await client.get("/v1/attempts", headers={"Authorization": "Bearer nope"})

    assert response.status_code == 401
