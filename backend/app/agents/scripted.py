"""Scripted pipeline.

Emits the complete event vocabulary from agents.md section 3.2 without calling
Groq or MongoDB. The point is to get the admin portal visibly alive before any
real agent exists, so the UI is built against the true event schema and the
real agents drop in behind it without touching the frontend.

Real agents replace these functions one at a time. Everything the portal needs
-- streaming tokens, threaded debate, three options, the admin gate -- is
exercised here.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any
from uuid import uuid4

from app.bus import gate
from app.bus.eventbus import bus
from app.config import get_settings

AGENTS = [
    ("a0_intake", "Intake Normalizer"),
    ("a1_dedupe", "Dedupe / Cluster"),
    ("a2_triage", "Triage"),
    ("a3_geo", "Geo Candidate Finder"),
    ("a4_advocates", "Helper Advocates"),
    ("a5_solver", "Allocation Solver"),
    ("a6_arbiter", "Arbiter"),
    ("a7_privacy", "Privacy Redactor"),
    ("a8_gate", "Admin Gate"),
    ("a9_narrator", "Narrator"),
]

_CANDIDATES = [
    {"cand_id": "c1", "name": "Sanjeevani NGO", "owner_kind": "org", "org_type": "ngo",
     "distance_km": 6.2, "eta_minutes": 55, "reliability": 0.86, "stock": {"medical_kits": 180}},
    {"cand_id": "c2", "name": "Metro Relief CSR", "owner_kind": "org", "org_type": "csr",
     "distance_km": 11.4, "eta_minutes": 80, "reliability": 0.79, "stock": {"medical_kits": 60}},
    {"cand_id": "c3", "name": "City Hospital", "owner_kind": "org", "org_type": "hospital",
     "distance_km": 3.1, "eta_minutes": 35, "reliability": 0.93, "stock": {"medical_kits": 20}},
    {"cand_id": "c4", "name": "R. Kumar (volunteer)", "owner_kind": "individual",
     "org_type": "volunteer", "distance_km": 1.8, "eta_minutes": 20, "reliability": 0.55,
     "stock": {"water_kits": 12}},
]


async def _pause(lo: float = 0.25, hi: float = 0.6) -> None:
    await asyncio.sleep(random.uniform(lo, hi))


async def _stream(trace_id: str, run_id: str, agent: str, text: str, chunk: int = 14) -> None:
    """Fake token streaming so the portal's rendering path is exercised."""
    for i in range(0, len(text), chunk):
        await bus.publish(
            trace_id, "agent.token", {"delta": text[i : i + chunk]}, agent=agent, run_id=run_id
        )
        await asyncio.sleep(0.035)


