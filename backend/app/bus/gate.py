"""Admin gate: parks the pipeline on an asyncio.Future until a human decides,
or the autopilot timeout fires.

Resolved from two places -- the REST endpoint and an inbound WebSocket frame --
so both funnel through `resolve()`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.bus.eventbus import bus

log = logging.getLogger(__name__)

_pending: dict[str, asyncio.Future] = {}


def pending_ids() -> list[str]:
    return list(_pending)


async def await_admin(
    trace_id: str,
    decision_id: str,
    *,
    run_id: str | None = None,
    timeout_s: int = 25,
    autopilot: bool = True,
) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()
    _pending[decision_id] = fut

    await bus.publish(
        trace_id,
        "awaiting_admin",
        {"decision_id": decision_id, "timeout_s": timeout_s, "autopilot": autopilot},
        agent="a8_gate",
        run_id=run_id,
    )

    try:
        if not autopilot:
            # Autopilot off means a human decides -- so wait for one, with no
            # deadline. This used to time out and return {"action": "hold"},
            # which NOTHING downstream reads: the run fell through the reject
            # and override branches and committed the arbiter's choice anyway,
            # writing "hold" into the audit trail beside a real stock movement.
            # Turning autopilot off therefore delayed the automatic approval by
            # `timeout_s` rather than preventing it, which is the opposite of
            # what the switch promises. The whole-run ceiling in
            # scripted._guarded is the backstop against waiting forever.
            log.info("gate %s waiting for a human (autopilot off)", decision_id)
            return await fut
        return await asyncio.wait_for(fut, timeout_s)
    except asyncio.TimeoutError:
        log.info("gate %s timed out -> auto_approve", decision_id)
        return {"action": "auto_approve", "decision_id": decision_id,
                "admin_id": "autopilot"}
    finally:
        _pending.pop(decision_id, None)


def resolve(decision_id: str, action: dict[str, Any]) -> bool:
    """Returns True if a waiting pipeline was actually released."""
    fut = _pending.get(decision_id)
    if fut is None or fut.done():
        return False
    fut.set_result(action)
    return True
