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
