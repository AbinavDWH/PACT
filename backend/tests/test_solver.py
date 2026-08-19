"""A5 scoring and admin-override validation.

The allocations were always real. The *scores* were four literals -- 0.74,
0.81, 0.78, 0.80 -- identical on every run whatever the candidates looked
like, which is precisely the failure the governing rule exists to prevent:
a constant presented as a measurement.

These tests assert the score actually *responds* to its inputs. A formula that
returns a plausible number but ignores an input is the same bug wearing a
better disguise, so every weight gets a test that moves one field and requires
the score to move with it.
"""

from __future__ import annotations

import pytest

from app.agents import fallbacks, solver
from app.agents.scripted import _enforce_triage_invariants
from app.llm.schemas import TriageOut


def cand(cid="c1", *, eta=30, free=100, reliability=0.8, load=0.2):
    return {"cand_id": cid, "offer_id": f"OFF_{cid}", "name": f"Org {cid}",
            "owner_kind": "org", "owner_id": f"ORG_{cid}", "resource": "water_kits",
            "eta_minutes": eta, "free": free, "reliability": reliability,
            "capacity_load": load, "distance_km": 5.0}


# ---------------------------------------------------------------------------
# The score responds to every input it claims to weigh
# ---------------------------------------------------------------------------

def test_a_faster_candidate_scores_higher():
    assert (solver.candidate_score(cand(eta=15), 10, fit=70)
            > solver.candidate_score(cand(eta=120), 10, fit=70))


def test_a_more_reliable_candidate_scores_higher():
    assert (solver.candidate_score(cand(reliability=0.95), 10, fit=70)
            > solver.candidate_score(cand(reliability=0.40), 10, fit=70))


def test_a_saturated_candidate_scores_lower():
    assert (solver.candidate_score(cand(load=0.1), 10, fit=70)
            > solver.candidate_score(cand(load=0.9), 10, fit=70))


def test_more_stock_headroom_scores_higher():
    assert (solver.candidate_score(cand(free=100), 50, fit=70)
            > solver.candidate_score(cand(free=10), 50, fit=70))


def test_a4_fit_moves_the_score():
    assert (solver.candidate_score(cand(), 10, fit=95)
            > solver.candidate_score(cand(), 10, fit=20))


def test_risk_flags_penalise():
    assert (solver.candidate_score(cand(), 10, fit=70, blockers=0)
            > solver.candidate_score(cand(), 10, fit=70, blockers=3))


def test_the_score_is_not_a_constant_across_realistic_candidates():
    """The exact bug this replaces: same number every time."""
    cands = [cand("c1", eta=15, free=20, reliability=0.9, load=0.1),
             cand("c2", eta=90, free=300, reliability=0.6, load=0.8),
             cand("c3", eta=45, free=80, reliability=0.75, load=0.4)]
    scores = solver.score_candidates(cands, 50, {"c1": 80, "c2": 40, "c3": 60})
    assert len(set(scores.values())) == 3


def test_scores_stay_within_zero_and_one():
    extremes = [cand(eta=0, free=10_000, reliability=1.0, load=0.0),
                cand(eta=100_000, free=0, reliability=0.0, load=1.0)]
    for c in extremes:
        for fit in (0, 100, None):
            s = solver.candidate_score(c, 50, fit=fit, blockers=9)
            assert 0.0 <= s <= 1.0


def test_a_candidate_nobody_bid_on_is_not_punished_for_the_models_silence():
    """fit=None means A4 fell back or skipped it. Scoring that as fit=0 would
    bury a perfectly good supplier because the model stayed quiet."""
    strong = cand(eta=15, free=500, reliability=0.95, load=0.05)
    assert (solver.candidate_score(strong, 10, fit=None)
            > solver.candidate_score(strong, 10, fit=0))


# ---------------------------------------------------------------------------
# Option scoring
# ---------------------------------------------------------------------------

def _alloc(cid, qty, eta):
    return {"cand_id": cid, "qty": qty, "eta_min": eta, "owner_id": f"ORG_{cid}"}


