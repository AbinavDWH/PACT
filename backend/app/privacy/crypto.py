"""Hashing, field encryption, and the masking primitives.

Two different jobs, deliberately not conflated:

    phone_hash    one-way, deterministic, indexed. The join key that lets an
                  inbound SMS from a known number reach an existing account
                  (memory_draft.md 7.2). Never reversible.
    encrypt       two-way, for name_enc / phone_enc. Released by the redactor
                  only after an allocation is committed AND the helper accepts.

The masking functions are separate again: they are what a helper sees *before*
acceptance, and they must lose information irrecoverably at the point of
projection, not merely hide it behind a UI flag.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re

from app.config import get_settings

log = logging.getLogger(__name__)

# ~1.1 km at the equator. Matches repo_requests._mask and the "approximate
# area only" claim the portal makes to helpers.
MASK_DECIMALS = 2

_SALT = b"pact.v1.phone"


# ---------------------------------------------------------------------------
# One-way
# ---------------------------------------------------------------------------

def normalize_number(number: str | None) -> str:
    """Strip formatting so the same phone hashes identically whether it was
    typed as +91 98765 43210 or 09876543210."""
    if not number:
        return ""
    digits = re.sub(r"\D", "", number)
    # Indian numbers arrive with and without the country code and trunk zero.
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits


def phone_hash(number: str | None) -> str:
    """Salted SHA-256, truncated to 32 hex chars. Unique index in `seekers`
    and `helpers`, so one number is one account."""
    d = normalize_number(number)
    if not d:
        return ""
    return hashlib.sha256(_SALT + d.encode()).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Two-way -- field encryption at rest
# ---------------------------------------------------------------------------

_fernet = None
_fernet_ready = False


def _key() -> bytes:
    s = get_settings()
    secret = (s.pact_secret or s.pact_admin_pass or "pact-dev").encode()
    return base64.urlsafe_b64encode(hashlib.sha256(b"pact.v1.field" + secret).digest())


def _cipher():
    """Lazy, and degrades to plaintext with a loud warning rather than taking
    the pipeline down. memory_draft.md 23 cut-line 6 permits dropping field
    encryption while keeping the masking projection, which is the visible
    privacy story -- so this must never be load-bearing for the demo."""
    global _fernet, _fernet_ready
    if _fernet_ready:
        return _fernet
    _fernet_ready = True
    try:
        from cryptography.fernet import Fernet
        _fernet = Fernet(_key())
    except Exception:
        log.warning("cryptography unavailable: name_enc/phone_enc stored in clear")
        _fernet = None
    return _fernet


def encrypt(text: str | None) -> str | None:
    if not text:
        return text
    f = _cipher()
    if f is None:
        return text
    return "enc:" + f.encrypt(text.encode()).decode()


def decrypt(token: str | None) -> str | None:
    if not token or not token.startswith("enc:"):
        return token          # written before encryption was available
    f = _cipher()
    if f is None:
        return token
    try:
        return f.decrypt(token[4:].encode()).decode()
    except Exception:
        log.warning("field decrypt failed")
        return None


def is_encrypted(value: object) -> bool:
    return isinstance(value, str) and value.startswith("enc:")


# ---------------------------------------------------------------------------
# Masking -- lossy by construction
# ---------------------------------------------------------------------------

def mask_point(lat: float | None, lon: float | None) -> list[float] | None:
    """Snap to a ~1 km grid. The precision is destroyed, not hidden: the
    projected event carries no path back to the exact fix."""
    if lat is None or lon is None:
        return None
    return [round(float(lon), MASK_DECIMALS), round(float(lat), MASK_DECIMALS)]


def mask_name(name: str | None) -> str | None:
    """"Anita Sharma" -> "A. S." Enough for a helper to confirm they found the
    right person at the door once contact is revealed; not enough to identify
    anyone from an intercepted stream."""
    if not name:
        return None
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    if not parts:
        return None
    return " ".join(f"{p[0].upper()}." for p in parts[:3])


def mask_phone(number: str | None) -> str | None:
    """Last two digits only. Enough to disambiguate two entries in a list."""
    d = normalize_number(number)
    if not d:
        return None
    return "*" * max(0, len(d) - 2) + d[-2:]


def mask_uid(uid: str | None) -> str | None:
    """The UID is already pseudonymous on the wire (memory_draft.md 7.2), but
    it is a stable correlator across requests, so non-admin audiences get a
    truncated form."""
    if not uid:
        return None
    return uid[:2] + "••"
