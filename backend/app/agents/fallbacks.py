"""Deterministic stand-ins for every LLM agent.

These are not placeholders. They run whenever Groq is unconfigured, slow,
rate-limited, or returns something that fails validation -- which on a free tier
at 8000 tokens/minute during a live demo is a realistic Tuesday.

They are deliberately simple and explainable: a judge asking "what happens if
the API dies" should be able to watch it happen and still see a sane allocation.
"""

from __future__ import annotations

from typing import Any

from app.llm.schemas import (AdvocatesOut, ArbiterOut, Bid, DebateTurn,
                             NarratorOut, TriageOut)


def triage(prior: int, injury_rank: int, trapped: bool,
           people: int, urgency: str) -> TriageOut:
    """Mirrors the codec's priority score, rescaled to 0-100."""
    severity = min(100, prior * 2)
    if trapped:
        severity = min(100, severity + 8)
    if injury_rank >= 3:
        severity = min(100, severity + 10)

    tier = ("T1" if severity >= 80 or (injury_rank >= 3 and trapped)
            else "T2" if severity >= 55
            else "T3" if severity >= 30
            else "T4")

    return TriageOut(
        severity=severity, tier=tier,
        life_threat=tier == "T1",
        time_to_harm_hours=4 if tier == "T1" else 24 if tier == "T2" else 72,
        confidence=0.4,
        reasoning=(f"Deterministic prior {prior}, {people} affected, "
                   f"{'trapped, ' if trapped else ''}urgency {urgency}."),
    )


def advocates(candidates: list[dict[str, Any]], demand: int) -> AdvocatesOut:
    """Ranks on the same signals the solver uses, so the argument and the
    arithmetic never contradict each other."""
    if not candidates:
        return AdvocatesOut(bids=[])

    fastest = min(candidates, key=lambda c: c["eta_minutes"])
    biggest = max(candidates, key=lambda c: c["free"])
    bids: list[Bid] = []

    for c in candidates:
        covers = c["free"] >= demand
        load = c.get("capacity_load", 0.5)
        fit = int(max(0, min(100,
            50 + (25 if covers else 0)
               + (15 if c is fastest else 0)
               + int(c.get("reliability", 0.7) * 20)
               - int(load * 30))))

        if c is biggest and covers:
            arg = (f"Holds {c['free']} units, covers the whole need alone, "
                   f"reliability {c.get('reliability', 0):.2f}.")
            share = "full"
        elif c is fastest:
            arg = (f"Fastest at {c['eta_minutes']} min, {c['distance_km']} km out"
                   + ("." if covers else f", but only {c['free']} units."))
            share = "full" if covers else "partial"
        elif load > 0.7:
            arg = f"Already at {int(load * 100)}% capacity load; assigning here risks a miss."
            share = "none"
        else:
            arg = (f"{c['eta_minutes']} min out with {c['free']} units. "
                   f"Slower and smaller than {biggest['name']}.")
            share = "partial"

        flags = []
        if load > 0.7:
            flags.append("saturated capacity")
        if not covers:
            flags.append("cannot cover alone")

        bids.append(Bid(cand_id=c["cand_id"], fit=fit, argument=arg,
                        risk_flags=flags, recommended_share=share))
    return AdvocatesOut(bids=bids)


def arbiter(options: list[dict[str, Any]]) -> ArbiterOut:
    """Coverage first, then speed -- the same ordering the prompt specifies."""
    if not options:
        return ArbiterOut(chosen_option_id="", justification="No feasible option.")

    best = max(options, key=lambda o: (o["coverage_pct"], -o["total_eta"]))
    return ArbiterOut(
        chosen_option_id=best["option_id"], confidence=0.4,
        turns=[DebateTurn(speaker="arbiter",
                          claim=(f"'{best['label'].replace('_', ' ')}' reaches "
                                 f"{best['coverage_pct']}% coverage in "
                                 f"{best['total_eta']} minutes."),
                          rebuts=None)],
        justification=(f"{best['coverage_pct']}% coverage in {best['total_eta']} "
                       "minutes. Selected without model input."),
        dissent="",
    )


def narrator(resource: str, qty: int, where: str, eta: int) -> NarratorOut:
    pretty = resource.replace("_", " ")
    return NarratorOut(
        admin_summary=f"Allocated {qty} x {pretty} near {where}, arriving within {eta} minutes.",
        helper_message=f"Deliver {qty} x {pretty} near {where}. ETA {eta} min.",
        sms_variant=f"ASSIGN {qty} {resource[:6].upper()} {where[:12]} ETA{eta}M",
    )
