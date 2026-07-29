"""HMAC signing for the CV -> backend webhook (spec §4, §8).

The timestamp is part of the signed material, so a captured signature cannot be
replayed under a fresh timestamp.
"""

import hashlib
import hmac
import time


class SignatureError(Exception):
    """The webhook signature was absent, wrong, or too old to trust."""


def sign_payload(body: bytes, timestamp: str, secret: str) -> str:
    message = f"{timestamp}.".encode() + body
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_signature(
    body: bytes,
    timestamp: str,
    signature: str,
    secret: str,
    tolerance_sec: int,
) -> None:
    try:
        sent_at = int(timestamp)
    except (TypeError, ValueError):
        raise SignatureError("timestamp is not an integer") from None

    if abs(int(time.time()) - sent_at) > tolerance_sec:
        raise SignatureError("timestamp outside the tolerance window")

    expected = sign_payload(body, timestamp, secret)
    if not hmac.compare_digest(expected, signature or ""):
        raise SignatureError("signature mismatch")
