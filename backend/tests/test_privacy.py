"""A7 redactor tests.

These assert on ABSENCE. A privacy test that only checks the happy path
("admin sees everything") proves nothing -- the failure mode is a field
surviving a projection it should not have survived, so every test below
searches the redacted output for the secret and requires it to be gone.
"""

from __future__ import annotations

import json

import pytest

from app.privacy import crypto, policy, redact

EXACT_LAT, EXACT_LON = 23.25991, 77.41263
NAME = "Anita Sharma"
PHONE = "+91 98765 43210"


def _committed_event() -> dict:
    """A realistic decision.committed envelope, shaped like the ones
    scripted.run actually publishes."""
    return {
        "v": 1, "seq": 42, "ts": "2026-08-19T10:02:31.412Z",
        "trace_id": "REQ-8F2A1C", "run_id": "RUN-01", "agent": "a8_gate",
        "type": "decision.committed",
        "payload": {
            "match_id": "MATCH-AB12CD",
            "delivery_code": "K7M2QP",
            "name": NAME,
            "contact": PHONE,
            "request": {
                "lat": EXACT_LAT, "lon": EXACT_LON, "uid": "7X2K",
                "raw_code": "Q|7X2K|...", "name": NAME, "phone": PHONE,
                "decoded": {"latitude": EXACT_LAT, "longitude": EXACT_LON},
            },
            "allocations": [
                {"name": "Sanjeevani Relief Trust", "owner_id": "ORG_NGO_001",
                 "offer_id": "OFF_1", "qty": 3, "eta_min": 55},
                {"name": "Hamidia City Hospital", "owner_id": "ORG_HOSP_004",
                 "offer_id": "OFF_2", "qty": 2, "eta_min": 35},
            ],
            "justification": "80% coverage in 55 minutes.",
        },
    }


def _blob(obj) -> str:
    return json.dumps(obj, default=str)


# ---------------------------------------------------------------------------
# The core claim: data is gone, not hidden
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("audience", ["helper_pre", "org", "sms", "seeker"])
def test_exact_coordinates_never_survive_a_non_admin_projection(audience):
    out = redact.project_event(_committed_event(), audience)
    if out is None:
        return                       # whole event withheld: stricter, still passes
    blob = _blob(out)
    assert "23.25991" not in blob
    assert "77.41263" not in blob


@pytest.mark.parametrize("audience", ["helper_pre", "org", "sms"])
def test_seeker_name_and_phone_never_survive(audience):
    out = redact.project_event(_committed_event(), audience)
    if out is None:
        return
    blob = _blob(out)
    assert "Anita" not in blob and "Sharma" not in blob
    assert "9876543210" not in blob and "98765" not in blob


def test_admin_projection_is_untouched():
    ev = _committed_event()
    out = redact.project_event(ev, "admin")
    assert out == ev
    assert "23.25991" in _blob(out)


def test_projection_does_not_mutate_the_original():
    """The bus hands one dict to every subscriber. In-place redaction would
    blank the admin's copy and read as a rendering bug."""
    ev = _committed_event()
    before = _blob(ev)
    redact.project_event(ev, "org")
    redact.project_event(ev, "helper_pre")
    assert _blob(ev) == before


def test_hidden_removes_the_key_rather_than_nulling_it():
    out = redact.project_event(_committed_event(), "org")
    assert "delivery_code" not in out["payload"]
    assert "contact" not in out["payload"]


# ---------------------------------------------------------------------------
# Revelation is a state transition, not a UI toggle
# ---------------------------------------------------------------------------

def test_acceptance_is_what_unlocks_contact_and_exact_position():
    ev = _committed_event()
    pre = redact.project_event(ev, "helper_pre", owned=True)
    post = redact.project_event(ev, "helper_post", owned=True)

    assert "contact" not in pre["payload"]
    assert post["payload"]["contact"] == PHONE
    assert pre["payload"]["request"]["lat"] != EXACT_LAT
    assert post["payload"]["request"]["lat"] == EXACT_LAT


def test_masked_position_is_about_one_kilometre_coarse():
    out = redact.project_event(_committed_event(), "helper_pre")
    lat = out["payload"]["request"]["lat"]
    assert lat == 23.26
    # ~1.1 km of latitude per 0.01 degree.
    assert abs(lat - EXACT_LAT) < 0.011


# ---------------------------------------------------------------------------
# Shape independence
# ---------------------------------------------------------------------------
# Regression: GET /helpers/me/assignments returned the seeker's exact GPS to a
# helper who had not accepted, because the path table covered "request.lat"
# and that row nested it at "seeker.lat". Exact paths only redact where they
# were told to look, so unambiguous key names are now redacted at any depth.

