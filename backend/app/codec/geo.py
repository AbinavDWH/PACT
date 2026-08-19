"""PACK10 coordinate packing (codec.md section 6).

    lat_token = base36(round((lat +  90) * 100000)) padded to 5
    lon_token = base36(round((lon + 180) * 100000)) padded to 5

36^5 = 60,466,176, comfortably above the 18,000,000 / 36,000,000 ranges.
Resolution ~1.1 m, which is below civilian GPS error, so nothing is lost.

An optional 11th character encodes fix accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.codec.base36 import DIGITS, b36_decode, b36_encode, is_b36
from app.codec.tables import get_tables

SCALE = 100000
LAT_OFFSET = 90
LON_OFFSET = 180


@dataclass(frozen=True)
class GeoPoint:
    latitude: float
    longitude: float
    accuracy_m: float | None = None
    form: str = "pack10"          # pack10 | decimal | geohash | hex | location_code
    location_code: str | None = None


def _accuracy_char(accuracy_m: float | None) -> str:
    if accuracy_m is None:
        return "9"
    table = get_tables().accuracy
    for code, limit in sorted(table.items(), key=lambda kv: (kv[1] is None, kv[1] or 0)):
        if limit is not None and accuracy_m <= limit:
            return code
    return "9"


def encode_geo(lat: float, lon: float, accuracy_m: float | None = None,
               include_accuracy: bool = False) -> str:
    if not (-90 <= lat <= 90):
        raise ValueError(f"latitude out of range: {lat}")
    if not (-180 <= lon <= 180):
        raise ValueError(f"longitude out of range: {lon}")
    token = (b36_encode(round((lat + LAT_OFFSET) * SCALE), 5)
             + b36_encode(round((lon + LON_OFFSET) * SCALE), 5))
    return token + _accuracy_char(accuracy_m) if include_accuracy else token


def decode_geo(token: str) -> GeoPoint | None:
    """Disambiguates every accepted location form (codec.md section 6.4).

    Order matters: decimal and prefixed forms are checked before PACK10,
    because a bare 10-char base-36 run is the only unmarked form.
    """
    if not token:
        return None
    t = token.strip().upper()

    # Legacy decimal "lat,lon"
    if "," in t or "." in t:
        try:
            lat_s, lon_s = t.split(",")
            return GeoPoint(float(lat_s), float(lon_s), form="decimal")
        except ValueError:
            return None

    if t.startswith("GEO:"):
        return GeoPoint(0.0, 0.0, form="geohash", location_code=t[4:])

    if t.startswith("HX:"):                       # superseded, read-only
        h = t[3:]
        if len(h) != 16:
            return None
        try:
            return GeoPoint(int(h[:8], 16) / 1e7 , int(h[8:], 16) / 1e7, form="hex")
        except ValueError:
            return None

    if len(t) in (10, 11) and is_b36(t):
        try:
            lat = b36_decode(t[:5]) / SCALE - LAT_OFFSET
            lon = b36_decode(t[5:10]) / SCALE - LON_OFFSET
        except ValueError:
            return None
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return None                            # BAD_GEO
        acc = None
        if len(t) == 11:
            acc = get_tables().accuracy.get(t[10])
        return GeoPoint(round(lat, 5), round(lon, 5), acc, form="pack10")

    if 2 <= len(t) <= 4 and t in get_tables().location_codes:
        return GeoPoint(0.0, 0.0, form="location_code", location_code=t)

    return None


# ---------------------------------------------------------------------------
# Geohash -- used for clustering, not for the wire
# ---------------------------------------------------------------------------
# PACK10 above is the transport encoding. This is different: a prefix-shareable
# cell id, so "two reports from the same collapsed building" is a string
# comparison rather than a distance query (A1 dedupe, agents.md 2.1).
#
#   precision 5 ~ 4.9 km    6 ~ 1.2 km    7 ~ 153 m    8 ~ 38 m
#
# A1 uses 7: tight enough that two different buildings do not collide, loose
# enough that two phones in the same courtyard do.

_B32 = "0123456789bcdefghjkmnpqrstuvwxyz"      # no a/i/l/o


def geohash_encode(lat: float, lon: float, precision: int = 7) -> str:
    lat_lo, lat_hi = -90.0, 90.0
    lon_lo, lon_hi = -180.0, 180.0
    out: list[str] = []
    bits, ch, even = 0, 0, True

    while len(out) < precision:
        # `>=`, not `>`: a value exactly on a midpoint goes to the UPPER half.
        # That is the reference convention, and it is why geohash(0, 0) is
        # "s0000..." rather than the adjacent "7zzzz...". Getting this backwards
        # still round-trips correctly, so only a cross-check against another
        # implementation catches it.
        if even:
            mid = (lon_lo + lon_hi) / 2
            if lon >= mid:
                ch = (ch << 1) | 1
                lon_lo = mid
            else:
                ch <<= 1
                lon_hi = mid
        else:
            mid = (lat_lo + lat_hi) / 2
            if lat >= mid:
                ch = (ch << 1) | 1
                lat_lo = mid
            else:
                ch <<= 1
                lat_hi = mid
        even = not even
        bits += 1
        if bits == 5:
            out.append(_B32[ch])
            bits, ch = 0, 0

    return "".join(out)


def geohash_neighbours(gh: str) -> list[str]:
    """The cell plus its eight neighbours.

    Without this, dedupe has an edge problem: two phones twenty metres apart
    but either side of a cell boundary produce different geohashes and both
    requests go through. Recomputing at the cell centre offsets is cruder than
    proper base-32 neighbour arithmetic but has no boundary blind spot.
    """
    if not gh:
        return []
    p = len(gh)
    lat, lon, dlat, dlon = geohash_decode(gh)
    out = {gh}
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            out.add(geohash_encode(lat + i * dlat * 2, lon + j * dlon * 2, p))
    return sorted(out)


def geohash_decode(gh: str) -> tuple[float, float, float, float]:
    """Returns (lat_centre, lon_centre, lat_err, lon_err)."""
    lat_lo, lat_hi = -90.0, 90.0
    lon_lo, lon_hi = -180.0, 180.0
    even = True
    for c in gh.lower():
        idx = _B32.find(c)
        if idx < 0:
            raise ValueError(f"bad geohash character: {c}")
        for mask in (16, 8, 4, 2, 1):
            if even:
                mid = (lon_lo + lon_hi) / 2
                if idx & mask:
                    lon_lo = mid
                else:
                    lon_hi = mid
            else:
                mid = (lat_lo + lat_hi) / 2
                if idx & mask:
                    lat_lo = mid
                else:
                    lat_hi = mid
            even = not even
    return ((lat_lo + lat_hi) / 2, (lon_lo + lon_hi) / 2,
            (lat_hi - lat_lo) / 2, (lon_hi - lon_lo) / 2)
