import uuid
from datetime import UTC, datetime, timedelta

from app.models import RefreshToken
from app.services.auth import hash_refresh_token

EMAIL = "athlete@example.com"
PASSWORD = "correct-horse-battery-staple"


async def test_register_creates_a_user_and_returns_a_token_pair(client):
    response = await client.post(
        "/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "consent": True}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


async def test_register_rejects_a_duplicate_email(client):
    await client.post(
        "/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "consent": True}
    )

    response = await client.post(
        "/v1/auth/register",
        json={"email": EMAIL, "password": "a-different-password", "consent": True},
    )

    assert response.status_code == 409


async def test_register_rejects_a_too_short_password(client):
    response = await client.post(
        "/v1/auth/register", json={"email": EMAIL, "password": "short", "consent": True}
    )

    assert response.status_code == 422


async def test_register_requires_consent(client):
    response = await client.post(
        "/v1/auth/register", json={"email": EMAIL, "password": PASSWORD}
    )

    assert response.status_code == 422


async def test_register_rejects_explicit_false_consent(client):
    response = await client.post(
        "/v1/auth/register",
        json={"email": EMAIL, "password": PASSWORD, "consent": False},
    )

    assert response.status_code == 422


async def test_login_succeeds_with_correct_credentials(client):
    await client.post(
        "/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "consent": True}
    )

    response = await client.post(
        "/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]


async def test_login_rejects_wrong_password(client):
    await client.post(
        "/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "consent": True}
    )

    response = await client.post(
        "/v1/auth/login", json={"email": EMAIL, "password": "wrong-password"}
    )

    assert response.status_code == 401


async def test_login_rejects_unknown_email(client):
    unknown = await client.post(
        "/v1/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )
    wrong_password = await client.post(
        "/v1/auth/login", json={"email": EMAIL, "password": "wrong-password"}
    )

    assert unknown.status_code == 401
    assert wrong_password.status_code == 401
    assert unknown.json() == wrong_password.json()  # no enumeration signal


async def test_login_rejects_a_dev_login_created_account(client):
    await client.post("/v1/auth/dev-login", json={"email": "devonly@example.com"})

    response = await client.post(
        "/v1/auth/login", json={"email": "devonly@example.com", "password": "anything-at-all"}
    )

    assert response.status_code == 401


async def test_refresh_rotates_and_invalidates_the_old_token(client):
    registered = await client.post(
        "/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "consent": True}
    )
    old_refresh_token = registered.json()["refresh_token"]

    refreshed = await client.post(
        "/v1/auth/refresh", json={"refresh_token": old_refresh_token}
    )
    assert refreshed.status_code == 200
    new_refresh_token = refreshed.json()["refresh_token"]
    assert new_refresh_token != old_refresh_token

    reuse_attempt = await client.post(
        "/v1/auth/refresh", json={"refresh_token": old_refresh_token}
    )
    assert reuse_attempt.status_code == 401


async def test_refresh_can_be_chained_when_each_new_token_is_used_in_turn(client):
    registered = await client.post(
        "/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "consent": True}
    )
    token = registered.json()["refresh_token"]

    for _ in range(3):
        response = await client.post("/v1/auth/refresh", json={"refresh_token": token})
        assert response.status_code == 200
        token = response.json()["refresh_token"]


async def test_refresh_rejects_an_expired_token(client, session, user):
    raw_token = "expired-raw-token"
    session.add(
        RefreshToken(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=hash_refresh_token(raw_token),
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
    )
    await session.flush()

    response = await client.post("/v1/auth/refresh", json={"refresh_token": raw_token})

    assert response.status_code == 401


async def test_refresh_detects_reuse_and_revokes_the_whole_session_family(client):
    registered = await client.post(
        "/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "consent": True}
    )
    token_a = registered.json()["refresh_token"]

    first_refresh = await client.post("/v1/auth/refresh", json={"refresh_token": token_a})
    token_b = first_refresh.json()["refresh_token"]

    reuse = await client.post("/v1/auth/refresh", json={"refresh_token": token_a})
    assert reuse.status_code == 401

    token_b_now = await client.post("/v1/auth/refresh", json={"refresh_token": token_b})
    assert token_b_now.status_code == 401


async def test_logout_revokes_the_refresh_token(client):
    registered = await client.post(
        "/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "consent": True}
    )
    refresh_token = registered.json()["refresh_token"]

    logout = await client.post("/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout.status_code == 204

    response = await client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 401


async def test_logout_is_idempotent_for_an_unknown_token(client):
    response = await client.post(
        "/v1/auth/logout", json={"refresh_token": "not-a-real-token"}
    )

    assert response.status_code == 204


async def test_access_token_from_login_still_authorizes_protected_routes(client):
    await client.post(
        "/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "consent": True}
    )
    logged_in = await client.post(
        "/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )
    access_token = logged_in.json()["access_token"]

    response = await client.get(
        "/v1/attempts", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200
