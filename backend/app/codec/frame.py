"""Framing and checksum (sms.md sections 4 and 24).

Byte-identical to the original implementation, so nothing that works today
regresses.
"""

from __future__ import annotations

from app.codec.errors import BAD_CRC, BAD_FMT, TOO_LONG, CodecError

MAX_QG_LEN = 140          # Q/G are ~35 chars; anything near 140 is malformed
GSM7_EXTRA = set("|.,:- ")
_B36 = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def xor_checksum(text: str) -> str:
    value = 0
    for char in text:
        value ^= ord(char)
    return format(value, "02X")


def frame(*parts: str) -> str:
    """Join parts with | and append the checksum over everything before it."""
    body = "|".join(str(p) for p in parts)
    return f"{body}|{xor_checksum(body)}"


def is_gsm7_safe(text: str) -> bool:
    """A single character outside GSM-7 forces UCS-2 and halves capacity."""
    return all(c in _B36 or c in GSM7_EXTRA for c in text.upper())


def unframe(sms: str, *, verify: bool = True) -> list[str]:
    """Split and validate the checksum. Returns fields WITHOUT the checksum."""
    if not sms or not sms.strip():
        raise CodecError(BAD_FMT, "empty message")

    s = sms.strip().upper()
    parts = [p.strip() for p in s.split("|")]
    if len(parts) < 3:
        raise CodecError(BAD_FMT, f"only {len(parts)} fields")

    if s[0] in ("Q", "G") and len(s) > MAX_QG_LEN:
        raise CodecError(TOO_LONG, f"{len(s)} chars; Q/G are single-part by construction")

    if not verify:
        return parts

    body, received = "|".join(parts[:-1]), parts[-1]
    expected = xor_checksum(body)
    if received != expected:
        raise CodecError(BAD_CRC, "checksum mismatch",
                         expected_checksum=expected, received_checksum=received)
    return parts[:-1]
