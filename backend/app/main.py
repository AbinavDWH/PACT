import asyncio
import itertools
import json
import os
import urllib.request
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import db


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


class ConfirmHandoverBody(BaseModel):
    plan_id: Optional[str] = None
    request_id: Optional[str] = None
    organization_id: Optional[str] = None
    notes: Optional[str] = None


class ConfirmReceivedBody(BaseModel):
    plan_id: Optional[str] = None
    request_id: Optional[str] = None
    organization_id: Optional[str] = None
    notes: Optional[str] = None


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

# Chennai demo coordinates (lat, lng) per location code
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

# Human-readable labels for provider inventory
RESOURCE_CODE_LABELS = {
    "F": "Food kits", "W": "Water kits", "M": "Medical kits", "T": "Tents",
    "B": "Blankets", "H": "Hygiene kits", "D": "Medical teams", "U": "Unknown",
}

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


def parse_sms_location(loc):
    """Detect 'lat,lng' in an SMS location field (sms.md section 10)."""
    if not loc or "," not in str(loc):
        return None
    try:
        lat_s, lng_s = str(loc).split(",")[:2]
        return float(lat_s.strip()), float(lng_s.strip())
    except (ValueError, TypeError):
        return None


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
# REQUEST HUB - SQLite Persistent Store + Live Memory Cache
# =====================================================================

REQUESTS = {}
PLANS = {}
AGENT_ACTIVITY = []
ORGANIZATIONS = {}
PROCESSED_SEQS = set()
OUTBOUND_SMS_QUEUE = {}
GATEWAY_ACTIVITY_LOGS = []

ORG_PHONE_MAP = {
    "NGO01": "+919876543210",
    "CSR02": "+919876543211",
    "GOV03": "+919876543212",
    "ADMIN01": "+919876543200",
}

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def next_request_id() -> str:
    val = db.get_next_sequence("request_id", 1)
    return f"REQ-{val:03d}"

def next_seq() -> str:
    val = db.get_next_sequence("sms_seq", 1)
    return f"{val:03d}"

def next_plan_id() -> str:
    val = db.get_next_sequence("plan_id", 101)
    return f"PLAN-{val:03d}"

def next_outbound_sms_id() -> str:
    val = db.get_next_sequence("sms_out_id", 1)
    return f"SMS-OUT-{val:03d}"

def add_gateway_log(direction: str, from_to: str, message: str, status: str, detail: str = ""):
    entry = {
        "id": f"GW-{db.get_next_sequence('gw_log_id', 1):04d}",
        "ts": now_iso(),
        "direction": direction,
        "from_to": from_to,
        "message": message,
        "status": status,
        "detail": detail
    }
    db.save_gateway_log(entry)
    GATEWAY_ACTIVITY_LOGS.append(entry)
    if len(GATEWAY_ACTIVITY_LOGS) > 300:
        del GATEWAY_ACTIVITY_LOGS[: len(GATEWAY_ACTIVITY_LOGS) - 300]

def add_activity(agent: str, message: str):
    entry = db.save_activity(agent, message, now_iso())
    AGENT_ACTIVITY.append(entry)
    if len(AGENT_ACTIVITY) > 300:
        del AGENT_ACTIVITY[: len(AGENT_ACTIVITY) - 300]

def queue_outbound_sms(to_number: str, message: str, msg_type: str = "allocation", plan_id: Optional[str] = None):
    sms_id = next_outbound_sms_id()
    item = {
        "id": sms_id,
        "to_number": to_number,
        "message": message,
        "type": msg_type,
        "plan_id": plan_id,
        "status": "pending",
        "created_at": now_iso(),
        "dispatched_at": None,
        "error": None
    }
    OUTBOUND_SMS_QUEUE[sms_id] = item
    db.save_outbound_sms(item)
    add_gateway_log(
        direction="OUTBOUND",
        from_to=to_number,
        message=message,
        status="QUEUED_ON_SERVER",
        detail=f"Queued for mobile gateway dispatch ({msg_type})"
    )
    return item

AGENT_DELAY_SECONDS = 1.2
AUTO_ACCEPT_WEB = False

# ═══════════════════════════════════════════════════════
# GROQ AI CONFIG — agents powered by Llama 3.3 70B
# If GROQ_API_KEY is missing, pipeline falls back to
# deterministic logic so the demo never breaks.
# ═══════════════════════════════════════════════════════
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

BANNED_KEYWORDS = (
    "donor", "funding", "staff", "volunteer", "beneficiary",
    "warehouse", "salary", "bank_account", "password", "personal_id",
    "operational_plan", "security_detail",
)


