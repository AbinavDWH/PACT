"""PACT backend: app factory, lifespan, health.

Routers carry the surface area; this file only wires them up and does the
startup work that has to happen in order -- Groq warmup, Mongo, indexes, the
event sequence counter, then the seed and its geo sanity check.

The Evaluation-1 endpoints that used to live here (`POST /api/v1/crises`, plus
`RESOURCE_PROVIDERS`, `create_response_plan` and the resource/urgency maps) are
gone. They were superseded by `/api/v1/pact/ingest` and the real A5 solver, and
had no callers anywhere in backend, web or android -- but they still answered
requests, which meant a stale endpoint could produce a plausible-looking
allocation from a hardcoded provider table that no longer matched the database.
agents.md 6.6 already listed them as deleted.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.bus import envelope
from app.bus.eventbus import bus
from app import deps
from app.config import get_settings
from app.db import mongo
from app.db import repo_events
from app.db import seed as db_seed
from app.db.indexes import ensure_indexes
from app.llm import groq_client
from app.notify import fcm
from app.routers import admin as admin_router
from app.routers import assignments as assignments_router
from app.routers import ingest as ingest_router
from app.routers import session as session_router
from app.routers import tiles as tiles_router
from app.routers import ws as ws_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("pact")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    bus.set_delay_ms(s.demo_latency_ms)
    log.info("PACT backend starting")
    log.info("  groq:     %s", "configured" if s.groq_enabled else "NOT configured (scripted only)")
    log.info("  autopilot:%s  gate_timeout=%ss", s.autopilot, s.gate_timeout_s)

    if s.groq_enabled:
        await groq_client.warmup()

    # Optional. Without a service-account key this reports itself unavailable
    # and dispatch falls back to the outbox, rather than failing at send time.
    fcm_state = fcm.init()
    log.info("  fcm:      %s", "ready" if fcm_state.get("ready")
             else f"unavailable ({fcm_state.get('reason')})")

    # Hash the configured admin password once, so no comparison ever touches
    # the plaintext.
    deps.prepare_admin_credentials()
    # So a session issued from a `def` endpoint -- which FastAPI runs in a
    # threadpool with no loop of its own -- can still be persisted.
    deps.bind_loop()

    if await mongo.connect():
        await ensure_indexes()
        bus.set_persist(repo_events.persist)
        # Before serving: a client holding a valid token must not be signed out
        # by a restart it never saw.
        restored = await deps.restore()
        log.info("  auth:     %d session(s) restored", restored)
        # Before any event is published, so replay and ordering stay coherent
        # across a restart.
        envelope.seed_from(await repo_events.max_seq())
        if await db_seed.get_db_empty():
            await db_seed.seed()
        check = await db_seed.verify_lng_lat()
        if check.get("checked") and not check.get("ok"):
            log.error("GEO SANITY FAILED: %s", check)
        else:
            log.info("  geo:      ok (nearest offer %.2f km)", check.get("nearest_km", -1))
    else:
        log.info("  mongo:    unavailable -- in-memory fallback active")

    yield
    await mongo.disconnect()
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
app.include_router(admin_router.public)
app.include_router(admin_router.router)
app.include_router(ingest_router.router)
app.include_router(assignments_router.router)
app.include_router(session_router.router)
app.include_router(tiles_router.router)


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
        # configured != connected. Reporting only "configured" hid a live
        # outage behind a green check.
        "mongo": {"configured": s.mongo_enabled, "connected": mongo.is_healthy()},
        "groq": {"configured": s.groq_enabled, "model": s.groq_model},
        "mode": "live-agents" if s.groq_enabled else "deterministic-fallback",
        "storage": "mongo" if mongo.is_healthy() else "in-memory fallback",
        # Reported separately from "configured" for the same reason mongo is:
        # a half-configured push setup (app registers a token, server cannot
        # send) looks like nothing is wrong.
        "push": fcm.status(),
        "rate_limit": groq_client.stats(),
    }

