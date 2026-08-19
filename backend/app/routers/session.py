"""Sign-up and session (memory_draft.md 7.1, agents.md 6.1/6.2).

One short screen, once, then never again. No password, no email verification,
no reset flow -- an app that demands account creation from someone trapped in a
collapsed building is the wrong product.

The identity split this implements is the point (memory_draft.md 7.2):

    UID          4 base-36 chars, derived from the device install id. Goes on
                 the wire, in every codec frame. Pseudonymous.
    name/phone   server-side only, encrypted at rest, released by A7 only
                 after a helper accepts. NEVER encoded into a payload.

Until this router existed there was nowhere for a name or phone to be captured,
so a post-acceptance reveal returned `name: null` -- the transition was real and
had nothing behind it.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from app.codec.base36 import b36_encode
from app.db.mongo import get_db
from app.deps import issue, revoke
from app.deps import current_device
from app.privacy import crypto

log = logging.getLogger(__name__)
router = APIRouter(tags=["session"])

UID_LEN = 4


def _now():
    return datetime.now(timezone.utc)


def derive_uid(device_id: str, salt: int = 0) -> str:
    """First 4 base-36 characters of sha256(device install id), per codec.md 5.1.

    Stable across restarts, regenerated on reinstall, and pseudonymous on the
    wire. `salt` exists only to resolve the rare collision below -- 36^4 is
    1.68 million, which is ample for a demo but not infinite.
    """
    material = device_id if salt == 0 else f"{device_id}#{salt}"
    digest = hashlib.sha256(material.encode()).hexdigest()
    return b36_encode(int(digest, 16))[:UID_LEN].upper()


def _err(code: str, **extra):
    return {"status": "error", "error": code, **extra}


class SignupRequest(BaseModel):
    role: Literal["seeker", "helper"]
    device_id: str = Field(min_length=4)
    name: str = Field(min_length=1, max_length=80)
    phone: str = Field(min_length=6, max_length=24)
    # Helper mode only. An invalid code must never block someone from helping.
    group_code: str | None = None


async def _resolve_group_code(code: str | None) -> tuple[str | None, str | None, str | None]:
    """Returns (org_id, org_name, error). An unknown code is NOT an error the
    caller should act on -- memory_draft.md 7.3: never block someone from
    helping because a code failed. They stay an individual volunteer."""
    if not code:
        return None, None, None
    db = get_db()
    if db is None:
        return None, None, "NO_DATABASE"
    org = await db.organizations.find_one(
        {"group_code": code.strip().upper()}, {"name": 1})
    if org is None:
        return None, None, "UNKNOWN_GROUP_CODE"
    return org["_id"], org.get("name"), None


@router.post("/api/v1/session/signup")
async def signup(body: SignupRequest):
    db = get_db()
    if db is None:
        return _err("NO_DATABASE")

    coll = "seekers" if body.role == "seeker" else "helpers"
    phash = crypto.phone_hash(body.phone)

    # One number is one account (agents.md 4.2). A repeat sign-up from the same
    # number returns the existing identity rather than failing on the unique
    # index -- reinstalling the app must not lock someone out mid-disaster.
    existing = await db[coll].find_one({"phone_hash": phash})

    org_id, org_name, code_error = await _resolve_group_code(
        body.group_code if body.role == "helper" else None)

    if existing is not None:
        uid = existing["uid"]
        update: dict[str, Any] = {"last_seen": _now(), "device_id": body.device_id}
        if body.role == "helper" and org_id:
            update["org_id"] = org_id
        await db[coll].update_one({"_id": existing["_id"]}, {"$set": update})
        return {
            "status": "ok", "uid": uid, "role": body.role, "returning": True,
            "token": issue(uid, body.role, org_id or existing.get("org_id")),
            "org_id": org_id or existing.get("org_id"), "org_name": org_name,
            "group_code_error": code_error,
        }

    # New account. Resolve a UID collision by re-deriving with a salt rather
    # than failing the sign-up.
    uid = derive_uid(body.device_id)
    for salt in range(1, 6):
        if await db[coll].find_one({"uid": uid}, {"_id": 1}) is None:
            break
        uid = derive_uid(body.device_id, salt)

    doc: dict[str, Any] = {
        "_id": f"{'SKR' if body.role == 'seeker' else 'HLP'}_{uid}_{phash[:6]}",
        "uid": uid,
        "device_id": body.device_id,
        # Encrypted at rest. Never encoded into a codec payload.
        "name_enc": crypto.encrypt(body.name.strip()),
        "phone_enc": crypto.encrypt(body.phone.strip()),
        "phone_hash": phash,
        "created_at": _now(), "last_seen": _now(),
    }
    if body.role == "helper":
        # null org_id means an individual volunteer, dispatched directly. This
        # one nullable field is what implements the two dispatch paths.
        doc.update({"org_id": org_id, "status": "available", "capabilities": []})

    try:
        await db[coll].insert_one(doc)
    except Exception:
        log.exception("signup insert failed")
        return _err("SIGNUP_FAILED")

    return {
        "status": "ok", "uid": uid, "role": body.role, "returning": False,
        "token": issue(uid, body.role, org_id),
        "org_id": org_id, "org_name": org_name,
        "group_code_error": code_error,
    }


@router.get("/api/v1/session/me")
async def me(claims: dict = current_device):
    """Restores a persisted session. The name comes back decrypted because
    this is the account's own owner asking."""
    db = get_db()
    if db is None:
        return _err("NO_DATABASE")
    role = claims.get("role", "seeker")
    coll = "seekers" if role == "seeker" else "helpers"
    doc = await db[coll].find_one({"uid": claims.get("sub")})
    if doc is None:
        return _err("NO_SUCH_SESSION")

    org_name = None
    if doc.get("org_id"):
        org = await db.organizations.find_one({"_id": doc["org_id"]}, {"name": 1})
        org_name = (org or {}).get("name")

    return {
        "status": "ok", "uid": doc["uid"], "role": role,
        "name": crypto.decrypt(doc.get("name_enc")),
        "phone": crypto.decrypt(doc.get("phone_enc")),
        "org_id": doc.get("org_id"), "org_name": org_name,
        "helper_id": doc["_id"] if role == "helper" else None,
    }


