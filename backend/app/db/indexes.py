"""Index creation. Idempotent -- safe to run on every startup.

Coordinates are GeoJSON [longitude, latitude], in that order. This is the single
most common geospatial bug; see the assertion test in db/seed.py.
"""

from __future__ import annotations

import logging

import pymongo
from pymongo.errors import OperationFailure

from app.db.mongo import get_db

log = logging.getLogger(__name__)

# TTLs keep the free-tier cluster from filling. admin_actions is deliberately
# absent: it is the audit trail and must never expire.
EVENT_TTL_S = 24 * 60 * 60
SMS_TTL_S = 7 * 24 * 60 * 60
LOCK_TTL_S = 60


async def ensure_indexes() -> list[str]:
    db = get_db()
    if db is None:
        return []

    created: list[str] = []

    async def idx(coll: str, keys, **kw):
        try:
            name = await db[coll].create_index(keys, **kw)
            created.append(f"{coll}.{name}")
        except OperationFailure as e:
            # An existing index with different options is not fatal at demo scale.
            log.warning("index %s %s failed: %s", coll, keys, e.details.get("errmsg", e))

    # --- identities -------------------------------------------------------
    await idx("seekers", [("uid", 1)], unique=True)
    await idx("seekers", [("phone_hash", 1)], unique=True, sparse=True)

    await idx("helpers", [("uid", 1)], unique=True)
    await idx("helpers", [("phone_hash", 1)], unique=True, sparse=True)
    await idx("helpers", [("loc", pymongo.GEOSPHERE)])
    await idx("helpers", [("org_id", 1), ("status", 1)])

    await idx("organizations", [("group_code", 1)], unique=True)
    await idx("organizations", [("web_user", 1)], unique=True)
    await idx("organizations", [("base_loc", pymongo.GEOSPHERE)])

    # --- the geo-search collection ---------------------------------------
    await idx("offers", [("loc", pymongo.GEOSPHERE)])
    await idx("offers", [("resource", 1), ("available", -1)])
    await idx("offers", [("owner.id", 1), ("resource", 1)], unique=True)

    # --- requests and matches --------------------------------------------
    await idx("requests", [("loc", pymongo.GEOSPHERE)])
    await idx("requests", [("status", 1), ("triage.severity", -1)])
    await idx("requests", [("created_at", -1)])
    await idx("requests", [("dedupe_key", 1)], sparse=True)

    await idx("matches", [("request_id", 1)])
    await idx("matches", [("allocations.owner.id", 1), ("status", 1)])
    await idx("matches", [("created_at", -1)])

    # --- transcript, sms, audit, locks ------------------------------------
    await idx("agent_events", [("trace_id", 1), ("seq", 1)])
    await idx("agent_events", [("seq", -1)])
    await idx("agent_events", [("ts", 1)], expireAfterSeconds=EVENT_TTL_S)

    await idx("sms_messages", [("from_hash", 1), ("seq", 1)], unique=True, sparse=True)
    await idx("sms_messages", [("ts", 1)], expireAfterSeconds=SMS_TTL_S)

    await idx("admin_actions", [("ts", -1)])  # never TTL: audit trail

    await idx("locks", [("expires_at", 1)], expireAfterSeconds=LOCK_TTL_S)

    # Sessions. TTL 0 means "expire at the time in this field", so each session
    # carries its own lifetime -- a 90-day handset token and a 12-hour portal
    # token live in one collection without a second index.
    await idx("sessions", [("expires_at", 1)], expireAfterSeconds=0)
    await idx("sessions", [("sub", 1), ("role", 1)])

    await idx("notifications", [("ts", -1)])

    log.info("mongo: ensured %d indexes", len(created))
    return created
