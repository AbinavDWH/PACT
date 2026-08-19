"""Helper and organization assignment endpoints.

This is where `privacy.reveal` comes from. Before this router existed the
reveal transition had zero publishers: `matches.reveal` was in the schema,
`repo_matches.reveal()` was written and correct, and nothing in the system
could ever call it -- so the core of the privacy story ("identity unlocks on
acceptance") was unreachable at runtime.

Authorization is ownership, not a token: you may act on an allocation only if
your id is the owner on it. `find_allocation` returning None is a 403.
"""

from __future__ import annotations

import hmac
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.bus.eventbus import bus
from app.config import get_settings
from app.db import repo_matches, repo_requests
from app.db.mongo import get_db
from app.deps import current_org, issue
from app.notify import channels, dispatcher
from app.privacy import crypto
from app.privacy import policy as privacy_policy
from app.privacy import redact

log = logging.getLogger(__name__)
router = APIRouter(tags=["assignments"])


def _err(code: str, status: str = "error", **extra):
    return {"status": status, "error": code, **extra}


async def org_scope(org_id: str | None = None,
                    claims: dict = Depends(current_org)) -> str:
    """The organization the caller is actually allowed to act as.

    These endpoints previously took `org_id` straight from the query string
    with no authentication on the router at all, so any caller could read any
    organization's assignments and roster by editing the URL. That is precisely
    the boundary the org portal exists to demonstrate, so it is now derived
    from the token.

    When `require_auth` is off (the demo escape hatch in deps.py) `current_org`
    returns no org_id; only then is the query parameter honoured.
    """
    token_org = claims.get("org_id")
    if token_org:
        if org_id and org_id != token_org:
            raise HTTPException(
                status_code=403,
                detail="that organization is not yours to read")
        return token_org
    if org_id:
        return org_id
    raise HTTPException(status_code=400, detail="org_id required")


# ---------------------------------------------------------------------------
# Helper side
# ---------------------------------------------------------------------------

class ActorBody(BaseModel):
    """Demo-grade identity: the actor names itself. The ownership check below
    is what actually constrains it -- naming someone else's id gets you a 403,
    not their data."""
    actor_id: str
    reason: str | None = None


@router.get("/api/v1/helpers/me/assignments")
async def my_assignments(actor_id: str, state: str | None = None, limit: int = 20):
    """Masked assignment list. Each row is projected for `helper_pre` or
    `helper_post` depending on whether THAT match has been accepted -- the
    audience is per-row, because a helper can hold one accepted and one
    pending assignment at the same time."""
    rows = await repo_matches.for_owner(actor_id, limit, state)
    out = []
    for m in rows:
        found = await repo_matches.find_allocation(m["_id"], actor_id)
        if found is None:
            continue
        idx, alloc = found
        revealed = bool((m.get("reveal") or {}).get("helper_sees"))
        audience = privacy_policy.HELPER_POST if revealed else privacy_policy.HELPER_PRE

        req = await _request_for(m.get("request_id"))
        row = {
            "match_id": m["_id"], "request_id": m.get("request_id"),
            "allocation_index": idx, "allocation": alloc,
            "state": alloc.get("state"), "revealed": revealed,
            "justification": m.get("justification"),
            "delivery_code": m.get("delivery_code"),
            "seeker": req,
        }
        out.append(redact.project_record(row, audience, owned=True))
    return {"assignments": out, "count": len(out)}