@router.post("/api/v1/session/signout")
async def signout(authorization: str | None = Header(default=None)):
    """Clears the device session. The account survives -- the UID is derived
    from the device, so signing back in restores the same identity."""
    revoke(authorization)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Helper: organization membership
# ---------------------------------------------------------------------------

class GroupCodeBody(BaseModel):
    group_code: str


@router.post("/api/v1/helpers/join")
async def join(body: GroupCodeBody, claims: dict = current_device):
    """Binds a helper to an organization. An invalid code leaves them an
    individual volunteer -- it is reported, not enforced."""
    if claims.get("role") != "helper":
        return _err("NOT_A_HELPER")
    db = get_db()
    if db is None:
        return _err("NO_DATABASE")

    org_id, org_name, code_error = await _resolve_group_code(body.group_code)
    if code_error:
        return {"status": "ok", "joined": False, "org_id": None,
                "error": code_error,
                "detail": "you remain an individual volunteer and will still "
                          "be matched directly"}

    await db.helpers.update_one({"uid": claims["sub"]},
                                {"$set": {"org_id": org_id, "updated_at": _now()}})
    return {"status": "ok", "joined": True, "org_id": org_id, "org_name": org_name,
            "token": issue(claims["sub"], "helper", org_id)}


@router.post("/api/v1/helpers/leave")
async def leave(claims: dict = current_device):
    if claims.get("role") != "helper":
        return _err("NOT_A_HELPER")
    db = get_db()
    if db is None:
        return _err("NO_DATABASE")
    await db.helpers.update_one({"uid": claims["sub"]},
                                {"$set": {"org_id": None, "updated_at": _now()}})
    return {"status": "ok", "org_id": None,
            "token": issue(claims["sub"], "helper", None)}


class OfferLine(BaseModel):
    resource: str
    available: int = Field(ge=0)
    eta_base_min: int = Field(default=30, ge=0)
    capabilities: list[str] = Field(default_factory=list)


@router.put("/api/v1/helpers/me/offers")
async def put_offers(offers: list[OfferLine], claims: dict = current_device,
                     lat: float | None = None, lon: float | None = None):
    """Upserts this helper's inventory into `offers`.

    `offers` is the collection $geoNear searches, and it holds organizations
    and individuals together with a denormalized `loc` -- which is what lets
    one geo query serve both dispatch paths (agents.md 4.2).
    """
    if claims.get("role") != "helper":
        return _err("NOT_A_HELPER")
    db = get_db()
    if db is None:
        return _err("NO_DATABASE")

    helper = await db.helpers.find_one({"uid": claims["sub"]})
    if helper is None:
        return _err("NO_SUCH_HELPER")

    loc = helper.get("loc")
    if lat is not None and lon is not None:
        loc = {"type": "Point", "coordinates": [lon, lat]}     # [lng, lat]
        await db.helpers.update_one({"_id": helper["_id"]}, {"$set": {"loc": loc}})
    if loc is None:
        return _err("NO_POSITION",
                    detail="send lat and lon once so the offer can be matched")

    written = []
    for o in offers:
        offer_id = f"OFF_{helper['_id']}_{o.resource}"
        await db.offers.update_one(
            {"_id": offer_id},
            {"$set": {"owner": {"kind": "individual", "id": helper["_id"]},
                      "resource": o.resource, "available": o.available,
                      "loc": loc, "eta_base_min": o.eta_base_min,
                      "capabilities": o.capabilities, "updated_at": _now()},
             "$setOnInsert": {"reserved": 0}},
            upsert=True)
        written.append(offer_id)

    return {"status": "ok", "offers": written, "count": len(written)}
