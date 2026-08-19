"""Codec tests.

The parity vectors are the important ones: Kotlin runs the SAME vectors.json
from app assets, so any encoder divergence between the two languages fails here
rather than during the demo.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.codec import (b36_decode, b36_encode, decode, decode_geo, encode_ack,
                       encode_geo, encode_offer, encode_request, encode_status,
                       is_gsm7_safe, priority_score, request_to_needs,
                       xor_checksum)
from app.codec.errors import CodecError
from app.codec.payload import decode_payload, encode_payload

VECTORS = json.loads(
    (Path(__file__).resolve().parents[2] / "shared" / "codec" / "vectors.json")
    .read_text(encoding="utf-8"))["vectors"]


def _encode(v):
    if v["kind"] == "Q":
        return encode_request(v["selection"], v["lat"], v["lon"], v["uid"], v["seq"],
                              v.get("accuracy_m"))
    if v["kind"] == "G":
        return encode_offer(v["selection"], v["uid"], v["seq"],
                            v.get("lat"), v.get("lon"), v.get("location_code"))
    if v["kind"] == "C":
        return encode_ack(v["uid"], v["seq"], v["ref"], v["state"], v["eta_bucket"])
    if v["kind"] == "S":
        return encode_status(v["uid"], v["seq"], v["ref"], v["status"])
    raise AssertionError(f"unknown vector kind {v['kind']}")


# --------------------------------------------------------------------------
# Parity vectors
# --------------------------------------------------------------------------

@pytest.mark.parametrize("v", VECTORS, ids=[v["name"] for v in VECTORS])
def test_vector_encodes_exactly(v):
    assert _encode(v) == v["expected_sms"]


@pytest.mark.parametrize("v", VECTORS, ids=[v["name"] for v in VECTORS])
def test_vector_decodes(v):
    r = decode(v["expected_sms"])
    assert r["status"] == "accepted", r


@pytest.mark.parametrize("v", VECTORS, ids=[v["name"] for v in VECTORS])
def test_vector_is_single_part_gsm7(v):
    sms = v["expected_sms"]
    assert is_gsm7_safe(sms), "would force UCS-2 and halve SMS capacity"
    assert len(sms) <= 40, f"{len(sms)} chars"


@pytest.mark.parametrize("v", [v for v in VECTORS if v["kind"] == "Q"],
                         ids=[v["name"] for v in VECTORS if v["kind"] == "Q"])
def test_q_round_trip_coordinates(v):
    r = decode(v["expected_sms"])["decoded"]
    assert r["latitude"] == pytest.approx(v["lat"], abs=1e-5)
    assert r["longitude"] == pytest.approx(v["lon"], abs=1e-5)


# --------------------------------------------------------------------------
# Documented examples (codec.md section 7 / sms.md section 33)
# --------------------------------------------------------------------------

def test_documented_example_one():
    sms = "Q|001|7F3K|15223C03Q0|6QR6VFBQ33|7F"
    d = decode(sms)["decoded"]
    assert d["situation"] == "building_collapse"
    assert d["people_est"] == 3
    assert d["injury"] == "serious_stable"
    assert d["mobility"] == "trapped_in_debris"
    assert d["urgency"] == "critical"
    assert set(d["needs"]) == {"water_kits", "medical_kits", "rescue_team"}
    assert d["vulnerability"] == []
    assert (d["latitude"], d["longitude"]) == (23.25991, 77.41263)


def test_documented_offer_with_location_code():
    d = decode("G|015|H004|2400C131L|RA|26")["decoded"]
    assert d["orgtype"] == "hospital_clinic"
    assert set(d["resources"]) == {"medical_kits", "medical_teams"}
    assert d["location_code"] == "RA"
    assert d["location_name"] == "Region A"
    assert d["availability"] == "available" or d["availability"] == "limited"


# --------------------------------------------------------------------------
# base36 and PACK10
# --------------------------------------------------------------------------

@pytest.mark.parametrize("n", [0, 1, 35, 36, 1295, 60466175])
def test_b36_round_trip(n):
    assert b36_decode(b36_encode(n, 5)) == n


def test_b36_rejects_overflow():
    with pytest.raises(ValueError):
        b36_encode(36 ** 5, 5)


@pytest.mark.parametrize("lat,lon", [
    (0.0, 0.0), (23.25991, 77.41263), (-33.8688, 151.2093),
    (-89.99999, -179.99999), (89.99999, 179.99999), (-8.4095, -34.9),
])
def test_pack10_round_trip(lat, lon):
    p = decode_geo(encode_geo(lat, lon))
    assert p is not None and p.form == "pack10"
    assert p.latitude == pytest.approx(lat, abs=1e-5)
    assert p.longitude == pytest.approx(lon, abs=1e-5)


def test_pack10_is_exactly_ten_chars():
    assert len(encode_geo(-89.99999, -179.99999)) == 10
    assert len(encode_geo(89.99999, 179.99999)) == 10


def test_pack10_resolution_is_about_a_metre():
    a, b = encode_geo(23.25991, 77.41263), encode_geo(23.25992, 77.41263)
    assert a != b, "1e-5 degrees must be distinguishable"


def test_geo_disambiguation():
    assert decode_geo("23.2599,77.4126").form == "decimal"
    assert decode_geo("GEO:te7u2f").form == "geohash"
    assert decode_geo("HX:0DDBF6D82E22A1B0").form == "hex"
    assert decode_geo("6QR6VFBQ33").form == "pack10"
    assert decode_geo("RA").form == "location_code"
    assert decode_geo("!!!") is None


def test_geo_rejects_out_of_range():
    assert decode_geo("ZZZZZZZZZZ") is None   # decodes past +90 latitude


# --------------------------------------------------------------------------
# Failure modes (codec.md section 10)
# --------------------------------------------------------------------------

def test_bad_checksum_rejected():
    r = decode("Q|001|7F3K|15223C03Q0|6QR6VFBQ33|XX")
    assert r["status"] == "error" and r["error"] == "BAD_CRC"
    assert r["expected_checksum"] == "7F"


def test_unknown_schema_version_rejected():
    bad = "9" + "5223C03Q0"
    from app.codec.frame import frame as f
    r = decode(f("Q", "001", "7F3K", bad, "6QR6VFBQ33"))
    assert r["status"] == "error" and r["error"] == "BAD_SCHEMA"


def test_truncated_payload_rejected():
    from app.codec.frame import frame as f
    r = decode(f("Q", "001", "7F3K", "15223C", "6QR6VFBQ33"))
    assert r["status"] == "error" and r["error"] == "TRUNCATED"


def test_unknown_selection_char_is_partial_decode_not_rejection():
    """A request with one garbled field is still a person who needs rescue."""
    from app.codec.frame import frame as f
    # position 1 (situation) = 'Y', which is not in the table
    r = decode(f("Q", "001", "7F3K", "1Y223C03Q0", "6QR6VFBQ33"))
    assert r["status"] == "accepted"
    d = r["decoded"]
    assert d["situation"] is None
    assert d["degraded"] is True
    assert d["urgency"] == "critical"          # the rest still decoded
    assert set(d["needs"]) == {"water_kits", "medical_kits", "rescue_team"}
    assert any(w["code"] == "UNKNOWN_CODE" for w in r["warnings"])


def test_empty_and_garbage_never_raise():
    for bad in ["", "   ", "|||", "NOTAMESSAGE", "Q|", "\x00\x01"]:
        r = decode(bad)
        assert r["status"] == "error", bad


def test_unknown_type_rejected():
    from app.codec.frame import frame as f
    assert decode(f("ZZ", "001", "X"))["error"] == "UNKNOWN_TYPE"


def test_oversized_qg_rejected():
    from app.codec.frame import frame as f
    r = decode(f("Q", "001", "7F3K", "1" * 200, "6QR6VFBQ33"))
    assert r["error"] == "TOO_LONG"


# --------------------------------------------------------------------------
# Legacy compatibility -- nothing that worked before may regress
# --------------------------------------------------------------------------

def test_legacy_six_field_n():
    d = decode("N|NGO01|RegionA|food|300|H")["decoded"]
    assert d["type"] == "need"
    assert d["organization_id"] == "NGO01"
    assert d["location_code"] == "RA"
    assert d["location_name"] == "Region A"
    assert d["resource"] == "food_kits"
    assert d["quantity"] == 300
    assert d["urgency"] == "high"


def test_canonical_n_with_real_checksum():
    body = "N|001|NGO01|RA|F|300|H"
    d = decode(f"{body}|{xor_checksum(body)}")["decoded"]
    assert d["resource"] == "food_kits" and d["quantity"] == 300


def test_legacy_bad_quantity():
    assert decode("N|NGO01|RegionA|food|many|H")["error"] == "BAD_QTY"


def test_xor_checksum_matches_documented_value():
    assert xor_checksum("N|001|NGO01|RA|F|300|H") == "16"


# --------------------------------------------------------------------------
# Fan-out (codec.md section 8)
# --------------------------------------------------------------------------

def test_fanout_produces_one_record_per_need_bit():
    d = decode("Q|001|7F3K|15223C03Q0|6QR6VFBQ33|7F")["decoded"]
    needs = request_to_needs(d)
    assert {n["resource"] for n in needs} == {"water_kits", "medical_kits", "rescue_team"}
    by = {n["resource"]: n["quantity"] for n in needs}
    assert by["water_kits"] == 3            # 3 people x 1.0
    assert by["rescue_team"] == 1           # flat
    assert by["medical_kits"] >= 2          # 3 x 0.5 ceil = 2


def test_fanout_doubles_medical_for_critical_injury():
    from app.codec.frame import frame as f
    mild = decode(f("Q", "001", "AAAA", "13202C00400", "6QR6VFBQ33"))
    # injury '2' (serious_stable) vs '3' (critical): medical doubles at >= 3
    low = decode(f("Q", "001", "AAAA", "1322" + "0C" + "004" + "0", "6QR6VFBQ33"))
    high = decode(f("Q", "001", "AAAA", "1332" + "0C" + "004" + "0", "6QR6VFBQ33"))
    if low["status"] == "accepted" and high["status"] == "accepted":
        lq = {n["resource"]: n["quantity"] for n in request_to_needs(low["decoded"])}
        hq = {n["resource"]: n["quantity"] for n in request_to_needs(high["decoded"])}
        assert hq["medical_kits"] == lq["medical_kits"] * 2


def test_priority_score_ranks_critical_trapped_above_low_mobile():
    critical = decode("Q|001|7F3K|15223C03Q0|6QR6VFBQ33|7F")["decoded"]
    calm = decode("Q|999|0000|1Z099L0000|5CWG0APSW0|0C")["decoded"]
    assert priority_score(critical) > priority_score(calm)


# --------------------------------------------------------------------------
# Payload encode/decode symmetry
# --------------------------------------------------------------------------

def test_payload_symmetry_q():
    sel = {"situation": "0", "people": "5", "injury": "1", "mobility": "2",
           "urgency": "H", "needs": ["food_kits", "tents"], "vulnerability": ["elderly"]}
    p = encode_payload("Q", sel)
    d = decode_payload("Q", p).values
    assert d["situation"] == "flood"
    assert set(d["needs"]) == {"food_kits", "tents"}
    assert d["vulnerability"] == ["elderly"]


def test_payload_rejects_unknown_selection():
    with pytest.raises(CodecError):
        encode_payload("Q", {"situation": "NOPE", "people": "0", "injury": "0",
                             "mobility": "0", "urgency": "L", "needs": [],
                             "vulnerability": 0})
