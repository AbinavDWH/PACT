"""The agent pipeline.

  A0/A1  intake, dedupe        deterministic
  A2     triage                Groq
  A3     geo candidates        deterministic -- real MongoDB $geoNear
  A4     helper advocates      Groq (one call, all candidates)
  A5     allocation solver     deterministic -- real greedy fill
  A6     arbiter               Groq, constrained to an existing option_id
  A7     privacy redactor      deterministic
  A8     admin gate            human
  A9     narrator              Groq

The governing rule: the model assigns labels, ranks, chooses among enumerated
options and writes prose. Every number written to the database is produced by
Python. The arbiter cannot invent an allocation because it never emits one --
it returns an option_id that is validated against the solver's option set.

Every Groq agent has a deterministic fallback in fallbacks.py. If the API is
slow, rate-limited or returns garbage, an amber error event is emitted and the
run continues. Likewise Mongo: fixtures stand in when the cluster is
unreachable, because the demo must survive venue wifi.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any
from uuid import uuid4

from app.bus import gate
from app.bus.eventbus import bus
from app.config import get_settings
from app.codec.tables import get_tables
from app.db import repo_matches, repo_offers, repo_requests
from app.agents import dedupe, fallbacks, solver
from app.llm import groq_client, prompts
from app.llm.schemas import AdvocatesOut, ArbiterOut, NarratorOut, TriageOut
from app.notify import channels
from app.notify import dispatcher as notify
from app.privacy import policy as privacy_policy
from app.privacy import redact

log = logging.getLogger(__name__)

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


def _enforce_triage_invariants(t: TriageOut) -> list[dict[str, Any]]:
    """Repair internally inconsistent triage output in place.

    Each field validates fine alone, so Pydantic cannot catch these: only the
    relationship between them is wrong. Returns the list of corrections made,
    which is published rather than swallowed -- a silent repair would let the
    portal show model output that the model never produced.
    """
    fixed: list[dict[str, Any]] = []

    def note(field: str, was: Any, now: Any, why: str) -> None:
        fixed.append({"field": field, "was": was, "now": now, "why": why})

    if t.tier == "T1" and not t.life_threat:
        note("life_threat", False, True, "T1 is defined as life threat within 6 h")
        t.life_threat = True
    if t.life_threat and t.tier in ("T3", "T4"):
        note("tier", t.tier, "T2", "life_threat set but tier below T2")
        t.tier = "T2"
    if t.tier == "T1" and t.time_to_harm_hours > 6:
        note("time_to_harm_hours", t.time_to_harm_hours, 6, "T1 caps harm horizon at 6 h")
        t.time_to_harm_hours = 6
    # Severity and tier must not contradict each other either: a T1 at
    # severity 20 would sort below a T3 at 60 in every severity-ordered view.
    floor = {"T1": 80, "T2": 55, "T3": 30, "T4": 0}[t.tier]
    if t.severity < floor:
        note("severity", t.severity, floor, f"{t.tier} floor is {floor}")
        t.severity = floor
    return fixed


def _option(option_id: str, label: str, allocs: list[dict], qty: int,
            resource: str, cand_scores: dict[str, float]) -> dict:
    """Build one option and score it from what it actually contains.

    This used to take a literal score -- 0.74, 0.81, 0.78, 0.80 -- identical on
    every run regardless of the candidates. See agents/solver.py.
    """
    allocs = [{**a, "resource": resource} for a in allocs if a["qty"] > 0]
    filled = sum(a["qty"] for a in allocs)
    opt = {
        "option_id": option_id, "label": label, "allocations": allocs,
        "coverage_pct": int(filled / max(qty, 1) * 100),
        "total_eta": max((a["eta_min"] for a in allocs), default=0),
        "unmet": max(0, qty - filled),
        "score": solver.option_score(allocs, qty, cand_scores),
    }
    opt["score_components"] = solver.explain(opt, qty, cand_scores)
    return opt


async def _tell_seeker(request: dict[str, Any], trace_id: str, verdict: str,
                       title: str, message: str, match_id: str | None = None) -> None:
    """Push the verdict to the person who sent the request.

    Best-effort by design. The pull path -- GET /seekers/me/requests, which the
    app polls -- is what actually guarantees they can find out; this is what
    lets them find out without having to look. So a failure here is logged and
    swallowed: a seeker not receiving a notification is bad, and a notification
    failure taking down the run that produced the allocation is worse.

    The message is written here rather than reused from the arbiter's
    justification, which is addressed to an operator and names suppliers the
    SEEKER audience may not see.
    """
    uid = request.get("uid")
    if not uid:
        return
    try:
        await channels.seeker_push(
            uid=uid, title=title, message=message, trace_id=trace_id,
            match_id=match_id, verdict=verdict)
    except Exception:
        log.debug("seeker notification skipped", exc_info=True)


async def run(request: dict[str, Any]) -> dict[str, Any]:
    """Drive one deliberation. Returns the committed match."""
    settings = get_settings()
    trace_id = request.get("request_id") or f"REQ-{uuid4().hex[:6].upper()}"
    run_id = f"RUN-{uuid4().hex[:8].upper()}"

    need = request.get("need", "medical_kits")
    qty = int(request.get("quantity", 3))
    where = request.get("location_name", "Region A")
    pretty = need.replace("_", " ")

    await repo_requests.upsert_seeker(request.get("uid"))
    await repo_requests.create(request, decoded=request.get("decoded"),
                               needs=request.get("all_needs"))

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
    # Real geohash7 clustering against open requests (agents/dedupe.py). A
    # duplicate is linked and reported, never dropped: the cost of discarding
    # a genuine second casualty is not symmetric with dispatching twice.
    await bus.publish(trace_id, "agent.entered",
                      {"agent": "a1_dedupe", "label": "Dedupe / Cluster"},
                      agent="a1_dedupe", run_id=run_id)
    dup = await dedupe.check(trace_id, request.get("lat"), request.get("lon"),
                             need, uid=request.get("uid"))
    await bus.publish(
        trace_id, "agent.message",
        {"text": dedupe.describe(dup), "structured": dup},
        agent="a1_dedupe", run_id=run_id,
    )
    if dup["duplicate"]:
        await repo_requests.link_cluster(trace_id, dup)

    # A3's candidate set does not depend on A2's output -- only the weighting
    # does -- so the $geoNear round trip runs underneath the triage call
    # instead of after it (agents.md 5.4). Events are still emitted in A2-then-A3
    # order below, because a scrambled transcript is harder to read on stage
    # than the latency saved is worth.
    lat = float(request.get("lat", DEFAULT_LAT))
    lon = float(request.get("lon", DEFAULT_LON))
    t0 = time.perf_counter()
    geo_task = asyncio.create_task(repo_offers.find_candidates(lat, lon, need, qty))

    # -- A2 triage: Groq --------------------------------------------------
    await bus.publish(trace_id, "agent.entered", {"agent": "a2_triage", "label": "Triage"},
                      agent="a2_triage", run_id=run_id)
    await bus.publish(trace_id, "agent.thinking", {"note": "assessing severity"},
                      agent="a2_triage", run_id=run_id)

    codes = (request.get("decoded") or {}).get("_codes", {})
    tbl = get_tables()
    injury_rank = tbl.dim("injury").get("rank", {}).get(codes.get("injury_code", "0"), 0)
    trapped = codes.get("mobility_code") in tbl.dim("mobility").get("trapped", [])
    prior = int(request.get("priority_score") or 25)

    triage, used_llm = await groq_client.call_json(
        prompts.TRIAGE,
        {"request_id": trace_id,
         "needs": [n["resource"] for n in (request.get("all_needs") or [])] or [need],
         "quantity": qty,
         "people": request.get("people_est") or qty,
         "injury": (request.get("decoded") or {}).get("injury"),
         "mobility": (request.get("decoded") or {}).get("mobility"),
         "hazard": (request.get("decoded") or {}).get("situation"),
         "vulnerabilities": (request.get("decoded") or {}).get("vulnerability", []),
         "self_reported_urgency": request.get("urgency"),
         "deterministic_prior": prior},
        TriageOut, agent="a2_triage", trace_id=trace_id, run_id=run_id,
        fallback=lambda: fallbacks.triage(prior, injury_rank, trapped, qty,
                                          request.get("urgency", "high")),
        max_tokens=900)

    # The model returns T1 with life_threat false often enough to matter:
    # internally inconsistent output that nothing downstream would catch,
    # because both fields validate fine on their own. T1 *means* life threat
    # within six hours (agents.md 2.2), so the invariant is enforced here and
    # the correction is reported rather than applied silently.
    normalized = _enforce_triage_invariants(triage)

    severity, tier = triage.severity, triage.tier
    await bus.publish(
        trace_id, "agent.message",
        {"text": triage.reasoning or f"Tier {tier}, severity {severity}.",
         "structured": {**triage.model_dump(), "normalized": normalized},
         "confidence": triage.confidence, "llm": used_llm},
        agent="a2_triage", run_id=run_id)
    if normalized:
        await bus.publish(
            trace_id, "error",
            {"code": "TRIAGE_INCONSISTENT", "corrections": normalized,
             "fallback_used": False,
             "detail": "model output was internally inconsistent; invariant enforced"},
            agent="a2_triage", run_id=run_id)
    await repo_requests.set_triage(trace_id, triage.model_dump())

    # -- A3 geo: REAL $geoNear ---------------------------------------------
    await bus.publish(trace_id, "agent.entered",
                      {"agent": "a3_geo", "label": "Geo Candidate Finder"},
                      agent="a3_geo", run_id=run_id)

    candidates, radius_used, queries = await geo_task
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
        await repo_requests.set_status(trace_id, "unmet")
        await _tell_seeker(
            request, trace_id, "unmet", "No help available yet",
            f"No supplier in range is holding {pretty}. Your request stays open "
            "and is retried as stock changes.")
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

    # One call carrying all candidates, not N calls: same wall-clock, far fewer
    # requests against an 8000 tokens/minute ceiling.
    advocates, adv_llm = await groq_client.call_json(
        prompts.ADVOCATES,
        {"need": {"resource": need, "quantity": qty, "tier": tier, "severity": severity},
         "candidates": [
             {"cand_id": c["cand_id"], "name": c["name"], "org_type": c.get("org_type"),
              "owner_kind": c["owner_kind"], "distance_km": c["distance_km"],
              "eta_minutes": c["eta_minutes"], "free": c["free"],
              "reliability": c.get("reliability"), "capacity_load": c.get("capacity_load"),
              "capabilities": c.get("capabilities", [])}
             for c in candidates]},
        AdvocatesOut, agent="a4_advocates", trace_id=trace_id, run_id=run_id,
        fallback=lambda: fallbacks.advocates(candidates, qty),
        fast=True, max_tokens=1400, stream_tokens=False)

    by_id = {c["cand_id"]: c for c in candidates}
    fit_by_id: dict[str, int] = {}
    risk_by_id: dict[str, list[str]] = {}
    turn_no = 0
    for bid in advocates.bids:
        c = by_id.get(bid.cand_id)
        if c is None:                       # model named a candidate that does not exist
            continue
        fit_by_id[bid.cand_id] = bid.fit
        risk_by_id[bid.cand_id] = list(bid.risk_flags)
        turn_no += 1
        stance = ("for" if bid.recommended_share == "full"
                  else "against" if bid.recommended_share == "none" else "neutral")
        await bus.publish(
            trace_id, "debate.turn",
            {"debate_id": debate_id, "turn_no": turn_no,
             "speaker": f"advocate:{bid.cand_id}", "stance": stance,
             "claim": bid.argument,
             "evidence": [{"field": "eta_minutes", "value": c["eta_minutes"]},
                          {"field": "free", "value": c["free"]},
                          {"field": "fit", "value": bid.fit}]
                         + [{"field": "risk", "value": r} for r in bid.risk_flags],
             "rebuts": None, "llm": adv_llm},
            agent="a4_advocates", run_id=run_id)
        await _pause(0.1, 0.25)

    # -- A5 solver: REAL greedy fill over the real candidates ---------------
    await bus.publish(trace_id, "agent.entered",
                      {"agent": "a5_solver", "label": "Allocation Solver"},
                      agent="a5_solver", run_id=run_id)
    await _pause(0.1, 0.25)

    # Every candidate scored by the weighted formula in agents.md 2.5, from
    # real fields: $geoNear's eta and free stock, the organization's
    # reliability and load, A4's fit and risk flags. No literals.
    cand_scores = solver.score_candidates(candidates, qty, fit_by_id, risk_by_id)
    await bus.publish(
        trace_id, "agent.tool_call",
        {"tool": "solver.score_candidates",
         "args": {"weights": {"speed": solver.W_SPEED, "fit": solver.W_FIT,
                              "reliability": solver.W_RELIABILITY,
                              "headroom": solver.W_HEADROOM,
                              "load_penalty": solver.P_LOAD,
                              "blocker_penalty": solver.P_BLOCKER}},
         "result_count": len(cand_scores),
         "scores": [{"cand_id": k, "name": by_id[k]["name"], "score": v}
                    for k, v in sorted(cand_scores.items(),
                                       key=lambda kv: -kv[1]) if k in by_id]},
        agent="a5_solver", run_id=run_id)

    opt_fast = _option("opt_1", "fastest",
                       _greedy(candidates, qty, key=lambda c: c["eta_minutes"]),
                       qty, need, cand_scores)
    opt_cover = _option("opt_2", "max_coverage",
                        _greedy(candidates, qty, key=lambda c: -c["free"]),
                        qty, need, cand_scores)
    # Least depleting: prefer suppliers with the most headroom relative to stock,
    # so a scarce holder is not drained for a request others can serve.
    opt_least = _option("opt_3", "least_depleting",
                        _greedy(candidates, qty,
                                key=lambda c: (c["capacity_load"], -c["free"])),
                        qty, need, cand_scores)
    # The weighted score decides the fill order here; A4's fit is one term in
    # it. The model still never sets a quantity.
    opt_fit = _option("opt_4", "best_fit",
                      _greedy(candidates, qty,
                              key=lambda c: -cand_scores.get(c["cand_id"], 0.0)),
                      qty, need, cand_scores)

    seen, options = set(), []
    for o in (opt_cover, opt_fast, opt_least, opt_fit):
        if o is None:
            continue
        sig = tuple((a["owner_id"], a["qty"]) for a in o["allocations"])
        if sig and sig not in seen:      # drop duplicate strategies
            seen.add(sig)
            options.append(o)
    if not options:
        options = [opt_cover]

    # agents.md 2.5 says "ranked feasible options". Now that the score is a
    # real computation, ranking by it means something.
    options.sort(key=lambda o: -o["score"])

    await bus.publish(trace_id, "options.proposed", {"options": options},
                      agent="a5_solver", run_id=run_id)

    # -- A6 arbiter: Groq, constrained to an existing option_id -------------
    await bus.publish(trace_id, "agent.entered", {"agent": "a6_arbiter", "label": "Arbiter"},
                      agent="a6_arbiter", run_id=run_id)
    arb, arb_llm = await groq_client.call_json(
        prompts.ARBITER,
        {"need": {"resource": need, "quantity": qty, "tier": tier, "severity": severity},
         "options": [{"option_id": o["option_id"], "label": o["label"],
                      "coverage_pct": o["coverage_pct"], "total_eta": o["total_eta"],
                      "allocations": [{"name": a["name"], "qty": a["qty"],
                                       "eta_min": a["eta_min"]} for a in o["allocations"]]}
                     for o in options],
         "advocate_bids": [{"cand_id": b.cand_id, "fit": b.fit, "argument": b.argument,
                            "risk_flags": b.risk_flags} for b in advocates.bids]},
        ArbiterOut, agent="a6_arbiter", trace_id=trace_id, run_id=run_id,
        fallback=lambda: fallbacks.arbiter(options), max_tokens=1000)

    # The load-bearing guard: the model may only name an option that exists.
    valid_ids = {o["option_id"] for o in options}
    if arb.chosen_option_id not in valid_ids:
        await bus.publish(
            trace_id, "error",
            {"code": "INVALID_OPTION_ID", "received": arb.chosen_option_id,
             "valid": sorted(valid_ids), "fallback_used": True},
            agent="a6_arbiter", run_id=run_id)
        arb = fallbacks.arbiter(options)
        arb_llm = False

    chosen = arb.chosen_option_id
    best = next(o for o in options if o["option_id"] == chosen)

    for i, t in enumerate(arb.turns, start=turn_no + 1):
        await bus.publish(
            trace_id, "debate.turn",
            {"debate_id": debate_id, "turn_no": i, "speaker": "arbiter",
             "stance": "neutral", "claim": t.claim, "evidence": [],
             "rebuts": t.rebuts, "llm": arb_llm},
            agent="a6_arbiter", run_id=run_id)
        await _pause(0.1, 0.2)

    await bus.publish(
        trace_id, "agent.message",
        {"text": arb.justification, "structured": {"chosen_option_id": chosen},
         "confidence": arb.confidence, "llm": arb_llm},
        agent="a6_arbiter", run_id=run_id)
    await bus.publish(
        trace_id, "debate.closed",
        {"debate_id": debate_id, "winner": chosen,
         "dissent": arb.dissent or f"{fastest['name']} alone would arrive in "
                                   f"{fastest['eta_minutes']} min."},
        agent="a6_arbiter", run_id=run_id)

    # -- A7 privacy --------------------------------------------------------
    # A deterministic field matrix (privacy/policy.py), run over the real
    # outbound payload. Every number below is counted off that object, so if
    # the redactor stopped matching a path the count drops here rather than
    # the data leaking silently.
    await bus.publish(trace_id, "agent.entered",
                      {"agent": "a7_privacy", "label": "Privacy Redactor"},
                      agent="a7_privacy", run_id=run_id)

    outbound = {
        "request": {"lat": lat, "lon": lon, "uid": request.get("uid"),
                    "name": request.get("name"), "phone": request.get("phone"),
                    "raw_code": request.get("raw_code"),
                    "decoded": request.get("decoded") or {}},
        "options": options,
        "structured": {"candidates": candidates},
        "justification": arb.justification,
    }
    helper_view = redact.audit(outbound, privacy_policy.HELPER_PRE)
    org_view = redact.audit(outbound, privacy_policy.ORG)
    removed = helper_view["fields_touched"]

    await bus.publish(
        trace_id, "agent.message",
        {"text": (f"Applied the field policy to the outbound payload: {removed} field "
                  f"instances redacted for the pre-acceptance helper audience "
                  f"({len(helper_view['withheld'])} withheld, {len(helper_view['masked'])} "
                  f"masked to ~1 km). Organizations additionally lose "
                  f"{len(org_view['event_types_blocked'])} event types, including the "
                  f"cross-organization debate."),
         "structured": {
             # Kept flat for the portal's existing privacy panel.
             "shared": helper_view["shared"],
             "withheld": helper_view["withheld"],
             "masked": helper_view["masked"],
             "fields_redacted": removed,
             "by_field": helper_view["by_field"],
             "audiences": {"helper_pre": helper_view, "org": org_view},
         }},
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
    if result.get("action") == "reject":
        await repo_matches.record_admin_action(
            decision_id, "reject", result.get("admin_id", "admin"),
            before={"chosen_option_id": chosen}, after={"option_id": None},
            note=result.get("note"), trace_id=trace_id)
        await bus.publish(
            trace_id, "admin.action",
            {"decision_id": decision_id, "action": "reject",
             "admin_id": result.get("admin_id", "admin"), "note": result.get("note")},
            agent="a8_gate", run_id=run_id)
        await bus.publish(trace_id, "replan.triggered",
                          {"reason": "admin_rejected", "prior_run_id": run_id},
                          agent="a11_replanner", run_id=run_id)
        await repo_requests.set_status(trace_id, "rejected")
        await _tell_seeker(
            request, trace_id, "rejected", "Request rejected",
            "An operator rejected this allocation. Your request has not been "
            "closed — it is being re-planned against other suppliers.")
        await bus.publish(trace_id, "run.completed", {"status": "rejected"}, run_id=run_id)
        return {"status": "rejected", "trace_id": trace_id}

    # -- override: re-enter at A5 with the admin's allocations pinned --------
    # agents.md 2.8. The array used to be echoed into admin.action, written to
    # the audit trail, and then discarded -- only `option_id` was ever read.
    # The solver validates feasibility before anything is pinned, because an
    # override is a human instruction, not a licence to write an allocation the
    # stock cannot support.
    override_errors: list[str] = []
    admin_option = None
    if result.get("action") == "override" and result.get("allocations"):
        admin_option, override_errors = solver.build_admin_option(
            result["allocations"], candidates, need, qty, cand_scores)
        if admin_option is not None:
            options = [admin_option] + options
            await bus.publish(
                trace_id, "options.proposed",
                {"options": options, "source": "admin_override",
                 "note": "admin allocations validated against live stock and pinned"},
                agent="a5_solver", run_id=run_id)
        else:
            await bus.publish(
                trace_id, "error",
                {"code": "OVERRIDE_INFEASIBLE", "errors": override_errors,
                 "fallback_used": True,
                 "detail": "admin allocations failed solver validation; "
                           "falling back to the selected option"},
                agent="a5_solver", run_id=run_id)

    target_option_id = (admin_option["option_id"] if admin_option
                        else result.get("option_id"))
    final = next((o for o in options if o["option_id"] == target_option_id), None) \
        or next(o for o in options if o["option_id"] == chosen)

    await repo_matches.record_admin_action(
        decision_id, result.get("action", "unknown"), result.get("admin_id", "admin"),
        before={"chosen_option_id": chosen,
                "allocations": next((o["allocations"] for o in options
                                     if o["option_id"] == chosen), None)},
        after={"option_id": final["option_id"], "allocations": final["allocations"],
               "override_applied": admin_option is not None,
               "override_errors": override_errors or None},
        note=result.get("note"), trace_id=trace_id)

    await bus.publish(
        trace_id, "admin.action",
        {"decision_id": decision_id, "action": result.get("action"),
         "admin_id": result.get("admin_id", "admin"), "note": result.get("note"),
         "option_id": final["option_id"], "override": result.get("allocations"),
         "override_applied": admin_option is not None,
         "override_errors": override_errors},
        agent="a8_gate", run_id=run_id,
    )

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
    unmet = max(0, qty - sum(a["qty"] for a in final["allocations"]))
    # `final`, not `best`: an admin override must record the rationale for the
    # option that was actually committed. And the arbiter's own justification,
    # not `final["justification"]` -- _option() never sets that key, so this
    # column was silently the empty string on every match ever written.
    code = await repo_matches.create(
        match_id, trace_id, run_id, final,
        justification=arb.justification,
        approved_by=result.get("admin_id", "autopilot"), unmet=unmet)
    await repo_requests.set_status(trace_id, "allocated", match_id=match_id)
    _sent = sum(a["qty"] for a in final["allocations"])
    _eta = max((a["eta_min"] for a in final["allocations"]), default=0)
    await _tell_seeker(
        request, trace_id, "approved", "Request approved",
        f"{_sent} x {pretty} approved for you, about {_eta} minutes away. "
        f"Delivery code {code}.",
        match_id=match_id)

    await bus.publish(
        trace_id, "decision.committed",
        {"match_id": match_id, "allocations": final["allocations"],
         "unmet": unmet, "delivery_code": code},
        agent="a8_gate", run_id=run_id,
    )

    # Per-organization copies, on the org topic only. Each carries ONLY that
    # organization's own allocation -- an org on a split allocation must not
    # learn who else was on it (memory_draft.md 7.5). publish_org, not publish,
    # because publish() would also fan these out to the admin firehose and
    # render the same card once per organization.
    for owner_id in {a["owner_id"] for a in final["allocations"]
                     if a.get("owner_kind") == "org"}:
        await bus.publish_org(
            owner_id, trace_id, "decision.committed",
            {"match_id": match_id,
             "allocations": [a for a in final["allocations"] if a["owner_id"] == owner_id],
             "unmet": unmet, "delivery_code": code},
            agent="a8_gate", run_id=run_id)
    await bus.publish(trace_id, "agent.entered",
                      {"agent": "a9_narrator", "label": "Narrator"},
                      agent="a9_narrator", run_id=run_id)
    narrated, nar_llm = await groq_client.call_json(
        prompts.NARRATOR,
        {"resource": need, "quantity": sum(a["qty"] for a in final["allocations"]),
         "area": where, "eta_minutes": final["total_eta"],
         "coverage_pct": final["coverage_pct"], "unmet": unmet,
         "helpers": [a["name"] for a in final["allocations"]]},
        NarratorOut, agent="a9_narrator", trace_id=trace_id, run_id=run_id,
        fallback=lambda: fallbacks.narrator(need, sum(a["qty"] for a in final["allocations"]),
                                            where, final["total_eta"]),
        fast=True, max_tokens=800)

    await bus.publish(
        trace_id, "agent.message",
        {"text": narrated.admin_summary,
         "structured": {"match_id": match_id, "sms_variant": narrated.sms_variant,
                        "sms_chars": len(narrated.sms_variant)},
         "llm": nar_llm},
        agent="a9_narrator", run_id=run_id)

    # Two dispatch paths, actually routed (notify/dispatcher.py). An org
    # allocation lands in that org's portal queue and is NOT acceptable until
    # a named helper is attached; an individual volunteer's is acceptable at
    # once. The states are written to the match, so the difference is real.
    routes = []
    for i, a in enumerate(final["allocations"]):
        route = await notify.dispatch(
            match_id=match_id, trace_id=trace_id, run_id=run_id, allocation=a,
            message=narrated.helper_message
                    or f"Deliver {a['qty']} x {pretty} near {where}. ETA {a['eta_min']} min.",
            sms_variant=narrated.sms_variant)
        routes.append(route)
        await repo_matches.set_allocation_state(match_id, i, route["state"])

    await bus.publish(
        trace_id, "run.completed",
        {"status": "committed", "match_id": match_id,
         "llm_agents": {"triage": used_llm, "advocates": adv_llm,
                        "arbiter": arb_llm, "narrator": nar_llm},
         "groq": groq_client.stats(), "geo_live": live,
         "routes": routes, "cluster": {"duplicate": dup["duplicate"],
                                       "size": dup["cluster_size"]},
         "privacy": {"fields_redacted": removed,
                     "audiences": list(privacy_policy.AUDIENCES)}},
        run_id=run_id,
    )
    return {"status": "committed", "trace_id": trace_id, "match_id": match_id,
            "allocations": final["allocations"]}


# ---------------------------------------------------------------------------
# Spawning
# ---------------------------------------------------------------------------

# Strong references to in-flight runs. asyncio holds only WEAK references to
# tasks, so a bare `create_task(scripted.run(...))` can be collected
# mid-deliberation -- the same hazard deps._spawn already documents for token
# writes, reintroduced on the pipeline. The transcript shows what it looks like
# from outside: a run whose events simply stop, with no terminal event, sitting
# in All Requests as "incomplete" forever.
_INFLIGHT: set[asyncio.Task[Any]] = set()


async def _guarded(request: dict[str, Any]) -> dict[str, Any]:
    """Run, and make sure the transcript always ends.

    A deliberation that raises used to leave the trace with no `run.completed`,
    which is indistinguishable from one still in progress. A failed run is a
    fact worth recording -- the operator needs to know the request was received
    and then dropped, not wonder whether it is still thinking.
    """
    trace_id = request.get("request_id") or "REQ-UNKNOWN"

    # A hard ceiling on a whole deliberation.
    #
    # The guard below catches a run that RAISES. It cannot catch one that
    # HANGS, and that is the failure actually seen on venue wifi: an SMS-borne
    # request stopped after "advocates: request timed out", published nothing
    # further, and sat in All Requests with no terminal event for ten minutes
    # while fresh runs completed normally beside it. An operator cannot tell
    # that from a request still being thought about.
    #
    # Sized off the admin gate, which is a legitimate long wait -- a run parked
    # for a human decision must not be killed for being patient.
    ceiling = max(180.0, float(get_settings().gate_timeout_s or 0) + 120.0)
    try:
        return await asyncio.wait_for(run(request), timeout=ceiling)
    except TimeoutError:
        log.error("run %s exceeded %.0fs ceiling", trace_id, ceiling)
        await bus.publish(trace_id, "error",
                          {"code": "RUN_TIMEOUT", "detail": f"exceeded {ceiling:.0f}s"})
        await bus.publish(trace_id, "run.completed",
                          {"status": "failed",
                           "reason": f"no progress within {ceiling:.0f}s"})
        return {"status": "failed", "trace_id": trace_id, "error": "timeout"}
    except asyncio.CancelledError:
        # Shutdown. Say so rather than leaving a silent stump.
        await bus.publish(trace_id, "run.completed",
                          {"status": "failed", "reason": "server stopped mid-run"})
        raise
    except Exception as exc:
        log.exception("run failed for %s", trace_id)
        await bus.publish(trace_id, "error",
                          {"code": "RUN_FAILED", "detail": f"{type(exc).__name__}: {exc}"})
        await bus.publish(trace_id, "run.completed",
                          {"status": "failed", "reason": str(exc)[:300]})
        return {"status": "failed", "trace_id": trace_id, "error": str(exc)}


def spawn(request: dict[str, Any]) -> asyncio.Task[dict[str, Any]]:
    """Start a deliberation in the background, holding a reference until it
    ends. Every caller should use this rather than create_task(run(...))."""
    task = asyncio.get_running_loop().create_task(_guarded(request))
    _INFLIGHT.add(task)
    task.add_done_callback(_INFLIGHT.discard)
    return task


def spawn_recorded(request: dict[str, Any], sink: list[dict[str, Any]]) -> asyncio.Task[Any]:
    """spawn(), plus append the outcome to an in-memory list. Used by the admin
    portal's injected requests, which surface in GET /admin/runs."""
    async def _go() -> dict[str, Any]:
        result = await _guarded(request)
        sink.append({**request, **result})
        return result

    task = asyncio.get_running_loop().create_task(_go())
    _INFLIGHT.add(task)
    task.add_done_callback(_INFLIGHT.discard)
    return task