def _assignment_row() -> dict:
    """The real shape returned by GET /api/v1/helpers/me/assignments."""
    return {
        "match_id": "MATCH-AB476C", "request_id": "REQ-8AC8DA",
        "allocation": {"name": "Sanjeevani Relief Trust", "qty": 3, "eta_min": 56},
        "state": "pending_accept", "revealed": False,
        "delivery_code": "763FKN",
        "seeker": {"lat": EXACT_LAT, "lon": EXACT_LON, "name": NAME,
                   "contact": PHONE, "uid": "7F3K", "need": "water_kits"},
    }


def test_a_pending_assignment_row_does_not_leak_exact_gps():
    out = redact.project(_assignment_row(), "helper_pre", owned=True)
    blob = _blob(out)
    assert "23.25991" not in blob
    assert "77.41263" not in blob
    assert out["seeker"]["lat"] == 23.26


def test_a_pending_assignment_row_does_not_leak_contact_or_code():
    out = redact.project(_assignment_row(), "helper_pre", owned=True)
    assert "contact" not in out["seeker"]
    assert "delivery_code" not in out
    assert "9876543210" not in _blob(out)


def test_a_pending_assignment_row_does_not_leak_the_seekers_name():
    """Regression. `seeker.name` cannot be caught by the global key list --
    an allocation's `name` is the helper organization, which the helper IS
    entitled to see. Only the enclosing container separates them.

    This leaked in production the moment sign-up existed and seekers actually
    had names. While the field was always null, the surrounding tests passed
    without exercising anything."""
    out = redact.project(_assignment_row(), "helper_pre", owned=True)
    assert "Anita" not in _blob(out)
    assert "Sharma" not in _blob(out)


def test_the_helpers_own_organization_name_survives_the_same_projection():
    """The other half: over-redacting `name` everywhere would blank the
    helper's own allocation and make the assignment unusable."""
    out = redact.project(_assignment_row(), "helper_pre", owned=True)
    assert out["allocation"]["name"] == "Sanjeevani Relief Trust"


def test_the_same_row_opens_up_after_acceptance():
    out = redact.project(_assignment_row(), "helper_post", owned=True)
    assert out["seeker"]["lat"] == EXACT_LAT
    assert out["seeker"]["contact"] == PHONE
    assert out["delivery_code"] == "763FKN"


@pytest.mark.parametrize("nest", [
    {"seeker": {"lat": EXACT_LAT}},
    {"a": {"b": {"c": {"latitude": EXACT_LAT}}}},
    {"rows": [{"inner": [{"lon": EXACT_LON}]}]},
    {"payload": {"request": {"decoded": {"longitude": EXACT_LON}}}},
])
def test_coordinates_are_redacted_at_any_nesting_depth(nest):
    blob = _blob(redact.project(nest, "helper_pre", owned=True))
    assert "23.25991" not in blob and "77.41263" not in blob


def test_the_key_walk_terminates_on_a_deeply_nested_payload():
    """A pathological payload must not be able to stall the pipeline from
    inside the privacy tier."""
    deep: dict = {"lat": EXACT_LAT}
    for _ in range(200):
        deep = {"n": deep}
    redact.project(deep, "helper_pre")      # must return, not recurse forever


# ---------------------------------------------------------------------------
# Free text
# ---------------------------------------------------------------------------
# A9 writes prose and its prompt merely *asks* it not to include coordinates.
# The field matrix cannot see inside a sentence, so prose is scrubbed by regex.

def test_a_coordinate_pair_inside_narrator_prose_is_removed():
    ev = {**_committed_event(), "payload": {
        "message": f"Deliver to {EXACT_LAT}, {EXACT_LON} now.", "allocations": []}}
    out = redact.project_event(ev, "helper_pre", owned=True)
    assert "23.25991" not in _blob(out)
    assert "approx" in out["payload"]["message"]


def test_a_phone_number_inside_prose_is_removed():
    out = redact.project({"admin_summary": "Call the seeker on 9876543210."},
                         "helper_pre", owned=True)
    assert "9876543210" not in out["admin_summary"]


def test_scrubbing_leaves_ordinary_numbers_alone():
    """Over-redaction that eats every number would make the narrator useless."""
    text = "80% coverage in 55 minutes across 3 helpers, ETA 16.5 min."
    assert redact.scrub_text(text) == text


def test_scrubbing_is_skipped_for_an_audience_that_may_see_position():
    text = f"Deliver to {EXACT_LAT}, {EXACT_LON} now."
    out = redact.project({"message": text}, "helper_post", owned=True)
    assert out["message"] == text


def test_admin_prose_is_never_scrubbed():
    ev = {**_committed_event(), "payload": {"message": f"{EXACT_LAT}, {EXACT_LON}"}}
    assert redact.project_event(ev, "admin") == ev


# ---------------------------------------------------------------------------
# The organization boundary (memory_draft.md 7.5)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("etype", [
    "debate.opened", "debate.turn", "debate.closed", "options.proposed",
    "agent.token", "decision.proposed", "agent.tool_call", "admin.action",
])
def test_an_organization_never_receives_the_cross_org_deliberation(etype):
    ev = {**_committed_event(), "type": etype, "agent": "a4_advocates"}
    assert redact.project_event(ev, "org") is None