async def _request_for(request_id: str | None) -> dict[str, Any]:
    """The seeker-side fields an assignment row needs. Returned RAW -- the
    caller projects it. Never return this unprojected to a client."""
    db = get_db()
    if db is None or not request_id:
        return {}
    doc = await db.requests.find_one({"_id": request_id})
    if not doc:
        return {}
    seeker = await db.seekers.find_one({"uid": doc.get("seeker_uid")}) or {}
    coords = (doc.get("loc") or {}).get("coordinates") or [None, None]
    # Decrypt here, redact after. The store holds ciphertext, this read path
    # decrypts, and A7 decides who is allowed to see the result. Returning
    # `name_enc` raw instead would hand an authorized helper an unreadable
    # "enc:gAAAA..." blob while looking like it worked.
    return {
        "lat": coords[1], "lon": coords[0],
        "name": crypto.decrypt(seeker.get("name_enc")),
        "contact": crypto.decrypt(seeker.get("phone_enc")),
        "uid": doc.get("seeker_uid"),
        "need": doc.get("need"), "quantity": doc.get("quantity"),
        "urgency": doc.get("urgency"),
    }


@router.post("/api/v1/assignments/{match_id}/accept")
async def accept(match_id: str, body: ActorBody):
    """THE reveal trigger. memory_draft.md 8.3: identity, contact and exact
    GPS unlock between a seeker and a helper only after an allocation is
    committed AND the helper accepts."""
    match = await repo_matches.get(match_id)
    if match is None:
        return _err("NO_SUCH_MATCH")

    found = await repo_matches.find_allocation(match_id, body.actor_id)
    if found is None:
        return _err("NOT_YOUR_ASSIGNMENT")
    idx, alloc = found

    # The org path's intermediary step is enforced here, which is what makes
    # the two dispatch paths differ in behaviour rather than in wording.
    if alloc.get("state") == dispatcher.ORG_STATE:
        return _err("NOT_ASSIGNED", detail=(
            "this allocation is held by an organization; its portal must assign a "
            "named helper from the roster before it can be accepted"))
    if alloc.get("state") in ("accepted", "delivered"):
        return _err("ALREADY_ACCEPTED")

    revealed = await repo_matches.reveal(match_id, "helper")
    await repo_matches.set_allocation_state(match_id, idx, "accepted")
    trace_id = match.get("request_id", match_id)
    await repo_requests.set_status(trace_id, "accepted", match_id=match_id)

    await bus.publish(
        trace_id, "privacy.reveal",
        {"match_id": match_id, "revealed_fields": revealed,
         "to": body.actor_id, "audience_before": privacy_policy.HELPER_PRE,
         "audience_after": privacy_policy.HELPER_POST,
         "trigger": "helper_accepted"},
        agent="a7_privacy",
        org_id=alloc.get("owner", {}).get("id") if alloc.get("owner", {}).get("kind") == "org" else None,
    )

    # The seeker learns who is coming at the same moment, and not before.
    await bus.publish(
        trace_id, "privacy.reveal",
        {"match_id": match_id, "revealed_fields": await repo_matches.reveal(match_id, "seeker"),
         "to": match.get("request_id"), "trigger": "helper_accepted",
         "audience_after": privacy_policy.SEEKER},
        agent="a7_privacy")

    seeker = await _request_for(match.get("request_id"))
    return {
        "status": "ok", "match_id": match_id, "state": "accepted",
        "revealed_fields": revealed,
        # Post-acceptance projection: exact position and contact, now legitimately.
        "seeker": redact.project(seeker, privacy_policy.HELPER_POST, owned=True),
        "delivery_code": match.get("delivery_code"),
    }


@router.post("/api/v1/assignments/{match_id}/decline")
async def decline(match_id: str, body: ActorBody):
    """Triggers A11. The declined owner is excluded on the replan."""
    match = await repo_matches.get(match_id)
    if match is None:
        return _err("NO_SUCH_MATCH")
    found = await repo_matches.find_allocation(match_id, body.actor_id)
    if found is None:
        return _err("NOT_YOUR_ASSIGNMENT")
    idx, alloc = found

    await repo_matches.set_allocation_state(match_id, idx, "declined")
    trace_id = match.get("request_id", match_id)
    await repo_matches.record_admin_action(
        match_id, "helper_declined", body.actor_id,
        before={"state": alloc.get("state")}, after={"state": "declined"},
        note=body.reason, trace_id=trace_id)

    await bus.publish(trace_id, "replan.triggered",
                      {"reason": "helper_declined", "prior_run_id": match.get("run_id"),
                       "excluded_owner": body.actor_id, "note": body.reason},
                      agent="a11_replanner")
    return {"status": "ok", "match_id": match_id, "state": "declined",
            "replan": "triggered"}


