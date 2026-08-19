"""Admin portal endpoints.

Step 1 scope: enough to drive the scripted pipeline and the approve/override
bar. Mongo-backed listing lands with the persistence layer.
"""

from __future__ import annotations

import asyncio
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agents import scripted
from app.bus import gate
from app.bus.eventbus import bus
from app.config import get_settings

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

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


@router.post("/login")
def login(payload: LoginRequest):
    s = get_settings()
    ok = payload.username == s.pact_admin_user and payload.password == s.pact_admin_pass
    if not ok:
        return {"status": "error", "error": "BAD_CREDENTIALS"}
    # Demo-grade session. Real auth is post-hackathon work (memory_draft 7.6).
    return {"status": "ok", "token": f"admin-{uuid4().hex[:12]}", "user": payload.username}


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


@router.get("/stats")
def stats():
    s = get_settings()
    return {
        "runs": len(_runs),
        "committed": sum(1 for r in _runs if r.get("status") == "committed"),
        "subscribers": bus.subscriber_count(),
        "pending_decisions": gate.pending_ids(),
        "mongo": s.mongo_enabled,
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
