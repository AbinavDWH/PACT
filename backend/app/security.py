"""Password hashing.

`bcrypt` has been in requirements.txt since the first commit, described as
"credential hashing", and was never called once: the admin password was
compared against a plaintext environment variable and organizations shared a
single plaintext password. The dependency was documentation, not behaviour.

Two properties matter here beyond "it hashes":

  - **Constant-time comparison.** bcrypt.checkpw does this internally. The
    plaintext path used hmac.compare_digest for the admin, which was right, and
    a bare `==` for organizations, which leaked length and prefix through
    timing.

  - **Failing closed on a malformed hash.** A stored value that is not a bcrypt
    hash must reject every password rather than raising, or one bad seed row
    turns into a 500 on the login endpoint.
"""

from __future__ import annotations

import logging

import bcrypt

log = logging.getLogger(__name__)

# bcrypt truncates silently at 72 bytes. Rejecting longer input is better than
# accepting a password whose tail is ignored, which would make two different
# long passwords interchangeable.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    """Returns the standard `$2b$...` string, safe to store."""
    raw = password.encode()
    if len(raw) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"password exceeds bcrypt's {MAX_PASSWORD_BYTES}-byte limit; "
            "the remainder would be silently ignored")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str | None) -> bool:
    """Constant-time check. False for anything malformed or missing."""
    if not password or not hashed:
        return False
    raw = password.encode()
    if len(raw) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(raw, hashed.encode())
    except (ValueError, TypeError):
        # Not a bcrypt hash. Reject rather than raise: one bad row must not
        # turn the login endpoint into a 500.
        log.warning("stored credential is not a valid bcrypt hash; rejecting")
        return False


def is_hashed(value: str | None) -> bool:
    return bool(value) and value.startswith(("$2a$", "$2b$", "$2y$"))
