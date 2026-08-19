"""WebSocket endpoints.

/ws/agents -- admin, full deliberation firehose
/ws/org    -- one organization's slice, same bus and envelope, redacted

One bus, two audiences, no second implementation.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.bus import gate
from app.bus.eventbus import bus
from app.db import repo_events
from app.deps import verify_ws_token
from app.privacy import policy as privacy_policy
from app.privacy import redact

log = logging.getLogger(__name__)
router = APIRouter()


async def _pump(ws: WebSocket, q: asyncio.Queue, audience: str | None = None) -> None:
    """One bus, two audiences, no second implementation (agents.md 3.5).

    `audience=None` is the admin firehose. Anything else goes through the A7
    projection, which may return None -- meaning the whole event is withheld
    and never reaches the socket at all. Field redaction alone is not enough:
    an organization must not learn that a cross-org debate happened.
    """
    while True:
        ev = await q.get()
        if audience is not None:
            ev = redact.project_event(ev, audience, owned=True)
            if ev is None:
                continue
        await ws.send_json(ev)


async def _serve(ws: WebSocket, topic: str, *, q: asyncio.Queue | None = None,
                 audience: str | None = None) -> None:
    if q is None:
        q = bus.subscribe(topic)
    sender = asyncio.create_task(_pump(ws, q, audience))
    try:
        while True:
            msg = await ws.receive_json()
            op = msg.get("op")
            if op == "ping":
                await ws.send_json({"type": "pong"})
            elif op == "decision":
                released = gate.resolve(msg.get("decision_id", ""), msg)
                await ws.send_json(
                    {"type": "decision.ack", "decision_id": msg.get("decision_id"), "released": released}
                )
            else:
                await ws.send_json({"type": "error", "payload": {"code": "UNKNOWN_OP", "op": op}})
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("websocket error on %s", topic)
    finally:
        bus.unsubscribe(topic, q)
        sender.cancel()


@router.websocket("/ws/agents")
async def ws_agents(ws: WebSocket, trace_id: str | None = None, since: int | None = None,
                    token: str | None = None):
    if verify_ws_token(token, "admin") is None:
        await ws.close(code=4401)          # policy violation: unauthenticated
        return
    await ws.accept()

    # Subscribe BEFORE replaying, so events arriving mid-replay are queued
    # rather than lost in the gap between the two.
    topic = trace_id or "*"
    q = bus.subscribe(topic)

    replayed = 0
    if since is not None:
        for ev in await repo_events.replay(trace_id, since):
            await ws.send_json(ev)
            replayed += 1

    await ws.send_json({"type": "hello",
                        "payload": {"topic": topic, "since": since, "replayed": replayed}})
    await _serve(ws, topic, q=q)


@router.websocket("/ws/org")
async def ws_org(ws: WebSocket, org_id: str, token: str | None = None):
    """One organization's slice, through the A7 org-audience projection.

    Two things were wrong here before. It had no authentication at all, while
    /ws/agents next to it verified a token. And it was silent: the bus only
    routes to `org:<id>` when an event carries `org_id`, and nothing in the
    pipeline set it -- so the socket subscribed to a topic no frame reached.
    notify/dispatcher.py now stamps org_id on the frames an org is entitled to.
    """
    if verify_ws_token(token, "org") is None:
        await ws.close(code=4401)
        return
    await ws.accept()
    topic = f"org:{org_id}"
    await ws.send_json({
        "type": "hello",
        "payload": {"topic": topic, "audience": privacy_policy.ORG,
                    "blocked_event_types": sorted(privacy_policy.blocked_types(
                        privacy_policy.ORG))},
    })
    await _serve(ws, topic, audience=privacy_policy.ORG)
