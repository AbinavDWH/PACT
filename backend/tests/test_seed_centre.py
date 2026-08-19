"""Seed re-centring.

The bug this guards against is silent. The radius ladder stops at 150 km, so
fixtures left in Bhopal while the demo runs in Chennai make every `$geoNear`
return nothing -- and the pipeline then falls back to hardcoded candidates and
carries on, publishing a debate and committing an allocation with
`geo_live: false`. Nothing on screen says the database query stopped running.

So these tests assert the *geometry survives the move*: relative distances
preserved, absolute position changed. A test that only checked "seed() returned
ok" would pass against a seed that planted every helper on top of the centre.
"""

from __future__ import annotations

import math

import pytest

from app.db import seed

BHOPAL = (23.2599, 77.4126)
CHENNAI = (13.0827, 80.2707)
REYKJAVIK = (64.1466, -21.9426)


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance. Independent of the flat-earth offset maths in
    seed.py, so an error there cannot cancel out in the assertion."""
    r = 6371.0088
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp = math.radians(b[0] - a[0])
    dl = math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def latlon(point: dict) -> tuple[float, float]:
    lon, lat = point["coordinates"]
    return (lat, lon)


# ---------------------------------------------------------------------------
# offset_point
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("centre", [BHOPAL, CHENNAI, REYKJAVIK, (0.0, 0.0)])
def test_offset_distance_is_preserved_at_every_latitude(centre):
    """The reason offsets are stored in km, not degrees: one degree of
    longitude is 102 km at Bhopal and 108 km at Chennai, so degree offsets
    would stretch the layout east-west as it moved toward the equator."""
    p = latlon(seed.offset_point(centre, 0.0, 10.0))     # 10 km east
    assert haversine_km(centre, p) == pytest.approx(10.0, abs=0.15)

    p = latlon(seed.offset_point(centre, 10.0, 0.0))     # 10 km north
    assert haversine_km(centre, p) == pytest.approx(10.0, abs=0.15)


def test_offset_directions_are_not_transposed():
    """North must change latitude and east must change longitude. Swapping
    them still round-trips distance, so distance alone cannot catch it."""
    north = latlon(seed.offset_point(BHOPAL, 5.0, 0.0))
    east = latlon(seed.offset_point(BHOPAL, 0.0, 5.0))
    assert north[0] > BHOPAL[0] and north[1] == pytest.approx(BHOPAL[1])
    assert east[1] > BHOPAL[1] and east[0] == pytest.approx(BHOPAL[0])


def test_negative_offsets_go_south_and_west():
    p = latlon(seed.offset_point(BHOPAL, -5.0, -5.0))
    assert p[0] < BHOPAL[0]
    assert p[1] < BHOPAL[1]


def test_a_zero_offset_is_the_centre():
    assert latlon(seed.offset_point(CHENNAI, 0.0, 0.0)) == pytest.approx(CHENNAI, abs=1e-6)


def test_offset_point_emits_lng_lat_in_that_order():
    """The number one geospatial bug. Bhopal: longitude 77 > latitude 23."""
    pt = seed.offset_point(BHOPAL, 1.0, 1.0)
    assert pt["type"] == "Point"
    assert pt["coordinates"][0] > pt["coordinates"][1]


def test_the_poles_do_not_divide_by_zero():
    """cos(latitude) reaches zero at the pole. No demo happens at 89.9 degrees,
    but a silent `inf` in a coordinate would be unpleasant to debug on stage."""
    pt = seed.offset_point((89.99, 0.0), 0.0, 10.0)
    lon, lat = pt["coordinates"]
    assert math.isfinite(lon) and math.isfinite(lat)


# ---------------------------------------------------------------------------
# The fixture layout survives the move
# ---------------------------------------------------------------------------

def _layout(centre):
    return {o["_id"]: latlon(seed.offset_point(centre, *o["offset"]))
            for o in seed.ORGANIZATIONS + seed.HELPERS}


def test_relative_geometry_is_preserved_when_the_layout_moves():
    """Every pairwise distance must survive re-centring. This is what makes a
    re-seeded demo behave like the Bhopal one: same ETAs, same ranking, same
    argument between advocates."""
    a, b = _layout(BHOPAL), _layout(CHENNAI)
    ids = sorted(a)
    for i, x in enumerate(ids):
        for y in ids[i + 1:]:
            d_bhopal = haversine_km(a[x], a[y])
            d_chennai = haversine_km(b[x], b[y])
            assert d_chennai == pytest.approx(d_bhopal, rel=0.02, abs=0.05), \
                f"{x}-{y} distorted: {d_bhopal:.3f} -> {d_chennai:.3f}"


def test_the_layout_actually_moves():
    """The complement of the test above: preserving geometry by planting
    everything in the same place would satisfy it trivially."""
    a, b = _layout(BHOPAL), _layout(CHENNAI)
    for k in a:
        assert haversine_km(a[k], b[k]) > 1000


def test_every_fixture_lands_inside_the_first_radius_rung():
    """The whole point of re-centring. If a fixture sat beyond the ladder's
    150 km top rung, $geoNear would return nothing for a request at the centre
    and the pipeline would fall back to fixtures without saying so."""
    for centre in (BHOPAL, CHENNAI, REYKJAVIK):
        for oid, pos in _layout(centre).items():
            d = haversine_km(centre, pos)
            assert d < 25, f"{oid} is {d:.1f} km from the centre at {centre}"


def test_the_layout_is_spread_out_enough_to_discriminate():
    """$geoNear needs something to rank. A layout collapsed onto one point
    would make every option identical and the debate meaningless."""
    pos = _layout(CHENNAI)
    ds = sorted(haversine_km(CHENNAI, p) for p in pos.values())
    assert ds[0] < 1.0, "nothing is close to the centre"
    assert ds[-1] > 5.0, "nothing is far from the centre"


def test_offsets_match_the_original_bhopal_fixtures():
    """The offsets were derived from hand-placed coordinates. If someone
    retypes one, this catches it: the Bhopal layout must reproduce the
    positions the earlier fixtures used, to within a few metres."""
    original = {
        "ORG_NGO_001": (23.2712, 77.4520), "ORG_CSR_002": (23.1985, 77.3401),
        "ORG_GOV_003": (23.3150, 77.3890), "ORG_HOSP_004": (23.2540, 77.4008),
        "HLP_1": (23.2700, 77.4490), "HLP_2": (23.2668, 77.4402),
        "HLP_3": (23.2010, 77.3450), "HLP_4": (23.2545, 77.4012),
        "HLP_5": (23.2610, 77.4180), "HLP_6": (23.2555, 77.4260),
    }
    got = _layout(BHOPAL)
    for k, want in original.items():
        drift_m = haversine_km(want, got[k]) * 1000
        assert drift_m < 25, f"{k} drifted {drift_m:.0f} m from its original position"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def test_the_default_centre_is_bhopal_when_nothing_is_configured():
    from app.config import get_settings
    s = get_settings()
    if s.seed_lat is None and s.seed_lon is None:
        assert seed.default_centre() == seed.BHOPAL
    else:
        # A machine that configured a demo centre must report that one.
        assert seed.default_centre() == (s.seed_lat, s.seed_lon)


def test_owner_ids_are_unique_across_organizations_and_helpers():
    """`_OWNER_LOC` used to merge both dicts; a collision would have silently
    given an organization a volunteer's position."""
    ids = [o["_id"] for o in seed.ORGANIZATIONS] + [h["_id"] for h in seed.HELPERS]
    assert len(ids) == len(set(ids))


def test_every_offer_names_an_owner_that_exists():
    known = {o["_id"] for o in seed.ORGANIZATIONS} | {h["_id"] for h in seed.HELPERS}
    for owner_id, *_ in seed.OFFERS:
        assert owner_id in known, f"offer references unknown owner {owner_id}"
