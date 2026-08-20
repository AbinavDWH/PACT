"""Delivery channels.

There is no FCM project and no SMS gateway account, so every channel writes to
an inspectable outbox instead of pretending to send. `GET /api/v1/sms/outbox`
renders it (agents.md 6.5) -- which is the honest version of "the notification
was sent" and is also the only version a judge can verify on stage.

memory_draft.md 23 cut-line 5 explicitly permits this.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.db.mongo import get_db
from app.notify import fcm
from app.privacy import crypto

log = logging.getLogger(__name__)

# Newest last. Bounded so a long demo cannot grow it without limit.
_OUTBOX: list[dict[str, Any]] = []
MAX_OUTBOX = 500


def _now():
    return datetime.now(timezone.utc)


async def _record(entry: dict[str, Any]) -> dict[str, Any]:
    _OUTBOX.append(entry)
    del _OUTBOX[:-MAX_OUTBOX]
    db = get_db()
    if db is not None:
        try:
            await db.notifications.insert_one(dict(entry))
        except Exception:
            log.debug("notification persist skipped", exc_info=True)
    return entry


def outbox(limit: int = 50, channel: str | None = None) -> list[dict[str, Any]]:
    """In-process view. Empty after a restart -- use `outbox_durable`."""
    rows = [e for e in _OUTBOX if channel is None or e["channel"] == channel]
    return list(reversed(rows[-limit:]))


async def outbox_durable(limit: int = 50, channel: str | None = None) -> list[dict[str, Any]]:
    """Read back from Mongo so the outbox survives a restart.

    The in-memory list alone made the endpoint look broken after any restart:
    notifications had been persisted, and nothing ever read them.
    """
    db = get_db()
    if db is None:
        return outbox(limit, channel)
    q = {"channel": channel} if channel else {}
    try:
        rows = await db.notifications.find(q, {"_id": 0}).sort("ts", -1).to_list(limit)
        return rows
    except Exception:
        log.debug("outbox read fell back to memory", exc_info=True)
        return outbox(limit, channel)


def clear() -> None:
    _OUTBOX.clear()


async def _fcm_token_for(owner_id: str, collection: str = "helpers") -> str | None:
    """The registration token for one account, by document id or uid.

    `collection` because seekers register tokens through the same endpoint and
    live in their own collection -- looking a seeker up in `helpers` returns
    None and reads as "no registered device", which is the wrong answer given
    with confidence.
    """
    db = get_db()
    if db is None or not owner_id:
        return None
    doc = await db[collection].find_one(
        {"$or": [{"_id": owner_id}, {"uid": owner_id}]}, {"fcm_token": 1})
    return (doc or {}).get("fcm_token")


async def push(*, to: str, to_name: str | None, message: str, match_id: str,
               trace_id: str, kind: str, meta: dict | None = None) -> dict[str, Any]:
    """The helper app channel. Sends a real FCM message when configured.

    The outbox row is written either way. It is no longer a stand-in for the
    send -- it is the delivery record, and it now carries whether the send
    actually happened and why not.
    """
    token = await _fcm_token_for(to)
    result = await fcm.send(
        token or "",
        title="New assignment" if kind == "assignment" else "PACT",
        body=message,
        data={"match_id": match_id, "trace_id": trace_id, "kind": kind},
    ) if token else {"sent": False, "reason": "helper has no registered device"}

    # A token that Firebase rejects as unregistered means the app was
    # reinstalled. Clearing it stops every future dispatch retrying a dead
    # address, and the next launch registers a fresh one.
    if result.get("stale_token"):
        db = get_db()
        if db is not None:
            await db.helpers.update_one({"$or": [{"_id": to}, {"uid": to}]},
                                        {"$unset": {"fcm_token": ""}})

    return await _record({
        "channel": "push", "kind": kind, "to": to,
        "to_masked": crypto.mask_name(to_name) or to,
        "match_id": match_id, "trace_id": trace_id,
        "message": message, "meta": meta or {}, "ts": _now(),
        "state": "delivered" if result.get("sent") else "queued",
        "delivered": bool(result.get("sent")),
        "delivery_detail": result.get("reason"),
        "message_id": result.get("message_id"),
    })


async def seeker_push(*, uid: str, title: str, message: str, trace_id: str,
                      match_id: str | None = None, verdict: str,
                      meta: dict | None = None) -> dict[str, Any]:
    """Tell the person who sent a request what was decided about it.

    The seeker app registers an FCM token through the same endpoint the helper
    app does -- `PUT /helpers/me/push-token` writes to `seekers` when the
    session role is seeker -- and nothing has ever sent to it. So a seeker
    could only learn the verdict by opening the app and pulling
    `/seekers/me/requests`.

    `message` must already be safe for the SEEKER audience: their own data is
    fine, the helper's identity is not. Callers pass a fixed sentence rather
    than the arbiter's justification, which is written for an operator.

    Degrades exactly like `push`: no token, or no server credentials, and the
    outbox row is still written, so the console can show that the seeker was
    told even when the send could not happen.
    """
    token = await _fcm_token_for(uid, collection="seekers")
    result = await fcm.send(
        token or "", title=title, body=message,
        data={"trace_id": trace_id, "match_id": match_id or "",
              "kind": "verdict", "verdict": verdict},
    ) if token else {"sent": False, "reason": "seeker has no registered device"}

    if result.get("stale_token"):
        db = get_db()
        if db is not None:
            await db.seekers.update_one({"uid": uid}, {"$unset": {"fcm_token": ""}})

    return await _record({
        "channel": "push", "kind": "verdict", "to": uid,
        # A uid is the seeker's identity in this system. `mask_name` is wrong
        # for it -- it would render "a3f9c1" as "A." -- so the outbox shows a
        # prefix, the same shape the SMS channel uses for a hashed number.
        "to_masked": (uid[:4] + "…") if uid else "seeker",
        "match_id": match_id, "trace_id": trace_id,
        "message": message, "meta": {**(meta or {}), "verdict": verdict},
        "ts": _now(),
        "state": "delivered" if result.get("sent") else "queued",
        "delivered": bool(result.get("sent")),
        "delivery_detail": result.get("reason"),
        "message_id": result.get("message_id"),
    })


async def portal(*, org_id: str, org_name: str | None, message: str, match_id: str,
                 trace_id: str, kind: str, meta: dict | None = None) -> dict[str, Any]:
    """The organization web portal channel. Not a device notification: it
    lands in the org's assignment queue and waits for a human to assign it."""
    return await _record({
        "channel": "portal", "kind": kind, "to": org_id,
        "to_masked": org_name or org_id,
        "match_id": match_id, "trace_id": trace_id,
        "message": message, "meta": meta or {}, "ts": _now(), "state": "queued",
    })


async def sms(*, to_hash: str, message: str, match_id: str, trace_id: str,
              kind: str) -> dict[str, Any]:
    """Outbound SMS. The message has already been through the `sms` audience
    projection, which is the strictest in the policy -- no personal data at
    all, because SMS is plaintext over the operator network."""
    body = message[:160]
    return await _record({
        "channel": "sms", "kind": kind, "to": to_hash, "to_masked": to_hash[:8] + "…",
        "match_id": match_id, "trace_id": trace_id,
        "message": body, "chars": len(body), "ts": _now(), "state": "queued",
    })
