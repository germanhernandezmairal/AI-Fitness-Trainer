async def test_allows_the_frontend_dev_origin(client):
    response = await client.options(
        "/v1/attempts",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


async def test_rejects_an_unlisted_origin(client):
    response = await client.options(
        "/v1/attempts",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers
