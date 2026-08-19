"""Base-36 integer encoding.

Deliberately hand-rolled rather than using int(s, 36) alone, because the encode
side needs fixed-width zero padding and Kotlin's Long.toString(n, 36) must
produce byte-identical output. Two tiny functions, no library on either side.
"""

from __future__ import annotations

DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def b36_encode(n: int, width: int = 0) -> str:
    if n < 0:
        raise ValueError(f"base36 cannot encode negative: {n}")
    if n == 0:
        return "0".rjust(width, "0") if width else "0"
    out: list[str] = []
    while n:
        n, r = divmod(n, 36)
        out.append(DIGITS[r])
    s = "".join(reversed(out))
    if width and len(s) > width:
        raise ValueError(f"base36 value {s!r} exceeds width {width}")
    return s.rjust(width, "0") if width else s


def b36_decode(s: str) -> int:
    s = s.strip().upper()
    if not s:
        raise ValueError("empty base36 string")
    n = 0
    for ch in s:
        i = DIGITS.find(ch)
        if i < 0:
            raise ValueError(f"invalid base36 character {ch!r} in {s!r}")
        n = n * 36 + i
    return n


def is_b36(s: str) -> bool:
    return bool(s) and all(c in DIGITS for c in s.upper())
