"""A5 -- the allocation solver's scoring model (agents.md 2.5).

The allocations themselves were always real greedy fills. The *scores* were
not: `_option(...)` took four literals -- 0.74, 0.81, 0.78, 0.80 -- so every
run emitted the same four numbers regardless of ETA, stock, reliability or
load. A constant dressed as a computation is exactly the thing the project's
governing rule exists to rule out:

    the LLM produces labels, rankings and prose; every number written by the
    system is produced by Python

A number produced by nobody is worse than one produced by a model.

Everything here is arithmetic over fields that came from MongoDB or from A4's
fit scores. No LLM call, and no constant that pretends to be a measurement.
"""

from __future__ import annotations

from typing import Any

# --- candidate weights -----------------------------------------------------
# Positive terms sum to 0.85; penalties can subtract up to 0.35. The result is
# clamped to [0, 1]. The ordering of the weights is the policy statement:
# speed matters most, then how well A4 argued the candidate fits, then whether
# the supplier is reliable and actually holds enough.
W_SPEED = 0.30
W_FIT = 0.25
W_RELIABILITY = 0.15
W_HEADROOM = 0.15
P_LOAD = 0.20
P_BLOCKER = 0.15

# An ETA at or beyond this is scored as maximally slow. Six hours: past that,
# for a T1 request, the difference between "late" and "later" stops mattering.
ETA_CEILING_MIN = 360.0

# --- option weights --------------------------------------------------------
# Coverage dominates: an option that leaves people unserved is worse than a
# slow one. This ordering mirrors the arbiter's prompt, so the deterministic
# fallback and the model are optimising the same thing.
O_COVERAGE = 0.45
O_CANDIDATES = 0.35
O_SPEED = 0.20


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def speed_term(eta_minutes: float) -> float:
    """1.0 for instant, 0.0 at the ceiling. Linear between."""
    return _clamp(1.0 - (float(eta_minutes) / ETA_CEILING_MIN))


def headroom_term(free: float, demand: float) -> float:
    """How much of the demand this supplier could cover alone, capped at 1."""
    if demand <= 0:
        return 1.0
    return _clamp(float(free) / float(demand))


def candidate_score(cand: dict[str, Any], demand: int, *,
                    fit: int | None = None, blockers: int = 0) -> float:
    """The formula from agents.md 2.5, with every input coming from a real
    field: `eta_minutes` and `free` from $geoNear, `reliability` and
    `capacity_load` from the organization document, `fit` and `risk_flags`
    from A4.

    `fit` is None when A4 fell back or did not bid on this candidate. Rather
    than invent a value, the term is dropped and its weight is redistributed
    across the remaining evidence -- a candidate nobody argued for should not
    be penalised for the model's silence.
    """
    speed = speed_term(cand.get("eta_minutes", ETA_CEILING_MIN))
    reliability = _clamp(float(cand.get("reliability") or 0.5))
    headroom = headroom_term(cand.get("free", 0), demand)
    load = _clamp(float(cand.get("capacity_load") or 0.0))
    blocker = _clamp(blockers / 3.0)

    if fit is None:
        total_w = W_SPEED + W_RELIABILITY + W_HEADROOM
        positive = (W_SPEED * speed + W_RELIABILITY * reliability
                    + W_HEADROOM * headroom)
        # Rescale to the same 0.85 envelope the fit-bearing path uses, so the
        # two are comparable in one ranking.
        positive = positive / total_w * (W_SPEED + W_FIT + W_RELIABILITY + W_HEADROOM)
    else:
        positive = (W_SPEED * speed + W_FIT * _clamp(fit / 100.0)
                    + W_RELIABILITY * reliability + W_HEADROOM * headroom)

    return round(_clamp(positive - P_LOAD * load - P_BLOCKER * blocker), 4)


def score_candidates(candidates: list[dict[str, Any]], demand: int,
                     fit_by_id: dict[str, int] | None = None,
                     risk_by_id: dict[str, list[str]] | None = None) -> dict[str, float]:
    fit_by_id = fit_by_id or {}
    risk_by_id = risk_by_id or {}
    return {
        c["cand_id"]: candidate_score(
            c, demand,
            fit=fit_by_id.get(c["cand_id"]),
            blockers=len(risk_by_id.get(c["cand_id"], [])),
        )
        for c in candidates
    }


