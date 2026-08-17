from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional


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


class SmsWebhookRequest(BaseModel):
    sms: str
    from_number: Optional[str] = None


RESOURCE_MAP = {
    "F": "food_kits",
    "W": "water_kits",
    "M": "medical_kits",
    "T": "tents",
    "B": "blankets",
    "H": "hygiene_kits",
    "D": "medical_teams",
    "U": "unknown",

    "food": "food_kits",
    "water": "water_kits",
    "medical": "medical_kits",
    "medicine": "medical_kits",
    "tents": "tents",
    "tent": "tents",
    "blankets": "blankets",
    "blanket": "blankets",
}

URGENCY_MAP = {
    "L": "low",
    "M": "medium",
    "H": "high",
    "C": "critical",

    "low": "low",
    "medium": "medium",
    "high": "high",
    "critical": "critical",
}

LOCATION_CODE_MAP = {
    "RA": "RA",
    "RB": "RB",
    "RC": "RC",
    "RegionA": "RA",
    "Region A": "RA",
    "RegionB": "RB",
    "Region B": "RB",
    "RegionC": "RC",
    "Region C": "RC",
}

LOCATION_NAME_MAP = {
    "RA": "Region A",
    "RB": "Region B",
    "RC": "Region C",
}


def xor_checksum(text: str) -> str:
    value = 0
    for char in text:
        value ^= ord(char)
    return format(value, "02X")


def map_resource(value: str) -> str:
    value = value.strip()
    upper_value = value.upper()
    lower_value = value.lower()

    if upper_value in RESOURCE_MAP:
        return RESOURCE_MAP[upper_value]

    if lower_value in RESOURCE_MAP:
        return RESOURCE_MAP[lower_value]

    return value


def map_urgency(value: str) -> str:
    value = value.strip()
    upper_value = value.upper()
    lower_value = value.lower()

    if upper_value in URGENCY_MAP:
        return URGENCY_MAP[upper_value]

    if lower_value in URGENCY_MAP:
        return URGENCY_MAP[lower_value]

    return value


def location_info(location: str):
    location = location.strip()

    code = LOCATION_CODE_MAP.get(location)

    if not code:
        code = location

    name = LOCATION_NAME_MAP.get(code, location)

    return code, name


def parse_sms(sms: str):
    sms = sms.strip()

    if not sms:
        return {
            "status": "error",
            "error": "EMPTY_SMS"
        }

    parts = sms.split("|")
    message_type = parts[0].strip().upper()

    # Legacy need format:
    # N|NGO01|RegionA|food|300|H
    if message_type == "N" and len(parts) == 6:
        organization_id = parts[1].strip()
        location_raw = parts[2].strip()
        resource_raw = parts[3].strip()
        quantity_raw = parts[4].strip()
        urgency_raw = parts[5].strip()

        try:
            quantity = int(quantity_raw)
        except ValueError:
            return {
                "status": "error",
                "error": "BAD_QTY"
            }

        location_code, location_name = location_info(location_raw)

        return {
            "status": "accepted",
            "mode": "legacy",
            "decoded": {
                "type": "need",
                "organization_id": organization_id,
                "location_code": location_code,
                "location_name": location_name,
                "resource": map_resource(resource_raw),
                "quantity": quantity,
                "urgency": map_urgency(urgency_raw),
                "source": "sms"
            }
        }

    # Canonical need format:
    # N|SEQ|ORG|LOC|RESOURCE|QTY|URGENCY|CRC
    if message_type == "N" and len(parts) == 8:
        body = "|".join(parts[:7])
        received_checksum = parts[7].strip().upper()
        expected_checksum = xor_checksum(body)

        if received_checksum != expected_checksum:
            return {
                "status": "error",
                "error": "BAD_CRC",
                "expected_checksum": expected_checksum,
                "received_checksum": received_checksum
            }

        seq = parts[1].strip()
        organization_id = parts[2].strip()
        location_raw = parts[3].strip()
        resource_raw = parts[4].strip()
        quantity_raw = parts[5].strip()
        urgency_raw = parts[6].strip()

        try:
            quantity = int(quantity_raw)
        except ValueError:
            return {
                "status": "error",
                "error": "BAD_QTY"
            }

        location_code, location_name = location_info(location_raw)

        return {
            "status": "accepted",
            "mode": "canonical",
            "decoded": {
                "type": "need",
                "seq": seq,
                "organization_id": organization_id,
                "location_code": location_code,
                "location_name": location_name,
                "resource": map_resource(resource_raw),
                "quantity": quantity,
                "urgency": map_urgency(urgency_raw),
                "checksum": received_checksum,
                "source": "sms"
            }
        }

    return {
        "status": "accepted",
        "message": "SMS received",
        "raw_sms": sms,
        "note": "This SMS type is not fully decoded yet"
    }


@app.get("/")
def root():
    return {
        "message": "Backend is running",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


@app.get("/api/v1/health")
def health():
    return {
        "status": "ok",
        "service": "humanitarian-coordination-backend",
        "version": "0.1.0"
    }


@app.post("/api/v1/needs")
def create_need(payload: NeedRequest):
    # TODO later:
    # 1. Save need to PostgreSQL
    # 2. Push to Redis need_assessment_queue

    return {
        "status": "accepted",
        "need_id": "NEED_101",
        "message": "Need received by backend",
        "data": payload
    }


@app.post("/api/v1/sms/webhook")
def sms_webhook(payload: SmsWebhookRequest):
    result = parse_sms(payload.sms)

    # TODO later:
    # If valid, push decoded JSON to Redis sms_incoming_queue

    return result