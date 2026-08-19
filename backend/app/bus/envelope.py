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
from datetime import datetime, timezone
from typing import Any

V = 1

_counter = itertools.count(1)


def next_seq() -> int:
    return next(_counter)


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
