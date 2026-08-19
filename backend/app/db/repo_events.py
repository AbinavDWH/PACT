"""Deliberation transcript.

Two jobs: durability for the audit story, and gap recovery for a portal that
reconnects (?since=<seq>). Writes are fire-and-forget from the bus, so a slow
or dead cluster never stalls the pipeline.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.db.mongo import get_db

log = logging.getLogger(__name__)

# agent.token is the highest-volume event by far and is pure presentation --
# replaying it adds nothing but cost. The finalized agent.message carries the
# same text.
SKIP_PERSIST = {"agent.token"}


async def persist(ev: dict[str, Any]) -> None:
    db = get_db()
    if db is None or ev.get("type") in SKIP_PERSIST:
        return
    doc = dict(ev)
    doc["ts"] = datetime.now(timezone.utc)   # real datetime so the TTL index works
    doc["ts_iso"] = ev.get("ts")
    await db.agent_events.insert_one(doc)


async def replay(trace_id: str | None, since: int, limit: int = 500) -> list[dict[str, Any]]:
    """Events after `since`, oldest first, for a reconnecting client."""
    db = get_db()
    if db is None:
        return []
    q: dict[str, Any] = {"seq": {"$gt": since}}
    if trace_id and trace_id != "*":
        q["trace_id"] = trace_id
    try:
        rows = await db.agent_events.find(q, {"_id": 0, "ts": 0}).sort("seq", 1).to_list(limit)
        for r in rows:
            r["ts"] = r.pop("ts_iso", None)
            r["replayed"] = True
        return rows
    except Exception:
        log.exception("replay failed")
        return []


async def trace(trace_id: str, limit: int = 1000) -> list[dict[str, Any]]:
    db = get_db()
    if db is None:
        return []
    rows = await db.agent_events.find(
        {"trace_id": trace_id}, {"_id": 0, "ts": 0}).sort("seq", 1).to_list(limit)
    for r in rows:
        r["ts"] = r.pop("ts_iso", None)
    return rows


async def recent_traces(limit: int = 50) -> list[dict[str, Any]]:
    """Distinct requests seen, newest first -- hydrates the All Requests view
    on a fresh page load."""
    db = get_db()
    if db is None:
        return []
    rows = await db.agent_events.aggregate([
        {"$sort": {"seq": -1}},
        {"$group": {
            "_id": "$trace_id",
            "last_seq": {"$first": "$seq"},
            "ts": {"$first": "$ts_iso"},
            "types": {"$addToSet": "$type"},
        }},
        {"$sort": {"last_seq": -1}},
        {"$limit": limit},
    ]).to_list(limit)
    return [{"trace_id": r["_id"], "last_seq": r["last_seq"], "ts": r["ts"],
             "completed": "run.completed" in r["types"]} for r in rows]
