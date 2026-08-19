"""A1 -- dedupe and cluster.

There are two different duplicate problems and the system needs both:

    transport-level   the same message arriving twice, e.g. the app retrying
                      over SMS after an HTTP attempt it never saw acknowledged.
                      Keyed on (uid, seq) in routers/ingest.py. Already solved.

    situation-level   two different people, on two different phones, reporting
                      the same collapsed building. Same event, two requests,
                      and the solver will allocate for it twice.

This module is the second one. The key is geohash7 + resource + a 15-minute
window (agents.md 2.1), which is deliberately deterministic: a cluster decision
that changes between runs is not auditable.

The verdict is advisory. A duplicate is *linked and de-weighted*, never
dropped, because the cost of wrongly discarding a real second casualty is not
symmetric with the cost of dispatching twice.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.codec.geo import geohash_encode, geohash_neighbours
from app.db.mongo import get_db

log = logging.getLogger(__name__)

PRECISION = 7                 # ~153 m cell
WINDOW_MINUTES = 15


def dedupe_key(lat: float | None, lon: float | None, resource: str,
               precision: int = PRECISION) -> str:
    """geohash7:resource. Written to `requests.dedupe_key`, which is indexed."""
    if lat is None or lon is None:
        return f"nogeo:{resource}"
    return f"{geohash_encode(lat, lon, precision)}:{resource}"


async def check(request_id: str, lat: float | None, lon: float | None,
                resource: str, uid: str | None = None,
                window_minutes: int = WINDOW_MINUTES) -> dict[str, Any]:
    """Look for open requests for the same resource in the same cell within
    the window. Returns a verdict dict, always -- never raises into the
    pipeline.
    """
    key = dedupe_key(lat, lon, resource)
    cell = key.split(":")[0]
    since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)

    verdict: dict[str, Any] = {
        "duplicate": False,
        "cluster_size": 1,
        "geohash": cell,
        "precision": PRECISION,
        "dedupe_key": key,
        "window_minutes": window_minutes,
        "cells_searched": 1,
        "matches": [],
        "checked": False,
        "same_reporter": False,
    }

    db = get_db()
    if db is None or lat is None or lon is None:
        # Honest about not having checked, rather than reporting "no duplicate".
        verdict["reason"] = ("no database" if db is None else "no position on the request")
        return verdict

    # Search the cell and its eight neighbours: two phones twenty metres apart
    # can still land either side of a cell boundary.
    cells = geohash_neighbours(cell)
    verdict["cells_searched"] = len(cells)

    try:
        rows = await db.requests.find(
            {"_id": {"$ne": request_id},
             "dedupe_key": {"$in": [f"{c}:{resource}" for c in cells]},
             "created_at": {"$gte": since},
             "status": {"$nin": ["cancelled", "rejected", "verified"]}},
            {"_id": 1, "seeker_uid": 1, "created_at": 1, "quantity": 1, "status": 1},
        ).sort("created_at", -1).to_list(10)
    except Exception:
        log.exception("dedupe query failed")
        verdict["reason"] = "query failed"
        return verdict

    verdict["checked"] = True
    verdict["cluster_size"] = len(rows) + 1
    verdict["matches"] = [
        {"request_id": r["_id"], "status": r.get("status"),
         "quantity": r.get("quantity"),
         "age_s": int((datetime.now(timezone.utc)
                       - r["created_at"].replace(tzinfo=timezone.utc)).total_seconds())
                  if r.get("created_at") else None,
         "same_reporter": bool(uid) and r.get("seeker_uid") == uid}
        for r in rows
    ]
    verdict["duplicate"] = bool(rows)
    verdict["same_reporter"] = any(m["same_reporter"] for m in verdict["matches"])
    return verdict


def describe(v: dict[str, Any]) -> str:
    """The line A1 says out loud. It reports what was searched even when
    nothing was found -- 'no duplicate' with no stated scope is the message
    this replaces, and it was true by construction."""
    if not v["checked"]:
        return (f"Dedupe not performed: {v.get('reason', 'unknown')}. "
                f"Key would be {v['dedupe_key']}.")
    scope = (f"{v['cells_searched']} geohash-{v['precision']} cells around {v['geohash']} "
             f"(~153 m each), {v['window_minutes']}-minute window")
    if not v["duplicate"]:
        return f"No open request for this resource in {scope}. Cluster size 1."
    who = "the same reporter" if v["same_reporter"] else "a different reporter"
    ids = ", ".join(m["request_id"] for m in v["matches"][:3])
    return (f"{len(v['matches'])} open request(s) for the same resource in {scope}, "
            f"from {who}: {ids}. Clustered, not dropped -- a second caller may be a "
            f"second casualty. Cluster size {v['cluster_size']}.")
