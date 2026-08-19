"""Compressed selection payload (codec.md section 4).

Fixed-position base-36 fields, not a packed bitfield. Position 0 is the schema
version and is checked first: an unknown version means every later position is
untrustworthy, so it rejects rather than misreading.

Partial decode is deliberate. One unrecognised selection character sets that
field to None and records a warning -- a request with one garbled field is still
a person who needs rescue. Only BAD_SCHEMA rejects outright.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.codec.base36 import b36_decode, b36_encode
from app.codec.errors import BAD_SCHEMA, TRUNCATED, UNKNOWN_CODE, CodecError
from app.codec.tables import get_tables


@dataclass
class Decoded:
    values: dict[str, Any] = field(default_factory=dict)
    warnings: list[dict[str, str]] = field(default_factory=list)


def _slices(kind: str) -> list[tuple[str, int, int]]:
    layout = get_tables().layouts[kind]
    out, pos = [], 0
    for f in layout["fields"]:
        out.append((f["name"], pos, pos + f["chars"]))
        pos += f["chars"]
    return out


def decode_payload(kind: str, payload: str) -> Decoded:
    t = get_tables()
    layout = t.layouts.get(kind)
    if layout is None:
        raise CodecError(BAD_SCHEMA, f"unknown payload kind {kind!r}")

    p = payload.strip().upper()
    if len(p) < layout["length"]:
        raise CodecError(TRUNCATED,
                         f"{kind} payload is {len(p)} chars, expected {layout['length']}")
    if p[0] != layout["version_char"]:
        raise CodecError(BAD_SCHEMA,
                         f"payload version {p[0]!r}, this decoder speaks "
                         f"{layout['version_char']!r}")

    out = Decoded()
    for name, a, b in _slices(kind):
        chunk = p[a:b]
        if name == "version":
            out.values["schema"] = int(chunk)
            continue

        d = t.dim(name)
        kindof = d.get("kind")

        if kindof == "bitfield":
            try:
                raw = b36_decode(chunk)
            except ValueError:
                out.values[name] = []
                out.warnings.append({"code": UNKNOWN_CODE, "field": name, "value": chunk})
                continue
            out.values[name] = t.keys_from_bits(name, raw)
            out.values[f"_{name}_bits"] = raw
        else:
            label = t.value(name, chunk)
            if label is None:
                out.values[name] = None
                out.warnings.append({"code": UNKNOWN_CODE, "field": name, "value": chunk})
                continue
            out.values[name] = label
            out.values[f"_{name}_code"] = chunk
            rep = t.rep(name, chunk)
            if rep is not None:
                out.values[f"{name}_est"] = rep

    return out


def encode_payload(kind: str, sel: dict[str, Any]) -> str:
    """Selections in, payload string out. Mirrors decode_payload exactly."""
    t = get_tables()
    layout = t.layouts.get(kind)
    if layout is None:
        raise CodecError(BAD_SCHEMA, f"unknown payload kind {kind!r}")

    parts = [layout["version_char"]]
    for f in layout["fields"][1:]:
        name, width = f["name"], f["chars"]
        d = t.dim(name)

        if d.get("kind") == "bitfield":
            raw = sel.get(name, 0)
            if isinstance(raw, (list, tuple, set)):
                raw = t.bits_from_keys(name, list(raw))
            parts.append(b36_encode(int(raw), width))
            continue

        v = sel.get(name)
        if v is None:
            raise CodecError(BAD_SCHEMA, f"missing selection for {name!r}")
        code = str(v).upper()
        if code not in d["values"]:
            # Accept a label as well as a code, so callers can pass either.
            match = [k for k, val in d["values"].items()
                     if (val if isinstance(val, str) else val.get("label")) == v]
            if not match:
                raise CodecError(UNKNOWN_CODE, f"{v!r} is not a valid {name}")
            code = match[0]
        parts.append(code.rjust(width, "0"))

    out = "".join(parts)
    if len(out) != layout["length"]:
        raise CodecError(BAD_SCHEMA,
                         f"encoded {kind} payload is {len(out)} chars, "
                         f"expected {layout['length']}")
    return out
