"""Ingest -- the one wire format, both transports.

POST /api/v1/pact/ingest      the codec string over HTTP
POST /api/v1/sms/webhook      a thin adapter that calls the same path

The only difference between a connected request and an SMS request is which
function delivered the string. That is what "one wire format" means concretely.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any, Literal, Optional
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel

from app.agents import scripted
from app.codec import decode, priority_score, request_to_needs
from app.db import mongo

log = logging.getLogger(__name__)
router = APIRouter(tags=["ingest"])

# Duplicate suppression on (from_hash, seq). Mongo's unique index is the durable
# version; this in-process set covers the no-database case.
_seen: set[tuple[str, str]] = set()


class IngestRequest(BaseModel):
    payload: str
    transport: Literal["http", "sms"] = "http"
    from_number: Optional[str] = None


class SmsWebhookRequest(BaseModel):
    sms: str
    from_number: Optional[str] = None


def _hash_number(number: str | None) -> str:
    """Never store a raw MSISDN (sms.md 31.1)."""
    if not number:
        return "anon"
    return hashlib.sha256(number.encode()).hexdigest()[:16]


async def _record_sms(raw: str, result: dict, from_hash: str) -> None:
    db = mongo.get_db()
    if db is None:
        return
    try:
        await db.sms_messages.insert_one({
            "direction": "in", "from_hash": from_hash, "raw": raw,
            "parsed": result.get("decoded"), "seq": (result.get("decoded") or {}).get("seq"),
            "crc_ok": result.get("status") == "accepted",
            "status": result.get("status"), "error": result.get("error"),
            "ts": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        })
    except Exception:
        log.debug("sms_messages insert skipped", exc_info=True)


async def ingest_payload(payload: str, transport: str, from_number: str | None) -> dict[str, Any]:
    source = "sms" if transport == "sms" else "http"
    result = decode(payload, source=source)
    from_hash = _hash_number(from_number)

    asyncio.create_task(_record_sms(payload, result, from_hash))

    if result.get("status") != "accepted":
        return result

    d = result["decoded"]

    # Duplicate suppression (sms.md 25). Idempotent, so the app's
    # retry-until-acknowledged loop is safe.
    key = (d.get("uid") or d.get("organization_id") or from_hash, str(d.get("seq") or ""))
    if key[1] and key in _seen:
        return {"status": "accepted", "duplicate": True, "error": "DUP",
                "detail": f"{key[0]}/{key[1]} already processed"}
    if key[1]:
        _seen.add(key)

    # A seeker request fans out into need records and enters the pipeline.
    if d.get("type") == "seeker_request":
        needs = request_to_needs(d)
        result["needs"] = needs
        result["priority_score"] = priority_score(d)

        if needs:
            primary = max(needs, key=lambda n: n["quantity"])
            request = {
                "request_id": f"REQ-{uuid4().hex[:6].upper()}",
                "need": primary["resource"],
                "quantity": primary["quantity"],
                "location_name": d.get("location_name") or "reported position",
                "urgency": d.get("urgency", "high"),
                "lat": d.get("latitude"),
                "lon": d.get("longitude"),
                "uid": d.get("uid"),
                "source": source,
                # Without this the triage agent reasons over nulls -- the whole
                # point of the codec is that these selections reach the agents.
                "decoded": d,
                "people_est": d.get("people_est"),
                "all_needs": needs,
                "priority_score": result["priority_score"],
            }
            if request["lat"] is None:
                request.pop("lat"), request.pop("lon")
            scripted.spawn(request)
            result["trace_id"] = request["request_id"]
            result["dispatched"] = True

    return result


@router.post("/api/v1/pact/ingest")
async def pact_ingest(payload: IngestRequest):
    return await ingest_payload(payload.payload, payload.transport, payload.from_number)


@router.post("/api/v1/sms/webhook")
async def sms_webhook(payload: SmsWebhookRequest):
    """Thin adapter. Identical pipeline, identical result."""
    return await ingest_payload(payload.sms, "sms", payload.from_number)


@router.post("/api/v1/sms/simulate")
async def sms_simulate(payload: SmsWebhookRequest):
    """Admin portal SMS simulator. Same path, labelled for the demo."""
    return await ingest_payload(payload.sms, "sms", payload.from_number or "+demo")
