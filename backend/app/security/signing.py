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
    # Compare bytes, not str: hmac.compare_digest raises TypeError on two str
    # arguments when either contains non-ASCII characters, and an attacker fully
    # controls `signature` (a request header). A raw byte > 0x7F in the header is
    # decoded as non-ASCII by Starlette (headers are latin-1), so this is reachable
    # by any caller, not just a captured/tampered signature. Every Python str
    # encodes to UTF-8 without error, so this never raises for a legitimate value.
    if not hmac.compare_digest(expected.encode(), (signature or "").encode()):
        raise SignatureError("signature mismatch")
