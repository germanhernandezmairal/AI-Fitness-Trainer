"""bcrypt password hashing. Mirrors app/security/tokens.py's shape.

bcrypt truncates input at 72 bytes; RegisterRequest/LoginRequest (app/schemas/auth.py)
enforce max_length=72 at the schema level so that limit is visible to the caller instead
of silently discarding the tail of a longer password.
"""

import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        # hashed_password isn't a valid bcrypt hash (shouldn't happen in practice) —
        # never let a malformed hash raise past this boundary as a 500.
        return False