def test_full_coverage_beats_partial_coverage():
    s = {"c1": 0.7}
    assert (solver.option_score([_alloc("c1", 10, 30)], 10, s)
            > solver.option_score([_alloc("c1", 4, 30)], 10, s))


def test_a_faster_option_beats_a_slower_one_at_equal_coverage():
    s = {"c1": 0.7}
    assert (solver.option_score([_alloc("c1", 10, 20)], 10, s)
            > solver.option_score([_alloc("c1", 10, 200)], 10, s))


def test_candidate_quality_is_weighted_by_quantity_not_averaged_flat():
    """90% from a strong supplier must not score the same as the reverse."""
    s = {"strong": 0.9, "weak": 0.2}
    mostly_strong = [_alloc("strong", 9, 30), _alloc("weak", 1, 30)]
    mostly_weak = [_alloc("strong", 1, 30), _alloc("weak", 9, 30)]
    assert (solver.option_score(mostly_strong, 10, s)
            > solver.option_score(mostly_weak, 10, s))


def test_an_empty_option_scores_zero():
    assert solver.option_score([], 10, {}) == 0.0


def test_explain_components_sum_consistently_with_the_score():
    s = {"c1": 0.8}
    allocs = [_alloc("c1", 8, 40)]
    opt = {"allocations": allocs}
    e = solver.explain(opt, 10, s)
    recomputed = (solver.O_COVERAGE * e["coverage"]
                  + solver.O_CANDIDATES * e["candidate_quality"]
                  + solver.O_SPEED * e["speed"])
    assert abs(recomputed - solver.option_score(allocs, 10, s)) < 1e-3


# ---------------------------------------------------------------------------
# The arbiter fallback now means something
# ---------------------------------------------------------------------------

def test_the_fallback_arbiter_follows_the_real_score():
    """It used to pick max_coverage every time, because the literal score for
    that strategy happened to be the highest one hardcoded."""
    options = [
        {"option_id": "opt_1", "label": "fastest", "coverage_pct": 100,
         "total_eta": 20, "score": 0.91},
        {"option_id": "opt_2", "label": "max_coverage", "coverage_pct": 100,
         "total_eta": 200, "score": 0.62},
    ]
    assert fallbacks.arbiter(options).chosen_option_id == "opt_1"


def test_the_fallback_arbiter_survives_an_empty_option_set():
    """This branch used to raise: it returned "" for a field with
    min_length=1, so the one input it existed to handle crashed it."""
    out = fallbacks.arbiter([])
    assert out.chosen_option_id == fallbacks.NO_OPTION
    assert "No feasible option" in out.justification


# ---------------------------------------------------------------------------
# A2 triage invariants
# ---------------------------------------------------------------------------
# Each of these fields validates fine on its own; only the relationship
# between them is wrong, so Pydantic cannot catch it. The model returns
# tier T1 with life_threat false often enough to matter.

def test_t1_forces_life_threat_true():
    t = TriageOut(severity=90, tier="T1", life_threat=False)
    fixed = _enforce_triage_invariants(t)
    assert t.life_threat is True
    assert any(f["field"] == "life_threat" for f in fixed)


def test_life_threat_lifts_a_low_tier():
    t = TriageOut(severity=60, tier="T4", life_threat=True)
    _enforce_triage_invariants(t)
    assert t.tier == "T2"


def test_t1_caps_the_harm_horizon_at_six_hours():
    t = TriageOut(severity=90, tier="T1", life_threat=True, time_to_harm_hours=48)
    _enforce_triage_invariants(t)
    assert t.time_to_harm_hours == 6


def test_severity_is_lifted_to_its_tier_floor():
    """A T1 at severity 20 would sort below a T3 at 60 in every
    severity-ordered view."""
    t = TriageOut(severity=20, tier="T1", life_threat=True)
    _enforce_triage_invariants(t)
    assert t.severity >= 80


def test_consistent_triage_output_is_left_alone():
    t = TriageOut(severity=88, tier="T1", life_threat=True, time_to_harm_hours=4)
    assert _enforce_triage_invariants(t) == []
    assert (t.severity, t.tier, t.time_to_harm_hours) == (88, "T1", 4)