class StatusBody(ActorBody):
    state: str = "delivered"
    qty_delivered: int | None = None
    delivery_code: str | None = None


@router.post("/api/v1/assignments/{match_id}/status")
async def status(match_id: str, body: StatusBody):
    """Feeds A10. The delivery-code check is deterministic; the LLM branch is
    a cut-line (agents.md 9.2) and is not implemented."""
    match = await repo_matches.get(match_id)
    if match is None:
        return _err("NO_SUCH_MATCH")
    found = await repo_matches.find_allocation(match_id, body.actor_id)
    if found is None:
        return _err("NOT_YOUR_ASSIGNMENT")
    idx, _ = found

    code_ok = None
    if body.delivery_code is not None:
        code_ok = body.delivery_code.strip().upper() == (match.get("delivery_code") or "")
    await repo_matches.set_allocation_state(match_id, idx, body.state)

    verdict = ("verified" if code_ok else "disputed" if code_ok is False else "partial")
    await bus.publish(match.get("request_id", match_id), "verify.result",
                      {"match_id": match_id, "verdict": verdict,
                       "code_ok": code_ok, "qty_delivered": body.qty_delivered},
                      agent="a10_verify")
    return {"status": "ok", "match_id": match_id, "state": body.state,
            "code_ok": code_ok, "verdict": verdict}


# ---------------------------------------------------------------------------
# Organization side -- the intermediary the group code buys
# ---------------------------------------------------------------------------

class AssignBody(BaseModel):
    org_id: str
    helper_id: str


class OrgLogin(BaseModel):
    username: str
    password: str


@router.post("/api/v1/org/login")
async def org_login(body: OrgLogin):
    """Demo-grade, and described as such (memory_draft.md 7.6). It exists
    because /ws/org now requires an org token -- previously that socket had no
    authentication at all while /ws/agents beside it verified one."""
    db = get_db()
    if db is None:
        return _err("NO_DATABASE")
    org = await db.organizations.find_one({"web_user": body.username})
    if org is None:
        return _err("BAD_CREDENTIALS")
    # Seeded organizations carry web_pass_hash: None. Until per-org passwords
    # are seeded, the shared demo password gates them.
    expected = org.get("web_pass_hash") or get_settings().pact_org_pass
    if not hmac.compare_digest(body.password, expected):
        return _err("BAD_CREDENTIALS")
    return {"status": "ok", "token": issue(body.username, "org", org["_id"]),
            "org_id": org["_id"], "org_name": org.get("name"),
            "group_code": org.get("group_code")}


@router.get("/api/v1/org/group-code")
async def group_code(org_id: str = Depends(org_scope)):
    db = get_db()
    if db is None:
        return _err("NO_DATABASE")
    org = await db.organizations.find_one({"_id": org_id}, {"group_code": 1, "name": 1})
    if org is None:
        return _err("NO_SUCH_ORG")
    return {"org_id": org_id, "name": org.get("name"), "group_code": org.get("group_code")}


@router.get("/api/v1/org/assignments")
async def org_assignments(limit: int = 20,
                          org_id: str = Depends(org_scope)):
    """Only this org's allocations, projected for the `org` audience: masked
    seeker position, no contact, no cross-org debate, no rival stock."""
    rows = await repo_matches.for_owner(org_id, limit)
    out = []
    for m in rows:
        found = await repo_matches.find_allocation(m["_id"], org_id)
        if found is None:
            continue
        idx, alloc = found
        row = {
            "match_id": m["_id"], "request_id": m.get("request_id"),
            "allocation_index": idx, "allocation": alloc,
            "state": alloc.get("state"),
            "assigned_helper_id": m.get("assigned_helper_id"),
            "justification": m.get("justification"),
            "seeker": await _request_for(m.get("request_id")),
        }
        out.append(redact.project_record(row, privacy_policy.ORG, owned=True))
    return {"assignments": out, "count": len(out), "org_id": org_id}


