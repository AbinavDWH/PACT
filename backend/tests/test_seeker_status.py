"""What the seeker is told, and what they are not.

Two things are worth a regression test here, and neither is "the endpoint
returns rows".

The first is the verdict table. It is the only place in the system that turns
an internal status into a sentence a person in a disaster reads, and the
failure that matters is an unrecognised status reading as good news. A new
pipeline state must land on "in progress", never on "approved".

The second is the audience. The status row is assembled from a match document,
which holds the supplier's name, owner id and offer id -- data the SEEKER
column of privacy/policy.py masks. A test that only checked the delivery code
came through would have passed against a version that also leaked the helper.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.privacy import policy as privacy_policy
from app.privacy import redact
from app.routers.seeker import VERDICTS, seeker_scope, verdict_for

SEEKER = {"sub": "a3f9c1", "role": "seeker", "org_id": None}
OTHER = {"sub": "b7e402", "role": "seeker", "org_id": None}
ANON = {"sub": "anonymous", "role": "seeker", "org_id": None}


def _scope(uid, claims):
    """The suite drives coroutines with asyncio.run rather than pytest-asyncio;
    follow that so this file needs no extra plugin."""
    return asyncio.run(seeker_scope(uid=uid, claims=claims))


# ---------------------------------------------------------------------------
# The verdict table
# ---------------------------------------------------------------------------

def test_the_admin_gate_outcomes_are_unambiguous():
    """The whole feature: an approval reads as approved and a rejection reads
    as rejected, in one word, with no shared vocabulary between them."""
    assert verdict_for("allocated")["verdict"] == "approved"
    assert verdict_for("rejected")["verdict"] == "rejected"


def test_an_unknown_status_never_reads_as_a_verdict():
    """The regression that matters. A state added to the pipeline and not added
    here must look unfinished, not approved."""
    for status in (None, "", "quarantined", "some_future_state"):
        v = verdict_for(status)
        assert v["verdict"] == "pending"
        assert v["settled"] is False


def test_only_acceptance_settles_a_request():
    """Approved is not the end: the helper still has to accept, and a rejection
    is followed by a replan. Anything else and the app stops polling while the
    story is still moving."""
    settled = {s for s, v in VERDICTS.items() if v["settled"]}
    assert settled == {"accepted"}


def test_every_verdict_says_what_happens_next():
    for status, v in VERDICTS.items():
        assert v["detail"].strip(), f"{status} has no detail"
        assert v["headline"].strip(), f"{status} has no headline"


def test_verdict_for_returns_a_copy():
    """Callers merge the verdict into a row with `**`; handing out the table's
    own dict would let one request mutate what every later one is told."""
    v = verdict_for("rejected")
    v["headline"] = "mutated"
    assert VERDICTS["rejected"]["headline"] == "Rejected"


# ---------------------------------------------------------------------------
# Whose request it is
# ---------------------------------------------------------------------------

def test_the_token_decides_whose_requests_these_are():
    assert _scope(None, SEEKER) == "a3f9c1"
    assert _scope("a3f9c1", SEEKER) == "a3f9c1"


def test_another_uid_is_refused():
    with pytest.raises(HTTPException) as e:
        _scope("b7e402", SEEKER)
    assert e.value.status_code == 403


def test_two_seekers_are_pinned_to_their_own():
    assert _scope(None, SEEKER) != _scope(None, OTHER)
    with pytest.raises(HTTPException):
        _scope("a3f9c1", OTHER)


def test_the_query_param_is_only_the_no_auth_escape_hatch():
    assert _scope("a3f9c1", ANON) == "a3f9c1"
    with pytest.raises(HTTPException) as e:
        _scope(None, ANON)
    assert e.value.status_code == 400


# ---------------------------------------------------------------------------
# The SEEKER audience
# ---------------------------------------------------------------------------

ROW = {
    "request_id": "REQ-ABC123",
    "status": "allocated",
    "verdict": "approved",
    "need": "water_kits",
    "quantity": 5,
    "match_id": "MATCH-99",
    "allocations": [
        {"resource": "water_kits", "qty": 3, "eta_min": 24, "state": "dispatching",
         # Present here only to prove the projection removes them. The router
         # builds an allow-list and never copies these across.
         "name": "Sanjeevani Relief Trust", "owner_id": "ORG_NGO_001",
         "offer_id": "OFF_1"},
    ],
    "justification": "Sanjeevani at 2.1 km can cover 3 of 5 within 24 minutes.",
    "delivery_code": "7K3M2Q",
    "unmet": 2,
}


def _projected():
    return redact.project_record(ROW, privacy_policy.SEEKER, owned=True)


def test_the_seeker_gets_the_delivery_code_in_full():
    """They read it out at the door. FULL in the policy matrix, and the one
    field on this row that has to survive intact."""
    assert _projected()["delivery_code"] == "7K3M2Q"


def test_the_seeker_learns_what_is_coming_and_when():
    alloc = _projected()["allocations"][0]
    assert alloc["qty"] == 3
    assert alloc["eta_min"] == 24
    assert alloc["resource"] == "water_kits"


def test_the_supplier_is_not_named_to_the_seeker():
    """helper_identity is MASKED for this audience. Before acceptance the
    seeker knows help is coming, not who is bringing it."""
    alloc = _projected()["allocations"][0]
    assert alloc.get("name") != "Sanjeevani Relief Trust"
    assert alloc.get("owner_id") != "ORG_NGO_001"
    assert alloc.get("offer_id") != "OFF_1"


def test_the_operators_reasoning_is_not_handed_over_verbatim():
    """justification is MASKED for this audience, which is why the router does
    not put it on the row at all -- it would arrive as bullets. This asserts
    the policy that decision rests on."""
    assert _projected().get("justification") != ROW["justification"]


def test_the_verdict_itself_survives_the_projection():
    """A privacy rule that quietly removed the outcome would make the whole
    feature silently useless."""
    out = _projected()
    assert out["verdict"] == "approved"
    assert out["request_id"] == "REQ-ABC123"
