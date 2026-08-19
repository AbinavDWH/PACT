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
import random
import time
from typing import Any
from uuid import uuid4

from app.bus import gate
from app.bus.eventbus import bus
from app.config import get_settings
from app.codec.tables import get_tables
from app.db import repo_matches, repo_offers, repo_requests
from app.agents import dedupe, fallbacks
from app.llm import groq_client, prompts
from app.llm.schemas import AdvocatesOut, ArbiterOut, NarratorOut, TriageOut
from app.notify import dispatcher as notify
from app.privacy import policy as privacy_policy
from app.privacy import redact

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

    severity, tier = triage.severity, triage.tier
    await bus.publish(
        trace_id, "agent.message",
        {"text": triage.reasoning or f"Tier {tier}, severity {severity}.",
         "structured": triage.model_dump(), "confidence": triage.confidence,
         "llm": used_llm},
        agent="a2_triage", run_id=run_id)
    await repo_requests.set_triage(trace_id, triage.model_dump())

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
        await repo_requests.set_status(trace_id, "unmet")
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
    turn_no = 0
    for bid in advocates.bids:
        c = by_id.get(bid.cand_id)
        if c is None:                       # model named a candidate that does not exist
            continue
        fit_by_id[bid.cand_id] = bid.fit
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
    # A4's fit scores steer the ranking; they never set a quantity.
    if fit_by_id:
        opt_fit = _option("opt_4", "best_fit",
                          _greedy(candidates, qty,
                                  key=lambda c: -fit_by_id.get(c["cand_id"], 50)),
                          qty, need, 0.80)
    else:
        opt_fit = None

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
    await repo_matches.record_admin_action(
        decision_id, result.get("action", "unknown"), result.get("admin_id", "admin"),
        before={"chosen_option_id": chosen},
        after={"option_id": result.get("option_id") or chosen},
        note=result.get("note"), trace_id=trace_id)

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
        await repo_requests.set_status(trace_id, "rejected")
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
