"""The routing rule (memory_draft.md 7.4), implemented as branching.

Previously the two paths were one string:

    via = "org portal" if a["owner_kind"] == "org" else "direct to volunteer"

which rendered a label and routed nothing. Both paths produced the same event,
on the same channel, with the same next state.

They now differ in four observable ways:

    |                  | organization        | individual volunteer |
    |------------------|---------------------|----------------------|
    | channel          | portal              | push                 |
    | initial state    | awaiting_assignment | pending_accept       |
    | acceptable now   | no                  | yes                  |
    | intermediary     | org IT assigns      | none                 |

An org allocation is genuinely un-acceptable until someone attaches a named
helper -- POST /assignments/{id}/accept rejects it with NOT_ASSIGNED. That is
what makes the group code mean something.
"""

from __future__ import annotations

import logging
from typing import Any

from app.bus.eventbus import bus
from app.db.mongo import get_db
from app.notify import channels
from app.privacy import policy as privacy_policy
from app.privacy import redact

log = logging.getLogger(__name__)

ORG_STATE = "awaiting_assignment"
INDIVIDUAL_STATE = "pending_accept"


async def _owner_name(owner_kind: str, owner_id: str) -> str | None:
    db = get_db()
    if db is None or not owner_id:
        return None
    try:
        coll = "organizations" if owner_kind == "org" else "helpers"
        doc = await db[coll].find_one({"_id": owner_id}, {"name": 1, "name_enc": 1})
        if doc:
            return doc.get("name") or doc.get("name_enc")
    except Exception:
        log.debug("owner lookup skipped", exc_info=True)
    return None


async def dispatch(*, match_id: str, trace_id: str, run_id: str,
                   allocation: dict[str, Any], message: str,
                   sms_variant: str | None = None) -> dict[str, Any]:
    """Route one allocation. Returns the routing decision, which the caller
    publishes so the portal can render which path was taken."""
    owner_kind = allocation.get("owner_kind") or (allocation.get("owner") or {}).get("kind")
    owner_id = allocation.get("owner_id") or (allocation.get("owner") or {}).get("id")
    name = allocation.get("name") or await _owner_name(owner_kind or "", owner_id or "")

    is_org = owner_kind == "org"
    state = ORG_STATE if is_org else INDIVIDUAL_STATE

    # The notification body is the helper-audience projection, not the raw
    # message. Pre-acceptance, that means an approximate area and no contact.
    projected = redact.project(
        {"justification": message, "allocations": [allocation]},
        privacy_policy.HELPER_PRE, owned=True,
    )
    body = projected.get("justification") or message

    meta = {
        "owner_kind": owner_kind, "owner_id": owner_id,
        "resource": allocation.get("resource"), "qty": allocation.get("qty"),
        "eta_min": allocation.get("eta_min"), "offer_id": allocation.get("offer_id"),
        "state": state, "acceptable_now": not is_org,
    }

    if is_org:
        entry = await channels.portal(
            org_id=owner_id or "", org_name=name, message=body,
            match_id=match_id, trace_id=trace_id, kind="assignment", meta=meta)
        route = "org_portal"
        detail = ("queued in the organization portal; an IT operator must assign a "
                  "named helper from the roster before it can be accepted")
    else:
        entry = await channels.push(
            to=owner_id or "", to_name=name, message=body,
            match_id=match_id, trace_id=trace_id, kind="assignment", meta=meta)
        route = "direct_volunteer"
        detail = "delivered straight to the volunteer's app; acceptable immediately"

    if sms_variant:
        # The SMS audience is the strictest in the policy: no personal data.
        await channels.sms(to_hash=f"h:{owner_id}", message=sms_variant,
                           match_id=match_id, trace_id=trace_id, kind="assignment")

    decision = {
        "route": route, "channel": entry["channel"], "state": state,
        "acceptable_now": not is_org, "owner_kind": owner_kind,
        "owner_id": owner_id, "detail": detail,
    }

    await bus.publish(
        trace_id, "notify.sent",
        {"channel": entry["channel"], "route": route,
         "target_masked": entry["to_masked"], "message": body,
         "state": state, "acceptable_now": not is_org, "detail": detail},
        agent="a9_narrator", run_id=run_id,
        # Setting org_id is what puts the frame on the org:<id> topic. Without
        # it /ws/org subscribes to a topic no event ever reaches.
        org_id=owner_id if is_org else None,
    )
    return decision


def outbox(limit: int = 50, channel: str | None = None) -> list[dict[str, Any]]:
    return channels.outbox(limit, channel)
