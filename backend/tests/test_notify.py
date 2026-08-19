"""Dispatch routing.

The claim under test is memory_draft.md 7.4: an allocation to an organization
and one to an individual volunteer take genuinely different paths. Before
notify/ existed, both produced the same event on the same channel and the only
difference was the words "org portal" versus "direct to volunteer" inside a
string -- which is what these tests exist to stop coming back.
"""

from __future__ import annotations

import asyncio

import pytest

from app.notify import channels, dispatcher

ORG_ALLOC = {"owner_kind": "org", "owner_id": "ORG_NGO_001",
             "name": "Sanjeevani Relief Trust", "resource": "water_kits",
             "qty": 3, "eta_min": 56, "offer_id": "OFF_1"}

VOL_ALLOC = {"owner_kind": "individual", "owner_id": "HLP_5",
             "name": "R. Kumar", "resource": "water_kits",
             "qty": 2, "eta_min": 16, "offer_id": "OFF_2"}


def _dispatch(alloc):
    channels.clear()
    return asyncio.run(dispatcher.dispatch(
        match_id="MATCH-TEST", trace_id="REQ-TEST", run_id="RUN-TEST",
        allocation=alloc, message="Deliver 3 water kits near the reported position."))


def test_an_organization_allocation_goes_to_the_portal():
    d = _dispatch(ORG_ALLOC)
    assert d["route"] == "org_portal"
    assert d["channel"] == "portal"
    assert d["state"] == dispatcher.ORG_STATE


def test_an_individual_allocation_goes_straight_to_the_volunteer():
    d = _dispatch(VOL_ALLOC)
    assert d["route"] == "direct_volunteer"
    assert d["channel"] == "push"
    assert d["state"] == dispatcher.INDIVIDUAL_STATE


def test_the_two_paths_differ_in_more_than_wording():
    """Every field that distinguishes them, asserted together -- a single
    shared channel or state would make the group code mean nothing."""
    org, vol = _dispatch(ORG_ALLOC), _dispatch(VOL_ALLOC)
    assert org["route"] != vol["route"]
    assert org["channel"] != vol["channel"]
    assert org["state"] != vol["state"]
    assert org["acceptable_now"] != vol["acceptable_now"]


def test_only_the_individual_path_is_acceptable_immediately():
    """The org path's intermediary is real: routers/assignments.accept
    rejects ORG_STATE with NOT_ASSIGNED until a named helper is attached."""
    assert _dispatch(ORG_ALLOC)["acceptable_now"] is False
    assert _dispatch(VOL_ALLOC)["acceptable_now"] is True


def test_each_dispatch_lands_in_the_outbox_on_its_own_channel():
    _dispatch(ORG_ALLOC)
    assert [e["channel"] for e in channels.outbox()] == ["portal"]
    _dispatch(VOL_ALLOC)
    assert [e["channel"] for e in channels.outbox()] == ["push"]


def test_the_notification_body_is_the_pre_acceptance_projection():
    """A helper who has not accepted must not be handed the seeker's exact
    position in the notification text."""
    channels.clear()
    asyncio.run(dispatcher.dispatch(
        match_id="M", trace_id="T", run_id="R", allocation=VOL_ALLOC,
        message="Deliver to 23.25991, 77.41263 now."))
    body = channels.outbox()[0]["message"]
    assert "23.25991" not in body


def test_an_sms_variant_is_recorded_on_the_sms_channel():
    channels.clear()
    asyncio.run(dispatcher.dispatch(
        match_id="M", trace_id="T", run_id="R", allocation=VOL_ALLOC,
        message="full message", sms_variant="PACT: 2 water kits, ETA 16m"))
    chans = {e["channel"] for e in channels.outbox()}
    assert chans == {"push", "sms"}


def test_the_sms_body_is_capped_at_one_segment():
    channels.clear()
    asyncio.run(dispatcher.dispatch(
        match_id="M", trace_id="T", run_id="R", allocation=VOL_ALLOC,
        message="x", sms_variant="A" * 400))
    sms = next(e for e in channels.outbox() if e["channel"] == "sms")
    assert sms["chars"] <= 160


@pytest.mark.parametrize("alloc,expect_org", [
    ({"owner": {"kind": "org", "id": "ORG_X"}, "qty": 1}, True),
    ({"owner": {"kind": "individual", "id": "HLP_X"}, "qty": 1}, False),
])
def test_routing_reads_the_nested_owner_shape_too(alloc, expect_org):
    """`matches.allocations` stores {owner: {kind, id}}; the solver emits
    flat owner_kind/owner_id. Both must route identically."""
    channels.clear()
    d = asyncio.run(dispatcher.dispatch(
        match_id="M", trace_id="T", run_id="R", allocation=alloc, message="m"))
    assert (d["route"] == "org_portal") is expect_org
