import security


def test_check_api_key_accepts_the_configured_key():
    assert security.check_api_key(security.API_KEY) is True


def test_check_api_key_rejects_wrong_or_missing_key():
    assert security.check_api_key("wrong-key") is False
    assert security.check_api_key(None) is False


def test_sign_webhook_matches_hand_computed_hmac():
    import hashlib
    import hmac

    body = b'{"job_id": "abc123", "status": "completed"}'
    timestamp = "1700000000"
    expected = hmac.new(
        security.WEBHOOK_SECRET.encode(),
        f"{timestamp}.".encode() + body,
        hashlib.sha256,
    ).hexdigest()

    assert security.sign_webhook(body, timestamp) == expected
