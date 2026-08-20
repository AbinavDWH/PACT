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
    # Org-scoped frames are per-organization copies of events the admin already
    # received on the "*" topic. Replaying them to /ws/agents would double every
    # committed decision by the number of organizations on it.
    q: dict[str, Any] = {"seq": {"$gt": since}, "scope": {"$ne": "org"}}
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
        {"trace_id": trace_id, "scope": {"$ne": "org"}},
        {"_id": 0, "ts": 0}).sort("seq", 1).to_list(limit)
    for r in rows:
        r["ts"] = r.pop("ts_iso", None)
    return rows


async def recent_traces(limit: int = 50) -> list[dict[str, Any]]:
    """Distinct requests seen, newest first -- hydrates the All Requests view
    on a fresh page load.

    Ordered by time, not by `seq`. The sequence counter lives in the process
    (envelope._counter), so it only orders events that one process minted:
    across a restart, or while two backends briefly share a database, two runs
    can carry overlapping seq ranges whose timestamps disagree. That is not
    hypothetical -- it put a 01:56 request below a 01:55 one in this table,
    which is exactly the kind of thing that reads as lost data. The persisted
    `ts` is a real datetime written at insert, so it orders correctly however
    many processes wrote it.
    """
    db = get_db()
    if db is None:
        return []
    rows = await db.agent_events.aggregate([
        {"$sort": {"seq": 1}},
        {"$group": {
            "_id": "$trace_id",
            "last_seq": {"$max": "$seq"},
            "last_at": {"$max": "$ts"},         # real datetime, for ordering
            "ts": {"$max": "$ts_iso"},          # the string the portal renders
            "types": {"$addToSet": "$type"},
            # A row that says only "a request existed" is not worth a row. The
            # transcript already holds what it was, how it arrived and what it
            # got, so the archive reads the same as a live run instead of a
            # column of em dashes.
            "started": {"$first": {"$cond": [
                {"$eq": ["$type", "run.started"]}, "$payload", None]}},
            "summary": {"$max": {"$cond": [
                {"$eq": ["$type", "run.started"]}, "$payload.masked_summary", None]}},
            "source": {"$max": {"$cond": [
                {"$eq": ["$type", "run.started"]}, "$payload.request.source", None]}},
            "committed": {"$max": {"$cond": [
                {"$eq": ["$type", "decision.committed"]}, "$payload", None]}},
            "outcome": {"$max": {"$cond": [
                {"$eq": ["$type", "run.completed"]}, "$payload.status", None]}},
            "admin": {"$max": {"$cond": [
                {"$eq": ["$type", "admin.action"]}, "$payload.action", None]}},
            "agents": {"$addToSet": {"$cond": [
                {"$eq": ["$type", "agent.entered"]}, "$payload.agent", None]}},
        }},
        {"$sort": {"last_at": -1}},
        {"$limit": limit},
    ]).to_list(limit)

    out = []
    for r in rows:
        committed = r.get("committed") or {}
        allocations = committed.get("allocations") or []
        out.append({
            "trace_id": r["_id"],
            "last_seq": r["last_seq"],
            "ts": r["ts"],
            "completed": "run.completed" in r["types"],
            "summary": r.get("summary"),
            # "http" or "sms" -- which transport actually carried it. The
            # console had no way to show that a request arrived over SMS.
            "source": r.get("source"),
            "status": r.get("outcome"),
            "admin_action": r.get("admin"),
            # addToSet includes a null for every non-matching event.
            "agents": len([a for a in (r.get("agents") or []) if a]),
            "allocated": [
                {"qty": a.get("qty"), "name": a.get("name"),
                 "resource": a.get("resource")}
                for a in allocations
            ],
            "unmet": committed.get("unmet"),
        })
    return out


async def max_seq() -> int:
    """Highest seq already stored. Used at startup to resume numbering rather
    than restarting at 1 and colliding with history."""
    db = get_db()
    if db is None:
        return 0
    try:
        row = await db.agent_events.find_one({}, {"seq": 1}, sort=[("seq", -1)])
        return int((row or {}).get("seq") or 0)
    except Exception:
        log.exception("max_seq lookup failed")
        return 0
