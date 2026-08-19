"""/ws/org -- authentication and the org-audience projection.

Three separate faults were live here at once, and none of them would have
shown up as an error:

  1. No authentication at all, while /ws/agents beside it verified a token.
  2. Permanently silent: the bus only routes to `org:<id>` when an event
     carries org_id, and nothing in the pipeline ever set it.
  3. `_ORG_BLOCKED_TYPES` was defined and never referenced -- a dead constant
     that read like a working filter.

These tests run against the real app with the real bus, no server process.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.bus.eventbus import bus
from app.deps import issue
from app.main import app
from app.privacy import policy as privacy_policy

ORG = "ORG_NGO_001"
EXACT_LAT, EXACT_LON = 23.25991, 77.41263


@pytest.fixture
def client():
    # `with` runs the lifespan, which tries Mongo and Groq; the routes under
    # test do not need either, and both degrade rather than fail.
    with TestClient(app) as c:
        yield c


def _org_token():
    return issue("sanjeevani", "org", ORG)


def _admin_token():
    return issue("admin", "admin")


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def test_org_socket_rejects_a_connection_with_no_token(client):
    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/org?org_id={ORG}") as ws:
            ws.receive_json()


def test_org_socket_rejects_an_admin_token(client):
    """Role is checked, not merely token validity."""
    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/org?org_id={ORG}&token={_admin_token()}") as ws:
            ws.receive_json()


def test_org_socket_accepts_a_valid_org_token(client):
    with client.websocket_connect(f"/ws/org?org_id={ORG}&token={_org_token()}") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello"
        assert hello["payload"]["audience"] == privacy_policy.ORG
        assert "debate.turn" in hello["payload"]["blocked_event_types"]


# ---------------------------------------------------------------------------
# The projection
# ---------------------------------------------------------------------------

def test_an_org_scoped_frame_reaches_the_org_topic():
    """Regression for the silent-socket bug.

    The bus only routes to `org:<id>` when an event carries org_id, and
    nothing in the pipeline set it -- so /ws/org subscribed to a topic no
    frame ever reached. Tested on the bus directly: the WebSocket above is
    only a pump over these queues.
    """
    async def go():
        org_q = bus.subscribe(f"org:{ORG}")
        try:
            await bus.publish_org(ORG, "REQ-T", "decision.committed",
                                  {"match_id": "M1"})
            assert not org_q.empty()
            ev = org_q.get_nowait()
            assert ev["type"] == "decision.committed"
            assert ev["org_id"] == ORG
        finally:
            bus.unsubscribe(f"org:{ORG}", org_q)

    asyncio.run(go())


def test_an_org_scoped_frame_does_not_duplicate_on_the_admin_firehose():
    """publish(), not publish_org(), would fan a per-org copy out to "*" too,
    rendering the same committed card once per organization in the admin
    portal."""
    async def go():
        star_q = bus.subscribe("*")
        trace_q = bus.subscribe("REQ-T")
        try:
            await bus.publish_org(ORG, "REQ-T", "decision.committed", {"match_id": "M1"})
            assert star_q.empty()
            assert trace_q.empty()
        finally:
            bus.unsubscribe("*", star_q)
            bus.unsubscribe("REQ-T", trace_q)

    asyncio.run(go())


def test_an_ordinary_publish_still_reaches_both_admin_topics():
    async def go():
        star_q = bus.subscribe("*")
        try:
            await bus.publish("REQ-T", "agent.message", {"text": "hi"})
            assert not star_q.empty()
        finally:
            bus.unsubscribe("*", star_q)

    asyncio.run(go())


def test_an_org_never_receives_the_deliberation(client):
    """Every debate-bearing type is dropped before it reaches the socket."""
    for t in ("debate.turn", "debate.opened", "options.proposed",
              "agent.token", "decision.proposed", "agent.tool_call"):
        ev = {"v": 1, "seq": 1, "ts": "t", "trace_id": "T", "type": t,
              "agent": "a4_advocates", "payload": {"claim": "c2 is closest"}}
        from app.privacy import redact
        assert redact.project_event(ev, privacy_policy.ORG) is None


def test_an_org_frame_carries_no_exact_position(client):
    from app.privacy import redact
    ev = {"v": 1, "seq": 1, "ts": "t", "trace_id": "T", "type": "decision.committed",
          "agent": "a8_gate",
          "payload": {"request": {"lat": EXACT_LAT, "lon": EXACT_LON},
                      "delivery_code": "K7M2QP",
                      "message": f"Deliver to {EXACT_LAT}, {EXACT_LON}."}}
    out = redact.project_event(ev, privacy_policy.ORG, owned=True)
    import json
    blob = json.dumps(out)
    assert "23.25991" not in blob
    assert "delivery_code" not in out["payload"]


# ---------------------------------------------------------------------------
# The admin socket is unaffected
# ---------------------------------------------------------------------------

def test_admin_socket_still_requires_a_token(client):
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/agents") as ws:
            ws.receive_json()


def test_admin_socket_accepts_and_announces_its_topic(client):
    with client.websocket_connect(f"/ws/agents?token={_admin_token()}") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello"
        assert hello["payload"]["topic"] == "*"
