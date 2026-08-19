"""A1 dedupe: geohash correctness and key construction.

The database-backed half of A1 is exercised by the live run; these cover the
deterministic half, which is where a silent failure would hide. A geohash that
is merely *plausible* would cluster nothing and the agent would still print a
confident "no duplicate" line -- exactly the failure this replaces.
"""

from __future__ import annotations

import asyncio

import pytest

from app.agents import dedupe
from app.codec.geo import geohash_decode, geohash_encode, geohash_neighbours

BHOPAL = (23.2599, 77.4126)


# ---------------------------------------------------------------------------
# Known-good vectors, checked against the published geohash algorithm
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lat,lon,precision,expected", [
    # Published vectors, not values this implementation produced. Three
    # independent sources agreeing is what rules out a plausible-but-wrong
    # bit order, which round-trip tests alone cannot catch.
    (57.64911, 10.40744, 11, "u4pruydqqvj"),
    (42.60000, -5.60000, 5, "ezs42"),
    (37.83240, 112.55840, 12, "ww8p1r4t8yd0"),
    (57.64911, 10.40744, 5, "u4pru"),
    # Midpoint convention: exactly (0, 0) belongs to the upper half.
    (0.0, 0.0, 6, "s00000"),
    (-90.0, -180.0, 5, "00000"),
    (90.0, 180.0, 5, "zzzzz"),
])
def test_geohash_matches_the_published_algorithm(lat, lon, precision, expected):
    assert geohash_encode(lat, lon, precision) == expected


def test_geohash_length_is_the_requested_precision():
    for p in range(1, 13):
        assert len(geohash_encode(*BHOPAL, p)) == p


def test_geohash_round_trips_within_its_own_error_bounds():
    gh = geohash_encode(*BHOPAL, 7)
    lat, lon, dlat, dlon = geohash_decode(gh)
    assert abs(lat - BHOPAL[0]) <= dlat
    assert abs(lon - BHOPAL[1]) <= dlon


def test_precision_7_cell_is_roughly_150_metres():
    _, _, dlat, dlon = geohash_decode(geohash_encode(*BHOPAL, 7))
    # Degrees -> metres at this latitude, near enough for a sanity bound.
    assert 50 < dlat * 111_320 * 2 < 250
    assert 50 < dlon * 111_320 * 2 < 250


def test_lat_and_lon_are_not_transposed():
    """The number one geospatial bug. Bhopal and its mirror must differ."""
    assert geohash_encode(23.2599, 77.4126, 7) != geohash_encode(77.4126, 23.2599, 7)


# ---------------------------------------------------------------------------
# Clustering behaviour
# ---------------------------------------------------------------------------

def test_two_phones_in_the_same_courtyard_share_a_cell():
    a = geohash_encode(23.2599, 77.4126, 7)
    b = geohash_encode(23.25995, 77.41265, 7)     # ~7 m away
    assert a == b


def test_two_different_buildings_do_not_share_a_cell():
    a = geohash_encode(23.2599, 77.4126, 7)
    b = geohash_encode(23.2650, 77.4180, 7)       # ~750 m away
    assert a != b


def test_neighbours_cover_the_cell_boundary():
    """Two phones twenty metres apart either side of a boundary get different
    geohashes; without the neighbour ring both requests would go through."""
    gh = geohash_encode(*BHOPAL, 7)
    ns = geohash_neighbours(gh)
    assert gh in ns
    assert 4 <= len(ns) <= 9
    lat, lon, dlat, dlon = geohash_decode(gh)
    just_outside = geohash_encode(lat + dlat * 1.5, lon, 7)
    assert just_outside != gh
    assert just_outside in ns


# ---------------------------------------------------------------------------
# The key
# ---------------------------------------------------------------------------

def test_dedupe_key_separates_resources_in_the_same_cell():
    """Water and medical kits at one address are two needs, not a duplicate."""
    assert (dedupe.dedupe_key(*BHOPAL, "water_kits")
            != dedupe.dedupe_key(*BHOPAL, "medical_kits"))


def test_dedupe_key_is_stable():
    assert dedupe.dedupe_key(*BHOPAL, "water_kits") == dedupe.dedupe_key(*BHOPAL, "water_kits")


def test_dedupe_key_survives_a_request_with_no_position():
    k = dedupe.dedupe_key(None, None, "water_kits")
    assert k == "nogeo:water_kits"


# ---------------------------------------------------------------------------
# Honesty of the verdict
# ---------------------------------------------------------------------------

def test_no_database_reports_not_checked_rather_than_no_duplicate():
    """The failure this whole module replaces: a confident 'no duplicate'
    that was true by construction because nothing was ever queried."""
    v = asyncio.run(dedupe.check("REQ-1", *BHOPAL, "water_kits"))
    assert v["checked"] is False
    assert v["duplicate"] is False
    assert "Dedupe not performed" in dedupe.describe(v)


def test_a_request_with_no_position_cannot_be_deduped():
    # Under test there is no Mongo either, so `reason` reports whichever
    # precondition failed first; what matters is that it did not claim to have
    # checked, and that the key degrades to the no-geo form.
    v = asyncio.run(dedupe.check("REQ-1", None, None, "water_kits"))
    assert v["checked"] is False
    assert v["dedupe_key"] == "nogeo:water_kits"
    assert "Dedupe not performed" in dedupe.describe(v)


def test_describe_states_the_scope_it_actually_searched():
    v = {"checked": True, "duplicate": False, "cells_searched": 9, "precision": 7,
         "geohash": "tsk8h2r", "window_minutes": 15, "matches": [], "cluster_size": 1,
         "same_reporter": False}
    text = dedupe.describe(v)
    assert "9 geohash-7 cells" in text
    assert "tsk8h2r" in text
    assert "15-minute" in text