async def _say(
    trace_id: str,
    run_id: str,
    agent: str,
    text: str,
    structured: dict[str, Any] | None = None,
    confidence: float | None = None,
) -> None:
    await bus.publish(trace_id, "agent.thinking", {"note": "reasoning"}, agent=agent, run_id=run_id)
    await _stream(trace_id, run_id, agent, text)
    await bus.publish(
        trace_id,
        "agent.message",
        {
            "text": text,
            "structured": structured or {},
            "confidence": confidence,
            "latency_ms": random.randint(180, 900),
            "tokens": max(1, len(text) // 4),
        },
        agent=agent,
        run_id=run_id,
    )


async def run(request: dict[str, Any]) -> dict[str, Any]:
    """Drive one scripted deliberation. Returns the committed match."""
    settings = get_settings()
    trace_id = request.get("request_id") or f"REQ-{uuid4().hex[:6].upper()}"
    run_id = f"RUN-{uuid4().hex[:8].upper()}"

    need = request.get("need", "medical_kits")
    qty = int(request.get("quantity", 3))
    where = request.get("location_name", "Region A")

    await bus.publish(
        trace_id,
        "run.started",
        {
            "request": request,
            "masked_summary": f"{qty} x {need} needed near {where}",
            "planned_agents": [{"agent": a, "label": l} for a, l in AGENTS],
        },
        run_id=run_id,
    )

    # -- A0 intake ---------------------------------------------------------
    await bus.publish(trace_id, "agent.entered", {"agent": "a0_intake", "label": "Intake Normalizer"},
                      agent="a0_intake", run_id=run_id)
    await _pause()
    await bus.publish(
        trace_id, "agent.message",
        {"text": f"Normalized request. {qty} x {need}. Position masked to ~1 km for non-admin audiences.",
         "structured": {"resource": need, "quantity": qty}},
        agent="a0_intake", run_id=run_id,
    )

    # -- A1 dedupe ---------------------------------------------------------
    await bus.publish(trace_id, "agent.entered", {"agent": "a1_dedupe", "label": "Dedupe / Cluster"},
                      agent="a1_dedupe", run_id=run_id)
    await _pause(0.1, 0.3)
    await bus.publish(
        trace_id, "agent.message",
        {"text": "No duplicate within the 15-minute window at this geohash.", "structured": {"duplicate": False}},
        agent="a1_dedupe", run_id=run_id,
    )

    # -- A2 triage ---------------------------------------------------------
    await bus.publish(trace_id, "agent.entered", {"agent": "a2_triage", "label": "Triage"},
                      agent="a2_triage", run_id=run_id)
    severity = random.randint(72, 95)
    tier = "T1" if severity >= 80 else "T2"
    await _say(
        trace_id, run_id, "a2_triage",
        f"Structural collapse with a trapped, injured casualty. Tier {tier}, severity {severity}. "
        "Medical supply need is immediate; time to harm estimated at 4 hours.",
        {"severity": severity, "tier": tier, "life_threat": tier == "T1", "time_to_harm_hours": 4},
        confidence=0.84,
    )

    # -- A3 geo ------------------------------------------------------------
    await bus.publish(trace_id, "agent.entered", {"agent": "a3_geo", "label": "Geo Candidate Finder"},
                      agent="a3_geo", run_id=run_id)
    await _pause(0.15, 0.35)
    await bus.publish(
        trace_id, "agent.tool_call",
        {"tool": "mongo.$geoNear", "args": {"resource": need, "radius_km": 25, "collection": "offers"},
         "result_count": len(_CANDIDATES), "ms": random.randint(6, 24)},
        agent="a3_geo", run_id=run_id,
    )
    await bus.publish(
        trace_id, "agent.message",
        {"text": f"{len(_CANDIDATES)} candidates within 25 km holding {need}.",
         "structured": {"candidates": _CANDIDATES}},
        agent="a3_geo", run_id=run_id,
    )

    # -- A4 advocates: the discussion --------------------------------------
    debate_id = f"DEB-{uuid4().hex[:6].upper()}"
    await bus.publish(trace_id, "agent.entered", {"agent": "a4_advocates", "label": "Helper Advocates"},
                      agent="a4_advocates", run_id=run_id)
    await bus.publish(
        trace_id, "debate.opened",
        {"debate_id": debate_id, "topic": f"Who should serve {qty} x {need}?",
         "participants": [c["cand_id"] for c in _CANDIDATES]},
        agent="a4_advocates", run_id=run_id,
    )

    arguments = [
        ("c1", "for", "Largest stock by far and a strong reliability record. Can cover the whole need alone."),
        ("c3", "for", "Closest and fastest at 35 minutes, but only 20 kits. Best as a first wave, not the whole answer."),
        ("c2", "against", "80 minutes out with only 60 kits. Slower and smaller than c1 on every axis."),
        ("c4", "against", "Volunteer holds water, not medical supplies. Wrong resource for this need."),
    ]
    for turn_no, (cand, stance, claim) in enumerate(arguments, start=1):
        await bus.publish(
            trace_id, "debate.turn",
            {"debate_id": debate_id, "turn_no": turn_no, "speaker": f"advocate:{cand}",
             "stance": stance, "claim": claim,
             "evidence": [{"field": "eta_minutes",
                           "value": next(c["eta_minutes"] for c in _CANDIDATES if c["cand_id"] == cand)}],
             "rebuts": None},
            agent="a4_advocates", run_id=run_id,
        )
        await _pause(0.2, 0.45)

    # -- A5 solver: deterministic ------------------------------------------
    await bus.publish(trace_id, "agent.entered", {"agent": "a5_solver", "label": "Allocation Solver"},
                      agent="a5_solver", run_id=run_id)
    await _pause(0.1, 0.25)
    def option(option_id: str, label: str, parts, score: float):
        """Drop zero-quantity allocations -- an allocation of nothing is not an
        allocation, and rendering one makes the solver look broken."""
        allocs = [
            {"cand_id": c, "name": n, "resource": need, "qty": q, "eta_min": e}
            for c, n, q, e in parts
            if q > 0
        ]
        filled = sum(a["qty"] for a in allocs)
        return {
            "option_id": option_id, "label": label, "allocations": allocs,
            "coverage_pct": int(filled / max(qty, 1) * 100),
            "total_eta": max((a["eta_min"] for a in allocs), default=0),
            "score": score,
        }

    hosp_share = min(qty, 20)          # City Hospital holds 20
    ngo_first = min(qty, 180)          # Sanjeevani NGO holds 180
    split_hosp = min(qty, 10)          # keep the hospital's stock for walk-ins
    split_ngo = max(0, qty - split_hosp)

    options = [
        option("opt_1", "fastest", [("c3", "City Hospital", hosp_share, 35)], 0.74),
        option("opt_2", "max_coverage", [("c1", "Sanjeevani NGO", ngo_first, 55)], 0.81),
        option("opt_3", "least_depleting",
               [("c3", "City Hospital", split_hosp, 35),
                ("c1", "Sanjeevani NGO", split_ngo, 55)], 0.78),
    ]
    await bus.publish(
        trace_id, "options.proposed", {"options": options}, agent="a5_solver", run_id=run_id
    )

    # -- A6 arbiter --------------------------------------------------------
    await bus.publish(trace_id, "agent.entered", {"agent": "a6_arbiter", "label": "Arbiter"},
                      agent="a6_arbiter", run_id=run_id)
    chosen = "opt_3"
    await bus.publish(
        trace_id, "debate.turn",
        {"debate_id": debate_id, "turn_no": 5, "speaker": "arbiter", "stance": "neutral",
         "claim": "Accepting c3's first-wave argument, rejecting the framing that it must be the whole answer.",
         "evidence": [], "rebuts": "turn:2"},
        agent="a6_arbiter", run_id=run_id,
    )
    await bus.publish(
        trace_id, "debate.turn",
        {"debate_id": debate_id, "turn_no": 6, "speaker": "arbiter", "stance": "for",
         "claim": "Splitting preserves NGO stock for other open T1 requests while still meeting this one in full.",
         "evidence": [], "rebuts": "turn:1"},
        agent="a6_arbiter", run_id=run_id,
    )
    await _say(
        trace_id, run_id, "a6_arbiter",
        "Choosing the least-depleting split. Full coverage, 20 minutes slower than the fastest option, "
        "and it leaves the NGO able to serve the next critical request.",
        {"chosen_option_id": chosen}, confidence=0.77,
    )
    await bus.publish(
        trace_id, "debate.closed",
        {"debate_id": debate_id, "winner": chosen,
         "dissent": "Fastest option would reach the casualty 20 minutes sooner."},
        agent="a6_arbiter", run_id=run_id,
    )

    # -- A7 privacy --------------------------------------------------------
    await bus.publish(trace_id, "agent.entered", {"agent": "a7_privacy", "label": "Privacy Redactor"},
                      agent="a7_privacy", run_id=run_id)
    await bus.publish(
        trace_id, "agent.message",
        {"text": "Helper payload masked: approximate area only. Name and phone withheld pending acceptance.",
         "structured": {"withheld": ["name", "phone", "exact_loc"], "shared": ["resource", "quantity", "area", "urgency"]}},
        agent="a7_privacy", run_id=run_id,
    )

    # -- A8 admin gate -----------------------------------------------------
    decision_id = f"DEC-{uuid4().hex[:8].upper()}"
    await bus.publish(
        trace_id, "decision.proposed",
        {"decision_id": decision_id, "chosen_option_id": chosen, "options": options,
         "justification": "Full coverage without depleting the only large medical stock in range.",
         "expires_at": None},
        agent="a6_arbiter", run_id=run_id,
    )
    result = await gate.await_admin(
        trace_id, decision_id, run_id=run_id,
        timeout_s=settings.gate_timeout_s, autopilot=settings.autopilot,
    )
    await bus.publish(
        trace_id, "admin.action",
        {"decision_id": decision_id, "action": result.get("action"),
         "admin_id": result.get("admin_id", "admin"), "note": result.get("note"),
         "option_id": result.get("option_id"), "override": result.get("allocations")},
        agent="a8_gate", run_id=run_id,
    )

    if result.get("action") == "reject":
        await bus.publish(
            trace_id, "replan.triggered",
            {"reason": "admin_rejected", "prior_run_id": run_id}, agent="a11_replanner", run_id=run_id,
        )
        await bus.publish(trace_id, "run.completed", {"status": "rejected"}, run_id=run_id)
        return {"status": "rejected", "trace_id": trace_id}

    final_option = next(
        (o for o in options if o["option_id"] == result.get("option_id")), None
    ) or next(o for o in options if o["option_id"] == chosen)

    # -- A9 narrator + dispatch -------------------------------------------
    match_id = f"MATCH-{uuid4().hex[:6].upper()}"
    await bus.publish(
        trace_id, "decision.committed",
        {"match_id": match_id, "allocations": final_option["allocations"],
         "unmet": max(0, qty - sum(a["qty"] for a in final_option["allocations"]))},
        agent="a8_gate", run_id=run_id,
    )
    await bus.publish(trace_id, "agent.entered", {"agent": "a9_narrator", "label": "Narrator"},
                      agent="a9_narrator", run_id=run_id)
    await _say(
        trace_id, run_id, "a9_narrator",
        f"Allocated {qty} x {need} near {where}. First wave arrives in 35 minutes, remainder in 55.",
        {"match_id": match_id},
    )
    for alloc in final_option["allocations"]:
        await bus.publish(
            trace_id, "notify.sent",
            {"channel": "console", "target_masked": alloc["name"],
             "message": f"Deliver {alloc['qty']} x {need} near {where}. ETA {alloc['eta_min']} min."},
            agent="a9_narrator", run_id=run_id,
        )

    await bus.publish(
        trace_id, "run.completed",
        {"status": "committed", "match_id": match_id, "ms_total": random.randint(1800, 4200),
         "groq_calls": 0, "tokens": 0, "scripted": True},
        run_id=run_id,
    )
    return {"status": "committed", "trace_id": trace_id, "match_id": match_id,
            "allocations": final_option["allocations"]}
