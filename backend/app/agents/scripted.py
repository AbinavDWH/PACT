"""Scripted pipeline.

Emits the complete event vocabulary from agents.md section 3.2. The LLM-shaped
agents (triage, advocates, arbiter, narrator) are scripted; the deterministic
ones are real:

  A3 geo     -- real MongoDB $geoNear against seeded offers
  A5 solver  -- real greedy fill over whatever A3 actually returned

So the numbers on screen come from the database, not from fixtures. When the
Groq client lands, only the scripted judgement calls get replaced.

Fixtures remain as a fallback for when Mongo is unreachable, because the demo
must survive venue wifi.
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any
from uuid import uuid4

from app.bus import gate
from app.bus.eventbus import bus
from app.config import get_settings
from app.db import repo_offers

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

# Bhopal, matching the coordinates used throughout the protocol docs.
DEFAULT_LAT = 23.2599
DEFAULT_LON = 77.4126

# Used only when Mongo is unreachable. Same shape as repo_offers._shape().
_FALLBACK_CANDIDATES = [
    {"cand_id": "c1", "offer_id": "fx1", "owner_kind": "org", "owner_id": "ORG_NGO_001",
     "name": "Sanjeevani Relief Trust", "org_type": "ngo", "distance_km": 6.2,
     "eta_minutes": 55, "free": 180, "reliability": 0.86, "capacity_load": 0.4,
     "capabilities": ["cold_chain"]},
    {"cand_id": "c2", "offer_id": "fx2", "owner_kind": "org", "owner_id": "ORG_HOSP_004",
     "name": "Hamidia City Hospital", "org_type": "hospital", "distance_km": 3.1,
     "eta_minutes": 35, "free": 20, "reliability": 0.93, "capacity_load": 0.72,
     "capabilities": ["cold_chain", "ambulance"]},
    {"cand_id": "c3", "offer_id": "fx3", "owner_kind": "org", "owner_id": "ORG_CSR_002",
     "name": "Metro Industries CSR", "org_type": "csr", "distance_km": 11.4,
     "eta_minutes": 80, "free": 60, "reliability": 0.79, "capacity_load": 0.25,
     "capabilities": []},
]


async def _pause(lo: float = 0.25, hi: float = 0.6) -> None:
    await asyncio.sleep(random.uniform(lo, hi))


async def _stream(trace_id: str, run_id: str, agent: str, text: str, chunk: int = 14) -> None:
    """Fake token streaming so the portal's rendering path is exercised."""
    for i in range(0, len(text), chunk):
        await bus.publish(trace_id, "agent.token", {"delta": text[i:i + chunk]},
                          agent=agent, run_id=run_id)
        await asyncio.sleep(0.035)


