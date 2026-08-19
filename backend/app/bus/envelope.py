"""Event envelope construction.

Every frame the portal receives has this shape (agents.md section 3.1):

    {v, seq, ts, trace_id, run_id, agent, type, payload}

`seq` is process-wide monotonic rather than per-connection. That makes replay
(`?since=`) unambiguous with a single comparison, and lets a client dedupe
across a reconnect. A client filtered to one trace_id will see gaps in seq --
those are other traces' events, not lost frames, so treat seq as an ordering
and dedup key, never as a completeness check.
"""

from __future__ import annotations

import itertools
import logging
import threading
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)

V = 1

# Seeded from the highest persisted seq at startup (see seed_from). Starting at
# 1 every boot meant that after a restart, fresh events carried LOWER numbers
# than events already in agent_events: `?since=` replay returned nothing, and
# the All Requests list sorted stale traces above live ones.
_counter = itertools.count(1)
_lock = threading.Lock()


def next_seq() -> int:
    return next(_counter)


def seed_from(highest_persisted: int) -> int:
    """Resume numbering above anything already stored. Idempotent and safe to
    call before any event is published."""
    global _counter
    if highest_persisted <= 0:
        return 0
    with _lock:
        _counter = itertools.count(highest_persisted + 1)
    log.info("event seq resumed at %d", highest_persisted + 1)
    return highest_persisted + 1


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def build(
    trace_id: str,
    type_: str,
    payload: dict[str, Any] | None = None,
    *,
    agent: str = "system",
    run_id: str | None = None,
    org_id: str | None = None,
) -> dict[str, Any]:
    ev: dict[str, Any] = {
        "v": V,
        "seq": next_seq(),
        "ts": now_iso(),
        "trace_id": trace_id,
        "run_id": run_id,
        "agent": agent,
        "type": type_,
        "payload": payload or {},
    }
    if org_id:
        ev["org_id"] = org_id
    return ev
