"""Admin portal endpoints.

Drives the live agent pipeline, the approve/override bar, the persisted request
list and the seed/inventory reads the portal uses to stay off hardcoded values.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents import scripted
from app.bus import gate
from app.bus.eventbus import bus
from app.config import get_settings
from app.db import mongo, repo_events, repo_matches, repo_offers, repo_requests
from app.db import seed as db_seed
from app.deps import check_admin_credentials, current_admin, issue
from app.llm import groq_client

router = APIRouter(prefix="/api/v1/admin", tags=["admin"],
                   dependencies=[Depends(current_admin)])

# /login must stay open, so it lives on its own unprotected router.
public = APIRouter(prefix="/api/v1/admin", tags=["admin"])

# In-memory run log for /stats. The durable record is the event transcript
# in Mongo, read back via /requests.
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
    """A request injected by the admin portal.

    lat/lon are optional but matter: without them the pipeline falls back to
    DEFAULT_LAT/LON in the agent module, which is Bhopal. A database seeded
    anywhere else then puts every offer outside the 150 km radius ladder, so
    `$geoNear` returns nothing and the run silently uses hardcoded fixtures
    (`geo_live: false`). The portal reads GET /admin/seed and sends the real
    seeded centre, so the one real database query actually runs.
    """
    need: str = "medical_kits"
    quantity: int = Field(default=3, gt=0)
    location_name: str | None = None
    urgency: str = "critical"
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


@public.post("/login")
async def login(payload: LoginRequest):
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
    """Inject one request and run the full pipeline on it.

    Same `scripted.run` the codec/SMS path uses -- the module name is historical,
    the agents behind it are the live Groq ones. Only the input differs: this
    endpoint takes a need and a position directly instead of decoding them from
    a codec string.
    """
    centre = await db_seed.seeded_centre()
    lat = payload.lat if payload.lat is not None else (centre[0] if centre else None)
    lon = payload.lon if payload.lon is not None else (centre[1] if centre else None)

    request: dict[str, Any] = {
        "request_id": f"REQ-{uuid4().hex[:6].upper()}",
        "need": payload.need,
        "quantity": payload.quantity,
        # Matches the wording the codec/SMS path uses for an unnamed
        # position, so the two entry points do not produce differently
        # phrased summaries for the same kind of request.
        "location_name": payload.location_name or "reported position",
        "urgency": payload.urgency,
    }
    # Only set when known. A null lat would be cast to float downstream.
    if lat is not None and lon is not None:
        request["lat"] = lat
        request["lon"] = lon

    scripted.spawn_recorded(request, _runs)
    return {"status": "accepted", "trace_id": request["request_id"],
            "lat": lat, "lon": lon}





@router.get("/runs")
def runs():
    return {"runs": _runs, "count": len(_runs)}


class SeedRequest(BaseModel):
    """Where to plant the fixtures.

    Omit lat/lon to use PACT_SEED_LAT/LON, or Bhopal if those are unset.
    """
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    label: str | None = None


@router.post("/seed")
async def reseed(payload: SeedRequest | None = None):
    """Idempotent demo reset, optionally re-centred.

    Re-centring matters more than it looks. The radius ladder stops at 150 km,
    so fixtures left in Bhopal while the demo runs anywhere else make every
    `$geoNear` return nothing -- and the pipeline then falls back to hardcoded
    candidates and carries on, showing a debate and an allocation with
    `geo_live: false`. The failure is invisible unless you look for it.
    """
    payload = payload or SeedRequest()
    centre = None
    if payload.lat is not None and payload.lon is not None:
        centre = (payload.lat, payload.lon)
    elif payload.lat is not None or payload.lon is not None:
        return {"status": "error", "error": "BOTH_OR_NEITHER",
                "detail": "supply lat and lon together, or neither"}

    result = await db_seed.seed(reset=True, centre=centre, label=payload.label)
    check = await db_seed.verify_lng_lat()
    _runs.clear()
    return {**result, "geo_check": check}


@router.get("/seed")
async def seed_info():
    """Where the fixtures currently sit. Lets the portal warn when a request
    lands outside the seeded area instead of quietly using fixtures."""
    centre = await db_seed.seeded_centre()
    return {"centre": ({"lat": centre[0], "lon": centre[1]} if centre else None),
            "default": {"lat": db_seed.default_centre()[0],
                        "lon": db_seed.default_centre()[1]},
            "radius_ladder_km": repo_offers.RADIUS_LADDER_KM}


@router.get("/inventory")
async def inventory():
    """What is actually in stock, by resource.

    The portal used to hardcode five resource names, three of which happened to
    match the seed. Selecting one of the others produced zero candidates and a
    fixture-backed run, which looks identical to a real one.
    """
    db = mongo.get_db()
    if db is None or not mongo.is_healthy():
        return {"resources": [], "source": "unavailable"}
    rows = await db.offers.aggregate([
        {"$match": {"available": {"$gt": 0}}},
        {"$group": {"_id": "$resource",
                    "available": {"$sum": "$available"},
                    "offers": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]).to_list(length=100)
    return {
        "resources": [{"resource": r["_id"], "available": r["available"],
                       "offers": r["offers"]} for r in rows],
        "source": "mongo",
    }


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
        "mode": "live-agents" if s.groq_enabled else "deterministic-fallback",
        "rate_limit": groq_client.stats(),
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

    scripted.spawn({
        "request_id": request_id,
        "need": original.get("need"), "quantity": original.get("quantity"),
        "location_name": "reported position", "urgency": original.get("urgency"),
        **({"lat": original["loc"]["coordinates"][1],
            "lon": original["loc"]["coordinates"][0]} if original.get("loc") else {}),
        "uid": original.get("seeker_uid"),
    })
    return {"status": "accepted", "trace_id": request_id, "replan": True}
