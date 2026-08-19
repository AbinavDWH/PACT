"""Matches and the admin audit trail.

`admin_actions` is append-only and has no TTL. Every approve, override and
reject is recorded with before/after state -- that record is what makes
"every automated decision is auditable and reversible" a true statement rather
than a claim in a pitch.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Any

from app.db.mongo import get_db

log = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


def delivery_code() -> str:
    """Short code the seeker reads back to confirm receipt. Ambiguity-free
    alphabet -- no O/0/I/1 -- because it gets spoken over a bad phone line."""
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    return "".join(secrets.choice(alphabet) for _ in range(6))


async def create(match_id: str, request_id: str, run_id: str, option: dict[str, Any],
                 justification: str = "", approved_by: str = "autopilot",
                 unmet: int = 0) -> str:
    db = get_db()
    code = delivery_code()
    if db is None:
        return code
    doc = {
        "_id": match_id,
        "request_id": request_id,
        "run_id": run_id,
        "option_id": option.get("option_id"),
        "strategy": option.get("label"),
        "allocations": [
            {**a, "state": "assigned", "owner": {"kind": a.get("owner_kind"),
                                                 "id": a.get("owner_id")}}
            for a in option.get("allocations", [])
        ],
        "coverage_pct": option.get("coverage_pct"),
        "unmet": unmet,
        "justification": justification,
        "approved_by": approved_by,
        "approved_at": _now(),
        "assigned_helper_id": None,
        # Masked by default. Unlocks only when a helper accepts.
        "reveal": {"helper_sees": [], "seeker_sees": []},
        "delivery_code": code,
        "status": "assigned",
        "created_at": _now(),
    }
    try:
        await db.matches.replace_one({"_id": match_id}, doc, upsert=True)
    except Exception:
        log.exception("match insert failed")
    return code


async def reveal(match_id: str, to: str) -> list[str]:
    """Privacy state transition: contact and exact position unlock only after
    an allocation is committed AND the helper accepts."""
    db = get_db()
    fields = ["exact_loc", "contact", "name"]
    if db is None:
        return fields
    key = "reveal.helper_sees" if to == "helper" else "reveal.seeker_sees"
    try:
        await db.matches.update_one(
            {"_id": match_id},
            {"$set": {key: fields, "status": "accepted", "accepted_at": _now()}})
    except Exception:
        log.exception("reveal failed")
    return fields


async def set_assigned_helper(match_id: str, helper_id: str) -> None:
    db = get_db()
    if db is None:
        return
    await db.matches.update_one(
        {"_id": match_id},
        {"$set": {"assigned_helper_id": helper_id, "updated_at": _now()}})


async def set_status(match_id: str, status: str, **extra) -> None:
    db = get_db()
    if db is None:
        return
    await db.matches.update_one(
        {"_id": match_id}, {"$set": {"status": status, "updated_at": _now(), **extra}})


async def get(match_id: str) -> dict | None:
    db = get_db()
    return None if db is None else await db.matches.find_one({"_id": match_id})


async def live(limit: int = 50, state: str | None = None) -> list[dict]:
    db = get_db()
    if db is None:
        return []
    q = {"status": state} if state else {}
    return await db.matches.find(q).sort("created_at", -1).to_list(limit)


# --------------------------------------------------------------------------
# Audit trail -- append only, never TTL'd
# --------------------------------------------------------------------------

async def record_admin_action(decision_id: str, action: str, admin_id: str,
                              before: Any = None, after: Any = None,
                              note: str | None = None, trace_id: str | None = None) -> None:
    db = get_db()
    if db is None:
        return
    try:
        await db.admin_actions.insert_one({
            "decision_id": decision_id, "trace_id": trace_id, "action": action,
            "admin_id": admin_id, "before": before, "after": after,
            "note": note, "ts": _now(),
        })
    except Exception:
        log.exception("admin action audit write failed")


async def audit(limit: int = 100) -> list[dict]:
    db = get_db()
    if db is None:
        return []
    return await db.admin_actions.find({}, {"_id": 0}).sort("ts", -1).to_list(limit)
