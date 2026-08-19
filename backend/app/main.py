"""PACT backend.

Step 1 of the build order (memory_draft.md section 22): event bus, WebSocket,
and a scripted pipeline, so the admin portal is visibly alive before any real
agent exists. Mongo and Groq land behind this without changing the wire format.

The legacy Evaluation-1 endpoints below still work; they are marked for removal
once /api/v1/pact/ingest replaces them (agents.md section 6.6).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.bus.eventbus import bus
from app.config import get_settings
from app.db import mongo
from app.db import repo_events
from app.db import seed as db_seed
from app.db.indexes import ensure_indexes
from app.llm import groq_client
from app.routers import admin as admin_router
from app.routers import assignments as assignments_router
from app.routers import ingest as ingest_router
from app.routers import session as session_router
from app.routers import ws as ws_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("pact")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    bus.set_delay_ms(s.demo_latency_ms)
    log.info("PACT backend starting")
    log.info("  groq:     %s", "configured" if s.groq_enabled else "NOT configured (scripted only)")
    log.info("  autopilot:%s  gate_timeout=%ss", s.autopilot, s.gate_timeout_s)

    if s.groq_enabled:
        await groq_client.warmup()

    if await mongo.connect():
        await ensure_indexes()
        bus.set_persist(repo_events.persist)
        if await db_seed.get_db_empty():
            await db_seed.seed()
        check = await db_seed.verify_lng_lat()
        if check.get("checked") and not check.get("ok"):
            log.error("GEO SANITY FAILED: %s", check)
        else:
            log.info("  geo:      ok (nearest offer %.2f km)", check.get("nearest_km", -1))
    else:
        log.info("  mongo:    unavailable -- in-memory fallback active")

    yield
    await mongo.disconnect()
    log.info("PACT backend stopped")


app = FastAPI(
    title="PACT Backend",
    description="Privacy-Preserving Multi-Agent Humanitarian Coordination Platform",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router.router)
app.include_router(admin_router.public)
app.include_router(admin_router.router)
app.include_router(ingest_router.router)
app.include_router(assignments_router.router)
app.include_router(session_router.router)


@app.get("/")
def root():
    return {"message": "PACT backend running", "docs": "/docs", "health": "/api/v1/health"}


@app.get("/api/v1/health")
def health():
    s = get_settings()
    return {
        "status": "ok",
        "service": "pact-backend",
        "version": "0.2.0",
        # configured != connected. Reporting only "configured" hid a live
        # outage behind a green check.
        "mongo": {"configured": s.mongo_enabled, "connected": mongo.is_healthy()},
        "groq": {"configured": s.groq_enabled, "model": s.groq_model},
        "mode": "live-agents" if s.groq_enabled else "deterministic-fallback",
        "storage": "mongo" if mongo.is_healthy() else "in-memory fallback",
        "rate_limit": groq_client.stats(),
    }


# ---------------------------------------------------------------------------
# Legacy Evaluation-1 endpoints. Superseded by /api/v1/pact/ingest; kept so the
# existing web page keeps working until the portal rewrite lands.
# ---------------------------------------------------------------------------

RESOURCE_MAP = {
    "F": "food_kits", "W": "water_kits", "M": "medical_kits", "T": "tents",
    "B": "blankets", "H": "hygiene_kits", "D": "medical_teams", "U": "unknown",
    "food": "food_kits", "water": "water_kits", "medical": "medical_kits",
    "medicine": "medical_kits", "tents": "tents", "tent": "tents",
    "blankets": "blankets", "blanket": "blankets",
}

URGENCY_MAP = {
    "L": "low", "M": "medium", "H": "high", "C": "critical",
    "low": "low", "medium": "medium", "high": "high", "critical": "critical",
}

LOCATION_NAME_MAP = {"RA": "Region A", "RB": "Region B", "RC": "Region C"}

RESOURCE_PROVIDERS = {
    "food_kits": [
        {"organization_id": "CSR_002", "available_quantity": 220, "eta_hours": 4, "service_region": "Region A"},
        {"organization_id": "GOV_003", "available_quantity": 180, "eta_hours": 6, "service_region": "Region A"},
    ],
    "water_kits": [
        {"organization_id": "NGO_001", "available_quantity": 260, "eta_hours": 3, "service_region": "Region A"},
        {"organization_id": "CSR_002", "available_quantity": 150, "eta_hours": 5, "service_region": "Region A"},
    ],
    "medical_kits": [
        {"organization_id": "NGO_001", "available_quantity": 150, "eta_hours": 3, "service_region": "Region A"},
        {"organization_id": "HOSP_004", "available_quantity": 200, "eta_hours": 5, "service_region": "Region A"},
    ],
    "tents": [
        {"organization_id": "GOV_003", "available_quantity": 120, "eta_hours": 6, "service_region": "Region B"},
        {"organization_id": "CSR_002", "available_quantity": 90, "eta_hours": 5, "service_region": "Region B"},
    ],
}


def xor_checksum(text: str) -> str:
    value = 0
    for char in text:
        value ^= ord(char)
    return format(value, "02X")


def map_resource(value: str) -> str:
    v = value.strip()
    return RESOURCE_MAP.get(v.upper()) or RESOURCE_MAP.get(v.lower()) or v


def map_urgency(value: str) -> str:
    v = value.strip()
    return URGENCY_MAP.get(v.upper()) or URGENCY_MAP.get(v.lower()) or v


def create_response_plan(location: str, resource: str, quantity: int, urgency: str):
    """Greedy fill by fastest ETA. Becomes the A5 solver skeleton and the
    Groq-unavailable fallback (agents.md section 6.6)."""
    normalized = map_resource(resource)
    remaining = max(0, quantity)
    allocations = []
    for provider in sorted(RESOURCE_PROVIDERS.get(normalized, []), key=lambda i: i["eta_hours"]):
        if remaining <= 0:
            break
        assigned = min(provider["available_quantity"], remaining)
        remaining -= assigned
        allocations.append({
            "organization_id": provider["organization_id"], "resource": normalized,
            "quantity": assigned, "eta_hours": provider["eta_hours"],
            "approximate_service_region": provider["service_region"], "status": "assigned",
        })

    plan_id = f"PLAN-{uuid4().hex[:6].upper()}"
    return {
        "plan_id": plan_id,
        "need": {"location": location, "resource": normalized, "quantity": quantity,
                 "urgency": map_urgency(urgency)},
        "allocations": allocations,
        "allocated_quantity": quantity - remaining,
        "unmet_quantity": remaining,
        "privacy": {
            "shared": ["organization ID", "resource type", "available quantity",
                       "approximate service region", "response ETA"],
            "withheld": ["donor details", "staff data", "exact warehouse location",
                         "full inventory", "funding details", "internal routes"],
        },
        "activity": [
            f"Triage Agent classified the request as {map_urgency(urgency)}.",
            "Privacy Filter shared only minimum-necessary coordination data.",
            f"Geo Candidate Finder found {len(allocations)} eligible providers.",
            f"Allocation Solver generated {plan_id}.",
        ],
    }


class CrisisRequest(BaseModel):
    location: str
    resource: str
    quantity: int
    urgency: str = "high"
    organization_id: str = "FIELD_WEB_01"


@app.post("/api/v1/crises", deprecated=True)
def create_crisis(payload: CrisisRequest):
    if payload.quantity <= 0:
        return {"status": "error", "error": "BAD_QTY"}
    plan = create_response_plan(payload.location, payload.resource, payload.quantity, payload.urgency)
    return {"status": "accepted", "crisis_id": f"CRISIS-{uuid4().hex[:6].upper()}", "plan": plan}
