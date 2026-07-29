import time

import pytest

from app.security.signing import SignatureError, sign_payload, verify_signature

SECRET = "shared-webhook-secret"
BODY = b'{"status":"completed"}'


def _now() -> str:
    return str(int(time.time()))


def test_accepts_a_correctly_signed_payload():
    timestamp = _now()
    signature = sign_payload(BODY, timestamp, SECRET)

    verify_signature(BODY, timestamp, signature, SECRET, tolerance_sec=300)


def test_rejects_a_tampered_body():
    timestamp = _now()
    signature = sign_payload(BODY, timestamp, SECRET)

    with pytest.raises(SignatureError):
        verify_signature(b'{"status":"failed"}', timestamp, signature, SECRET, tolerance_sec=300)


def test_rejects_the_wrong_secret():
    timestamp = _now()
    signature = sign_payload(BODY, timestamp, "some-other-secret")

    with pytest.raises(SignatureError):
        verify_signature(BODY, timestamp, signature, SECRET, tolerance_sec=300)


def test_rejects_a_replayed_old_timestamp():
    old = str(int(time.time()) - 3600)
    signature = sign_payload(BODY, old, SECRET)

    with pytest.raises(SignatureError):
        verify_signature(BODY, old, signature, SECRET, tolerance_sec=300)


def test_rejects_a_timestamp_from_the_future():
    future = str(int(time.time()) + 3600)
    signature = sign_payload(BODY, future, SECRET)

    with pytest.raises(SignatureError):
        verify_signature(BODY, future, signature, SECRET, tolerance_sec=300)


def test_rejects_a_non_numeric_timestamp():
    signature = sign_payload(BODY, "yesterday", SECRET)

    with pytest.raises(SignatureError):
        verify_signature(BODY, "yesterday", signature, SECRET, tolerance_sec=300)


def test_signature_binds_the_timestamp_to_the_body():
    """Reusing a valid signature under a fresher timestamp must fail."""
    old = str(int(time.time()) - 1000)
    signature = sign_payload(BODY, old, SECRET)

    with pytest.raises(SignatureError):
        verify_signature(BODY, _now(), signature, SECRET, tolerance_sec=300)
