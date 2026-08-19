"""Error codes, matching sms.md section 23."""

from __future__ import annotations


class CodecError(Exception):
    def __init__(self, code: str, detail: str = "", **extra):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail
        self.extra = extra

    def as_dict(self) -> dict:
        return {"status": "error", "error": self.code,
                **({"detail": self.detail} if self.detail else {}), **self.extra}


# Fatal: reject the message.
BAD_CRC = "BAD_CRC"
BAD_FMT = "BAD_FMT"
UNKNOWN_TYPE = "UNKNOWN_TYPE"
BAD_SCHEMA = "BAD_SCHEMA"
BAD_GEO = "BAD_GEO"
TRUNCATED = "TRUNCATED"
TOO_LONG = "TOO_LONG"
EMPTY_SMS = "EMPTY_SMS"
BAD_QTY = "BAD_QTY"
DUP = "DUP"
PRIVACY = "PRIVACY"

# Non-fatal: recorded as a warning, message still accepted.
UNKNOWN_CODE = "UNKNOWN_CODE"
UNKNOWN_RES = "UNKNOWN_RES"
UNKNOWN_LOC = "UNKNOWN_LOC"