def build_canonical_sms(rec: dict):
    seq = rec.get("seq", "000")
    if rec["type"] == "need":
        lat, lng = rec.get("latitude"), rec.get("longitude")
        loc_val = f"{lat:.4f},{lng:.4f}" if (lat and lng and (lat != 0 or lng != 0)) else rec.get("location_code", "RA")
        body = (f"N|{seq}|{rec['organization_id']}|{loc_val}"
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
    db.save_request(rec)
    return rec


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

    # NEW: SMS loc field may carry real GPS ("lat,lng") — sms.md section 10
    gps = parse_sms_location(rec.get("location_code"))
    if gps:
        rec["latitude"], rec["longitude"] = gps
        rec["location_name"] = rec.get("location_name") or f"GPS {rec['location_code']}"
    else:
        # Chennai fallback per location code
        loc = rec.get("location_code")
        if loc in LOCATION_COORDS:
            rec["latitude"], rec["longitude"] = LOCATION_COORDS[loc]

    key = (rec["organization_id"], rec["seq"])
    rec["status"] = "duplicate" if key in PROCESSED_SEQS else "pending"
    finalize_request(rec)
    add_activity("SMS Gateway", f"SMS from {rec['organization_id']} decoded -> {rec['id']} ({request_type})")
    return rec


def create_request_from_need(payload: NeedRequest):
    location_code, location_name = location_info(payload.location_code)
    resource_name = map_resource(payload.resource)
    urgency_name = map_urgency(payload.urgency)

    # GPS: prefer real device coords, else Chennai fallback
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


def init_db_and_load_state():
    """
    Initializes SQLite database tables and loads all persistent historical records.
    Zero mock data. Everything is sourced from real field transmissions and database records.
    """
    db.init_db()

    # 1. Load Requests
    loaded_requests = db.load_all_requests()
    REQUESTS.clear()
    REQUESTS.update(loaded_requests)

    # 2. Load Organizations
    loaded_orgs = db.load_all_organizations()
    ORGANIZATIONS.clear()
    ORGANIZATIONS.update(loaded_orgs)

    # 3. Load Plans
    loaded_plans = db.load_all_plans()
    PLANS.clear()
    PLANS.update(loaded_plans)

    # 4. Load Outbound SMS Queue
    loaded_sms = db.load_all_outbound_sms()
    OUTBOUND_SMS_QUEUE.clear()
    OUTBOUND_SMS_QUEUE.update(loaded_sms)

    # 5. Load Gateway Logs & Activity Logs
    loaded_gw = db.load_gateway_logs(300)
    GATEWAY_ACTIVITY_LOGS.clear()
    GATEWAY_ACTIVITY_LOGS.extend(loaded_gw)

    loaded_acts = db.load_activities(300)
    AGENT_ACTIVITY.clear()
    AGENT_ACTIVITY.extend(loaded_acts)

    # 6. Populate Processed Sequence Cache to prevent replay attacks
    PROCESSED_SEQS.clear()
    for r in REQUESTS.values():
        if r.get("organization_id") and r.get("seq"):
            PROCESSED_SEQS.add((r["organization_id"], r["seq"]))

    # 7. Initialize baseline organization directories if clean database
    if not ORGANIZATIONS:
        baseline_orgs = {
            "NGO01": {"name": "NGO Alpha", "resources": {}, "eta_hours": 3, "radius_km": 50, "phone": "+919876543210"},
            "CSR02": {"name": "CSR Beta", "resources": {}, "eta_hours": 4, "radius_km": 80, "phone": "+919876543211"},
            "GOV03": {"name": "Gov Gamma", "resources": {}, "eta_hours": 6, "radius_km": 120, "phone": "+919876543212"},
        }
        for org_id, org_data in baseline_orgs.items():
            ORGANIZATIONS[org_id] = org_data
            db.save_organization(org_id, org_data)

    add_activity("System", f"ResiLink SQLite DB Online · {len(REQUESTS)} request(s), {len(PLANS)} plan(s), {len(ORGANIZATIONS)} partner org(s) loaded.")


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


def check_anomaly_and_rate_limit(rec: dict) -> tuple[bool, Optional[str]]:
    """
    AI Anomaly & Safety Rule Engine:
    1. Quantity Too High Check (Excessive quota abuse)
    2. Frequency / Repeated Resource Request Check (Same ID spamming same resource)
    3. Medical Supply Quota & Hoarding Check (Medical items requested repeatedly by same ID)
    """
    if rec.get("type") != "need":
        return True, None

    org_id = (rec.get("organization_id") or "").strip().upper()
    resource_code = (rec.get("resource_code") or "U").upper()
    resource_name = (rec.get("resource") or "").lower()
    qty = int(rec.get("quantity") or 0)
    is_medical = (resource_code in ("M", "D") or "medical" in resource_name or "medicine" in resource_name)

    # 1. QUANTITY ANOMALY: Request too high
    max_threshold = 1000 if is_medical else 5000
    if qty > max_threshold:
        return False, f"EXCESSIVE_QUANTITY (Requested {qty} units exceeds safety threshold of {max_threshold})"

    # 2. FREQUENCY CHECK: Count existing active requests by same org for same resource
    recent_same_resource = [
        r for r in REQUESTS.values()
        if r.get("organization_id") == org_id
        and r.get("resource_code") == resource_code
        and r.get("id") != rec.get("id")
        and r.get("status") not in ("rejected", "duplicate", "delivered")
    ]
    if len(recent_same_resource) >= 3:
        return False, f"FREQUENCY_LIMIT (Org {org_id} has {len(recent_same_resource)} active requests for {resource_code})"

    # 3. MEDICAL QUOTA & HOARDING CHECK: Medical items requested repeatedly by same ID
    if is_medical:
        all_medical_reqs = [
            r for r in REQUESTS.values()
            if r.get("organization_id") == org_id
            and (r.get("resource_code") in ("M", "D") or "medical" in (r.get("resource") or "").lower())
            and r.get("id") != rec.get("id")
            and r.get("status") not in ("rejected", "duplicate", "delivered")
        ]
        total_medical_qty = sum(int(r.get("quantity") or 0) for r in all_medical_reqs) + qty
        if len(all_medical_reqs) >= 2 or total_medical_qty > 2000:
            return False, f"MEDICAL_QUOTA_EXCEEDED (Org {org_id} medical requests exceed maximum field quota)"

    return True, None


def validate_for_accept(rec: dict):
    if not check_checksum(rec):
        return False, "BAD_CRC"
    if check_duplicate(rec):
        return False, "DUP"
    if not check_privacy(rec):
        return False, "PRIVACY"
    
    ok_anomaly, reason_anomaly = check_anomaly_and_rate_limit(rec)
    if not ok_anomaly:
        return False, reason_anomaly
        
    return True, None


# ═══════════════════════════════════════════════════════
# GROQ HELPERS
# ═══════════════════════════════════════════════════════

def groq_chat_sync(system_prompt: str, user_prompt: str, temperature: float = 0.2, max_tokens: int = 600):
    """Synchronous Groq call. Returns response text or None on any failure."""
    if not GROQ_API_KEY:
        return None
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        GROQ_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
    except Exception:
        return None


def extract_json(text):
    """Parse JSON from an LLM response, tolerating markdown fences."""
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except Exception:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                return None
    return None


async def groq_json_async(system_prompt: str, user_prompt: str, temperature: float = 0.2):
    """Async Groq call returning parsed JSON dict or None."""
    text = await asyncio.to_thread(groq_chat_sync, system_prompt, user_prompt, temperature)
    return extract_json(text)


# ───────────── AI PRIVACY FLAG (on Accept) ─────────────

async def ai_flag_request(rec: dict):
    """Privacy Filter Agent (AI): scan request for sensitive data."""
    if not GROQ_API_KEY:
        return None
    payload = rec.get("payload") or {}
    notes = str(payload.get("notes", "")) if isinstance(payload, dict) else ""
    summary = {
        "type": rec.get("type"),
        "organization_id": rec.get("organization_id"),
        "location": rec.get("location_name") or rec.get("location_code"),
        "resource": rec.get("resource"),
        "quantity": rec.get("quantity"),
        "urgency": rec.get("urgency"),
        "notes": notes,
        "source": rec.get("source"),
    }
    system = (
        "You are the Privacy Filter Agent of a humanitarian coordination platform. "
        "Detect sensitive data that must never be shared: donor names, funding details, "
        "staff or volunteer names, exact warehouse addresses, beneficiary personal data, "
        "bank details, security or operational secrets. "
        "Respond ONLY with JSON: "
        '{"flagged": true|false, "risk_level": "none|low|high", "reasons": ["..."], "summary": "one short sentence"}'
    )
    user = f"Request to validate:\n{json.dumps(summary)}"
    result = await groq_json_async(system, user, temperature=0.0)
    if result and isinstance(result.get("flagged"), bool):
        return result
    return None


# ───────────── AI MATCHING (Resource Matching Agent) ─────────────

async def ai_enhance_matching(rec: dict, deterministic_matches: list):
    """Ask Groq to decide provider quantities. Falls back to deterministic matches."""
    if not GROQ_API_KEY or not deterministic_matches:
        return deterministic_matches, None
    inventory = json.dumps([
        {"organization_id": m["organization_id"], "available": m["quantity"], "eta_hours": m["eta_hours"]}
        for m in deterministic_matches
    ])
    system = (
        "You are the Resource Matching Agent of a humanitarian coordination platform. "
        "Decide how much each provider should contribute to satisfy the need. "
        "Rules: never exceed a provider's available quantity; prefer faster providers (lower eta_hours) "
        "for critical/high urgency; split across providers when sensible. "
        "Respond ONLY with JSON: "
        '{"matches": [{"organization_id": "...", "quantity": N}], "reasoning": "one short sentence"}'
    )
    user = (
        f"Need: {rec.get('quantity')} x {rec.get('resource')} at {rec.get('location_name')}, "
        f"urgency: {rec.get('urgency')}.\nAvailable providers: {inventory}"
    )
    result = await groq_json_async(system, user)
    if not result or not isinstance(result.get("matches"), list):
        return deterministic_matches, None

    avail = {m["organization_id"]: m["quantity"] for m in deterministic_matches}
    etas = {m["organization_id"]: m["eta_hours"] for m in deterministic_matches}
    validated = []
    for m in result["matches"]:
        oid = str(m.get("organization_id", "")).strip().upper()
        try:
            qty = int(m.get("quantity", 0))
        except (TypeError, ValueError):
            continue
        if oid in avail and 0 < qty <= avail[oid]:
            validated.append({"organization_id": oid, "quantity": qty, "eta_hours": etas[oid]})
    if not validated:
        return deterministic_matches, None
    return validated, (result.get("reasoning") if isinstance(result.get("reasoning"), str) else None)


# ───────────── AI PLANNING (Coordination Agent) ─────────────

async def ai_plan_summary(rec: dict, plan: dict):
    """Coordination Agent (AI): write dispatch summary + risk notes for the plan."""
    if not GROQ_API_KEY:
        return None
    system = (
        "You are the Coordination Agent of a humanitarian coordination platform. "
        "Write a concise dispatch briefing for the allocation plan. "
        "Respond ONLY with JSON: "
        '{"summary": "two short sentences", "risks": "one short sentence"}'
    )
    user = json.dumps({
        "need": {
            "resource": rec.get("resource"), "quantity": rec.get("quantity"),
            "location": rec.get("location_name"), "urgency": rec.get("urgency"),
        },
        "plan": {
            "plan_id": plan["plan_id"], "allocated": plan["allocated_quantity"],
            "required": plan["required_quantity"], "status": plan["status"],
            "allocations": plan["allocations"],
        },
    })
    result = await groq_json_async(system, user)
    if result and isinstance(result.get("summary"), str):
        return result
    return None


# ═══════════════════════════════════════════════════════
# ACCEPT FLOW with AI PRIVACY FLAG
# ═══════════════════════════════════════════════════════

async def do_accept(rec: dict):
    ok, reason = validate_for_accept(rec)
    rec["reviewed_at"] = now_iso()
    if not ok:
        rec["status"] = "duplicate" if reason == "DUP" else "rejected"
        rec["reject_reason"] = reason
        agent = "Privacy Filter Agent" if reason == "PRIVACY" else "AI Anomaly & Safety Agent"
        add_activity(agent, f"{rec['id']}: auto-rejected ({reason})")

        # AUTO REPLY: Send Rejection SMS to field phone
        req_phone = rec.get("from_number")
        if req_phone and req_phone != "Device-SIM":
            rej_body = f"X|{next_seq()}|{rec['id']}|{reason}"
            queue_outbound_sms(
                to_number=req_phone,
                message=f"{rej_body}|{xor_checksum(rej_body)}",
                msg_type="rejection",
                plan_id=rec["id"]
            )
        return rec, False, reason

    # ═══════ AI PRIVACY FLAG (Groq) ═══════
    ai_flag = await ai_flag_request(rec)
    if ai_flag:
        rec["ai_flag"] = ai_flag
        if ai_flag.get("flagged") and ai_flag.get("risk_level") == "high":
            rec["status"] = "rejected"
            rec["reject_reason"] = "PRIVACY (AI-flagged)"
            add_activity("Privacy Filter Agent (AI)",
                         f"{rec['id']}: auto-rejected — {ai_flag.get('summary', 'sensitive data detected')}")
            return rec, False, "PRIVACY_AI"
        add_activity("Privacy Filter Agent (AI)",
                     f"{rec['id']}: cleared — {ai_flag.get('summary', 'no sensitive data')}")

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

    deterministic_matches = []
    for org_id, org in ORGANIZATIONS.items():
        if org_id == rec.get("organization_id"):
            continue
        available = org["resources"].get(resource_code, 0)
        if available > 0:
            deterministic_matches.append({"organization_id": org_id, "quantity": available, "eta_hours": org["eta_hours"]})

    # ═══════ AI MATCHING (Groq) with fallback ═══════
    matches, ai_reasoning = await ai_enhance_matching(rec, deterministic_matches)

    await asyncio.sleep(AGENT_DELAY_SECONDS)
    rec["status"] = "matched"
    rec["matches"] = matches
    rec["total_matched"] = sum(m["quantity"] for m in matches)

    if ai_reasoning:
        rec["ai_match_reasoning"] = ai_reasoning
        add_activity("Resource Matching Agent (AI)",
                     f"{request_id}: {ai_reasoning}")
    add_activity("Resource Matching Agent",
                 f"{request_id}: matched {rec['total_matched']} {resource_name} across {len(matches)} organization(s)")

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

    # ═══════ AI PLANNING (Groq) — dispatch briefing ═══════
    ai_briefing = await ai_plan_summary(rec, plan)
    if ai_briefing:
        plan["ai_summary"] = ai_briefing.get("summary")
        plan["ai_risks"] = ai_briefing.get("risks")
        add_activity("Coordination Agent (AI)", f"{plan['plan_id']}: {ai_briefing.get('summary')}")

    PLANS[plan["plan_id"]] = plan
    db.save_plan(plan)

    # ═══════ REAL SMS GATEWAY OUTBOX TRIGGER ═══════
    # Automatically queue canonical allocation SMS for each provider and requester so mobile gateway relays it via GSM
    lat = rec.get("latitude")
    lng = rec.get("longitude")
    loc_str = f"{lat:.4f},{lng:.4f}" if (lat is not None and lng is not None and (lat != 0 or lng != 0)) else rec.get("location_code", "RA")

    for a in allocations:
        org_id = a["organization_id"]
        phone = ORG_PHONE_MAP.get(org_id, "+917401231450")
        alloc_seq = next_seq()
        alloc_body = f"A|{alloc_seq}|{plan['plan_id']}|{org_id}|{resource_code}|{a['quantity']}|{loc_str}|{a['eta_hours']}"
        full_alloc_sms = f"{alloc_body}|{xor_checksum(alloc_body)}"
        
        # Dispatch to provider organization
        queue_outbound_sms(to_number=phone, message=full_alloc_sms, msg_type="allocation", plan_id=plan["plan_id"])
        
        # AUTO REPLY: Also dispatch allocation update directly back to field requester phone (if not low urgency)
        req_phone = rec.get("from_number")
        is_low_urgency = (rec.get("urgency_code") in ("L", "low", "LOW") or rec.get("urgency") in ("L", "low", "LOW"))
        if req_phone and req_phone != "Device-SIM" and req_phone != phone and not is_low_urgency:
            queue_outbound_sms(to_number=req_phone, message=full_alloc_sms, msg_type="allocation", plan_id=plan["plan_id"])

    await asyncio.sleep(AGENT_DELAY_SECONDS)
    rec["available_resource"] = allocated_quantity
    rec["required_quantity"] = quantity

    # ═══════ AI CHECK: R < N -> SHOW STATE WAITING ═══════
    if allocated_quantity < quantity:
        rec["status"] = "waiting"
        rec["plan_id"] = plan["plan_id"] if allocated_quantity > 0 else None
        rec["ai_supply_status"] = f"AI Assessment: Insufficient Supply (R={allocated_quantity} < N={quantity}). Held in WAITING state until additional stock is registered."
        add_activity("Resource Matching Agent (AI)", f"{request_id}: R < N ({allocated_quantity} < {quantity}) -> Status set to WAITING")
    else:
        rec["status"] = "allocated"
        rec["plan_id"] = plan["plan_id"]
        rec["ai_supply_status"] = f"AI Assessment: Full Coverage (R={allocated_quantity} >= N={quantity})."
        detail = ", ".join(f"{a['quantity']} from {a['organization_id']}" for a in allocations) or "all resources fulfilled"
        add_activity("Coordination Agent", f"{request_id}: created {plan['plan_id']} - {detail}")

    db.save_request(rec)


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
    db.save_request(rec)
    add_activity("Resource Matching Agent", f"{request_id}: registering {quantity} x {resource_name} from {org_id}")

    org = ORGANIZATIONS.setdefault(org_id, {"name": org_id, "resources": {}, "eta_hours": 4, "radius_km": 50})
    org["resources"][resource_code] = org["resources"].get(resource_code, 0) + quantity
    db.save_organization(org_id, org)

    await asyncio.sleep(AGENT_DELAY_SECONDS)
    rec["status"] = "completed"
    db.save_request(rec)
    add_activity("Resource Matching Agent", f"{request_id}: {org_id} now holds {org['resources'][resource_code]} {resource_name}")

    # Auto re-evaluate waiting needs for this resource
    for waiting_req in list(REQUESTS.values()):
        if waiting_req.get("type") == "need" and waiting_req.get("status") in ("waiting", "pending") \
                and waiting_req.get("resource_code") == resource_code:
            asyncio.create_task(run_need_pipeline(waiting_req["id"]))


async def run_status_pipeline(request_id: str):
    rec = REQUESTS.get(request_id)
    if not rec:
        return
    await asyncio.sleep(AGENT_DELAY_SECONDS)
    rec["status"] = "processing"
    db.save_request(rec)
    plan_id = rec.get("plan_id")
    status_name = STATUS_CODE_TO_NAME.get(rec.get("status_code"), "unknown")
    add_activity("Coordination Agent", f"{request_id}: status '{status_name}' received for {plan_id}")

    plan = PLANS.get(plan_id)
    await asyncio.sleep(AGENT_DELAY_SECONDS)
    if plan:
        plan["status"] = "delivered" if rec.get("status_code") == 3 else status_name
        db.save_plan(plan)
        add_activity("Coordination Agent", f"{plan_id}: plan status -> {plan['status']}")
    else:
        add_activity("Coordination Agent", f"{plan_id}: plan not found - status logged only")
    rec["status"] = "completed"
    db.save_request(rec)


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
    from_num = payload.from_number or "Device-SIM"
    
    if result.get("status") == "accepted" and isinstance(decoded, dict) \
            and decoded.get("type") in ("need", "resource", "status"):
        hub_request = create_request_from_sms(decoded)
        if hub_request:
            result["hub_request_id"] = hub_request["id"]
            if payload.from_number:
                hub_request["from_number"] = payload.from_number

            # ═══════ AI ANOMALY & QUOTA VALIDATION (Auto-Reject) ═══════
            ok_anomaly, reason_anomaly = check_anomaly_and_rate_limit(hub_request)
            if not ok_anomaly:
                hub_request["status"] = "rejected"
                hub_request["reject_reason"] = reason_anomaly
                result["status"] = "rejected"
                result["accepted"] = False
                result["auto_reject_reason"] = reason_anomaly
                add_activity("AI Anomaly & Safety Agent", f"{hub_request['id']}: AUTO-REJECTED -> {reason_anomaly}")

                if payload.from_number and payload.from_number != "Device-SIM":
                    rej_body = f"X|{next_seq()}|{hub_request['id']}|{reason_anomaly}"
                    queue_outbound_sms(
                        to_number=payload.from_number,
                        message=f"{rej_body}|{xor_checksum(rej_body)}",
                        msg_type="rejection",
                        plan_id=hub_request["id"]
                    )
                add_gateway_log(
                    direction="INBOUND",
                    from_to=from_num,
                    message=payload.sms,
                    status="REJECTED",
                    detail=f"Auto-rejected by AI: {reason_anomaly}"
                )
                return result

            # ═══════ AI URGENCY ASSESSMENT & SMS SUPPRESSION ═══════
            urgency_code = hub_request.get("urgency_code") or "M"
            is_low_urgency = (urgency_code in ("L", "low", "LOW"))

            if is_low_urgency:
                hub_request["sync_mode"] = "internet_only"
                hub_request["status"] = "waiting"
                hub_request["ai_priority_note"] = "AI Assessment: Low Urgency · SMS updates suppressed to conserve network. Status updates via Internet only."
                add_activity("AI Assessment Agent", f"{hub_request['id']}: AI flagged LOW urgency -> held in WAITING, syncing via internet only")
            else:
                hub_request["sync_mode"] = "sms_and_internet"
                if payload.from_number and payload.from_number != "Device-SIM":
                    # AUTO REPLY: Send instant Confirmation SMS back to field phone for High/Med urgency
                    conf_body = f"C|{next_seq()}|{hub_request['id']}|OK"
                    conf_sms = f"{conf_body}|{xor_checksum(conf_body)}"
                    queue_outbound_sms(
                        to_number=payload.from_number,
                        message=conf_sms,
                        msg_type="confirmation",
                        plan_id=hub_request["id"]
                    )
            add_gateway_log(
                direction="INBOUND",
                from_to=from_num,
                message=payload.sms,
                status="FORWARDED_TO_SERVER",
                detail=f"Parsed as {decoded.get('type')} -> {hub_request['id']}"
            )
    else:
        add_gateway_log(
            direction="INBOUND",
            from_to=from_num,
            message=payload.sms,
            status="ERROR" if result.get("status") == "error" else "RECEIVED",
            detail=result.get("error", "Received raw SMS")
        )
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

    # Attach Chennai coordinates so web-form requests also appear on the map
    loc = rec.get("location_code")
    if loc in LOCATION_COORDS:
        rec["latitude"], rec["longitude"] = LOCATION_COORDS[loc]

    key = (rec["organization_id"], rec["seq"])
    rec["status"] = "duplicate" if key in PROCESSED_SEQS else "pending"
    finalize_request(rec)

    # ═══════════════════════════════════════════════════════
    # DONOR RESOURCE AUTO-REGISTRATION
    # Resource availability declarations (donations) do NOT need
    # coordinator approval. Add them to the provider pool instantly
    # so the Resource Matching Agent can find them immediately.
    # ═══════════════════════════════════════════════════════
    if request_type == "resource" and rec["status"] == "pending":
        rec["status"] = "accepted"
        rec["reviewed_at"] = now_iso()
        org_id = rec["organization_id"]
        org = ORGANIZATIONS.setdefault(
            org_id, {"name": org_id, "resources": {}, "eta_hours": 4, "radius_km": 50}
        )
        org["resources"][resource_code] = org["resources"].get(resource_code, 0) + body.quantity
        db.save_organization(org_id, org)
        PROCESSED_SEQS.add(key)
        db.save_request(rec)
        add_activity(
            "Resource Matching Agent",
            f"{rec['id']}: registered {body.quantity} x {resource_name} from {org_id} (auto-accepted)",
        )

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
    db.save_request(rec)
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
    db.save_request(rec)
    add_activity("Coordinator", f"{request_id} rejected ({rec['reject_reason']})")

    # AUTO REPLY: Queue Rejection SMS back to field phone
    req_phone = rec.get("from_number")
    if req_phone and req_phone != "Device-SIM":
        rej_body = f"X|{next_seq()}|{request_id}|{rec['reject_reason']}"
        queue_outbound_sms(
            to_number=req_phone,
            message=f"{rej_body}|{xor_checksum(rej_body)}",
            msg_type="rejection",
            plan_id=request_id
        )

    return rec


@app.get("/api/v1/plans")
def list_plans():
    items = sorted(PLANS.values(), key=lambda p: p.get("created_at", ""), reverse=True)
    return {"count": len(items), "plans": items}


@app.post("/api/v1/handoff/confirm")
def confirm_handover(body: ConfirmHandoverBody):
    org_id = (body.organization_id or "DONOR").strip().upper()
    plan = None
    request_rec = None

    if body.plan_id:
        plan_id = body.plan_id.strip().upper()
        plan = PLANS.get(plan_id)
        if plan:
            plan["status"] = "in_transit"
            plan["handed_over_at"] = now_iso()
            plan["handed_over_by"] = org_id
            db.save_plan(plan)
            # update associated request if exists
            if plan.get("request_id") and plan["request_id"] in REQUESTS:
                request_rec = REQUESTS[plan["request_id"]]
                request_rec["status"] = "in_transit"
                request_rec["handed_over_at"] = now_iso()
                request_rec["handed_over_by"] = org_id
                db.save_request(request_rec)

    if body.request_id and not request_rec:
        req_id = body.request_id.strip().upper()
        request_rec = REQUESTS.get(req_id)
        if request_rec:
            request_rec["status"] = "in_transit"
            request_rec["handed_over_at"] = now_iso()
            request_rec["handed_over_by"] = org_id
            db.save_request(request_rec)
            if request_rec.get("plan_id") and request_rec["plan_id"] in PLANS:
                plan = PLANS[request_rec["plan_id"]]
                plan["status"] = "in_transit"
                plan["handed_over_at"] = now_iso()
                plan["handed_over_by"] = org_id
                db.save_plan(plan)

    target_desc = body.plan_id or body.request_id or "Aid supplies"
    add_activity("Coordination Agent", f"[{org_id}] Confirmed handover for {target_desc} -> status: in_transit (Dispatched)")

    # Send status SMS update if requester has registered phone
    if request_rec and request_rec.get("from_number") and request_rec["from_number"] != "Device-SIM":
        plan_id_str = (plan.get("plan_id") if plan else (request_rec.get("plan_id") or "PLAN-101"))
        seq = next_seq()
        status_body = f"S|{seq}|{plan_id_str}|1"
        queue_outbound_sms(
            to_number=request_rec["from_number"],
            message=f"{status_body}|{xor_checksum(status_body)}",
            msg_type="status_update",
            plan_id=plan_id_str
        )

    return {
        "status": "success",
        "message": f"Handover confirmed for {target_desc}. Status updated to in_transit.",
        "plan": plan,
        "request": request_rec
    }


@app.post("/api/v1/delivery/confirm")
def confirm_receipt(body: ConfirmReceivedBody):
    org_id = (body.organization_id or "RECEIVER").strip().upper()
    plan = None
    request_rec = None

    if body.plan_id:
        plan_id = body.plan_id.strip().upper()
        plan = PLANS.get(plan_id)
        if plan:
            plan["status"] = "delivered"
            plan["received_at"] = now_iso()
            plan["received_by"] = org_id
            db.save_plan(plan)
            # update associated request
            if plan.get("request_id") and plan["request_id"] in REQUESTS:
                request_rec = REQUESTS[plan["request_id"]]
                request_rec["status"] = "completed"
                request_rec["received_at"] = now_iso()
                request_rec["received_by"] = org_id
                db.save_request(request_rec)

    if body.request_id and not request_rec:
        req_id = body.request_id.strip().upper()
        request_rec = REQUESTS.get(req_id)
        if request_rec:
            request_rec["status"] = "completed"
            request_rec["received_at"] = now_iso()
            request_rec["received_by"] = org_id
            db.save_request(request_rec)
            if request_rec.get("plan_id") and request_rec["plan_id"] in PLANS:
                plan = PLANS[request_rec["plan_id"]]
                plan["status"] = "delivered"
                plan["received_at"] = now_iso()
                plan["received_by"] = org_id
                db.save_plan(plan)

    target_desc = body.plan_id or body.request_id or "Aid supplies"
    add_activity("Coordination Agent", f"[{org_id}] Confirmed supplies received successfully for {target_desc} -> status: delivered/completed")

    return {
        "status": "success",
        "message": f"Receipt confirmed for {target_desc}. Status updated to delivered/completed.",
        "plan": plan,
        "request": request_rec
    }


@app.post("/api/v1/requests/{request_id}/handoff")
def request_handoff_shortcut(request_id: str):
    return confirm_handover(ConfirmHandoverBody(request_id=request_id))


@app.post("/api/v1/requests/{request_id}/receive")
def request_receive_shortcut(request_id: str):
    return confirm_receipt(ConfirmReceivedBody(request_id=request_id))


@app.post("/api/v1/plans/{plan_id}/handoff")
def plan_handoff_shortcut(plan_id: str):
    return confirm_handover(ConfirmHandoverBody(plan_id=plan_id))


@app.post("/api/v1/plans/{plan_id}/receive")
def plan_receive_shortcut(plan_id: str):
    return confirm_receipt(ConfirmReceivedBody(plan_id=plan_id))


# Provider inventory for the Matching page (privacy-safe shared profiles)
@app.get("/api/v1/organizations")
def list_organizations():
    return {"organizations": [
        {
            "organization_id": org_id,
            "name": org.get("name", org_id),
            "resources": org.get("resources", {}),
            "eta_hours": org.get("eta_hours"),
            "radius_km": org.get("radius_km"),
        }
        for org_id, org in ORGANIZATIONS.items()
    ]}


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


# ═══════════════════════════════════════════════════════
# AI STATUS ENDPOINT — web can show "AI: ON (llama-3.3-70b)"
# ═══════════════════════════════════════════════════════
@app.get("/api/v1/config/ai")
def get_ai_config():
    return {
        "groq_enabled": bool(GROQ_API_KEY),
        "model": GROQ_MODEL if GROQ_API_KEY else None,
    }


@app.on_event("startup")
def startup_db_init():
    init_db_and_load_state()


# =====================================================================
# REAL SMS GATEWAY - BIDIRECTIONAL RELAY ENGINE
# =====================================================================

class OutboundSmsCreate(BaseModel):
    to_number: str
    message: str
    type: Optional[str] = "manual"
    plan_id: Optional[str] = None


class OutboundAckBody(BaseModel):
    status: str = "sent"  # "sent" or "failed"
    error: Optional[str] = None


@app.get("/api/v1/sms/outbox")
def get_sms_outbox(status: Optional[str] = "pending"):
    """Mobile SMS Gateway polls this to get pending outgoing SMS messages to physically send via GSM"""
    items = list(OUTBOUND_SMS_QUEUE.values())
    if status:
        items = [m for m in items if m.get("status") == status]
    items.sort(key=lambda m: m.get("created_at", ""))
    return {"count": len(items), "messages": items}


@app.post("/api/v1/sms/outbox", status_code=201)
def create_outbound_sms(body: OutboundSmsCreate):
    """Queue an outbound SMS message to be sent by the mobile gateway"""
    item = queue_outbound_sms(
        to_number=body.to_number.strip(),
        message=body.message.strip(),
        msg_type=body.type or "manual",
        plan_id=body.plan_id
    )
    return item


@app.post("/api/v1/sms/outbox/{sms_id}/ack")
def ack_outbound_sms(sms_id: str, body: OutboundAckBody):
    """Mobile Gateway calls this after sending SMS via device SmsManager"""
    item = OUTBOUND_SMS_QUEUE.get(sms_id)
    if not item:
        raise HTTPException(status_code=404, detail="outbound sms not found")
    item["status"] = body.status
    item["dispatched_at"] = now_iso()
    if body.error:
        item["error"] = body.error
    db.save_outbound_sms(item)
    add_gateway_log(
        direction="OUTBOUND",
        from_to=item["to_number"],
        message=item["message"],
        status="SENT_VIA_GSM" if body.status == "sent" else "FAILED",
        detail=f"Mobile SIM dispatch {body.status} ({body.error or 'ok'})"
    )
    return {"status": "acknowledged", "item": item}


# =====================================================================
# SQLITE PERSISTENT HISTORY & AUDIT ENDPOINTS
# =====================================================================

@app.get("/api/v1/history/requests")
def get_requests_history(
    status: Optional[str] = None,
    type: Optional[str] = None,
    org_id: Optional[str] = None,
    limit: int = 200
):
    """Returns persistent SQLite requests history with full audit attributes"""
    items = list(REQUESTS.values())
    if status:
        items = [r for r in items if r.get("status") == status]
    if type:
        items = [r for r in items if r.get("type") == type]
    if org_id:
        items = [r for r in items if (r.get("organization_id") or "").upper() == org_id.upper()]
    items.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return {
        "source": "sqlite_database",
        "total_records": len(items),
        "history": items[:limit]
    }


@app.get("/api/v1/history/plans")
def get_plans_history(limit: int = 100):
    """Returns persistent dispatch plans history from SQLite"""
    items = list(PLANS.values())
    items.sort(key=lambda p: p.get("created_at", ""), reverse=True)
    return {
        "source": "sqlite_database",
        "total_plans": len(items),
        "plans": items[:limit]
    }


@app.get("/api/v1/history/gateway")
def get_gateway_history(limit: int = 200):
    """Returns persistent GSM & Webhook transmission logs from SQLite"""
    logs = db.load_gateway_logs(limit)
    return {
        "source": "sqlite_database",
        "total_logs": len(logs),
        "logs": logs
    }


@app.get("/api/v1/history/activities")
def get_activities_history(limit: int = 200):
    """Returns persistent AI reasoning and coordination decisions from SQLite"""
    acts = db.load_activities(limit)
    return {
        "source": "sqlite_database",
        "total_activities": len(acts),
        "activities": acts
    }


@app.delete("/api/v1/history/clear")
def clear_all_history():
    """Admin endpoint to clear database tables (resets to clean state)"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM requests")
        cursor.execute("DELETE FROM plans")
        cursor.execute("DELETE FROM outbound_sms")
        cursor.execute("DELETE FROM gateway_logs")
        cursor.execute("DELETE FROM agent_activities")
        conn.commit()
    init_db_and_load_state()
    return {"status": "success", "message": "SQLite history cleared. Database reset to clean state."}


@app.get("/api/v1/sms/gateway/logs")
def get_gateway_logs(limit: int = 50):
    """Returns real-time gateway activity logs"""
    return {
        "count": len(GATEWAY_ACTIVITY_LOGS),
        "logs": list(reversed(GATEWAY_ACTIVITY_LOGS[-limit:]))
    }


@app.get("/api/v1/sms/gateway/stats")
def get_gateway_stats():
    """Returns gateway aggregate counts"""
    inbound_count = sum(1 for l in GATEWAY_ACTIVITY_LOGS if l["direction"] == "INBOUND")
    outbound_count = sum(1 for l in GATEWAY_ACTIVITY_LOGS if l["direction"] == "OUTBOUND")
    pending_outbound = sum(1 for m in OUTBOUND_SMS_QUEUE.values() if m["status"] == "pending")
    return {
        "inbound_total": inbound_count,
        "outbound_total": outbound_count,
        "pending_outbound": pending_outbound,
        "logs_total": len(GATEWAY_ACTIVITY_LOGS)
    }


# =====================================================================
# FAKE SMS INBOX (Legacy Polling Demo compatibility)
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


# =====================================================================
# REAL-TIME LOCATION TRACKING + ANDROID STATUS POLLING
# =====================================================================

LIVE_LOCATIONS = {}


class LocationUpdate(BaseModel):
    organization_id: str
    latitude: float
    longitude: float


@app.post("/api/v1/location/update")
def update_location(payload: LocationUpdate):
    """Android sends live GPS every 10 seconds"""
    org_id = payload.organization_id.strip().upper()
    lat, lng = payload.latitude, payload.longitude

    # Ignore 0,0 — means the phone has no GPS lock yet
    if lat == 0.0 and lng == 0.0:
        return {"status": "ignored", "reason": "zero coordinates (no GPS lock)"}

    LIVE_LOCATIONS[org_id] = {
        "organization_id": org_id,
        "latitude": lat,
        "longitude": lng,
        "updated_at": now_iso(),
    }

    # Update every active request of this org so the web map marker MOVES live
    updated = 0
    for rec in REQUESTS.values():
        if (rec.get("organization_id") == org_id
                and rec.get("status") not in ("rejected", "duplicate", "completed")):
            rec["latitude"] = lat
            rec["longitude"] = lng
            updated += 1
    return {"status": "ok", "organization_id": org_id, "requests_updated": updated}


@app.get("/api/v1/locations")
def list_locations():
    return {"locations": list(LIVE_LOCATIONS.values())}


@app.get("/api/v1/requests/by-org/{organization_id}")
def requests_by_org(organization_id: str):
    """Android polls this to show approval status"""
    org_id = organization_id.strip().upper()
    items = [r for r in REQUESTS.values() if r.get("organization_id") == org_id]
    items.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return {"count": len(items), "requests": items}