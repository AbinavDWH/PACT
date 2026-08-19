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

log = logging.getLogger(__name__)
router = APIRouter()

# Fields an organization must never see, even on its own trace.
_ORG_BLOCKED_TYPES = {"debate.turn", "debate.opened", "debate.closed", "options.proposed", "agent.token"}


async def _pump(ws: WebSocket, q: asyncio.Queue) -> None:
    while True:
        ev = await q.get()
        await ws.send_json(ev)


async def _serve(ws: WebSocket, topic: str, *, q: asyncio.Queue | None = None) -> None:
    if q is None:
        q = bus.subscribe(topic)
    sender = asyncio.create_task(_pump(ws, q))
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
async def ws_org(ws: WebSocket, org_id: str):
    await ws.accept()
    await ws.send_json({"type": "hello", "payload": {"topic": f"org:{org_id}"}})
    # TODO: apply the A7 org-audience projection here before sending
    # (agents.md 3.5). Lands with the organization portal.
    await _serve(ws, f"org:{org_id}")
