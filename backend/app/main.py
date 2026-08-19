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
from app.routers import admin as admin_router
from app.routers import ws as ws_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("pact")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    bus.set_delay_ms(s.demo_latency_ms)
    log.info("PACT backend starting")
    log.info("  mongo:    %s", "configured" if s.mongo_enabled else "NOT configured (in-memory)")
    log.info("  groq:     %s", "configured" if s.groq_enabled else "NOT configured (scripted only)")
    log.info("  autopilot:%s  gate_timeout=%ss", s.autopilot, s.gate_timeout_s)
    yield
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
app.include_router(admin_router.router)


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
        "mongo": s.mongo_enabled,
        "groq": s.groq_enabled,
        "mode": "scripted",
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


class SmsWebhookRequest(BaseModel):
    sms: str
    from_number: Optional[str] = None


@app.post("/api/v1/crises", deprecated=True)
def create_crisis(payload: CrisisRequest):
    if payload.quantity <= 0:
        return {"status": "error", "error": "BAD_QTY"}
    plan = create_response_plan(payload.location, payload.resource, payload.quantity, payload.urgency)
    return {"status": "accepted", "crisis_id": f"CRISIS-{uuid4().hex[:6].upper()}", "plan": plan}


@app.post("/api/v1/sms/webhook")
def sms_webhook(payload: SmsWebhookRequest):
    """Thin adapter. Becomes a call into /api/v1/pact/ingest once the codec lands."""
    sms = payload.sms.strip()
    if not sms:
        return {"status": "error", "error": "EMPTY_SMS"}

    parts = sms.split("|")
    mtype = parts[0].strip().upper()

    if mtype == "N" and len(parts) in (6, 8):
        canonical = len(parts) == 8
        if canonical:
            body = "|".join(parts[:7])
            received, expected = parts[7].strip().upper(), xor_checksum(body)
            if received != expected:
                return {"status": "error", "error": "BAD_CRC",
                        "expected_checksum": expected, "received_checksum": received}
        idx = 2 if canonical else 1
        try:
            quantity = int(parts[idx + 3].strip())
        except ValueError:
            return {"status": "error", "error": "BAD_QTY"}
        loc = parts[idx + 1].strip()
        return {
            "status": "accepted",
            "mode": "canonical" if canonical else "legacy",
            "decoded": {
                "type": "need",
                "organization_id": parts[idx].strip(),
                "location_code": loc,
                "location_name": LOCATION_NAME_MAP.get(loc, loc),
                "resource": map_resource(parts[idx + 2].strip()),
                "quantity": quantity,
                "urgency": map_urgency(parts[idx + 4].strip()),
                "source": "sms",
            },
        }

    return {"status": "accepted", "raw_sms": sms, "note": "This SMS type is not fully decoded yet"}