@router.get("/api/v1/org/roster")
async def roster(org_id: str = Depends(org_scope)):
    """Helpers who joined with this org's group code."""
    db = get_db()
    if db is None:
        return {"roster": [], "org_id": org_id}
    rows = await db.helpers.find({"org_id": org_id}).to_list(100)
    out = []
    for r in rows:
        # Seeded helpers carry a plaintext name; anyone who signed up through
        # the app carries Fernet ciphertext. Returning the raw field leaked
        # "enc:gAAAAA..." straight into the roster table. An organization is
        # entitled to the names of helpers who joined with its own group code,
        # so decrypt; if the key has rotated and decryption fails, fall back to
        # a mask rather than showing ciphertext.
        raw = r.get("name_enc")
        name = crypto.decrypt(raw) if crypto.is_encrypted(raw) else raw
        out.append({
            "helper_id": r["_id"], "uid": r.get("uid"),
            "name": name or crypto.mask_uid(r.get("uid")),
            "status": r.get("status"),
            "capabilities": r.get("capabilities", []),
        })
    return {"org_id": org_id, "roster": out}


@router.post("/api/v1/org/assignments/{match_id}/assign")
async def org_assign(match_id: str, body: AssignBody,
                     scope: str = Depends(org_scope)):
    """The org portal step. Attaching a named helper is what moves an org
    allocation out of `awaiting_assignment` and makes it acceptable."""
    if body.org_id != scope:
        raise HTTPException(status_code=403,
                            detail="cannot assign on another organization's behalf")

    found = await repo_matches.find_allocation(match_id, body.org_id)
    if found is None:
        return _err("NOT_YOUR_ASSIGNMENT")
    idx, alloc = found

    db = get_db()
    helper = None
    if db is not None:
        helper = await db.helpers.find_one({"_id": body.helper_id, "org_id": body.org_id})
        if helper is None:
            return _err("NOT_ON_YOUR_ROSTER", detail=(
                "a helper can only be assigned by the organization whose group "
                "code they joined with"))

    await repo_matches.set_assigned_helper(match_id, body.helper_id)
    await repo_matches.set_allocation_state(match_id, idx, dispatcher.INDIVIDUAL_STATE)

    match = await repo_matches.get(match_id) or {}
    trace_id = match.get("request_id", match_id)
    await channels.push(
        to=body.helper_id, to_name=(helper or {}).get("name_enc"),
        message=match.get("justification") or "You have been assigned a delivery.",
        match_id=match_id, trace_id=trace_id, kind="assignment",
        meta={"via": "org_portal", "org_id": body.org_id,
              "state": dispatcher.INDIVIDUAL_STATE, "acceptable_now": True})

    await bus.publish(
        trace_id, "notify.sent",
        {"channel": "push", "route": "org_portal_to_named_helper",
         "target_masked": body.helper_id, "state": dispatcher.INDIVIDUAL_STATE,
         "acceptable_now": True,
         "message": "Organization assigned a named helper; now acceptable."},
        agent="a9_narrator", org_id=body.org_id)

    return {"status": "ok", "match_id": match_id, "helper_id": body.helper_id,
            "state": dispatcher.INDIVIDUAL_STATE}


# ---------------------------------------------------------------------------
# Outbox -- what would have been sent (agents.md 6.5)
# ---------------------------------------------------------------------------

@router.get("/api/v1/sms/outbox")
async def sms_outbox(limit: int = 50, channel: str | None = None):
    """There is no FCM project and no SMS gateway account. Every channel
    writes here instead of pretending to send."""
    return {"outbox": await channels.outbox_durable(limit, channel),
            "channels": ["push", "portal", "sms"]}