def test_corrections_are_reported_not_swallowed():
    """A silent repair would let the portal show model output the model never
    produced."""
    t = TriageOut(severity=10, tier="T1", life_threat=False, time_to_harm_hours=72)
    fixed = _enforce_triage_invariants(t)
    assert len(fixed) == 3
    for f in fixed:
        assert {"field", "was", "now", "why"} <= set(f)


# ---------------------------------------------------------------------------
# Admin override -- the solver validates before anything is pinned
# ---------------------------------------------------------------------------

CANDS = [cand("c1", free=10, eta=30), cand("c2", free=5, eta=60)]
SCORES = {"c1": 0.8, "c2": 0.5}


def test_a_feasible_override_is_pinned():
    opt, errs = solver.build_admin_option(
        [{"cand_id": "c1", "qty": 6}, {"cand_id": "c2", "qty": 4}],
        CANDS, "water_kits", 10, SCORES)
    assert errs == []
    assert opt["option_id"] == "opt_admin"
    assert opt["coverage_pct"] == 100
    assert [a["qty"] for a in opt["allocations"]] == [6, 4]
    assert 0.0 < opt["score"] <= 1.0


def test_an_override_beyond_available_stock_is_rejected():
    """The load-bearing check. An override is a human instruction, not a
    licence to write an allocation the stock cannot support."""
    opt, errs = solver.build_admin_option(
        [{"cand_id": "c2", "qty": 99}], CANDS, "water_kits", 10, SCORES)
    assert opt is None
    assert any("free" in e for e in errs)


def test_an_override_naming_an_unknown_candidate_is_rejected():
    opt, errs = solver.build_admin_option(
        [{"cand_id": "c99", "qty": 1}], CANDS, "water_kits", 10, SCORES)
    assert opt is None
    assert any("no candidate matches" in e for e in errs)


def test_an_override_exceeding_the_demand_is_rejected():
    opt, errs = solver.build_admin_option(
        [{"cand_id": "c1", "qty": 10}, {"cand_id": "c2", "qty": 5}],
        CANDS, "water_kits", 10, SCORES)
    assert opt is None
    assert any("more than" in e for e in errs)


def test_repeated_draws_on_one_candidate_are_summed_before_the_stock_check():
    """Two 6-unit lines against a 10-unit supplier must fail, even though
    neither line exceeds the stock on its own."""
    opt, errs = solver.build_admin_option(
        [{"cand_id": "c1", "qty": 6}, {"cand_id": "c1", "qty": 6}],
        CANDS, "water_kits", 20, SCORES)
    assert opt is None
    assert any("free" in e for e in errs)


@pytest.mark.parametrize("bad", [
    [{"cand_id": "c1", "qty": 0}],
    [{"cand_id": "c1", "qty": -3}],
    [{"cand_id": "c1", "qty": "lots"}],
    [],
])
def test_malformed_override_quantities_are_rejected(bad):
    opt, errs = solver.build_admin_option(bad, CANDS, "water_kits", 10, SCORES)
    assert opt is None and errs


def test_an_override_may_be_addressed_by_offer_or_owner_id():
    """The portal sends whichever identifier it has to hand."""
    for key, val in (("offer_id", "OFF_c1"), ("owner_id", "ORG_c1")):
        opt, errs = solver.build_admin_option(
            [{key: val, "qty": 3}], CANDS, "water_kits", 3, SCORES)
        assert errs == [], (key, errs)
        assert opt["allocations"][0]["cand_id"] == "c1"


def test_a_partial_override_is_allowed_and_reports_its_own_shortfall():
    """Deliberately under-allocating is a legitimate admin decision -- it must
    be recorded as partial coverage, not rejected."""
    opt, errs = solver.build_admin_option(
        [{"cand_id": "c1", "qty": 4}], CANDS, "water_kits", 10, SCORES)
    assert errs == []
    assert opt["coverage_pct"] == 40
