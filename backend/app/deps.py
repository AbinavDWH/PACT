"""Authentication and session handling.

Three things were demo-grade here and are no longer:

  1. **Passwords were compared in plaintext.** The admin password sat in an
     environment variable and was compared directly; organizations shared one
     plaintext password. `bcrypt` had been in requirements.txt since the first
     commit, described as credential hashing, and was never called. See
     `security.py`.

  2. **Sessions died on restart.** Tokens lived in a module-level dict. For a
     portal that is a re-login; for a phone in the field it is a dead app with
     no recovery path. See `db/repo_sessions.py`.

  3. **Every session shared a 12-hour lifetime.** A seeker who signed up
     yesterday was silently signed out. Device sessions are now long-lived and
     portal sessions stay short, because the threat models differ: a browser on
     a shared laptop should expire quickly, a handset belonging to someone in a
     disaster should not.

What remains deliberately password-free is the **app sign-up** itself
(memory_draft.md §7.1). Someone trapped in a collapsed building will not work
through a registration flow, and adding one would be a product failure dressed
as a security improvement. The device holds a long-lived token instead.
"""

from __future__ import annotations

import secrets
import time
from typing import Any

from fastapi import Depends, Header, HTTPException

from app.config import get_settings
from app.security import hash_password, verify_password

# Write-through cache over `sessions`. Hydrated at startup by `restore()`, so a
# restart is invisible to clients while token lookup stays synchronous -- the
# WebSocket handshake resolves a token without an event loop round trip.
_TOKENS: dict[str, dict[str, Any]] = {}

# Portals: a browser, often on a shared machine.
TTL_PORTAL_S = 12 * 60 * 60
# Handsets: signed in once and expected to keep working. A disaster does not
# pause for a re-login, and there is no password to re-enter anyway.
TTL_DEVICE_S = 90 * 24 * 60 * 60

_ADMIN_HASH: str | None = None


def ttl_for(role: str) -> int:
    return TTL_DEVICE_S if role in ("seeker", "helper") else TTL_PORTAL_S


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

async def restore() -> int:
    """Load persisted sessions. Called once at startup, before serving."""
    from app.db import repo_sessions
    _TOKENS.update(await repo_sessions.load_all())
    return len(_TOKENS)


def prepare_admin_credentials() -> None:
    """Hash the configured admin password once at startup.

    `PACT_ADMIN_PASS` may hold either a bcrypt hash (preferred) or a plaintext
    password, which is hashed here so the plaintext is never used in a
    comparison. Deployments should set the hash; `scripts/hash_password.py`
    prints one.
    """
    global _ADMIN_HASH
    from app.security import is_hashed
    configured = get_settings().pact_admin_pass
    _ADMIN_HASH = configured if is_hashed(configured) else hash_password(configured)


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

# Strong references to in-flight background writes.
#
# asyncio keeps only WEAK references to tasks, so a bare create_task() can be
# garbage-collected mid-execution. That is not theoretical: an admin session
# was silently never written to Mongo while a heavier request ran alongside it,
# and the token then failed to survive a restart -- the exact failure this
# persistence exists to prevent, reintroduced by the way it was scheduled.
_BACKGROUND: set = set()

# The application's event loop, captured at startup.
#
# FastAPI runs `def` endpoints in a threadpool, where there is no running loop.
# `/api/v1/admin/login` is one, so every admin session was silently not
# persisted while the `async def` org login worked -- a difference invisible
# from the endpoint itself. Holding the loop lets a write scheduled from a
# worker thread still reach it.
_LOOP = None


def bind_loop() -> None:
    """Record the serving loop. Called once at startup."""
    global _LOOP
    import asyncio
    try:
        _LOOP = asyncio.get_running_loop()
    except RuntimeError:
        _LOOP = None


def _spawn(coro) -> None:
    """Run a coroutine in the background, holding a reference until it ends."""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Called from a threadpool worker (a sync endpoint) or with no loop at
        # all (tests, scripts).
        if _LOOP is not None and not _LOOP.is_closed():
            asyncio.run_coroutine_threadsafe(coro, _LOOP)
        else:
            # Memory-only is fine here, but the coroutine must be closed or
            # Python warns that it was never awaited.
            coro.close()
        return
    task = loop.create_task(coro)
    _BACKGROUND.add(task)
    task.add_done_callback(_BACKGROUND.discard)


def issue(subject: str, role: str, org_id: str | None = None) -> str:
    """Mint a session.

    Persistence runs in the background so login latency does not depend on the
    database round trip; the in-memory copy is authoritative for this process
    either way, and the write only matters at the next restart.
    """
    from app.db import repo_sessions

    token = secrets.token_urlsafe(32)
    ttl = ttl_for(role)
    claims = {"sub": subject, "role": role, "org_id": org_id,
              "exp": time.time() + ttl}
    _TOKENS[token] = claims
    _spawn(repo_sessions.persist(token, claims, ttl))
    return token


def _resolve(token: str | None) -> dict | None:
    if not token:
        return None
    t = token.removeprefix("Bearer ").strip()
    claims = _TOKENS.get(t)
    if claims is None:
        return None
    if claims["exp"] < time.time():
        _TOKENS.pop(t, None)
        _forget(t)
        return None
    return claims


def _forget(token: str) -> None:
    from app.db import repo_sessions
    _spawn(repo_sessions.drop(token))


def revoke(token: str | None) -> bool:
    """Sign-out. The account survives: a device UID is derived from the install,
    so signing back in restores the same identity."""
    if not token:
        return False
    t = token.removeprefix("Bearer ").strip()
    existed = _TOKENS.pop(t, None) is not None
    if existed:
        _forget(t)
    return existed


def session_count() -> int:
    return len(_TOKENS)


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

def check_admin_credentials(username: str, password: str) -> bool:
    s = get_settings()
    if _ADMIN_HASH is None:
        prepare_admin_credentials()
    # Verify the password even when the username is wrong, so a valid username
    # is not distinguishable by response time.
    ok_pw = verify_password(password, _ADMIN_HASH)
    ok_user = secrets.compare_digest(username, s.pact_admin_user)
    return ok_user and ok_pw


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

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
    """A signed-in app user -- seeker or helper."""
    if not get_settings().require_auth:
        return {"sub": "anonymous", "role": "seeker", "org_id": None}
    claims = _resolve(authorization)
    if claims is None or claims["role"] not in ("seeker", "helper"):
        raise HTTPException(status_code=401, detail="device session required")
    return claims


current_device = Depends(_current_device)


def verify_ws_token(token: str | None, role: str = "admin") -> dict | None:
    """WebSockets cannot send headers, so the token arrives as a query param."""
    if not get_settings().require_auth:
        return {"sub": "anonymous", "role": role, "org_id": None}
    claims = _resolve(token)
    return claims if claims and claims["role"] == role else None
