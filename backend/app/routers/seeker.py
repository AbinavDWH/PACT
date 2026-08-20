"""What a seeker is allowed to know about their own request.

The app was write-only. A person tapped six chips, watched "Request sent", and
that was the last thing the system ever told them -- while the console behind
it went through triage, a geospatial query, a debate, and a human pressing
Approve or Reject. The one party with the most at stake in that decision was
the only party with no way to see it.

This router closes that loop, and it is the seeker's *own* record it returns:

  * The rows are selected by `seeker_uid`, never by a request id from the
    caller. There is no endpoint here that takes REQ-XXXXXX and hands back
    whatever it finds.
  * The uid comes from the session token. The `uid` query parameter is
    honoured only when the token carries no subject, which is the same demo
    escape hatch `org_scope` documents in assignments.py -- and asking for
    somebody else's uid with a real token is a 403, not a silent read.
  * Every row goes out through the SEEKER column of privacy/policy.py. That
    audience already existed and had no reader; this is it. It means the
    seeker sees their own position and contact in full and the delivery code
    in full, while the helper's identity stays masked and the
    cross-organization deliberation never leaves the console.

The verdict vocabulary below is deliberately small. Someone reading a phone
screen in a bad situation needs "approved" or "rejected", not the internal
status machine -- so the six database states collapse to five plain outcomes,
and each carries a sentence that says what happens next.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.db import repo_matches, repo_requests
from app.deps import current_device
from app.privacy import policy as privacy_policy
from app.privacy import redact

log = logging.getLogger(__name__)
router = APIRouter(tags=["seeker"])


# ---------------------------------------------------------------------------
# The verdict table
# ---------------------------------------------------------------------------
# request.status (written by agents/scripted.py and assignments.py) -> what the
# person who sent it is told. Data, not logic, for the same reason the privacy
# matrix is: what a seeker is told about a rejection is a product decision and
# should be reviewable without reading the pipeline.
#
# `verdict` is the machine-readable outcome the app styles on. `headline` and
# `detail` are what a person reads. `settled` says whether this is the end of
# the story -- the app polls while it is False and stops when it is True.

VERDICTS: dict[str, dict[str, Any]] = {
    "new": {
        "verdict": "pending",
        "headline": "Received",
        "detail": "Your request reached the coordination system and is queued.",
        "settled": False,
    },
    "triaged": {
        "verdict": "pending",
        "headline": "Being decided",
        "detail": "Severity assessed. Nearby suppliers are being searched and an "
                  "operator will approve or reject the allocation.",
        "settled": False,
    },
    "allocated": {
        "verdict": "approved",
        "headline": "Approved",
        "detail": "An operator approved help for you. It is being sent to a "
                  "responder now.",
        "settled": False,
    },
    "accepted": {
        "verdict": "approved",
        "headline": "Help is on the way",
        "detail": "A responder accepted your request and is on the way. Give them "
                  "the delivery code below.",
        "settled": True,
    },
    "rejected": {
        "verdict": "rejected",
        "headline": "Rejected",
        "detail": "An operator rejected this allocation. Your request has not been "
                  "closed — it is being re-planned against other suppliers.",
        "settled": False,
    },
    "unmet": {
        "verdict": "unmet",
        "headline": "Nothing available yet",
        "detail": "No supplier in range is holding what you asked for. Your request "
                  "stays open and is retried as stock changes.",
        "settled": False,
    },
}

# An unrecognised status must read as "still working", never as a verdict. A
# new state added to the pipeline should look unfinished here, not approved.
UNKNOWN: dict[str, Any] = {
    "verdict": "pending",
    "headline": "In progress",
    "detail": "Your request is moving through the system.",
    "settled": False,
}


def verdict_for(status: str | None) -> dict[str, Any]:
    """The outcome one request status carries. Pure -- unit-testable with no
    database and no session."""
    return dict(VERDICTS.get(status or "", UNKNOWN))


async def seeker_scope(uid: str | None = None,
                       claims: dict = current_device) -> str:
    """The uid the caller is actually allowed to read.

    Same shape as `assignments.org_scope`, and for the same reason: the token
    is the authority, the query parameter is only the escape hatch for when
    `require_auth` is off in a demo build.
    """
    token_uid = claims.get("sub")
    if token_uid and token_uid != "anonymous":
        if uid and uid != token_uid:
            raise HTTPException(
                status_code=403,
                detail="that request is not yours to read")
        return token_uid
    if uid:
        return uid
    raise HTTPException(status_code=400, detail="uid required")


async def _outcome(doc: dict[str, Any]) -> dict[str, Any]:
    """One request document as its own sender should see it. Raw -- the caller
    projects it. Never return this unprojected to a client."""
    row: dict[str, Any] = {
        "request_id": doc.get("_id"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
        "need": doc.get("need"),
        "quantity": doc.get("quantity"),
        "urgency": doc.get("urgency"),
        "source": doc.get("source"),
        "status": doc.get("status"),
        **verdict_for(doc.get("status")),
    }

    match_id = doc.get("match_id")
    if not match_id:
        return row

    match = await repo_matches.get(match_id)
    if not match:
        return row

    # An allow-list, not the stored allocation rows. Those carry `owner:
    # {kind, id}`, and policy.PATHS masks `allocations[].owner_id` but not that
    # nested spelling -- so passing them through whole would hand the seeker a
    # supplier id the helper_identity grant says they may not have. Naming the
    # four fields here means a new key added to a match document cannot reach
    # this audience by default. The key stays `allocations` so the policy paths
    # still apply on top, as the second line rather than the only one.
    row.update({
        "match_id": match_id,
        "allocations": [
            {"resource": a.get("resource"), "qty": a.get("qty"),
             "eta_min": a.get("eta_min"), "state": a.get("state")}
            for a in (match.get("allocations") or [])
        ],
        "unmet": match.get("unmet"),
        # The arbiter's justification is deliberately NOT here. The SEEKER
        # grant masks it, so it would arrive as a row of bullets -- noise on a
        # phone screen. The verdict detail above is what this audience gets
        # instead, written for them rather than for an operator.
        "delivery_code": match.get("delivery_code"),
        "approved_at": match.get("approved_at"),
        # The seeker's half of the acceptance transition. Set by
        # repo_matches.reveal(match_id, "seeker") when a helper accepts.
        "revealed": bool((match.get("reveal") or {}).get("seeker_sees")),
    })
    return row


@router.get("/api/v1/seekers/me/requests")
async def my_requests(limit: int = 10, uid: str = Depends(seeker_scope)):
    """Every request this person sent, newest first, with its verdict.

    A list rather than a single lookup because the honest answer to "what
    happened to my request" is sometimes "which one" -- the outbox retries and
    the codec's duplicate suppression both make more than one row normal.
    """
    limit = max(1, min(limit, 25))
    rows = await repo_requests.for_seeker(uid, limit)
    out = [
        redact.project_record(await _outcome(doc), privacy_policy.SEEKER, owned=True)
        for doc in rows
    ]
    return {
        "requests": out,
        "count": len(out),
        # The app polls while anything is unsettled and stops when nothing is,
        # so it does not have to re-derive that from five verdict strings.
        "settled": all(r.get("settled") for r in out) if out else True,
    }
