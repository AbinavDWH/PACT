"""Top-level encode/decode.

decode() NEVER raises. It returns {"status": "accepted"|"error", ...} so a
malformed SMS from a panicking user can never take the ingest path down.

Dispatch order (codec.md section 9.2):
    Q -> G -> legacy 6-field N -> canonical 8-field N -> other sms.md types
"""

from __future__ import annotations

from typing import Any

# Import the functions, not the module: the package __init__ re-exports a
# `frame` function, which would shadow `app.codec.frame` the module.
from app.codec.frame import frame as build_frame
from app.codec.frame import unframe
from app.codec.errors import (BAD_FMT, BAD_GEO, BAD_QTY, UNKNOWN_LOC,
                              UNKNOWN_TYPE, CodecError)
from app.codec.geo import decode_geo, encode_geo
from app.codec.payload import decode_payload, encode_payload
from app.codec.tables import get_tables

# Legacy word/letter maps preserved from the original main.py implementation.
RESOURCE_MAP = {
    "F": "food_kits", "W": "water_kits", "M": "medical_kits", "D": "medical_teams",
    "T": "tents", "B": "blankets", "H": "hygiene_kits", "X": "rescue_team",
    "V": "evac_transport", "P": "power_kits", "I": "infant_kits",
    "S": "search_request", "U": "unknown",
    "FOOD": "food_kits", "WATER": "water_kits", "MEDICAL": "medical_kits",
    "MEDICINE": "medical_kits", "TENTS": "tents", "TENT": "tents",
    "BLANKETS": "blankets", "BLANKET": "blankets",
}
URGENCY_MAP = {"L": "low", "M": "medium", "H": "high", "C": "critical",
               "LOW": "low", "MEDIUM": "medium", "HIGH": "high", "CRITICAL": "critical"}
LOCATION_CODE_MAP = {"REGIONA": "RA", "REGION A": "RA", "REGIONB": "RB",
                     "REGION B": "RB", "REGIONC": "RC", "REGION C": "RC"}


def map_resource(v: str) -> str:
    return RESOURCE_MAP.get(v.strip().upper(), v.strip().lower())


def map_urgency(v: str) -> str:
    return URGENCY_MAP.get(v.strip().upper(), v.strip().lower())


def _location(raw: str) -> tuple[str | None, str | None]:
    t = get_tables()
    code = LOCATION_CODE_MAP.get(raw.strip().upper(), raw.strip().upper())
    return code, t.location_codes.get(code)


# --------------------------------------------------------------------------
# Encoding
# --------------------------------------------------------------------------

def encode_request(sel: dict[str, Any], lat: float, lon: float, uid: str, seq: int | str,
                   accuracy_m: float | None = None) -> str:
    geo = encode_geo(lat, lon, accuracy_m, include_accuracy=accuracy_m is not None)
    return build_frame("Q", str(seq).zfill(3), uid.upper(), encode_payload("Q", sel), geo)


def encode_offer(sel: dict[str, Any], uid: str, seq: int | str,
                 lat: float | None = None, lon: float | None = None,
                 location_code: str | None = None) -> str:
    if location_code:
        geo = location_code.upper()
    elif lat is not None and lon is not None:
        geo = encode_geo(lat, lon)
    else:
        raise CodecError(BAD_GEO, "encode_offer needs coordinates or a location code")
    return build_frame("G", str(seq).zfill(3), uid.upper(), encode_payload("G", sel), geo)


def encode_ack(uid: str, seq: int | str, ref: str, state: str | int,
               eta_bucket: str | int) -> str:
    return build_frame("C", str(seq).zfill(3), uid.upper(), ref.upper(),
                    str(state), str(eta_bucket))


def encode_status(uid: str, seq: int | str, ref: str, status: str | int) -> str:
    return build_frame("S", str(seq).zfill(3), uid.upper(), ref.upper(), str(status))


# --------------------------------------------------------------------------
# Decoding
# --------------------------------------------------------------------------

