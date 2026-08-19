import asyncio
import itertools
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


app = FastAPI(
    title="Humanitarian Coordination Backend",
    description="Privacy-Preserving Multi-Agent Humanitarian Coordination Platform"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════
# EDIT 1: Added latitude / longitude to NeedRequest
# ═══════════════════════════════════════════════════════
class NeedRequest(BaseModel):
    organization_id: str
    location_code: str
    resource: str
    quantity: int
    urgency: str
    source: str = "web"
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class SmsWebhookRequest(BaseModel):
    sms: str
    from_number: Optional[str] = None


class HubRequestCreate(BaseModel):
    type: str                                   # need | resource | status
    organization_id: str
    seq: Optional[str] = None
    location: Optional[str] = None
    resource: Optional[str] = None
    quantity: Optional[int] = None
    urgency: Optional[str] = "M"
    availability_status: Optional[str] = "A"
    plan_id: Optional[str] = None
    status_code: Optional[int] = None
    source: str = "web"
    payload: Optional[dict] = None


class RejectBody(BaseModel):
    reason: str = "invalid"


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

LOCATION_CODE_MAP = {
    "RA": "RA", "RB": "RB", "RC": "RC", "D1": "D1", "D2": "D2",
    "RegionA": "RA", "Region A": "RA", "RegionB": "RB", "Region B": "RB",
    "RegionC": "RC", "Region C": "RC",
    "DistrictNorth": "D1", "District North": "D1",
    "DistrictSouth": "D2", "District South": "D2",
}

LOCATION_NAME_MAP = {
    "RA": "Region A", "RB": "Region B", "RC": "Region C",
    "D1": "District North", "D2": "District South",
}

# ═══════════════════════════════════════════════════════
# EDIT 2: Chennai demo coordinates (lat, lng) per location code
# ═══════════════════════════════════════════════════════
LOCATION_COORDS = {
    "RA": (13.0499, 80.2824),   # Marina area
    "RB": (13.0418, 80.2341),   # T. Nagar
    "RC": (13.0850, 80.2101),   # Anna Nagar
    "D1": (13.1150, 80.3010),   # Kasimedu (North)
    "D2": (13.0067, 80.2572),   # Adyar (South)
}
CHENNAI_CENTER = (13.0827, 80.2707)

RESOURCE_CODE_TO_NAME = {
    "F": "food_kits", "W": "water_kits", "M": "medical_kits", "T": "tents",
    "B": "blankets", "H": "hygiene_kits", "D": "medical_teams", "U": "unknown",
}
RESOURCE_NAME_TO_CODE = {v: k for k, v in RESOURCE_CODE_TO_NAME.items()}

URGENCY_CODE_TO_NAME = {"L": "low", "M": "medium", "H": "high", "C": "critical"}
URGENCY_NAME_TO_CODE = {v: k for k, v in URGENCY_CODE_TO_NAME.items()}

AVAILABILITY_MAP = {
    "A": "available", "L": "limited", "U": "unavailable",
    "available": "available", "limited": "limited", "unavailable": "unavailable",
}
AVAILABILITY_CODE_TO_NAME = {"A": "available", "L": "limited", "U": "unavailable"}
AVAILABILITY_NAME_TO_CODE = {v: k for k, v in AVAILABILITY_CODE_TO_NAME.items()}

STATUS_CODE_TO_NAME = {
    0: "assigned", 1: "dispatched", 2: "in_transit",
    3: "delivered", 4: "blocked", 5: "cancelled",
}
STATUS_NAME_TO_CODE = {v: k for k, v in STATUS_CODE_TO_NAME.items()}

QUEUE_BY_REQUEST_TYPE = {
    "need": "need_assessment_queue",
    "resource": "resource_matching_queue",
    "status": "coordination_queue",
}


def xor_checksum(text: str) -> str:
    value = 0
    for char in text:
        value ^= ord(char)
    return format(value, "02X")


def map_resource(value: str) -> str:
    value = value.strip()
    if value.upper() in RESOURCE_MAP:
        return RESOURCE_MAP[value.upper()]
    if value.lower() in RESOURCE_MAP:
        return RESOURCE_MAP[value.lower()]
    return value


def map_urgency(value: str) -> str:
    value = value.strip()
    if value.upper() in URGENCY_MAP:
        return URGENCY_MAP[value.upper()]
    if value.lower() in URGENCY_MAP:
        return URGENCY_MAP[value.lower()]
    return value


def map_availability(value: str):
    value = value.strip()
    return AVAILABILITY_MAP.get(value.upper()) or AVAILABILITY_MAP.get(value.lower())


def location_info(location: str):
    location = location.strip()
    code = LOCATION_CODE_MAP.get(location)
    if not code:
        code = location
    name = LOCATION_NAME_MAP.get(code, location)
    return code, name


def resource_code_for(value: str):
    return RESOURCE_NAME_TO_CODE.get(map_resource(value))


def urgency_code_for(value: str):
    return URGENCY_NAME_TO_CODE.get(map_urgency(value))


def availability_code_for(value: str):
    name = map_availability(value)
    return AVAILABILITY_NAME_TO_CODE.get(name) if name else None


def model_to_dict(model):
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def parse_sms(sms: str):
    sms = sms.strip()
    if not sms:
        return {"status": "error", "error": "EMPTY_SMS"}

    parts = sms.split("|")
    message_type = parts[0].strip().upper()

    # Legacy need: N|NGO01|RegionA|food|300|H
    if message_type == "N" and len(parts) == 6:
        organization_id = parts[1].strip()
        location_raw = parts[2].strip()
        resource_raw = parts[3].strip()
        quantity_raw = parts[4].strip()
        urgency_raw = parts[5].strip()
        try:
            quantity = int(quantity_raw)
        except ValueError:
            return {"status": "error", "error": "BAD_QTY"}
        location_code, location_name = location_info(location_raw)
        return {
            "status": "accepted", "mode": "legacy",
            "decoded": {
                "type": "need", "organization_id": organization_id,
                "location_code": location_code, "location_name": location_name,
                "resource": map_resource(resource_raw), "quantity": quantity,
                "urgency": map_urgency(urgency_raw), "source": "sms"
            }
        }

    # Canonical need: N|SEQ|ORG|LOC|RESOURCE|QTY|URGENCY|CRC
    if message_type == "N" and len(parts) == 8:
        body = "|".join(parts[:7])
        received_checksum = parts[7].strip().upper()
        expected_checksum = xor_checksum(body)
        if received_checksum != expected_checksum:
            return {
                "status": "error", "error": "BAD_CRC",
                "expected_checksum": expected_checksum,
                "received_checksum": received_checksum
            }
        seq, organization_id = parts[1].strip(), parts[2].strip()
        location_raw, resource_raw = parts[3].strip(), parts[4].strip()
        quantity_raw, urgency_raw = parts[5].strip(), parts[6].strip()
        try:
            quantity = int(quantity_raw)
        except ValueError:
            return {"status": "error", "error": "BAD_QTY"}
        location_code, location_name = location_info(location_raw)
        return {
            "status": "accepted", "mode": "canonical",
            "decoded": {
                "type": "need", "seq": seq, "organization_id": organization_id,
                "location_code": location_code, "location_name": location_name,
                "resource": map_resource(resource_raw), "quantity": quantity,
                "urgency": map_urgency(urgency_raw),
                "checksum": received_checksum, "source": "sms"
            }
        }

    # Legacy resource: R|CSR02|food|200|A
    if message_type == "R" and len(parts) == 5:
        organization_id = parts[1].strip()
        resource_raw, quantity_raw, availability_raw = parts[2].strip(), parts[3].strip(), parts[4].strip()
        try:
            quantity = int(quantity_raw)
        except ValueError:
            return {"status": "error", "error": "BAD_QTY"}
        availability = map_availability(availability_raw)
        if availability is None:
            return {"status": "error", "error": "UNKNOWN_AVAIL"}
        return {
            "status": "accepted", "mode": "legacy",
            "decoded": {
                "type": "resource", "organization_id": organization_id,
                "location_code": "RA", "location_name": "Region A",
                "resource": map_resource(resource_raw), "quantity": quantity,
                "status": availability, "source": "sms"
            }
        }

    # Canonical resource: R|SEQ|ORG|LOC|RESOURCE|QTY|STATUS|CRC
    if message_type == "R" and len(parts) == 8:
        body = "|".join(parts[:7])
        received_checksum = parts[7].strip().upper()
        expected_checksum = xor_checksum(body)
        if received_checksum != expected_checksum:
            return {
                "status": "error", "error": "BAD_CRC",
                "expected_checksum": expected_checksum,
                "received_checksum": received_checksum
            }
        seq, organization_id = parts[1].strip(), parts[2].strip()
        location_raw, resource_raw = parts[3].strip(), parts[4].strip()
        quantity_raw, availability_raw = parts[5].strip(), parts[6].strip()
        try:
            quantity = int(quantity_raw)
        except ValueError:
            return {"status": "error", "error": "BAD_QTY"}
        availability = map_availability(availability_raw)
        if availability is None:
            return {"status": "error", "error": "UNKNOWN_AVAIL"}
        location_code, location_name = location_info(location_raw)
        return {
            "status": "accepted", "mode": "canonical",
            "decoded": {
                "type": "resource", "seq": seq, "organization_id": organization_id,
                "location_code": location_code, "location_name": location_name,
                "resource": map_resource(resource_raw), "quantity": quantity,
                "status": availability, "checksum": received_checksum, "source": "sms"
            }
        }

    # Canonical status: S|SEQ|PLAN|STATUS|CRC
    if message_type == "S" and len(parts) == 5:
        body = "|".join(parts[:4])
        received_checksum = parts[4].strip().upper()
        expected_checksum = xor_checksum(body)
        if received_checksum != expected_checksum:
            return {
                "status": "error", "error": "BAD_CRC",
                "expected_checksum": expected_checksum,
                "received_checksum": received_checksum
            }
        seq, plan_id, status_raw = parts[1].strip(), parts[2].strip().upper(), parts[3].strip()
        try:
            status_code = int(status_raw)
        except ValueError:
            return {"status": "error", "error": "BAD_FMT"}
        if status_code not in STATUS_CODE_TO_NAME:
            return {"status": "error", "error": "UNKNOWN_STATUS"}
        return {
            "status": "accepted", "mode": "canonical",
            "decoded": {
                "type": "status", "seq": seq, "plan_id": plan_id,
                "status": STATUS_CODE_TO_NAME[status_code],
                "status_code": status_code,
                "checksum": received_checksum, "source": "sms"
            }
        }

    return {
        "status": "accepted", "message": "SMS received",
        "raw_sms": sms, "note": "This SMS type is not fully decoded yet"
    }


# =====================================================================
# REQUEST HUB - in-memory store + simulated agent bus (no Redis for MVP)
# =====================================================================

REQUESTS = {}
PLANS = {}
AGENT_ACTIVITY = []
ORGANIZATIONS = {}
PROCESSED_SEQS = set()

_REQUEST_COUNTER = itertools.count(1)
_SEQ_COUNTER = itertools.count(6)
_PLAN_COUNTER = itertools.count(101)

AGENT_DELAY_SECONDS = 1.2
AUTO_ACCEPT_WEB = False

BANNED_KEYWORDS = (
    "donor", "funding", "staff", "volunteer", "beneficiary",
    "warehouse", "salary", "bank_account", "password", "personal_id",
    "operational_plan", "security_detail",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def next_request_id() -> str:
    return f"REQ-{next(_REQUEST_COUNTER):03d}"


def next_seq() -> str:
    return f"{next(_SEQ_COUNTER):03d}"


def next_plan_id() -> str:
    return f"PLAN-{next(_PLAN_COUNTER):03d}"


def add_activity(agent: str, message: str):
    AGENT_ACTIVITY.append({"ts": now_iso(), "agent": agent, "message": message})
    if len(AGENT_ACTIVITY) > 200:
        del AGENT_ACTIVITY[: len(AGENT_ACTIVITY) - 200]


def build_canonical_sms(rec: dict):
    seq = rec.get("seq", "000")
    if rec["type"] == "need":
        body = (f"N|{seq}|{rec['organization_id']}|{rec.get('location_code')}"
                f"|{rec.get('resource_code')}|{rec.get('quantity')}|{rec.get('urgency_code')}")
    elif rec["type"] == "resource":
        body = (f"R|{seq}|{rec['organization_id']}|{rec.get('location_code')}"
                f"|{rec.get('resource_code')}|{rec.get('quantity')}|{rec.get('availability_code')}")
    elif rec["type"] == "status":
        body = f"S|{seq}|{rec.get('plan_id')}|{rec.get('status_code')}"
    else:
        return None
    return f"{body}|{xor_checksum(body)}"


def finalize_request(rec: dict) -> dict:
    rec["sms_canonical"] = build_canonical_sms(rec)
    if rec["sms_canonical"]:
        rec["checksum"] = xor_checksum(rec["sms_canonical"].rsplit("|", 1)[0])
    REQUESTS[rec["id"]] = rec
    return rec


# ═══════════════════════════════════════════════════════
# EDIT 4: Added Chennai coordinates inside create_request_from_sms
# ═══════════════════════════════════════════════════════
def create_request_from_sms(decoded: dict):
    request_type = decoded.get("type")
    if request_type not in ("need", "resource", "status"):
        return None

    organization_id = (decoded.get("organization_id") or "UNKNOWN").strip().upper()
    rec = {
        "id": next_request_id(), "type": request_type,
        "seq": decoded.get("seq") or next_seq(),
        "organization_id": organization_id, "source": "sms",
        "payload": decoded, "created_at": now_iso(),
        "reviewed_at": None, "reject_reason": None,
    }

    if request_type == "need":
        location_code = decoded.get("location_code") or "RA"
        resource_name = map_resource(decoded.get("resource", "U"))
        urgency_name = map_urgency(decoded.get("urgency", "M"))
        rec.update(
            location_code=location_code,
            location_name=decoded.get("location_name") or LOCATION_NAME_MAP.get(location_code, location_code),
            resource=resource_name, resource_code=RESOURCE_NAME_TO_CODE.get(resource_name, "U"),
            quantity=int(decoded.get("quantity") or 0),
            urgency=urgency_name, urgency_code=URGENCY_NAME_TO_CODE.get(urgency_name, "M"),
        )
    elif request_type == "resource":
        location_code = decoded.get("location_code") or "RA"
        resource_name = map_resource(decoded.get("resource", "U"))
        availability_name = map_availability(decoded.get("status", "available")) or "available"
        rec.update(
            location_code=location_code,
            location_name=decoded.get("location_name") or LOCATION_NAME_MAP.get(location_code, location_code),
            resource=resource_name, resource_code=RESOURCE_NAME_TO_CODE.get(resource_name, "U"),
            quantity=int(decoded.get("quantity") or 0),
            availability=availability_name,
            availability_code=AVAILABILITY_NAME_TO_CODE.get(availability_name, "A"),
        )
    else:
        rec.update(
            plan_id=(decoded.get("plan_id") or "").strip().upper(),
            status_code=decoded.get("status_code", STATUS_NAME_TO_CODE.get(decoded.get("status"), 0)),
        )

    # Attach Chennai coordinates for map display
    loc = rec.get("location_code")
    if loc in LOCATION_COORDS:
        rec["latitude"], rec["longitude"] = LOCATION_COORDS[loc]

    key = (rec["organization_id"], rec["seq"])
    rec["status"] = "duplicate" if key in PROCESSED_SEQS else "pending"
    finalize_request(rec)
    add_activity("SMS Gateway", f"SMS from {rec['organization_id']} decoded -> {rec['id']} ({request_type})")
    return rec


# ═══════════════════════════════════════════════════════
# EDIT 3: GPS — prefer real device coords, else Chennai fallback
# ═══════════════════════════════════════════════════════
def create_request_from_need(payload: NeedRequest):
    location_code, location_name = location_info(payload.location_code)
    resource_name = map_resource(payload.resource)
    urgency_name = map_urgency(payload.urgency)

    latitude = payload.latitude
    longitude = payload.longitude
    if latitude is None or longitude is None or (latitude == 0 and longitude == 0):
        latitude, longitude = LOCATION_COORDS.get(location_code, CHENNAI_CENTER)

    rec = {
        "id": next_request_id(), "type": "need", "seq": next_seq(),
        "organization_id": payload.organization_id.strip().upper(),
        "location_code": location_code, "location_name": location_name,
        "resource": resource_name, "resource_code": RESOURCE_NAME_TO_CODE.get(resource_name, "U"),
        "quantity": payload.quantity,
        "urgency": urgency_name, "urgency_code": URGENCY_NAME_TO_CODE.get(urgency_name, "M"),
        "latitude": latitude,
        "longitude": longitude,
        "source": payload.source if payload.source in ("web", "sms", "android") else "web",
        "payload": model_to_dict(payload),
        "created_at": now_iso(), "reviewed_at": None, "reject_reason": None,
        "status": "pending",
    }
    finalize_request(rec)
    return rec


# ═══════════════════════════════════════════════════════
# EDIT 5: seed_request now attaches Chennai coordinates
# ═══════════════════════════════════════════════════════
def seed_demo_data():
    if REQUESTS:
        return

    ORGANIZATIONS.update({
        "NGO01": {"name": "NGO Alpha", "resources": {"M": 150}, "eta_hours": 3, "radius_km": 50},
        "CSR02": {"name": "CSR Beta", "resources": {"F": 600, "M": 200}, "eta_hours": 4, "radius_km": 80},
        "GOV03": {"name": "Gov Gamma", "resources": {"W": 400, "F": 100}, "eta_hours": 6, "radius_km": 120},
    })

    def seed_request(**fields):
        rec = {
            "id": next_request_id(), "status": "pending", "source": "web",
            "payload": {}, "checksum": None, "created_at": now_iso(),
            "reviewed_at": None, "reject_reason": None,
            "latitude": None, "longitude": None,
        }
        rec.update(fields)
        loc = rec.get("location_code")
        if rec.get("latitude") is None and loc in LOCATION_COORDS:
            rec["latitude"], rec["longitude"] = LOCATION_COORDS[loc]
        return finalize_request(rec)

    seed_request(type="need", seq="001", organization_id="NGO01", source="sms",
                 location_code="RA", location_name="Region A",
                 resource="food_kits", resource_code="F", quantity=300,
                 urgency="high", urgency_code="H")
    seed_request(type="need", seq="002", organization_id="NGO01", source="web",
                 location_code="RA", location_name="Region A",
                 resource="medical_kits", resource_code="M", quantity=200,
                 urgency="critical", urgency_code="C")
    seed_request(type="resource", seq="003", organization_id="CSR02", source="sms",
                 location_code="RA", location_name="Region A",
                 resource="food_kits", resource_code="F", quantity=200,
                 availability="available", availability_code="A")
    seed_request(type="need", seq="004", organization_id="CSR02", source="android",
                 location_code="RB", location_name="Region B",
                 resource="tents", resource_code="T", quantity=120,
                 urgency="medium", urgency_code="M")
    seed_request(type="status", seq="005", organization_id="GOV03", source="sms",
                 plan_id="PLAN-100", status_code=3)

    PLANS["PLAN-100"] = {
        "plan_id": "PLAN-100", "request_id": None,
        "resource": "food_kits", "resource_code": "F",
        "location_code": "RA", "location_name": "Region A",
        "required_quantity": 300, "allocated_quantity": 300,
        "allocations": [
            {"organization_id": "CSR02", "quantity": 200, "eta_hours": 4},
            {"organization_id": "GOV03", "quantity": 100, "eta_hours": 6},
        ],
        "priority": "high", "status": "delivered", "created_at": now_iso(),
    }

    add_activity("System", "Request Hub online - 3 organizations registered")
    add_activity("SMS Gateway", "SMS from NGO01 decoded -> REQ-001 (need)")
    add_activity("SMS Gateway", "SMS from CSR02 decoded -> REQ-003 (resource)")
    add_activity("Coordination Agent", "PLAN-100 delivered to Region A")


def check_checksum(rec: dict) -> bool:
    sms = rec.get("sms_canonical")
    if not sms or "|" not in sms:
        return True
    body, _, crc = sms.rpartition("|")
    return xor_checksum(body) == crc.upper()


def check_duplicate(rec: dict) -> bool:
    return (rec.get("organization_id"), rec.get("seq")) in PROCESSED_SEQS


def check_privacy(rec: dict) -> bool:
    blob = json.dumps(rec.get("payload") or {}).lower()
    blob += " " + json.dumps({k: v for k, v in rec.items() if isinstance(v, str)}).lower()
    return not any(keyword in blob for keyword in BANNED_KEYWORDS)


def validate_for_accept(rec: dict):
    if not check_checksum(rec):
        return False, "BAD_CRC"
    if check_duplicate(rec):
        return False, "DUP"
    if not check_privacy(rec):
        return False, "PRIVACY"
    return True, None


async def do_accept(rec: dict):
    ok, reason = validate_for_accept(rec)
    rec["reviewed_at"] = now_iso()
    if not ok:
        rec["status"] = "duplicate" if reason == "DUP" else "rejected"
        rec["reject_reason"] = reason
        agent = "Privacy Filter Agent" if reason == "PRIVACY" else "Validator"
        add_activity(agent, f"{rec['id']}: auto-rejected ({reason})")
        return rec, False, reason

    rec["status"] = "accepted"
    PROCESSED_SEQS.add((rec.get("organization_id"), rec.get("seq")))
    publish_to_agent_bus(rec)
    return rec, True, None


def publish_to_agent_bus(rec: dict):
    queue = QUEUE_BY_REQUEST_TYPE[rec["type"]]
    add_activity("Coordinator", f"{rec['id']} accepted -> {queue}")
    asyncio.create_task(simulate_agent_pipeline(rec))


async def simulate_agent_pipeline(rec: dict):
    try:
        if rec["type"] == "need":
            await run_need_pipeline(rec["id"])
        elif rec["type"] == "resource":
            await run_resource_pipeline(rec["id"])
        else:
            await run_status_pipeline(rec["id"])
    except Exception as exc:
        add_activity("System", f"agent pipeline error for {rec['id']}: {exc}")


async def run_need_pipeline(request_id: str):
    rec = REQUESTS.get(request_id)
    if not rec:
        return
    resource_code = rec.get("resource_code") or "U"
    resource_name = rec.get("resource") or "unknown"
    quantity = rec.get("quantity") or 0
    location_label = rec.get("location_name") or rec.get("location_code") or "?"

    await asyncio.sleep(AGENT_DELAY_SECONDS)
    rec["status"] = "processing"
    add_activity("Need Assessment Agent",
                 f"{request_id}: need at {location_label} - {quantity} x {resource_name}, urgency {rec.get('urgency')}")

    matches = []
    for org_id, org in ORGANIZATIONS.items():
        if org_id == rec.get("organization_id"):
            continue
        available = org["resources"].get(resource_code, 0)
        if available > 0:
            matches.append({"organization_id": org_id, "quantity": available, "eta_hours": org["eta_hours"]})

    await asyncio.sleep(AGENT_DELAY_SECONDS)
    rec["status"] = "matched"
    add_activity("Resource Matching Agent",
                 f"{request_id}: found {sum(m['quantity'] for m in matches)} {resource_name} across {len(matches)} organization(s)")

    remaining = quantity
    allocations = []
    for match in sorted(matches, key=lambda m: m["eta_hours"]):
        if remaining <= 0:
            break
        take = min(remaining, match["quantity"])
        allocations.append({"organization_id": match["organization_id"], "quantity": take, "eta_hours": match["eta_hours"]})
        ORGANIZATIONS[match["organization_id"]]["resources"][resource_code] -= take
        remaining -= take

    allocated_quantity = sum(a["quantity"] for a in allocations)
    if remaining <= 0:
        plan_status = "ready_for_dispatch"
    elif allocated_quantity > 0:
        plan_status = "partial"
    else:
        plan_status = "no_suppliers"

    plan = {
        "plan_id": next_plan_id(), "request_id": request_id,
        "resource": resource_name, "resource_code": resource_code,
        "location_code": rec.get("location_code"), "location_name": location_label,
        "required_quantity": quantity, "allocated_quantity": allocated_quantity,
        "allocations": allocations, "priority": rec.get("urgency"),
        "status": plan_status, "created_at": now_iso(),
    }
    PLANS[plan["plan_id"]] = plan

    await asyncio.sleep(AGENT_DELAY_SECONDS)
    rec["status"] = "allocated"
    rec["plan_id"] = plan["plan_id"]
    detail = ", ".join(f"{a['quantity']} from {a['organization_id']}" for a in allocations) or "no suppliers found"
    add_activity("Coordination Agent", f"{request_id}: created {plan['plan_id']} - {detail}")


async def run_resource_pipeline(request_id: str):
    rec = REQUESTS.get(request_id)
    if not rec:
        return
    org_id = rec.get("organization_id")
    resource_code = rec.get("resource_code") or "U"
    resource_name = rec.get("resource") or "unknown"
    quantity = rec.get("quantity") or 0

    await asyncio.sleep(AGENT_DELAY_SECONDS)
    rec["status"] = "processing"
    add_activity("Resource Matching Agent", f"{request_id}: registering {quantity} x {resource_name} from {org_id}")

    org = ORGANIZATIONS.setdefault(org_id, {"name": org_id, "resources": {}, "eta_hours": 4, "radius_km": 50})
    org["resources"][resource_code] = org["resources"].get(resource_code, 0) + quantity

    await asyncio.sleep(AGENT_DELAY_SECONDS)
    rec["status"] = "completed"
    add_activity("Resource Matching Agent", f"{request_id}: {org_id} now holds {org['resources'][resource_code]} {resource_name}")


async def run_status_pipeline(request_id: str):
    rec = REQUESTS.get(request_id)
    if not rec:
        return
    await asyncio.sleep(AGENT_DELAY_SECONDS)
    rec["status"] = "processing"
    plan_id = rec.get("plan_id")
    status_name = STATUS_CODE_TO_NAME.get(rec.get("status_code"), "unknown")
    add_activity("Coordination Agent", f"{request_id}: status '{status_name}' received for {plan_id}")

    plan = PLANS.get(plan_id)
    await asyncio.sleep(AGENT_DELAY_SECONDS)
    if plan:
        plan["status"] = "delivered" if rec.get("status_code") == 3 else status_name
        add_activity("Coordination Agent", f"{plan_id}: plan status -> {plan['status']}")
    else:
        add_activity("Coordination Agent", f"{plan_id}: plan not found - status logged only")
    rec["status"] = "completed"


@app.get("/")
def root():
    return {"message": "Backend is running", "docs": "/docs", "health": "/api/v1/health"}


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": "humanitarian-coordination-backend", "version": "0.2.0"}


@app.post("/api/v1/needs")
def create_need(payload: NeedRequest):
    hub_request = create_request_from_need(payload)
    return {
        "status": "accepted", "need_id": "NEED_101",
        "message": "Need received by backend", "data": payload,
        "hub_request_id": hub_request["id"],
    }


@app.post("/api/v1/sms/webhook")
def sms_webhook(payload: SmsWebhookRequest):
    result = parse_sms(payload.sms)
    decoded = result.get("decoded")
    if result.get("status") == "accepted" and isinstance(decoded, dict) \
            and decoded.get("type") in ("need", "resource", "status"):
        hub_request = create_request_from_sms(decoded)
        if hub_request:
            result["hub_request_id"] = hub_request["id"]
    return result


@app.get("/api/v1/requests")
def list_requests(status: Optional[str] = None, type: Optional[str] = None, source: Optional[str] = None):
    items = list(REQUESTS.values())
    if status:
        items = [r for r in items if r.get("status") == status]
    if type:
        items = [r for r in items if r.get("type") == type]
    if source:
        items = [r for r in items if r.get("source") == source]
    items.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return {"count": len(items), "requests": items}


@app.post("/api/v1/requests", status_code=201)
async def create_request(body: HubRequestCreate):
    request_type = body.type.strip().lower()
    if request_type not in ("need", "resource", "status"):
        raise HTTPException(status_code=422, detail="type must be need, resource or status")

    rec = {
        "id": next_request_id(), "type": request_type,
        "seq": body.seq or next_seq(),
        "organization_id": body.organization_id.strip().upper(),
        "source": body.source if body.source in ("web", "sms", "android") else "web",
        "payload": body.payload or model_to_dict(body),
        "created_at": now_iso(), "reviewed_at": None, "reject_reason": None,
    }

    if request_type in ("need", "resource"):
        if not body.location or not body.resource or not body.quantity or body.quantity <= 0:
            raise HTTPException(status_code=422, detail="need/resource requires location, resource and quantity > 0")
        location_code, location_name = location_info(body.location)
        if location_code not in LOCATION_NAME_MAP:
            raise HTTPException(status_code=422, detail=f"unknown location '{body.location}'")
        resource_name = map_resource(body.resource)
        resource_code = RESOURCE_NAME_TO_CODE.get(resource_name)
        if not resource_code:
            raise HTTPException(status_code=422, detail=f"unknown resource '{body.resource}'")

        rec.update(location_code=location_code, location_name=location_name,
                   resource=resource_name, resource_code=resource_code, quantity=body.quantity)

        if request_type == "need":
            urgency_code = urgency_code_for(body.urgency or "M")
            if not urgency_code:
                raise HTTPException(status_code=422, detail=f"unknown urgency '{body.urgency}'")
            rec["urgency_code"] = urgency_code
            rec["urgency"] = URGENCY_CODE_TO_NAME[urgency_code]
        else:
            availability_code = availability_code_for(body.availability_status or "A")
            if not availability_code:
                raise HTTPException(status_code=422, detail=f"unknown availability '{body.availability_status}'")
            rec["availability_code"] = availability_code
            rec["availability"] = AVAILABILITY_CODE_TO_NAME[availability_code]
    else:
        if not body.plan_id or body.status_code is None or body.status_code not in STATUS_CODE_TO_NAME:
            raise HTTPException(status_code=422, detail="status requires plan_id and status_code between 0 and 5")
        rec["plan_id"] = body.plan_id.strip().upper()
        rec["status_code"] = body.status_code

    # Bonus: attach Chennai coordinates so web-form requests also appear on the map
    loc = rec.get("location_code")
    if loc in LOCATION_COORDS:
        rec["latitude"], rec["longitude"] = LOCATION_COORDS[loc]

    key = (rec["organization_id"], rec["seq"])
    rec["status"] = "duplicate" if key in PROCESSED_SEQS else "pending"
    finalize_request(rec)

    if AUTO_ACCEPT_WEB and rec["source"] == "web" and rec["status"] == "pending":
        rec, _, _ = await do_accept(rec)
    return rec


@app.post("/api/v1/requests/{request_id}/accept")
async def accept_request(request_id: str):
    rec = REQUESTS.get(request_id)
    if not rec:
        raise HTTPException(status_code=404, detail="request not found")
    if rec.get("status") != "pending":
        raise HTTPException(status_code=409, detail=f"request is '{rec.get('status')}', only 'pending' can be accepted")
    rec, accepted, reason = await do_accept(rec)
    return {"accepted": accepted, "auto_reject_reason": reason, "request": rec}


@app.post("/api/v1/requests/{request_id}/reject")
def reject_request(request_id: str, body: RejectBody):
    rec = REQUESTS.get(request_id)
    if not rec:
        raise HTTPException(status_code=404, detail="request not found")
    if rec.get("status") != "pending":
        raise HTTPException(status_code=409, detail=f"request is '{rec.get('status')}', only 'pending' can be rejected")
    rec["status"] = "rejected"
    rec["reject_reason"] = body.reason.strip() or "invalid"
    rec["reviewed_at"] = now_iso()
    add_activity("Coordinator", f"{request_id} rejected ({rec['reject_reason']})")
    return rec


@app.get("/api/v1/plans")
def list_plans():
    items = sorted(PLANS.values(), key=lambda p: p.get("created_at", ""), reverse=True)
    return {"count": len(items), "plans": items}


@app.get("/api/v1/agent-activity")
def agent_activity(limit: int = 50):
    return {"activity": list(reversed(AGENT_ACTIVITY[-limit:]))}


@app.get("/api/v1/config/auto-accept")
def get_auto_accept():
    return {"enabled": AUTO_ACCEPT_WEB}


@app.post("/api/v1/config/auto-accept")
def set_auto_accept(enabled: bool = True):
    global AUTO_ACCEPT_WEB
    AUTO_ACCEPT_WEB = enabled
    return {"enabled": AUTO_ACCEPT_WEB}


@app.on_event("startup")
def seed_request_hub_on_startup():
    seed_demo_data()


# =====================================================================
# FAKE SMS INBOX (For Android Polling Demo)
# =====================================================================
fake_sms_inbox = []


@app.get("/api/v1/sms/inbox")
def get_sms_inbox():
    """Android app polls this to get pending fake SMS messages"""
    return {"messages": fake_sms_inbox}


@app.post("/api/v1/sms/clear")
def clear_sms_inbox():
    """Android app clears the inbox after reading messages"""
    fake_sms_inbox.clear()
    return {"status": "cleared"}


@app.post("/api/v1/sms/push")
def push_fake_sms(payload: dict):
    """Use this to send a fake SMS from backend/web to the Android app"""
    msg = payload.get("message", "")
    if msg:
        fake_sms_inbox.append(msg)
    return {"status": "pushed", "count": len(fake_sms_inbox)}