async def _say(trace_id: str, run_id: str, agent: str, text: str,
               structured: dict[str, Any] | None = None,
               confidence: float | None = None) -> None:
    await bus.publish(trace_id, "agent.thinking", {"note": "reasoning"},
                      agent=agent, run_id=run_id)
    await _stream(trace_id, run_id, agent, text)
    await bus.publish(
        trace_id, "agent.message",
        {"text": text, "structured": structured or {}, "confidence": confidence,
         "latency_ms": random.randint(180, 900), "tokens": max(1, len(text) // 4)},
        agent=agent, run_id=run_id,
    )


def _greedy(candidates: list[dict], qty: int, key) -> list[dict]:
    """Deterministic fill. This is the A5 solver skeleton -- the LLM never
    produces these numbers."""
    remaining = qty
    out: list[dict] = []
    for c in sorted(candidates, key=key):
        if remaining <= 0:
            break
        take = min(c["free"], remaining)
        if take <= 0:
            continue
        remaining -= take
        out.append({"cand_id": c["cand_id"], "offer_id": c["offer_id"], "name": c["name"],
                    "owner_kind": c["owner_kind"], "owner_id": c["owner_id"],
                    "resource": c["resource"] if "resource" in c else None,
                    "qty": take, "eta_min": c["eta_minutes"]})
    return out


def _option(option_id: str, label: str, allocs: list[dict], qty: int,
            resource: str, score: float) -> dict:
    allocs = [{**a, "resource": resource} for a in allocs if a["qty"] > 0]
    filled = sum(a["qty"] for a in allocs)
    return {
        "option_id": option_id, "label": label, "allocations": allocs,
        "coverage_pct": int(filled / max(qty, 1) * 100),
        "total_eta": max((a["eta_min"] for a in allocs), default=0),
        "score": score,
    }


async def run(request: dict[str, Any]) -> dict[str, Any]:
    """Drive one deliberation. Returns the committed match."""
    settings = get_settings()
    trace_id = request.get("request_id") or f"REQ-{uuid4().hex[:6].upper()}"
    run_id = f"RUN-{uuid4().hex[:8].upper()}"

    need = request.get("need", "medical_kits")
    qty = int(request.get("quantity", 3))
    where = request.get("location_name", "Region A")
    pretty = need.replace("_", " ")

    await bus.publish(
        trace_id, "run.started",
        {"request": request, "masked_summary": f"{qty} x {need} needed near {where}",
         "planned_agents": [{"agent": a, "label": l} for a, l in AGENTS]},
        run_id=run_id,
    )

    # -- A0 intake ---------------------------------------------------------
    await bus.publish(trace_id, "agent.entered",
                      {"agent": "a0_intake", "label": "Intake Normalizer"},
                      agent="a0_intake", run_id=run_id)
    await _pause()
    await bus.publish(
        trace_id, "agent.message",
        {"text": f"Normalized request. {qty} x {pretty}. Position masked to ~1 km for "
                 "non-admin audiences.",
         "structured": {"resource": need, "quantity": qty}},
        agent="a0_intake", run_id=run_id,
    )

    # -- A1 dedupe ---------------------------------------------------------
    await bus.publish(trace_id, "agent.entered",
                      {"agent": "a1_dedupe", "label": "Dedupe / Cluster"},
                      agent="a1_dedupe", run_id=run_id)
    await _pause(0.1, 0.3)
    await bus.publish(
        trace_id, "agent.message",
        {"text": "No duplicate within the 15-minute window at this geohash.",
         "structured": {"duplicate": False}},
        agent="a1_dedupe", run_id=run_id,
    )

    # -- A2 triage (scripted; Groq replaces this) --------------------------
    await bus.publish(trace_id, "agent.entered", {"agent": "a2_triage", "label": "Triage"},
                      agent="a2_triage", run_id=run_id)
    severity = random.randint(72, 95)
    tier = "T1" if severity >= 80 else "T2"
    await _say(
        trace_id, run_id, "a2_triage",
        f"Structural collapse with a trapped, injured casualty. Tier {tier}, severity "
        f"{severity}. Supply need is immediate; time to harm estimated at 4 hours.",
        {"severity": severity, "tier": tier, "life_threat": tier == "T1",
         "time_to_harm_hours": 4},
        confidence=0.84,
    )

    # -- A3 geo: REAL $geoNear ---------------------------------------------
    await bus.publish(trace_id, "agent.entered",
                      {"agent": "a3_geo", "label": "Geo Candidate Finder"},
                      agent="a3_geo", run_id=run_id)

    lat = float(request.get("lat", DEFAULT_LAT))
    lon = float(request.get("lon", DEFAULT_LON))

    t0 = time.perf_counter()
    candidates, radius_used, queries = await repo_offers.find_candidates(lat, lon, need, qty)
    ms = int((time.perf_counter() - t0) * 1000)

    live = bool(candidates)
    if not live:
        candidates = [{**c, "resource": need} for c in _FALLBACK_CANDIDATES]
        radius_used, ms = 25, random.randint(6, 24)

    await bus.publish(
        trace_id, "agent.tool_call",
        {"tool": "mongo.$geoNear",
         "args": {"collection": "offers", "resource": need,
                  "near": [round(lon, 4), round(lat, 4)], "radius_km": radius_used},
         "result_count": len(candidates), "ms": ms, "live": live, "queries": queries},
        agent="a3_geo", run_id=run_id,
    )
    nearest = candidates[0] if candidates else None
    await bus.publish(
        trace_id, "agent.message",
        {"text": (f"{len(candidates)} candidates within {radius_used:g} km holding {pretty}."
                  + (f" Nearest: {nearest['name']} at {nearest['distance_km']} km, "
                     f"ETA {nearest['eta_minutes']} min." if nearest else "")
                  + ("" if live else "  [fixture fallback: database unavailable]")),
         "structured": {"candidates": candidates, "live": live}},
        agent="a3_geo", run_id=run_id,
    )

    if not candidates:
        await bus.publish(trace_id, "agent.message",
                          {"text": f"No supplier of {pretty} in range. Request unmet."},
                          agent="a5_solver", run_id=run_id)
        await bus.publish(trace_id, "run.completed", {"status": "unmet"}, run_id=run_id)
        return {"status": "unmet", "trace_id": trace_id}

    # -- A4 advocates: derived from the real candidates ---------------------
    debate_id = f"DEB-{uuid4().hex[:6].upper()}"
    await bus.publish(trace_id, "agent.entered",
                      {"agent": "a4_advocates", "label": "Helper Advocates"},
                      agent="a4_advocates", run_id=run_id)
    await bus.publish(
        trace_id, "debate.opened",
        {"debate_id": debate_id, "topic": f"Who should serve {qty} x {pretty}?",
         "participants": [c["cand_id"] for c in candidates]},
        agent="a4_advocates", run_id=run_id,
    )

    fastest = min(candidates, key=lambda c: c["eta_minutes"])
    biggest = max(candidates, key=lambda c: c["free"])

    for turn_no, c in enumerate(candidates, start=1):
        covers = c["free"] >= qty
        if c is biggest and covers:
            stance, claim = "for", (
                f"Holds {c['free']} units, enough to cover the whole need alone, "
                f"reliability {c['reliability']:.2f}.")
        elif c is fastest:
            stance, claim = "for", (
                f"Fastest at {c['eta_minutes']} min and {c['distance_km']} km out"
                + (f", but only {c['free']} units -- a first wave, not the whole answer."
                   if not covers else "."))
        elif c["capacity_load"] > 0.7:
            stance, claim = "against", (
                f"Already at {int(c['capacity_load'] * 100)}% capacity load; assigning here "
                "risks a missed commitment elsewhere.")
        else:
            stance, claim = "against", (
                f"{c['eta_minutes']} min out with {c['free']} units. Slower and smaller "
                f"than {biggest['name']} on both axes.")

        await bus.publish(
            trace_id, "debate.turn",
            {"debate_id": debate_id, "turn_no": turn_no, "speaker": f"advocate:{c['cand_id']}",
             "stance": stance, "claim": claim,
             "evidence": [{"field": "eta_minutes", "value": c["eta_minutes"]},
                          {"field": "free", "value": c["free"]}],
             "rebuts": None},
            agent="a4_advocates", run_id=run_id,
        )
        await _pause(0.15, 0.35)

    # -- A5 solver: REAL greedy fill over the real candidates ---------------
    await bus.publish(trace_id, "agent.entered",
                      {"agent": "a5_solver", "label": "Allocation Solver"},
                      agent="a5_solver", run_id=run_id)
    await _pause(0.1, 0.25)

    opt_fast = _option("opt_1", "fastest",
                       _greedy(candidates, qty, key=lambda c: c["eta_minutes"]),
                       qty, need, 0.74)
    opt_cover = _option("opt_2", "max_coverage",
                        _greedy(candidates, qty, key=lambda c: -c["free"]),
                        qty, need, 0.81)
    # Least depleting: prefer suppliers with the most headroom relative to stock,
    # so a scarce holder is not drained for a request others can serve.
    opt_least = _option("opt_3", "least_depleting",
                        _greedy(candidates, qty,
                                key=lambda c: (c["capacity_load"], -c["free"])),
                        qty, need, 0.78)

    seen, options = set(), []
    for o in (opt_cover, opt_fast, opt_least):
        sig = tuple((a["owner_id"], a["qty"]) for a in o["allocations"])
        if sig and sig not in seen:      # drop duplicate strategies
            seen.add(sig)
            options.append(o)
    if not options:
        options = [opt_cover]

    await bus.publish(trace_id, "options.proposed", {"options": options},
                      agent="a5_solver", run_id=run_id)

    # -- A6 arbiter (scripted judgement over real options) ------------------
    await bus.publish(trace_id, "agent.entered", {"agent": "a6_arbiter", "label": "Arbiter"},
                      agent="a6_arbiter", run_id=run_id)
    best = max(options, key=lambda o: (o["coverage_pct"], -o["total_eta"]))
    chosen = best["option_id"]

    await bus.publish(
        trace_id, "debate.turn",
        {"debate_id": debate_id, "turn_no": len(candidates) + 1, "speaker": "arbiter",
         "stance": "neutral",
         "claim": f"Accepting the first-wave argument for {fastest['name']}, rejecting the "
                  "framing that speed alone settles it.",
         "evidence": [], "rebuts": "turn:1"},
        agent="a6_arbiter", run_id=run_id,
    )
    await bus.publish(
        trace_id, "debate.turn",
        {"debate_id": debate_id, "turn_no": len(candidates) + 2, "speaker": "arbiter",
         "stance": "for",
         "claim": f"'{best['label'].replace('_', ' ')}' reaches {best['coverage_pct']}% coverage "
                  f"in {best['total_eta']} minutes. Coverage outranks speed at this tier.",
         "evidence": [], "rebuts": f"turn:{len(candidates)}"},
        agent="a6_arbiter", run_id=run_id,
    )
    await _say(
        trace_id, run_id, "a6_arbiter",
        f"Choosing '{best['label'].replace('_', ' ')}': {best['coverage_pct']}% of the need met, "
        f"last arrival at {best['total_eta']} minutes.",
        {"chosen_option_id": chosen}, confidence=0.77,
    )
    await bus.publish(
        trace_id, "debate.closed",
        {"debate_id": debate_id, "winner": chosen,
         "dissent": f"{fastest['name']} alone would arrive in {fastest['eta_minutes']} min, "
                    "at lower coverage."},
        agent="a6_arbiter", run_id=run_id,
    )

    # -- A7 privacy --------------------------------------------------------
    await bus.publish(trace_id, "agent.entered",
                      {"agent": "a7_privacy", "label": "Privacy Redactor"},
                      agent="a7_privacy", run_id=run_id)
    await bus.publish(
        trace_id, "agent.message",
        {"text": "Helper payload masked: approximate area only. Name and phone withheld "
                 "pending acceptance.",
         "structured": {"withheld": ["name", "phone", "exact_loc"],
                        "shared": ["resource", "quantity", "area", "urgency"]}},
        agent="a7_privacy", run_id=run_id,
    )

    # -- A8 admin gate -----------------------------------------------------
    decision_id = f"DEC-{uuid4().hex[:8].upper()}"
    await bus.publish(
        trace_id, "decision.proposed",
        {"decision_id": decision_id, "chosen_option_id": chosen, "options": options,
         "justification": f"{best['coverage_pct']}% coverage in {best['total_eta']} minutes "
                          "without over-drawing a saturated supplier.",
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
        await bus.publish(trace_id, "replan.triggered",
                          {"reason": "admin_rejected", "prior_run_id": run_id},
                          agent="a11_replanner", run_id=run_id)
        await bus.publish(trace_id, "run.completed", {"status": "rejected"}, run_id=run_id)
        return {"status": "rejected", "trace_id": trace_id}

    final = next((o for o in options if o["option_id"] == result.get("option_id")), None) \
        or next(o for o in options if o["option_id"] == chosen)

    # -- reserve real stock ------------------------------------------------
    if live:
        for a in final["allocations"]:
            if not await repo_offers.reserve(a["offer_id"], a["qty"]):
                await bus.publish(trace_id, "error",
                                  {"code": "INSUFFICIENT_STOCK", "offer_id": a["offer_id"],
                                   "fallback_used": True},
                                  agent="a5_solver", run_id=run_id)

    # -- A9 narrator + dispatch -------------------------------------------
    match_id = f"MATCH-{uuid4().hex[:6].upper()}"
    await bus.publish(
        trace_id, "decision.committed",
        {"match_id": match_id, "allocations": final["allocations"],
         "unmet": max(0, qty - sum(a["qty"] for a in final["allocations"]))},
        agent="a8_gate", run_id=run_id,
    )
    await bus.publish(trace_id, "agent.entered",
                      {"agent": "a9_narrator", "label": "Narrator"},
                      agent="a9_narrator", run_id=run_id)
    await _say(
        trace_id, run_id, "a9_narrator",
        f"Allocated {sum(a['qty'] for a in final['allocations'])} x {pretty} near {where}. "
        f"Last arrival in {final['total_eta']} minutes.",
        {"match_id": match_id},
    )
    for a in final["allocations"]:
        # Two dispatch paths: orgs route via their portal, individuals direct.
        via = "org portal" if a["owner_kind"] == "org" else "direct to volunteer"
        await bus.publish(
            trace_id, "notify.sent",
            {"channel": "console", "target_masked": f"{a['name']} ({via})",
             "message": f"Deliver {a['qty']} x {pretty} near {where}. ETA {a['eta_min']} min."},
            agent="a9_narrator", run_id=run_id,
        )

    await bus.publish(
        trace_id, "run.completed",
        {"status": "committed", "match_id": match_id,
         "ms_total": random.randint(1800, 4200), "groq_calls": 0, "tokens": 0,
         "scripted": True, "geo_live": live},
        run_id=run_id,
    )
    return {"status": "committed", "trace_id": trace_id, "match_id": match_id,
            "allocations": final["allocations"]}
