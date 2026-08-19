"""In-process publish/subscribe bus. No Redis -- the agents are coroutines in
this same process, so a network hop between them would buy nothing.

Topics:
    "*"             every event (admin portal firehose)
    "<trace_id>"    one request's deliberation
    "org:<org_id>"  one organization's slice
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable

from app.bus import envelope

log = logging.getLogger(__name__)

QUEUE_MAX = 1000

# Optional sink for durable storage. Wired to the Mongo repo at startup; left
# as None when Mongo is unconfigured so the bus still works standalone.
PersistFn = Callable[[dict[str, Any]], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._persist: PersistFn | None = None
        self._delay_ms: int = 0

    # -- wiring ------------------------------------------------------------
    def set_persist(self, fn: PersistFn | None) -> None:
        self._persist = fn

    def set_delay_ms(self, ms: int) -> None:
        """Presentation dial: slow emission so the debate is readable."""
        self._delay_ms = max(0, ms)

    # -- subscription ------------------------------------------------------
    def subscribe(self, topic: str = "*") -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAX)
        self._subs[topic].add(q)
        return q

    def unsubscribe(self, topic: str, q: asyncio.Queue) -> None:
        subs = self._subs.get(topic)
        if not subs:
            return
        subs.discard(q)
        if not subs:
            self._subs.pop(topic, None)

    def subscriber_count(self) -> int:
        return sum(len(v) for v in self._subs.values())

    # -- publication -------------------------------------------------------
    async def publish(
        self,
        trace_id: str,
        type_: str,
        payload: dict[str, Any] | None = None,
        *,
        agent: str = "system",
        run_id: str | None = None,
        org_id: str | None = None,
    ) -> dict[str, Any]:
        ev = envelope.build(
            trace_id, type_, payload, agent=agent, run_id=run_id, org_id=org_id
        )
        await self.emit(ev)
        return ev

    async def emit(self, ev: dict[str, Any]) -> None:
        if self._delay_ms:
            await asyncio.sleep(self._delay_ms / 1000)

        if self._persist is not None:
            # Fire and forget: durability must never gate the live stream.
            asyncio.create_task(self._safe_persist(ev))

        topics = ["*", ev["trace_id"]]
        if ev.get("org_id"):
            topics.append(f"org:{ev['org_id']}")

        for topic in topics:
            for q in list(self._subs.get(topic, ())):
                try:
                    q.put_nowait(ev)
                except asyncio.QueueFull:
                    # A slow browser tab must never stall aid allocation.
                    log.warning("dropping event for saturated subscriber on %s", topic)

    async def _safe_persist(self, ev: dict[str, Any]) -> None:
        try:
            await self._persist(ev)  # type: ignore[misc]
        except Exception:
            log.exception("failed to persist event %s", ev.get("seq"))


bus = EventBus()
