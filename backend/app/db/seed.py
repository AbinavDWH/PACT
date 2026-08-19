"""Demo seed data.

Centred on Bhopal (23.2599, 77.4126), the coordinates used throughout the
protocol docs. Deliberately varied so $geoNear has something to discriminate:
different distances, stock levels, reliability, and capabilities.

Idempotent: seeding twice produces the same database.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.db.mongo import get_db

log = logging.getLogger(__name__)

CENTRE = (23.2599, 77.4126)  # lat, lon -- flipped to [lon, lat] on write


def _pt(lat: float, lon: float) -> dict:
    """GeoJSON point. [longitude, latitude] -- in that order, always."""
    return {"type": "Point", "coordinates": [lon, lat]}


ORGANIZATIONS = [
    {
        "_id": "ORG_NGO_001", "name": "Sanjeevani Relief Trust", "type": "ngo",
        "group_code": "SNJV-4K2", "web_user": "sanjeevani", "web_pass_hash": None,
        "base_loc": _pt(23.2712, 77.4520), "service_radius_km": 50,
        "capabilities": ["cold_chain", "medical_staff"], "reliability": 0.86,
        "capacity_load": 0.40, "status": "active",
    },
    {
        "_id": "ORG_CSR_002", "name": "Metro Industries CSR", "type": "csr",
        "group_code": "MTRO-7X9", "web_user": "metrocsr", "web_pass_hash": None,
        "base_loc": _pt(23.1985, 77.3401), "service_radius_km": 80,
        "capabilities": ["bulk_transport"], "reliability": 0.79,
        "capacity_load": 0.25, "status": "active",
    },
    {
        "_id": "ORG_GOV_003", "name": "District Disaster Authority", "type": "government",
        "group_code": "DDMA-2B8", "web_user": "ddma", "web_pass_hash": None,
        "base_loc": _pt(23.3150, 77.3890), "service_radius_km": 150,
        "capabilities": ["heavy_rescue", "boat", "bulk_transport"], "reliability": 0.91,
        "capacity_load": 0.60, "status": "active",
    },
    {
        "_id": "ORG_HOSP_004", "name": "Hamidia City Hospital", "type": "hospital",
        "group_code": "HMDA-9C4", "web_user": "hamidia", "web_pass_hash": None,
        "base_loc": _pt(23.2540, 77.4008), "service_radius_km": 25,
        "capabilities": ["cold_chain", "medical_staff", "ambulance"], "reliability": 0.93,
        "capacity_load": 0.72, "status": "active",
    },
]

# uid values mimic the codec's 4-char base36 device hash (codec.md 5.1).
HELPERS = [
    {"_id": "HLP_1", "uid": "N001", "org_id": "ORG_NGO_001", "name_enc": "A. Sharma",
     "loc": _pt(23.2700, 77.4490), "status": "available", "capabilities": ["medical_staff"]},
    {"_id": "HLP_2", "uid": "N002", "org_id": "ORG_NGO_001", "name_enc": "P. Iyer",
     "loc": _pt(23.2668, 77.4402), "status": "available", "capabilities": []},
    {"_id": "HLP_3", "uid": "M001", "org_id": "ORG_CSR_002", "name_enc": "S. Khan",
     "loc": _pt(23.2010, 77.3450), "status": "available", "capabilities": ["bulk_transport"]},
    {"_id": "HLP_4", "uid": "H001", "org_id": "ORG_HOSP_004", "name_enc": "Dr. R. Nair",
     "loc": _pt(23.2545, 77.4012), "status": "available", "capabilities": ["medical_staff"]},
    # org_id None => individual volunteer, dispatched directly (memory_draft 7.3)
    {"_id": "HLP_5", "uid": "V001", "org_id": None, "name_enc": "R. Kumar",
     "loc": _pt(23.2610, 77.4180), "status": "available", "capabilities": []},
    {"_id": "HLP_6", "uid": "V002", "org_id": None, "name_enc": "T. Begum",
     "loc": _pt(23.2555, 77.4260), "status": "available", "capabilities": ["boat"]},
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

_OWNER_LOC = {
    **{o["_id"]: o["base_loc"] for o in ORGANIZATIONS},
    **{h["_id"]: h["loc"] for h in HELPERS},
}


async def get_db_empty() -> bool:
    """True when there is nothing to work with, so startup can seed once
    without clobbering data on every reload."""
    db = get_db()
    if db is None:
        return False
    return await db.offers.count_documents({}, limit=1) == 0


async def seed(reset: bool = True) -> dict:
    """Idempotent seed. Returns per-collection counts."""
    db = get_db()
    if db is None:
        return {"seeded": False, "reason": "mongo not configured"}

    if reset:
        for c in ("organizations", "helpers", "offers", "requests", "matches"):
            await db[c].delete_many({})

    now = datetime.now(timezone.utc)

    await db.organizations.insert_many([{**o, "created_at": now} for o in ORGANIZATIONS])
    await db.helpers.insert_many([{**h, "created_at": now} for h in HELPERS])

    offers = []
    for owner_id, kind, resource, available, eta_base, caps in OFFERS:
        offers.append({
            "_id": f"OFF_{owner_id}_{resource}",
            "owner": {"kind": kind, "id": owner_id},
            "resource": resource,
            "available": available,
            "reserved": 0,
            "loc": _OWNER_LOC[owner_id],   # denormalized so $geoNear runs here
            "eta_base_min": eta_base,
            "capabilities": caps,
            "updated_at": now,
        })
    await db.offers.insert_many(offers)

    counts = {
        "organizations": await db.organizations.count_documents({}),
        "helpers": await db.helpers.count_documents({}),
        "offers": await db.offers.count_documents({}),
    }
    log.info("mongo: seeded %s", counts)
    return {"seeded": True, **counts}


async def verify_lng_lat() -> dict:
    """Guard against the [lat,lng] inversion bug.

    Queries a point ~1 km from the centre. If coordinates were stored flipped,
    the nearest offer would come back thousands of km away instead of ~1 km.
    """
    db = get_db()
    if db is None:
        return {"checked": False}

    lat, lon = CENTRE
    res = await db.offers.aggregate([
        {"$geoNear": {
            "near": _pt(lat + 0.009, lon),      # ~1 km north
            "distanceField": "d_m", "spherical": True, "key": "loc",
        }},
        {"$limit": 1},
    ]).to_list(1)

    if not res:
        return {"checked": False, "reason": "no offers"}

    d_km = res[0]["d_m"] / 1000
    ok = d_km < 50
    return {"checked": True, "ok": ok, "nearest_km": round(d_km, 2),
            "hint": None if ok else "coordinates look flipped -- must be [lng, lat]"}
