"""Session persistence.

Tokens lived in a module-level dict, so every backend restart signed out every
client. For the portals that is a re-login. For a phone in the field it is
worse: the app holds a token from sign-up, the server has forgotten it, and
every request 401s with no recovery path — the user sees a dead app and has no
reason to connect it to a server restart they never saw.

The store is **write-through with an in-memory cache**, hydrated once at
startup. That shape is deliberate: `verify_ws_token` is called synchronously
from the WebSocket handshake, and making the token lookup async would push
`await` through every dependency for a dictionary read. Sessions are written to
Mongo when issued and read back once at boot, so a restart is invisible while
the hot path stays synchronous.

Falls back to memory-only when Mongo is unavailable, because the whole
application already degrades that way and auth must not be the one thing that
hard-fails.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.mongo import get_db

log = logging.getLogger(__name__)

COLLECTION = "sessions"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def persist(token: str, claims: dict[str, Any], ttl_s: int) -> None:
    db = get_db()
    if db is None:
        return
    try:
        await db[COLLECTION].replace_one(
            {"_id": token},
            {"_id": token,
             "sub": claims.get("sub"),
             "role": claims.get("role"),
             "org_id": claims.get("org_id"),
             "issued_at": _now(),
             # A real datetime so the TTL index can expire it. Mongo removes
             # the row; the in-memory copy is checked against `exp` anyway, so
             # the two never disagree in a way that grants access.
             "expires_at": _now() + timedelta(seconds=ttl_s)},
            upsert=True)
    except Exception:
        log.debug("session persist skipped", exc_info=True)


async def drop(token: str) -> None:
    db = get_db()
    if db is None:
        return
    try:
        await db[COLLECTION].delete_one({"_id": token})
    except Exception:
        log.debug("session drop skipped", exc_info=True)


async def load_all() -> dict[str, dict[str, Any]]:
    """Every live session, for the in-memory cache at startup.

    Expired rows are filtered here rather than trusted to the TTL monitor,
    which only runs about once a minute and would otherwise hand back a session
    that should already be gone.
    """
    db = get_db()
    if db is None:
        return {}
    try:
        rows = await db[COLLECTION].find({"expires_at": {"$gt": _now()}}).to_list(5000)
    except Exception:
        log.warning("could not restore sessions; clients will need to sign in again")
        return {}

    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        out[r["_id"]] = {
            "sub": r.get("sub"), "role": r.get("role"), "org_id": r.get("org_id"),
            "exp": r["expires_at"].replace(tzinfo=timezone.utc).timestamp(),
        }
    if out:
        log.info("auth: restored %d session(s) across restart", len(out))
    return out


async def purge_for(subject: str, role: str) -> int:
    """Invalidate every session for one account, e.g. on a password change."""
    db = get_db()
    if db is None:
        return 0
    try:
        res = await db[COLLECTION].delete_many({"sub": subject, "role": role})
        return res.deleted_count
    except Exception:
        return 0
