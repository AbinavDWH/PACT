"""Admin portal endpoints.

Step 1 scope: enough to drive the scripted pipeline and the approve/override
bar. Mongo-backed listing lands with the persistence layer.
"""

from __future__ import annotations

import asyncio
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents import scripted
from app.bus import gate
from app.bus.eventbus import bus
from app.config import get_settings
from app.db import mongo, repo_events, repo_matches, repo_requests
from app.db import seed as db_seed
from app.deps import check_admin_credentials, current_admin, issue

router = APIRouter(prefix="/api/v1/admin", tags=["admin"],
                   dependencies=[Depends(current_admin)])

# /login must stay open, so it lives on its own unprotected router.
public = APIRouter(prefix="/api/v1/admin", tags=["admin"])

# In-memory run log until Mongo is wired.
_runs: list[dict[str, Any]] = []


class LoginRequest(BaseModel):
    username: str
    password: str


class DecisionAction(BaseModel):
    action: Literal["approve", "override", "reject"]
    option_id: str | None = None
    allocations: list[dict[str, Any]] | None = None
    note: str | None = None
    admin_id: str = "admin"


class SimulateRequest(BaseModel):
    need: str = "medical_kits"
    quantity: int = Field(default=3, gt=0)
    location_name: str = "Region A"
    urgency: str = "critical"


@public.post("/login")
def login(payload: LoginRequest):
    if not check_admin_credentials(payload.username, payload.password):
        return {"status": "error", "error": "BAD_CREDENTIALS"}
    # Demo-grade session, but the token is now actually verified on protected
    # endpoints (deps.current_admin). Real auth is post-hackathon work.
    return {"status": "ok", "token": issue(payload.username, "admin"),
            "user": payload.username}


@router.post("/decisions/{decision_id}/action")
def decision_action(decision_id: str, payload: DecisionAction):
    released = gate.resolve(decision_id, payload.model_dump())
    return {"status": "ok" if released else "error",
            "released": released,
            "error": None if released else "NO_PENDING_DECISION",
            "pending": gate.pending_ids()}


@router.post("/simulate")
async def simulate(payload: SimulateRequest):
    """Fire one scripted deliberation. This is the demo trigger until the real
    ingest path lands."""
    request = {
        "request_id": f"REQ-{uuid4().hex[:6].upper()}",
        "need": payload.need,
        "quantity": payload.quantity,
        "location_name": payload.location_name,
        "urgency": payload.urgency,
    }
    asyncio.create_task(_run_and_record(request))
    return {"status": "accepted", "trace_id": request["request_id"]}


async def _run_and_record(request: dict[str, Any]) -> None:
    result = await scripted.run(request)
    _runs.append({**request, **result})


@router.get("/runs")
def runs():
    return {"runs": _runs, "count": len(_runs)}


@router.post("/seed")
async def reseed():
    """Idempotent demo reset."""
    result = await db_seed.seed(reset=True)
    check = await db_seed.verify_lng_lat()
    _runs.clear()
    return {**result, "geo_check": check}


@router.get("/requests")
async def list_requests(limit: int = 50):
    """Hydrates the All Requests view on a fresh page load, from the persisted
    transcript rather than whatever the socket has seen this session."""
    return {"traces": await repo_events.recent_traces(limit)}


@router.get("/requests/{trace_id}/trace")
async def get_trace(trace_id: str):
    events = await repo_events.trace(trace_id)
    return {"trace_id": trace_id, "count": len(events), "events": events}


@router.get("/stats")
def stats():
    s = get_settings()
    return {
        "runs": len(_runs),
        "committed": sum(1 for r in _runs if r.get("status") == "committed"),
        "subscribers": bus.subscriber_count(),
        "pending_decisions": gate.pending_ids(),
        "mongo_configured": s.mongo_enabled,
        "mongo_connected": mongo.is_healthy(),
        "groq": s.groq_enabled,
        "autopilot": s.autopilot,
        "gate_timeout_s": s.gate_timeout_s,
        "mode": "scripted",
    }