def _decode_qg(parts: list[str], kind: str, source: str) -> dict[str, Any]:
    if len(parts) < 5:
        raise CodecError(BAD_FMT, f"{kind} needs 5 fields before the checksum")
    _, seq, uid, payload, geo_raw = parts[:5]

    dec = decode_payload(kind, payload)
    point = decode_geo(geo_raw)

    out: dict[str, Any] = {
        "type": "seeker_request" if kind == "Q" else "helper_offer",
        "seq": seq, "uid": uid, "source": source,
        **{k: v for k, v in dec.values.items() if not k.startswith("_")},
    }
    out["_codes"] = {k[1:]: v for k, v in dec.values.items() if k.startswith("_")}

    warnings = list(dec.warnings)
    if point is None:
        warnings.append({"code": UNKNOWN_LOC, "field": "geo", "value": geo_raw})
        out["latitude"] = out["longitude"] = None
    elif point.form == "location_code":
        out["location_code"] = point.location_code
        out["location_name"] = get_tables().location_codes.get(point.location_code or "")
        out["latitude"] = out["longitude"] = None
    else:
        out["latitude"], out["longitude"] = point.latitude, point.longitude
        out["geo_form"] = point.form
        if point.accuracy_m is not None:
            out["accuracy_m"] = point.accuracy_m

    result = {"status": "accepted", "mode": "canonical", "decoded": out}
    if warnings:
        result["warnings"] = warnings
        out["degraded"] = True
    return result


def _decode_legacy_n(parts: list[str], canonical: bool, source: str) -> dict[str, Any]:
    i = 2 if canonical else 1
    try:
        quantity = int(parts[i + 3])
    except (ValueError, IndexError):
        raise CodecError(BAD_QTY, f"quantity {parts[i + 3]!r} is not an integer") from None
    code, name = _location(parts[i + 1])
    return {
        "status": "accepted",
        "mode": "canonical" if canonical else "legacy",
        "decoded": {
            "type": "need",
            **({"seq": parts[1]} if canonical else {}),
            "organization_id": parts[i],
            "location_code": code, "location_name": name,
            "resource": map_resource(parts[i + 2]),
            "quantity": quantity,
            "urgency": map_urgency(parts[i + 4]),
            "source": source,
        },
    }


def decode(sms: str, source: str = "sms") -> dict[str, Any]:
    """Never raises."""
    try:
        raw = (sms or "").strip().upper()
        if not raw:
            raise CodecError("EMPTY_SMS", "no content")

        mtype = raw.split("|", 1)[0]

        # Legacy 6-field N has no checksum.
        if mtype == "N" and len(raw.split("|")) == 6:
            return _decode_legacy_n(unframe(raw, verify=False), False, source)

        parts = unframe(raw)

        if mtype in ("Q", "G"):
            return _decode_qg(parts, mtype, source)

        if mtype == "N":
            return _decode_legacy_n(parts, True, source)

        if mtype == "S" and len(parts) >= 4:
            return {"status": "accepted", "mode": "canonical", "decoded": {
                "type": "status", "seq": parts[1], "uid": parts[2], "reference": parts[3],
                "status": get_tables().status_codes.get(parts[4], parts[4])
                if len(parts) > 4 else None,
                "source": source}}

        if mtype == "C" and len(parts) >= 4:
            return {"status": "accepted", "mode": "canonical", "decoded": {
                "type": "confirmation", "seq": parts[1], "uid": parts[2],
                "reference": parts[3],
                "result": parts[4] if len(parts) > 4 else None,
                "eta_bucket": parts[5] if len(parts) > 5 else None,
                "source": source}}

        raise CodecError(UNKNOWN_TYPE, f"message type {mtype!r} is not decoded yet")

    except CodecError as e:
        return e.as_dict()
    except Exception as e:                      # defensive: ingest must never 500
        return {"status": "error", "error": BAD_FMT, "detail": f"{type(e).__name__}: {e}"}