def test_advocate_and_arbiter_messages_are_dropped_for_an_org():
    """These arrive as agent.message, which orgs otherwise receive. Filtering
    on type alone would leak the debate through the wrong door."""
    for agent in ("a4_advocates", "a6_arbiter", "a2_triage", "a5_solver"):
        ev = {**_committed_event(), "type": "agent.message", "agent": agent,
              "payload": {"text": "c2 is closest", "structured": {}}}
        assert redact.project_event(ev, "org") is None


def test_an_org_sees_its_own_allocation_but_not_a_rivals_stock():
    ev = {
        **_committed_event(), "type": "agent.message", "agent": "a3_geo",
        "payload": {"structured": {"candidates": [
            {"name": "Sanjeevani Relief Trust", "free": 180, "reliability": 0.86,
             "capacity_load": 0.4, "distance_km": 6.2, "owner_id": "ORG_NGO_001"},
        ]}},
    }
    out = redact.project_event(ev, "org")
    cand = out["payload"]["structured"]["candidates"][0]
    assert "free" not in cand
    assert "reliability" not in cand


def test_blocked_types_is_computed_not_hand_listed():
    blocked = policy.blocked_types("org")
    assert "debate.turn" in blocked
    assert "decision.committed" not in blocked
    assert policy.blocked_types("admin") == frozenset()
    # Complement of the allow-list over the full registry from agents.md 3.2.
    assert blocked == policy.ALL_TYPES - policy.VISIBLE_TYPES["org"]


# ---------------------------------------------------------------------------
# The audit A7 publishes must be measured, not asserted
# ---------------------------------------------------------------------------

def test_audit_counts_come_from_the_real_payload():
    a = redact.audit(_committed_event()["payload"], "helper_pre")
    assert a["fields_touched"] > 0
    assert "seeker_contact" in a["withheld"]
    assert "seeker_loc" in a["masked"]
    assert a["by_field"]["seeker_loc"] >= 3      # lat, lon, decoded.latitude, ...


def test_audit_on_an_empty_payload_reports_zero_rather_than_a_fixed_list():
    """The bug this replaces: a hardcoded withheld list looked identical
    whether or not the redactor had done anything."""
    a = redact.audit({}, "helper_pre")
    assert a["fields_touched"] == 0
    assert a["withheld"]                          # policy is still described...
    assert a["by_field"] == {}                    # ...but nothing was touched


# ---------------------------------------------------------------------------
# crypto primitives
# ---------------------------------------------------------------------------

def test_phone_hash_is_stable_across_formatting():
    forms = ["+91 98765 43210", "+919876543210", "09876543210", "9876543210",
             "98765-43210"]
    assert len({crypto.phone_hash(f) for f in forms}) == 1
    assert crypto.phone_hash("9876543210") != crypto.phone_hash("9876543211")


def test_phone_hash_is_not_reversible_and_carries_no_digits():
    h = crypto.phone_hash(PHONE)
    assert "9876543210" not in h
    assert len(h) == 32


def test_encrypt_round_trips_and_ciphertext_hides_the_plaintext():
    tok = crypto.encrypt(NAME)
    if not crypto.is_encrypted(tok):
        pytest.skip("cryptography not installed; masking path still applies")
    assert NAME not in tok
    assert crypto.decrypt(tok) == NAME


def test_masking_helpers_are_lossy():
    assert crypto.mask_name("Anita Sharma") == "A. S."
    assert crypto.mask_phone(PHONE) == "********10"
    assert crypto.mask_uid("7X2K") == "7X••"
    assert crypto.mask_point(EXACT_LAT, EXACT_LON) == [77.41, 23.26]


def test_mask_point_returns_lng_lat_in_that_order():
    """The number one hackathon geospatial bug (agents.md 4)."""
    pt = crypto.mask_point(23.26, 77.41)
    assert pt[0] > pt[1]          # Bhopal: longitude 77 > latitude 23


# ---------------------------------------------------------------------------
# Policy table integrity
# ---------------------------------------------------------------------------

def test_every_audience_has_a_grant_for_every_field():
    for aud in policy.AUDIENCES:
        for field in policy.FIELDS:
            assert policy.grant(aud, field) in (
                policy.FULL, policy.MASKED, policy.OWN, policy.HIDDEN), (aud, field)


def test_every_field_has_at_least_one_path():
    for field in policy.FIELDS:
        assert policy.PATHS.get(field), f"{field} is in the matrix but redacts nothing"


def test_an_unknown_audience_falls_back_to_the_strictest_policy():
    """A typo in an audience name must fail closed."""
    ev = _committed_event()
    out = redact.project_event(ev, "helper_pr")     # typo
    assert out is None or "23.25991" not in _blob(out)