def option_score(allocations: list[dict[str, Any]], demand: int,
                 cand_scores: dict[str, float]) -> float:
    """Aggregate an option from the allocations it actually contains.

    The candidate term is weighted by quantity, not a flat mean: an option
    that draws 90% of its units from a strong supplier and 10% from a weak one
    should not score the same as the reverse.
    """
    if not allocations:
        return 0.0

    filled = sum(a.get("qty", 0) for a in allocations)
    coverage = _clamp(filled / demand) if demand > 0 else 1.0
    total_eta = max((a.get("eta_min", 0) for a in allocations), default=0)

    weight = sum(a.get("qty", 0) for a in allocations) or 1
    weighted = sum(cand_scores.get(a.get("cand_id", ""), 0.5) * a.get("qty", 0)
                   for a in allocations) / weight

    return round(_clamp(O_COVERAGE * coverage
                        + O_CANDIDATES * weighted
                        + O_SPEED * speed_term(total_eta)), 4)


def explain(option: dict[str, Any], demand: int,
            cand_scores: dict[str, float]) -> dict[str, Any]:
    """The score's own components, so the portal can show why an option ranked
    where it did rather than asking anyone to trust a single float."""
    allocations = option.get("allocations", [])
    filled = sum(a.get("qty", 0) for a in allocations)
    total_eta = max((a.get("eta_min", 0) for a in allocations), default=0)
    weight = sum(a.get("qty", 0) for a in allocations) or 1
    weighted = sum(cand_scores.get(a.get("cand_id", ""), 0.5) * a.get("qty", 0)
                   for a in allocations) / weight
    return {
        "coverage": round(_clamp(filled / demand) if demand > 0 else 1.0, 4),
        "candidate_quality": round(weighted, 4),
        "speed": round(speed_term(total_eta), 4),
        "weights": {"coverage": O_COVERAGE, "candidates": O_CANDIDATES,
                    "speed": O_SPEED},
    }


# ---------------------------------------------------------------------------
# Admin override (A8 -> re-enter at A5)
# ---------------------------------------------------------------------------

def build_admin_option(raw: list[dict[str, Any]], candidates: list[dict[str, Any]],
                       resource: str, demand: int,
                       cand_scores: dict[str, float]) -> tuple[dict[str, Any] | None,
                                                               list[str]]:
    """Turn an admin's hand-edited allocations into a real, feasible option.

    agents.md 2.8: override re-enters at A5 with the admin's allocations
    pinned, and *the solver validates feasibility before committing*. That
    validation is the whole point -- an override is a human instruction, not a
    licence to write an allocation the stock cannot support.

    Returns (option, errors). A non-empty error list means nothing is pinned
    and the caller falls back to the arbiter's choice.
    """
    if not raw:
        return None, ["no allocations supplied"]

    by_id = {c["cand_id"]: c for c in candidates}
    by_offer = {c["offer_id"]: c for c in candidates}
    by_owner = {c["owner_id"]: c for c in candidates}

    errors: list[str] = []
    allocations: list[dict[str, Any]] = []
    taken: dict[str, int] = {}

    for i, a in enumerate(raw):
        cand = (by_id.get(a.get("cand_id"))
                or by_offer.get(a.get("offer_id"))
                or by_owner.get(a.get("owner_id")))
        if cand is None:
            errors.append(f"[{i}] no candidate matches "
                          f"{a.get('cand_id') or a.get('offer_id') or a.get('owner_id')!r}")
            continue

        try:
            qty = int(a.get("qty", 0))
        except (TypeError, ValueError):
            errors.append(f"[{i}] quantity is not a number: {a.get('qty')!r}")
            continue
        if qty <= 0:
            errors.append(f"[{i}] quantity must be positive, got {qty}")
            continue

        taken[cand["cand_id"]] = taken.get(cand["cand_id"], 0) + qty
        if taken[cand["cand_id"]] > cand["free"]:
            errors.append(f"[{i}] {cand['name']} has {cand['free']} free, "
                          f"override asks for {taken[cand['cand_id']]}")
            continue

        allocations.append({
            "cand_id": cand["cand_id"], "offer_id": cand["offer_id"],
            "name": cand["name"], "owner_kind": cand["owner_kind"],
            "owner_id": cand["owner_id"], "resource": resource,
            "qty": qty, "eta_min": cand["eta_minutes"],
        })

    over = sum(a["qty"] for a in allocations) - demand
    if over > 0:
        errors.append(f"override allocates {over} more than the {demand} needed")

    if errors:
        return None, errors

    filled = sum(a["qty"] for a in allocations)
    return {
        "option_id": "opt_admin",
        "label": "admin_override",
        "allocations": allocations,
        "coverage_pct": int(filled / max(demand, 1) * 100),
        "total_eta": max((a["eta_min"] for a in allocations), default=0),
        "score": option_score(allocations, demand, cand_scores),
        "source": "admin",
    }, []
