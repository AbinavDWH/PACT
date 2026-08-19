"""Map tile cache.

The prefetch plan decides how many requests land on OpenStreetMap's donated
infrastructure. Their usage policy forbids bulk downloading, so most of these
tests assert the plan stays *small* and that the guard refuses rather than
quietly proceeding — the failure mode worth preventing is a typo'd zoom level
pulling forty thousand tiles.
"""

from __future__ import annotations

import math

import pytest

from app.routers.tiles import MAX_ZOOM, _deg2num, _valid, plan

CHENNAI = (13.008, 80.006)
BHOPAL = (23.2599, 77.4126)


# ---------------------------------------------------------------------------
# Slippy-map maths, against the published formula
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lat,lon,z,expected", [
    # Zoom 0 is one tile covering the world.
    (0.0, 0.0, 0, (0, 0)),
    (85.0, -179.0, 0, (0, 0)),
    # Published reference: the tile containing (0, 0) at z1 is (1, 1).
    (0.0, 0.0, 1, (1, 1)),
    # Hand-checked against (lon+180)/360*2^z and the Mercator y formula.
    (13.008, 80.006, 10, (739, 474)),
])
def test_deg2num_matches_the_slippy_map_formula(lat, lon, z, expected):
    assert _deg2num(lat, lon, z) == expected


def test_x_grows_eastward_and_y_grows_southward():
    """A transposition would still produce plausible tile numbers, so the
    directions are asserted separately from the values."""
    x_w, _ = _deg2num(0.0, -100.0, 8)
    x_e, _ = _deg2num(0.0, 100.0, 8)
    assert x_e > x_w

    _, y_n = _deg2num(60.0, 0.0, 8)
    _, y_s = _deg2num(-60.0, 0.0, 8)
    assert y_s > y_n


def test_tile_counts_quadruple_per_zoom_level_once_counts_are_large():
    """Each zoom halves the tile edge, so the count approaches 4x per level.

    Only *approaches*: a box is rounded out to whole tiles, and that rounding
    dominates at small counts -- a 5 km box goes 4 -> 9 (2.25x) at z12 -> z13,
    not 4 -> 16. Measured at 40 km, where the boundary effect is negligible,
    z13 -> z14 -> z15 is 4.00x exactly.

    Worth pinning because it is the whole justification for the max_tiles
    guard: two extra zoom levels is sixteen times the load on donated servers.
    """
    a = len(plan(*CHENNAI, 40.0, range(13, 14)))
    b = len(plan(*CHENNAI, 40.0, range(14, 15)))
    c = len(plan(*CHENNAI, 40.0, range(15, 16)))
    assert 3.4 <= b / a <= 4.2, f"{a} -> {b}"
    assert 3.8 <= c / b <= 4.2, f"{b} -> {c}"


# ---------------------------------------------------------------------------
# Bounds checking
# ---------------------------------------------------------------------------

def test_valid_rejects_out_of_range_tiles():
    assert _valid(0, 0, 0)
    assert _valid(10, 739, 474)
    assert not _valid(-1, 0, 0)
    assert not _valid(MAX_ZOOM + 1, 0, 0)
    assert not _valid(1, 2, 0), "x must be under 2^z"
    assert not _valid(1, 0, 2), "y must be under 2^z"
    assert not _valid(0, -1, 0)


# ---------------------------------------------------------------------------
# The plan stays polite
# ---------------------------------------------------------------------------

def test_the_demo_area_is_a_few_hundred_tiles_not_thousands():
    """8 km across z10-15 is what the runbook prefetches. If this grows by an
    order of magnitude, the prefetch has become a bulk download."""
    n = len(plan(*CHENNAI, 8.0, range(10, 16)))
    assert 100 < n < 1000, n


def test_the_plan_covers_the_requested_radius():
    """Every corner of the box must fall inside a planned tile, or the map has
    holes exactly where someone panned to."""
    lat, lon, r, z = *CHENNAI, 5.0, 13
    tiles = {(x, y) for _, x, y in plan(lat, lon, r, range(z, z + 1))}
    dlat = r / 111.32
    dlon = r / (111.32 * math.cos(math.radians(lat)))
    for clat in (lat - dlat, lat + dlat):
        for clon in (lon - dlon, lon + dlon):
            assert _deg2num(clat, clon, z) in tiles, (clat, clon)


def test_the_plan_moves_with_the_centre():
    """A plan pinned to one city would leave a demo elsewhere with blank
    ground -- the same failure the seed re-centring fixed."""
    a = {(x, y) for _, x, y in plan(*CHENNAI, 5.0, range(12, 13))}
    b = {(x, y) for _, x, y in plan(*BHOPAL, 5.0, range(12, 13))}
    assert not (a & b)


def test_longitude_span_widens_away_from_the_equator():
    """Degrees of longitude shrink with latitude, so a fixed-km box needs more
    of them further north. Using a constant would under-cover high latitudes."""
    near_equator = len(plan(1.0, 0.0, 20.0, range(12, 13)))
    far_north = len(plan(60.0, 0.0, 20.0, range(12, 13)))
    assert far_north > near_equator


def test_a_single_zoom_at_a_tiny_radius_is_at_least_one_tile():
    assert len(plan(*CHENNAI, 0.1, range(14, 15))) >= 1
