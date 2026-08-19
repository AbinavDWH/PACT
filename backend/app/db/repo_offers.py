"""Geospatial candidate search -- the real $geoNear from agents.md section 4.3.

This replaces the hardcoded candidate list in the scripted pipeline. The geo
query is one of the four things the plan says never to cut, so it becomes real
before the LLM agents do.
"""

from __future__ import annotations

import logging
from typing import Any

from pymongo import ReturnDocument

from app.db.mongo import get_db

log = logging.getLogger(__name__)

# Try each radius until we have enough candidates or cover the demand.
RADIUS_LADDER_KM = [10, 25, 60, 150]
MAX_CANDIDATES = 8          # caps LLM tokens downstream
FIELD_SPEED_KMH = 24        # rough ground speed for ETA estimation


def _pipeline(lat: float, lon: float, resource: str, radius_km: float) -> list[dict]:
    return [
        {"$geoNear": {                                   # MUST be stage 1
            "near": {"type": "Point", "coordinates": [lon, lat]},
            "distanceField": "distance_m",
            "maxDistance": radius_km * 1000,
            "spherical": True,
            "query": {"resource": resource, "available": {"$gt": 0}},
            "key": "loc",
        }},
        {"$addFields": {
            "distance_km": {"$divide": ["$distance_m", 1000]},
            "eta_min": {"$add": [
                "$eta_base_min",
                {"$multiply": [{"$divide": ["$distance_m", 1000]}, 60 / FIELD_SPEED_KMH]},
            ]},
            "free": {"$subtract": ["$available", "$reserved"]},
        }},
        {"$match": {"free": {"$gt": 0}}},
        {"$lookup": {"from": "organizations", "localField": "owner.id",
                     "foreignField": "_id", "as": "_org"}},
        {"$lookup": {"from": "helpers", "localField": "owner.id",
                     "foreignField": "_id", "as": "_helper"}},
        {"$sort": {"eta_min": 1}},
        {"$limit": MAX_CANDIDATES},
    ]


async def find_candidates(lat: float, lon: float, resource: str,
                          demand: int = 0) -> tuple[list[dict[str, Any]], float, int]:
    """Returns (candidates, radius_km_used, queries_run).

    Empty list if Mongo is unavailable -- the caller falls back to fixtures.
    """
    db = get_db()
    if db is None:
        return [], 0.0, 0

    queries = 0
    for radius in RADIUS_LADDER_KM:
        queries += 1
        try:
            rows = await db.offers.aggregate(_pipeline(lat, lon, resource, radius)).to_list(
                MAX_CANDIDATES)
        except Exception:
            log.exception("geoNear failed")
            return [], 0.0, queries

        covered = sum(r["free"] for r in rows)
        if len(rows) >= 3 or (demand and covered >= demand) or radius == RADIUS_LADDER_KM[-1]:
            return [_shape(r, i) for i, r in enumerate(rows, 1)], radius, queries

    return [], 0.0, queries


def _shape(row: dict, i: int) -> dict[str, Any]:
    """Project to the candidate view the agents see. Never hand a raw document
    to an LLM -- it wastes tokens and leaks fields the audience should not get."""
    org = (row.get("_org") or [None])[0]
    helper = (row.get("_helper") or [None])[0]
    owner = row["owner"]

    if org:
        name, kind, reliability, load = org["name"], org["type"], org.get("reliability", 0.7), org.get("capacity_load", 0.5)
    elif helper:
        name, kind, reliability, load = f"{helper.get('name_enc', 'Volunteer')}", "volunteer", 0.55, 0.1
    else:
        name, kind, reliability, load = owner["id"], "unknown", 0.5, 0.5

    return {
        "cand_id": f"c{i}",
        "offer_id": row["_id"],
        "owner_kind": owner["kind"],
        "owner_id": owner["id"],
        "name": name,
        "org_type": kind,
        "resource": row["resource"],
        "distance_km": round(row["distance_km"], 2),
        "eta_minutes": int(round(row["eta_min"])),
        "free": int(row["free"]),
        "reliability": reliability,
        "capacity_load": load,
        "capabilities": row.get("capabilities", []),
    }


async def reserve(offer_id: str, qty: int) -> bool:
    """Atomic check-and-reserve. Prevents two concurrent runs double-booking
    the same stock (agents.md section 4.4)."""
    db = get_db()
    if db is None:
        return True
    res = await db.offers.find_one_and_update(
        {"_id": offer_id,
         "$expr": {"$gte": [{"$subtract": ["$available", "$reserved"]}, qty]}},
        {"$inc": {"reserved": qty}},
        return_document=ReturnDocument.AFTER,
    )
    return res is not None


async def release(offer_id: str, qty: int) -> None:
    db = get_db()
    if db is not None:
        await db.offers.update_one({"_id": offer_id}, {"$inc": {"reserved": -qty}})
