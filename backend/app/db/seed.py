"""Demo seed data.

The layout below is defined **relative to a centre**, not in absolute
coordinates, and can be planted anywhere on Earth.

That is not a generalisation for its own sake. The fixtures were originally
pinned to Bhopal, and the radius ladder tops out at 150 km, so a request from
anywhere else returned nothing from `$geoNear` and the pipeline fell back to
hardcoded candidates with `geo_live: false`. The failure is silent: the portal
still shows a debate and an allocation, and the one part of the system that is
genuinely a database query has quietly stopped running. The geo query is one of
the four things `memory_draft.md` §23 says never to cut, so it must not be
possible to lose it by demoing in the wrong city.

Offsets are stored in **kilometres**, then converted to degrees at the target
latitude. Storing degree offsets instead would stretch the layout east-west as
it moved toward the equator: one degree of longitude is 102 km at Bhopal and
108 km at Chennai, so a 6% distortion would be baked into every ETA.

Idempotent: seeding twice with the same centre produces the same database.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from app.config import get_settings
from app.db.mongo import get_db

log = logging.getLogger(__name__)

# The reference the offsets below were measured against. Bhopal, the
# coordinates used throughout the protocol docs and every worked example.
BHOPAL = (23.2599, 77.4126)

KM_PER_DEG_LAT = 111.32


def default_centre() -> tuple[float, float]:
    """Where to plant the fixtures when nobody says otherwise.

    Settable per machine via PACT_SEED_LAT / PACT_SEED_LON so a demo laptop is
    configured once rather than reseeded by hand every restart.
    """
    s = get_settings()
    if s.seed_lat is not None and s.seed_lon is not None:
        return (s.seed_lat, s.seed_lon)
    return BHOPAL


def _pt(lat: float, lon: float) -> dict:
    """GeoJSON point. [longitude, latitude] -- in that order, always."""
    return {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]}


def offset_point(centre: tuple[float, float], north_km: float, east_km: float) -> dict:
    """A point `north_km` north and `east_km` east of `centre`.

    The longitude conversion divides by cos(latitude), which is what keeps the
    layout's real ground distances intact when it is moved north or south.
    """
    lat0, lon0 = centre
    lat = lat0 + north_km / KM_PER_DEG_LAT
    # Guard the poles: cos() reaches zero and the division explodes. No demo
    # happens at 89.9 degrees, but a silent inf in a coordinate would be an
    # unpleasant thing to debug on stage.
    cos_lat = max(math.cos(math.radians(lat0)), 0.01)
    lon = lon0 + east_km / (KM_PER_DEG_LAT * cos_lat)
    return _pt(lat, lon)


# ---------------------------------------------------------------------------
# The layout, in kilometres from the centre
# ---------------------------------------------------------------------------
# Deliberately varied so $geoNear has something to discriminate: different
# distances, stock levels, reliability and capabilities. (north_km, east_km).

ORGANIZATIONS = [
    {
        "_id": "ORG_NGO_001", "name": "Sanjeevani Relief Trust", "type": "ngo",
        "group_code": "SNJV-4K2", "web_user": "sanjeevani", "web_pass_hash": None,
        "offset": (1.258, 4.030), "service_radius_km": 50,
        "capabilities": ["cold_chain", "medical_staff"], "reliability": 0.86,
        "capacity_load": 0.40, "status": "active",
    },
    {
        "_id": "ORG_CSR_002", "name": "Metro Industries CSR", "type": "csr",
        "group_code": "MTRO-7X9", "web_user": "metrocsr", "web_pass_hash": None,
        "offset": (-6.835, -7.415), "service_radius_km": 80,
        "capabilities": ["bulk_transport"], "reliability": 0.79,
        "capacity_load": 0.25, "status": "active",
    },
    {
        "_id": "ORG_GOV_003", "name": "District Disaster Authority", "type": "government",
        "group_code": "DDMA-2B8", "web_user": "ddma", "web_pass_hash": None,
        "offset": (6.134, -2.414), "service_radius_km": 150,
        "capabilities": ["heavy_rescue", "boat", "bulk_transport"], "reliability": 0.91,
        "capacity_load": 0.60, "status": "active",
    },
    {
        "_id": "ORG_HOSP_004", "name": "Hamidia City Hospital", "type": "hospital",
        "group_code": "HMDA-9C4", "web_user": "hamidia", "web_pass_hash": None,
        "offset": (-0.657, -1.207), "service_radius_km": 25,
        "capabilities": ["cold_chain", "medical_staff", "ambulance"], "reliability": 0.93,
        "capacity_load": 0.72, "status": "active",
    },
]

# uid values mimic the codec's 4-char base36 device hash (codec.md 5.1).
HELPERS = [
    {"_id": "HLP_1", "uid": "N001", "org_id": "ORG_NGO_001", "name_enc": "A. Sharma",
     "offset": (1.124, 3.723), "status": "available", "capabilities": ["medical_staff"]},
    {"_id": "HLP_2", "uid": "N002", "org_id": "ORG_NGO_001", "name_enc": "P. Iyer",
     "offset": (0.768, 2.823), "status": "available", "capabilities": []},
    {"_id": "HLP_3", "uid": "M001", "org_id": "ORG_CSR_002", "name_enc": "S. Khan",
     "offset": (-6.557, -6.914), "status": "available", "capabilities": ["bulk_transport"]},
    {"_id": "HLP_4", "uid": "H001", "org_id": "ORG_HOSP_004", "name_enc": "Dr. R. Nair",
     "offset": (-0.601, -1.166), "status": "available", "capabilities": ["medical_staff"]},
    # org_id None => individual volunteer, dispatched directly (memory_draft 7.3)
    {"_id": "HLP_5", "uid": "V001", "org_id": None, "name_enc": "R. Kumar",
     "offset": (0.122, 0.552), "status": "available", "capabilities": []},
    {"_id": "HLP_6", "uid": "V002", "org_id": None, "name_enc": "T. Begum",
     "offset": (-0.490, 1.370), "status": "available", "capabilities": ["boat"]},
]

# owner.kind distinguishes the two dispatch paths; one collection serves both.
OFFERS = [
    ("ORG_NGO_001", "org", "medical_kits", 180, 45, ["cold_chain"]),
    ("ORG_NGO_001", "org", "water_kits", 260, 45, []),
    ("ORG_NGO_001", "org", "hygiene_kits", 140, 45, []),
    ("ORG_CSR_002", "org", "food_kits", 220, 70, ["bulk_transport"]),
    ("ORG_CSR_002", "org", "water_kits", 150, 70, []),
    ("ORG_CSR_002", "org", "blankets", 300, 70, []),
    ("ORG_GOV_003", "org", "tents", 120, 90, ["bulk_transport"]),
    ("ORG_GOV_003", "org", "rescue_team", 4, 60, ["heavy_rescue"]),
    ("ORG_GOV_003", "org", "evac_transport", 8, 60, ["boat"]),
    ("ORG_GOV_003", "org", "food_kits", 180, 90, []),
    ("ORG_HOSP_004", "org", "medical_kits", 20, 25, ["cold_chain"]),
    ("ORG_HOSP_004", "org", "medical_teams", 3, 25, ["medical_staff", "ambulance"]),
    ("HLP_5", "individual", "water_kits", 12, 15, []),
    ("HLP_6", "individual", "evac_transport", 1, 20, ["boat"]),
]


async def get_db_empty() -> bool:
    """True when there is nothing to work with, so startup can seed once
    without clobbering data on every reload."""
    db = get_db()
    if db is None:
        return False
    return await db.offers.count_documents({}, limit=1) == 0


async def seeded_centre() -> tuple[float, float] | None:
    """Where the fixtures currently sit, read back from the database.

    Needed because the centre is no longer a constant: after a restart the
    process has no memory of what the last reseed chose, and a sanity check
    that assumed Bhopal would fail against a database planted in Chennai.
    """
    db = get_db()
    if db is None:
        return None
    meta = await db.seed_meta.find_one({"_id": "centre"})
    if meta and "lat" in meta and "lon" in meta:
        return (meta["lat"], meta["lon"])
    # Seeded before this collection existed: fall back to any offer's position.
    doc = await db.offers.find_one({}, {"loc": 1})
    if doc and doc.get("loc"):
        lon, lat = doc["loc"]["coordinates"]
        return (lat, lon)
    return None


async def seed(reset: bool = True, centre: tuple[float, float] | None = None,
               label: str | None = None) -> dict:
    """Idempotent seed. Returns per-collection counts and the centre used."""
    db = get_db()
    if db is None:
        return {"seeded": False, "reason": "mongo not configured"}

    centre = centre or default_centre()
    lat0, lon0 = centre
    if not (-90 <= lat0 <= 90) or not (-180 <= lon0 <= 180):
        return {"seeded": False, "reason": f"centre out of range: {centre}"}

    if reset:
        for c in ("organizations", "helpers", "offers", "requests", "matches"):
            await db[c].delete_many({})

    now = datetime.now(timezone.utc)

    orgs, helpers, owner_loc = [], [], {}
    for o in ORGANIZATIONS:
        loc = offset_point(centre, *o["offset"])
        owner_loc[o["_id"]] = loc
        orgs.append({**{k: v for k, v in o.items() if k != "offset"},
                     "base_loc": loc, "created_at": now})
    for h in HELPERS:
        loc = offset_point(centre, *h["offset"])
        owner_loc[h["_id"]] = loc
        helpers.append({**{k: v for k, v in h.items() if k != "offset"},
                        "loc": loc, "created_at": now})

    await db.organizations.insert_many(orgs)
    await db.helpers.insert_many(helpers)

    offers = []
    for owner_id, kind, resource, available, eta_base, caps in OFFERS:
        offers.append({
            "_id": f"OFF_{owner_id}_{resource}",
            "owner": {"kind": kind, "id": owner_id},
            "resource": resource,
            "available": available,
            "reserved": 0,
            "loc": owner_loc[owner_id],     # denormalized so $geoNear runs here
            "eta_base_min": eta_base,
            "capabilities": caps,
            "updated_at": now,
        })
    await db.offers.insert_many(offers)

    await db.seed_meta.replace_one(
        {"_id": "centre"},
        {"_id": "centre", "lat": lat0, "lon": lon0,
         "label": label, "seeded_at": now},
        upsert=True)

    counts = {
        "organizations": await db.organizations.count_documents({}),
        "helpers": await db.helpers.count_documents({}),
        "offers": await db.offers.count_documents({}),
    }
    log.info("mongo: seeded %s at %.4f, %.4f%s",
             counts, lat0, lon0, f" ({label})" if label else "")
    return {"seeded": True, **counts,
            "centre": {"lat": lat0, "lon": lon0, "label": label}}


async def verify_lng_lat() -> dict:
    """Guard against the [lat,lng] inversion bug.

    Queries a point ~1 km from an offer that is actually in the database,
    rather than from a hardcoded city. If coordinates were stored flipped, the
    nearest offer comes back thousands of km away instead of ~1 km.

    Deriving the probe from the data is what makes this survive a reseed
    elsewhere: pinned to Bhopal, it reported a false failure the moment the
    fixtures moved.
    """
    db = get_db()
    if db is None:
        return {"checked": False}

    anchor = await db.offers.find_one({}, {"loc": 1})
    if not anchor or not anchor.get("loc"):
        return {"checked": False, "reason": "no offers"}

    lon, lat = anchor["loc"]["coordinates"]
    res = await db.offers.aggregate([
        {"$geoNear": {
            "near": _pt(lat + 0.009, lon),      # ~1 km north of a real offer
            "distanceField": "d_m", "spherical": True, "key": "loc",
        }},
        {"$limit": 1},
    ]).to_list(1)

    if not res:
        return {"checked": False, "reason": "no offers"}

    d_km = res[0]["d_m"] / 1000
    ok = d_km < 50
    return {"checked": True, "ok": ok, "nearest_km": round(d_km, 2),
            "centre": {"lat": lat, "lon": lon},
            "hint": None if ok else "coordinates look flipped -- must be [lng, lat]"}
