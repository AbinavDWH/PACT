"""Auth dependencies.

Demo-grade by design (memory_draft.md section 7.6): static credentials, signed
opaque tokens, no refresh flow. But it is ENFORCED -- previously /admin/login
handed out a token that nothing ever checked, which meant every admin endpoint
was open.
"""

from __future__ import annotations

import hmac
import secrets
import time

from fastapi import Depends, Header, HTTPException

from app.config import get_settings

# Issued tokens, in memory. A restart logs everyone out, which is fine for a
# demo and avoids a session store.
_TOKENS: dict[str, dict] = {}

TTL_S = 12 * 60 * 60


def issue(subject: str, role: str, org_id: str | None = None) -> str:
    token = secrets.token_urlsafe(24)
    _TOKENS[token] = {"sub": subject, "role": role, "org_id": org_id,
                      "exp": time.time() + TTL_S}
    return token


def _resolve(token: str | None) -> dict | None:
    if not token:
        return None
    t = token.removeprefix("Bearer ").strip()
    claims = _TOKENS.get(t)
    if claims is None or claims["exp"] < time.time():
        _TOKENS.pop(t, None)
        return None
    return claims


def check_admin_credentials(username: str, password: str) -> bool:
    s = get_settings()
    # compare_digest on both fields so the check is not short-circuited.
    return (hmac.compare_digest(username, s.pact_admin_user)
            and hmac.compare_digest(password, s.pact_admin_pass))


async def current_admin(authorization: str | None = Header(default=None)) -> dict:
    if not get_settings().require_auth:
        return {"sub": "anonymous", "role": "admin", "org_id": None}
    claims = _resolve(authorization)
    if claims is None or claims["role"] != "admin":
        raise HTTPException(status_code=401, detail="admin authentication required")
    return claims


async def current_org(authorization: str | None = Header(default=None)) -> dict:
    if not get_settings().require_auth:
        return {"sub": "anonymous", "role": "org", "org_id": None}
    claims = _resolve(authorization)
    if claims is None or claims["role"] != "org":
        raise HTTPException(status_code=401, detail="organization authentication required")
    return claims


async def optional_admin(authorization: str | None = Header(default=None)) -> dict | None:
    """For endpoints that stay open in demo mode but want to record who acted."""
    return _resolve(authorization)


async def _current_device(authorization: str | None = Header(default=None)) -> dict:
    """A signed-in app user -- seeker or helper. The device holds this token
    from sign-up until it explicitly signs out."""
    if not get_settings().require_auth:
        return {"sub": "anonymous", "role": "seeker", "org_id": None}
    claims = _resolve(authorization)
    if claims is None or claims["role"] not in ("seeker", "helper"):
        raise HTTPException(status_code=401, detail="device session required")
    return claims


current_device = Depends(_current_device)


def revoke(token: str | None) -> bool:
    """Sign-out. The account survives -- the UID is derived from the device, so
    signing back in restores the same identity."""
    if not token:
        return False
    return _TOKENS.pop(token.removeprefix("Bearer ").strip(), None) is not None


def verify_ws_token(token: str | None, role: str = "admin") -> dict | None:
    """WebSockets cannot send headers, so the token arrives as a query param."""
    if not get_settings().require_auth:
        return {"sub": "anonymous", "role": role, "org_id": None}
    claims = _resolve(token)
    return claims if claims and claims["role"] == role else None