class SettingsPatch(BaseModel):
    autopilot: bool | None = None
    gate_timeout_s: int | None = None
    demo_latency_ms: int | None = None


@router.post("/settings")
def update_settings(payload: SettingsPatch):
    s = get_settings()
    if payload.autopilot is not None:
        s.autopilot = payload.autopilot
    if payload.gate_timeout_s is not None:
        s.gate_timeout_s = payload.gate_timeout_s
    if payload.demo_latency_ms is not None:
        s.demo_latency_ms = payload.demo_latency_ms
        bus.set_delay_ms(payload.demo_latency_ms)
    return {"status": "ok", "autopilot": s.autopilot,
            "gate_timeout_s": s.gate_timeout_s, "demo_latency_ms": s.demo_latency_ms}


@router.get("/matches")
async def list_matches(state: str | None = None, limit: int = 50):
    """Primary view hydration. Survives a portal reload, unlike the event
    stream alone."""
    rows = await repo_matches.live(limit, state)
    for r in rows:
        r["match_id"] = r.pop("_id", None)
        # The delivery code is for the seeker and the assigned helper only.
        r.pop("delivery_code", None)
    return {"matches": rows, "count": len(rows)}


@router.get("/audit")
async def audit(limit: int = 100):
    """Append-only record of every approve / override / reject, autopilot
    included. Never TTL'd."""
    return {"actions": await repo_matches.audit(limit)}


class VerifyRequest(BaseModel):
    verdict: Literal["verified", "partial", "disputed"] = "verified"
    qty_delivered: int | None = None
    note: str | None = None
    admin_id: str = "admin"


@router.post("/matches/{match_id}/verify")
async def verify_match(match_id: str, payload: VerifyRequest):
    match = await repo_matches.get(match_id)
    if match is None:
        return {"status": "error", "error": "NO_SUCH_MATCH"}
    await repo_matches.set_status(match_id, payload.verdict,
                                  qty_delivered=payload.qty_delivered)
    await repo_matches.record_admin_action(
        match_id, f"verify:{payload.verdict}", payload.admin_id,
        before={"status": match.get("status")}, after={"status": payload.verdict},
        note=payload.note, trace_id=match.get("request_id"))
    await bus.publish(match.get("request_id", match_id), "verify.result",
                      {"match_id": match_id, "verdict": payload.verdict,
                       "qty_delivered": payload.qty_delivered},
                      agent="a10_verify")
    return {"status": "ok", "match_id": match_id, "verdict": payload.verdict}


class ReplanRequest(BaseModel):
    reason: str = "admin_forced"
    admin_id: str = "admin"


@router.post("/replan/{request_id}")
async def replan(request_id: str, payload: ReplanRequest):
    """Force A11. Re-enters the pipeline under a NEW run_id but the SAME
    trace_id, so the portal chains the replan under the original request."""
    db_req = await repo_requests.recent(limit=200)
    original = next((r for r in db_req if r["_id"] == request_id), None)
    if original is None:
        return {"status": "error", "error": "NO_SUCH_REQUEST"}

    await bus.publish(request_id, "replan.triggered",
                      {"reason": payload.reason, "prior_run_id": None},
                      agent="a11_replanner")
    await repo_matches.record_admin_action(
        request_id, "replan", payload.admin_id, note=payload.reason,
        trace_id=request_id)

    asyncio.create_task(scripted.run({
        "request_id": request_id,
        "need": original.get("need"), "quantity": original.get("quantity"),
        "location_name": "reported position", "urgency": original.get("urgency"),
        **({"lat": original["loc"]["coordinates"][1],
            "lon": original["loc"]["coordinates"][0]} if original.get("loc") else {}),
        "uid": original.get("seeker_uid"),
    }))
    return {"status": "accepted", "trace_id": request_id, "replan": True}
