"""Deterministic fallbacks.

These exist so a Groq outage, a malformed response, or a rate-limit shed
degrades the run instead of killing it. STATUS.md claimed that was verified.
For A4 it was not: `AdvocatesOut._normalise`, written to handle the three JSON
shapes gpt-oss returns, dropped every element that was not a `dict` -- and the
fallback returns real `Bid` objects. The list emptied, `min_length=1` raised,
and the exception escaped `call_json` and took the whole pipeline down.

So each test here constructs the fallback exactly as `scripted.py` does and
asserts it is *usable*, not merely that it returns. Asserting "it did not
throw" would have passed against the broken version, because the throw
happened inside Pydantic during construction.
"""

from __future__ import annotations

import pytest

from app.agents import fallbacks
from app.llm.schemas import AdvocatesOut, Bid


def candidates(n: int = 3) -> list[dict]:
    return [
        {"cand_id": f"c{i}", "offer_id": f"OFF_{i}", "name": f"Org {i}",
         "owner_kind": "org", "owner_id": f"ORG_{i}", "org_type": "ngo",
         "resource": "water_kits", "distance_km": 2.0 + i, "eta_minutes": 20 + i * 10,
         "free": 50 * (i + 1), "reliability": 0.8, "capacity_load": 0.2 * i,
         "capabilities": []}
        for i in range(1, n + 1)
    ]


# ---------------------------------------------------------------------------
# A4 advocates -- the one that was broken
# ---------------------------------------------------------------------------

def test_the_advocates_fallback_produces_usable_bids():
    """The regression. This raised ValidationError before the fix."""
    out = fallbacks.advocates(candidates(3), demand=10)
    assert isinstance(out, AdvocatesOut)
    assert len(out.bids) == 3
    assert all(isinstance(b, Bid) for b in out.bids)


def test_advocates_fallback_bids_carry_real_values():
    """Not just present -- populated. A bid with an empty argument and a
    zero fit would satisfy min_length while telling the solver nothing."""
    out = fallbacks.advocates(candidates(3), demand=10)
    for b in out.bids:
        assert b.cand_id
        assert 0 <= b.fit <= 100
        assert b.argument.strip(), "an advocate with nothing to say is not a bid"
        assert b.recommended_share in ("full", "partial", "none")


def test_advocates_fallback_covers_every_candidate_exactly_once():
    ids = [b.cand_id for b in fallbacks.advocates(candidates(5), demand=10).bids]
    assert sorted(ids) == [f"c{i}" for i in range(1, 6)]


@pytest.mark.parametrize("n", [1, 2, 8])
def test_advocates_fallback_works_for_any_candidate_count(n):
    assert len(fallbacks.advocates(candidates(n), demand=25).bids) == n


def test_constructing_advocates_from_bid_objects_survives_normalisation():
    """The exact mechanism of the bug, isolated: the normaliser must not
    discard already-constructed models."""
    built = AdvocatesOut(bids=[
        Bid(cand_id="c1", fit=70, argument="close and stocked",
            risk_flags=[], recommended_share="full"),
    ])
    assert len(built.bids) == 1
    assert built.bids[0].cand_id == "c1"


def test_the_normaliser_still_accepts_the_model_json_shapes():
    """The behaviour it was written for must keep working: gpt-oss returns
    {"bids": [...]}, a bare [...], or {"c1": {...}}, and `fit_score` for `fit`
    (STATUS.md §9.5)."""
    a = AdvocatesOut.model_validate({"bids": [{"cand_id": "c1", "fit": 60}]})
    b = AdvocatesOut.model_validate([{"cand_id": "c1", "fit": 60}])
    c = AdvocatesOut.model_validate({"c1": {"fit_score": 60}})
    for out in (a, b, c):
        assert len(out.bids) == 1
        assert out.bids[0].fit == 60


def test_an_empty_candidate_list_is_still_rejected():
    """min_length=1 is load-bearing (STATUS.md §9.4): a wrong-shaped model
    response with zero bids must not validate as success. The fix must not
    have weakened that."""
    with pytest.raises(Exception):
        AdvocatesOut.model_validate({"bids": []})


# ---------------------------------------------------------------------------
# The other three, constructed the way scripted.py constructs them
# ---------------------------------------------------------------------------

def test_the_triage_fallback_is_usable():
    t = fallbacks.triage(prior=47, injury_rank=3, trapped=True, people=3,
                         urgency="critical")
    assert t.tier in ("T1", "T2", "T3", "T4")
    assert 0 <= t.severity <= 100
    assert t.reasoning.strip()


def test_the_arbiter_fallback_is_usable():
    options = [
        {"option_id": "opt_1", "label": "fastest", "coverage_pct": 80,
         "total_eta": 30, "score": 0.7, "allocations": []},
        {"option_id": "opt_2", "label": "max_coverage", "coverage_pct": 100,
         "total_eta": 60, "score": 0.9, "allocations": []},
    ]
    a = fallbacks.arbiter(options)
    assert a.chosen_option_id in ("opt_1", "opt_2")
    assert a.justification.strip()


def test_the_narrator_fallback_is_usable():
    n = fallbacks.narrator("water_kits", 3, "Region A", 45)
    assert n.admin_summary.strip()
    assert n.helper_message.strip()
    assert n.sms_variant.strip()
    assert len(n.sms_variant) <= 110
    assert all(ord(ch) < 128 for ch in n.sms_variant), "sms_variant must be ASCII"


def test_every_fallback_constructs_without_a_network_or_a_key():
    """The whole point: these run when Groq is unreachable. None of them may
    touch the client, and all four must be constructible in one pass."""
    assert fallbacks.triage(25, 1, False, 2, "high")
    assert fallbacks.advocates(candidates(2), 5)
    assert fallbacks.arbiter([{"option_id": "o", "label": "l", "coverage_pct": 50,
                               "total_eta": 10, "score": 0.5, "allocations": []}])
    assert fallbacks.narrator("food_kits", 1, "here", 10)
