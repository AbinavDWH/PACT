"""Requests and seekers.

Until now a committed allocation existed only in the event transcript, so a
portal reload lost it. These writes are what make the request survive.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.db.mongo import get_db

log = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


def _point(lat: float | None, lon: float | None) -> dict | None:
    if lat is None or lon is None:
        return None
    return {"type": "Point", "coordinates": [lon, lat]}      # [lng, lat]


def _mask(lat: float | None, lon: float | None) -> dict | None:
    """~1 km grid centroid for non-admin audiences."""
    if lat is None or lon is None:
        return None
    return _point(round(lat, 2), round(lon, 2))


async def upsert_seeker(uid: str, name: str | None = None,
                        phone_hash: str | None = None) -> None:
    db = get_db()
    if db is None or not uid:
        return
    try:
        await db.seekers.update_one(
            {"uid": uid},
            {"$setOnInsert": {"uid": uid, "created_at": _now()},
             "$set": {"last_seen": _now(),
                      **({"name_enc": name} if name else {}),
                      **({"phone_hash": phone_hash} if phone_hash else {})}},
            upsert=True)
    except Exception:
        log.debug("seeker upsert skipped", exc_info=True)


async def create(request: dict[str, Any], decoded: dict[str, Any] | None = None,
                 needs: list[dict] | None = None) -> None:
    db = get_db()
    if db is None:
        return
    lat, lon = request.get("lat"), request.get("lon")
    doc = {
        "_id": request["request_id"],
        "seeker_uid": request.get("uid"),
        "source": request.get("source", "http"),
        "raw_code": request.get("raw_code"),
        "decoded": decoded,
        "loc": _point(lat, lon),
        "loc_masked": _mask(lat, lon),
        "line_items": needs or [],
        "need": request.get("need"),
        "quantity": request.get("quantity"),
        "urgency": request.get("urgency"),
        "priority_score": request.get("priority_score"),
        "status": "new",
        "created_at": _now(),
    }
    try:
        await db.requests.replace_one({"_id": doc["_id"]}, doc, upsert=True)
    except Exception:
        log.exception("request insert failed")


async def set_status(request_id: str, status: str, **extra) -> None:
    db = get_db()
    if db is None:
        return
    try:
        await db.requests.update_one(
            {"_id": request_id},
            {"$set": {"status": status, "updated_at": _now(), **extra}})
    except Exception:
        log.debug("request status update skipped", exc_info=True)


async def set_triage(request_id: str, triage: dict[str, Any]) -> None:
    await set_status(request_id, "triaged", triage=triage)


async def recent(limit: int = 50, status: str | None = None) -> list[dict]:
    db = get_db()
    if db is None:
        return []
    q = {"status": status} if status else {}
    return await db.requests.find(q).sort("created_at", -1).to_list(limit)
