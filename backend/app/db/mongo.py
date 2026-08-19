"""Motor client, optional by design.

If MONGO_URI is unset or the cluster is unreachable, `get_db()` returns None and
every caller degrades to in-memory behaviour. That is deliberate: the demo runs
on venue wifi against Atlas, and a network drop must not take the pipeline down.
"""

from __future__ import annotations

import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings

log = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None
_healthy = False


async def connect() -> bool:
    """Called once at startup. Never raises -- returns False and logs instead."""
    global _client, _db, _healthy
    s = get_settings()
    if not s.mongo_enabled:
        log.info("mongo: not configured, using in-memory stores")
        return False
    try:
        # 12s: Atlas SRV lookup plus TLS handshake is slow on venue wifi.
        _client = AsyncIOMotorClient(s.mongo_uri, serverSelectionTimeoutMS=12000)
        await _client.admin.command("ping")
        _db = _client[s.mongo_db]
        _healthy = True
        log.info("mongo: connected to %s", s.mongo_db)
        return True
    except Exception as e:
        detail = str(e)
        hint = ""
        # Atlas answers a non-allowlisted IP with a TLS internal-error alert
        # rather than an auth error. It reads like a certificate problem and is
        # not one -- it means Network Access is blocking this IP.
        if "TLSV1_ALERT_INTERNAL_ERROR" in detail or "SSL handshake failed" in detail:
            hint = " -- likely cause: this IP is not in the Atlas Network Access allowlist"
        elif "Authentication failed" in detail:
            hint = " -- check the username/password in MONGO_URI"
        log.warning("mongo: connect failed (%s)%s -- degrading to in-memory",
                    type(e).__name__, hint)
        _client, _db, _healthy = None, None, False
        return False


async def disconnect() -> None:
    global _client, _db, _healthy
    if _client is not None:
        _client.close()
    _client, _db, _healthy = None, None, False


def get_db() -> AsyncIOMotorDatabase | None:
    return _db


def is_healthy() -> bool:
    return _healthy


def mark_unhealthy() -> None:
    """Called when an operation fails mid-run so callers stop trying."""
    global _healthy
    _healthy = False
