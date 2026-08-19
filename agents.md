# AGENTS.md — Agent Pipeline, Groq, MongoDB, and API Surface

This document specifies PACT's server side: the autonomous agent pipeline, how the agents use the
Groq API, how their deliberation streams to the admin portal, the MongoDB schema, and the full HTTP
and WebSocket surface.

Related documents:

| File | Purpose |
|---|---|
| `memory_draft.md` | High-level project memory, identity model, architecture, demo strategy |
| `sms.md` | SMS transport protocol |
| `codec.md` | Option taxonomy and compressed code language |
| `agents.md` | This file |

---

## 1. Shape of the System

```text
Android app (seeker or helper)
        |
        |  taps -> codec string (codec.md)
        v
   +----+----------------------------+
   |  data available?                |
   +--------+-------------+----------+
            | yes         | no
            v             v
  POST /api/v1/pact/  SMS -> gateway -> POST /api/v1/sms/webhook
       ingest                          (thin adapter, calls ingest)
            |             |
            +------+------+
                   v
          decoded JSON dict
                   v
   +---------------------------------+
   |  In-process async agent pipeline |
   |  (FastAPI, asyncio, no Redis)    |
   +---------------+-----------------+
                   |
        +----------+----------+
        v                     v
    MongoDB            EventBus (asyncio pub/sub)
   (2dsphere)                  |
                    +----------+----------+
                    v                     v
             WS /ws/agents          WS /ws/org
            (admin, full)      (org portal, own slice)
```

The core principle, stated once and enforced everywhere below:

> **The LLM produces labels, rankings, choices among enumerated options, and prose.
> Every number written to the database is produced by Python.**

An LLM never divides 300 kits across 4 providers.

---

## 2. Agent Pipeline

`det.` marks a deterministic Python agent with no LLM call.

```text
decoded JSON
   |
[A0  Intake Normalizer]      det.       -> Request document, masked/raw split
   |
[A1  Dedupe / Cluster]       det.       -> drop or merge repeats
   |
[A2  Triage]                 LLM        -> severity, tier, resource line items
   |
[A3  Geo Candidate Finder]   det.       -> candidates via $geoNear
   |
[A4  Helper Advocates x N]   LLM (par.) -> per-candidate bid + risk flags   <- the discussion
   |
[A5  Allocation Solver]      det.       -> 3 named feasible options
   |
[A6  Arbiter]                LLM        -> picks one option_id + rebuttals  <- the debate
   |
[A7  Privacy Redactor]       det.       -> per-audience projection
   |
[A8  Admin Gate]             human      -> approve / override / reject
   |
[A9  Narrator + Dispatcher]  LLM + det. -> justification, notify helpers
   |
[A10 Verification]           det. + LLM -> delivery confirmation
   |
[A11 Replanner Watchdog]     det.       -> re-enters at A3 on change
```

### 2.1 Agent Roster

| # | Agent | LLM? | Rationale |
|---|---|---|---|
| A0 | Intake Normalizer | No | Schema mapping, unit coercion, geohash computation. Pure code. |
| A1 | Dedupe / Cluster | No | geohash7 + resource + 15-minute window + UID. Deterministic key. |
| A2 | **Triage** | **Yes** | Genuine multi-factor judgement: three infants with no water at 46 °C versus one adult with a sprain. This is what language models are actually good at. |
| A3 | Geo Candidate Finder | No | `$geoNear`. Never an LLM. |
| A4 | **Helper Advocates** | **Yes** | Produces the visible discussion. Each advocate argues one candidate's fit in one or two sentences plus structured flags. High demo value, small token cost. |
| A5 | **Allocation Solver** | **No** | Arithmetic and constraint satisfaction. Emits ranked feasible options. |
| A6 | **Arbiter** | **Yes** | Chooses among *precomputed* options when scores are close, or when two requests contend for one scarce stock. Constrained to return an existing `option_id`. |
| A7 | Privacy Redactor | No | A deterministic field policy is auditable. Never trust a language model to gate personal data. |
| A8 | Admin Gate | Human | `asyncio.Future` with a timeout and an autopilot fallback. |
| A9 | Narrator | **Yes** | Human-readable justification and helper notification copy, plus a short SMS variant. |
| A10 | Verification | Mixed | Delivery-code matching is deterministic; the LLM only reasons over free-text discrepancies. |
| A11 | Replanner | No trigger, Yes narrative | Timer, decline, and new-critical detection are code; re-enters at A3. |

### 2.2 A2 — Triage

```jsonc
// input
{
  "request_id": "REQ-8F2A1C",
  "raw_needs": [{ "code": "M", "qty": 3, "key": "medical_kits" }],
  "people": { "est": 3, "bucket": "3-4" },
  "vulnerabilities": ["child_under_5"],
  "injury": "serious_stable",
  "mobility": "trapped_debris",
  "hazard": "building_collapse",
  "hours_since_event": 9,
  "self_reported_urgency": "critical",
  "deterministic_prior": 47,
  "area_context": { "open_requests_nearby": 12 }
}
```

```jsonc
// output — validated with Pydantic
{
  "severity": 0,                       // 0-100
  "tier": "T1",                        // T1..T4; T1 = life threat within 6 h
  "life_threat": true,
  "time_to_harm_hours": 4,
  "line_items": [{ "resource": "medical_kits", "quantity": 3, "rationale": "..." }],
  "escalations": ["insulin implies cold chain required"],
  "confidence": 0.82,
  "reasoning": "<= 40 words"
}
```

System prompt:

> You are the Triage Agent in a disaster response system. Given a structured request, assign a
> severity from 0 to 100 and a tier. T1 means life threat within 6 hours. Weigh infants, elderly,
> injured and disabled people; hazard type; hours since the event; resource type (medical, then
> water, then food, then shelter for immediate life risk); and local saturation. A deterministic
> prior is supplied — you may depart from it, but say why in your reasoning. Do NOT compute
> allocations. Do NOT choose providers. Do NOT inflate everything to T1; the tiers must
> discriminate. Output JSON only, matching the given schema. Keep `reasoning` under 40 words.

**Invariants are enforced in Python after validation**, because these fields are individually valid
and only jointly wrong — Pydantic cannot see the contradiction:

| Invariant | Why |
|---|---|
| `tier == T1` ⇒ `life_threat` | T1 is *defined* as life threat within 6 h |
| `life_threat` ⇒ `tier ≥ T2` | A life threat cannot sit in T3/T4 |
| `tier == T1` ⇒ `time_to_harm_hours ≤ 6` | Same definition |
| `severity ≥ tier floor` (80/55/30/0) | A T1 at severity 20 sorts below a T3 at 60 in every severity-ordered view |

Corrections are published as `error{code: TRIAGE_INCONSISTENT}` carrying was/now/why per field.
Repairing silently would let the portal display output the model never produced.

### 2.3 A3 — Geo Candidate Finder

Deterministic. See §4.3 for the exact aggregation pipeline. Emits an `agent.tool_call` event so the
portal visibly shows the database query rather than implying one.

Radius ladder: 10 km, then 25, then 60, then 150. Stop at the first radius yielding at least three
candidates or covering the full demand. Cap the result at **8 candidates** — this is also the token
cap for A4.

### 2.4 A4 — Helper Advocates

One Groq call carrying all candidates, returning an array. Not N calls: same wall-clock, but eight
times fewer requests against the rate limit.

```jsonc
// input
{
  "need": { "severity": 88, "tier": "T1", "line_items": [...] },
  "candidates": [
    { "cand_id": "c1", "owner_kind": "org", "org_type": "ngo",
      "distance_km": 6.2, "stock": { "medical_kits": 180 }, "eta_minutes": 55,
      "reliability": 0.86, "capacity_load": 0.4, "capabilities": [],
      "constraints": ["no cold chain"] }
  ]
}
```

```jsonc
// output
{ "bids": [ { "cand_id": "c1", "fit": 74, "argument": "<= 25 words",
              "risk_flags": ["no cold chain, insulin unsafe"],
              "recommended_share": "full" } ] }   // full | partial | none
```

System prompt:

> You are a panel of Helper Advocate Agents. For each candidate helper, argue in at most 25 words
> why it should or should not serve this need, and give a fit score from 0 to 100. Ground every
> claim in the supplied fields — never invent stock, distance, or capability. Flag hard blockers
> such as missing cold chain, blocked access, or saturated capacity. You do NOT allocate
> quantities. JSON only.

### 2.5 A5 — Allocation Solver (deterministic)

**As built** — `app/agents/solver.py`. Weights are named constants, not literals in the pipeline:

```python
candidate = (0.30 * speed          # 1 - eta/360, clamped
           + 0.25 * fit/100        # from A4
           + 0.15 * reliability    # from the organization document
           + 0.15 * headroom       # min(free/demand, 1)
           - 0.20 * capacity_load
           - 0.15 * blockers/3)    # len(A4 risk_flags)

option    = (0.45 * coverage
           + 0.35 * quantity_weighted_mean(candidate scores)
           + 0.20 * speed(total_eta))
```

Both clamped to `[0, 1]`. Every input comes from `$geoNear`, an organization document, or A4 —
nothing is a constant standing in for a measurement. When A4 did not bid on a candidate, the `fit`
term is dropped and its weight is redistributed across the remaining evidence rather than scored as
zero: a supplier nobody argued for should not be buried by the model's silence.

The candidate term is weighted by quantity, not a flat mean, so an option drawing 90% of its units
from a strong supplier does not tie with the reverse.

A5 emits an `agent.tool_call` carrying the weights and the per-candidate scores, so the ranking is
inspectable on screen rather than asserted.

Greedy fill by descending score, respecting available stock, a minimum viable split size, and active
reservation locks.

Emits **three named options**, which is what makes the arbiter's choice legible on screen:

| Option | Optimises for |
|---|---|
| `fastest` | Lowest total ETA |
| `max_coverage` | Highest fraction of the need met |
| `least_depleting` | Preserves stock that other open T1 requests depend on |

```jsonc
{ "options": [ { "option_id": "opt_1", "label": "fastest",
                 "allocations": [{ "owner_kind": "org", "owner_id": "...",
                                   "resource": "medical_kits", "qty": 3, "eta_min": 55 }],
                 "coverage_pct": 100, "unmet": 0, "total_eta": 55, "score": 0.81 } ] }
```

### 2.6 A6 — Arbiter

```jsonc
// output
{ "chosen_option_id": "opt_2",
  "confidence": 0.77,
  "turns": [ { "speaker": "arbiter", "claim": "...", "rebuts": "advocate:c3" } ],
  "justification": "<= 50 words",
  "dissent": "<= 25 words" }
```

System prompt:

> You are the Arbiter Agent. Choose exactly one of the provided allocation options by its
> `option_id`. You may NOT modify quantities, change providers, or invent new options. Weigh life
> threat first, then coverage, then speed, then avoiding depletion of a helper that other open T1
> requests depend on. Produce two to four short debate turns showing which advocate arguments you
> accepted and which you rejected. JSON only.

**`chosen_option_id` is validated against the option set before anything is written.** A value not
in the set is treated as a validation failure and triggers the deterministic fallback: **highest
solver score**, then coverage, then speed. That ordering only became meaningful once the score was a
real computation — while it was a per-strategy literal this path returned `max_coverage` every time,
whatever the candidates looked like. This is the structural answer to "what if the model hallucinates an allocation": it
cannot, because it never emits quantities.

### 2.7 A7 — Privacy Redactor (deterministic)

A field policy matrix, not a model. Audiences: `seeker`, `helper`, `org`, `admin`, `sms`.

| Field | Seeker | Helper (pre-accept) | Helper (post-accept) | Org portal | Admin |
|---|---|---|---|---|---|
| Seeker exact GPS | own | masked to ~1 km | exact | masked until its helper accepts | exact |
| Seeker contact | own | hidden | revealed | hidden | visible |
| Helper identity | after accept | own | own | own roster | visible |
| Other orgs' stock | hidden | hidden | hidden | **hidden** | visible |
| Full advocate debate | hidden | hidden | hidden | **hidden** | visible |
| Own allocation justification | summary | yes | yes | yes | yes |

Revelation is a state transition, not a default: `matches.reveal.helper_sees` gains `exact_loc` and
`contact` only after `decision.committed` **and** helper acceptance. The single publisher is
`POST /api/v1/assignments/{match_id}/accept`.

**Implementation** — `app/privacy/`, three passes in this order:

1. **Event-type filtering.** Whole types are dropped per audience *before* any field walk. An
   organization must not learn that a cross-org debate happened at all; the existence of the
   argument is itself a disclosure. Advocate and arbiter `agent.message` frames are dropped too,
   since filtering on type alone would leak the debate through the wrong door.
2. **Field redaction**, in two sub-passes. Unambiguous key names (`lat`, `phone`, `delivery_code`)
   are redacted at *any depth*; position-dependent ones (`free`, `qty`) use exact paths. The key
   pass exists because an exact-path table only redacts where it was told to look — a payload that
   nests the same data one level deeper sails through. That was a live leak, not a hypothetical.
3. **Free-text scrubbing.** A9 writes prose, and a coordinate pair inside a sentence is invisible to
   a path table. The narrator's prompt below *asks* the model not to emit coordinates; A7 does not
   rely on that, which is the entire reason A7 is deterministic.

`HIDDEN` removes the key rather than nulling it: a null looks like missing data, an absent key is a
visible redaction. Unknown audience names fail **closed**, to the strictest policy.

A7 publishes counts measured off the real payload, not a fixed list. If a rule stops matching, the
count drops and the portal shows it.

### 2.8 A8 — Admin Gate

```python
_pending: dict[str, asyncio.Future] = {}

async def await_admin(decision_id, payload, timeout_s=25, autopilot=True):
    fut = asyncio.get_running_loop().create_future()
    _pending[decision_id] = fut
    await bus.publish(trace_id, "awaiting_admin",
                      {"decision_id": decision_id, "timeout_s": timeout_s, "autopilot": autopilot})
    try:
        return await asyncio.wait_for(fut, timeout_s)
    except asyncio.TimeoutError:
        return {"action": "auto_approve"} if autopilot else {"action": "hold"}
    finally:
        _pending.pop(decision_id, None)

def resolve(decision_id, action):
    f = _pending.get(decision_id)
    if f and not f.done():
        f.set_result(action)
```

Admin actions arrive over **either** `POST /api/v1/admin/decisions/{id}/action` or an inbound
WebSocket frame; both funnel into `resolve()`.

| Action | Effect |
|---|---|
| `approve` | Proceed to A9 with the arbiter's chosen option |
| `override` | Re-enter at **A5** with the admin's allocations pinned as `opt_admin`; the solver validates feasibility before committing. An infeasible override emits `error{code: OVERRIDE_INFEASIBLE}` naming the actual free stock and the pipeline falls back to the arbiter's option. Deliberate under-allocation is allowed and recorded as partial coverage |
| `reject` | Re-enter at **A3** with the rejected helper excluded from candidates |
| `auto_approve` | Timeout path, identical to approve, tagged as unattended in `admin_actions` |

Ship with `autopilot = true` so the demo never stalls; toggle it off live to show human-in-the-loop.

### 2.9 A9 — Narrator and Dispatcher

System prompt:

> You write the human-facing record of a committed aid allocation. Produce three fields:
> `admin_summary` at most 45 words; `helper_message` at most 200 characters, imperative, including
> resource, quantity, masked area and ETA window; `sms_variant` at most 110 characters, ASCII only,
> no personal data. Never include the seeker's name, phone number, or exact coordinates.

Dispatch then follows the routing rule from `memory_draft.md`:

```text
allocation owner is an ORG        -> org web portal -> IT team assigns a named helper -> helper's app
allocation owner is an INDIVIDUAL -> straight to that volunteer's app
```

`app/notify/dispatcher.py`. The two paths differ in behaviour, not wording:

| | organization | individual volunteer |
|---|---|---|
| channel | `portal` | `push` |
| initial allocation state | `awaiting_assignment` | `pending_accept` |
| acceptable immediately | **no** | yes |

The org path's intermediary is enforced: `POST /assignments/{id}/accept` on an `awaiting_assignment`
allocation returns `NOT_ASSIGNED`, and `POST /org/assignments/{id}/assign` rejects a helper who is
not on that org's roster with `NOT_ON_YOUR_ROSTER`. That is what the group code buys.

There is no FCM project and no SMS gateway account, so every channel writes to `GET
/api/v1/sms/outbox` instead of pretending to send (cut-line 5).

### 2.10 A10 — Verification

Deterministic: delivery-code match, quantity delta, proximity of the helper's status ping to the
request point. The LLM is invoked **only** when a free-text discrepancy is present.

```jsonc
{ "verdict": "verified",             // verified | partial | disputed | fraud_suspected
  "delta_explained": true,
  "followup_action": "reallocate_remainder",
  "reason": "<= 30 words" }
```

### 2.11 A11 — Replanner Watchdog

Triggers, all deterministic: helper declined, SLA breach on ETA, helper marked blocked, a new T1
request contends for reserved stock, or the seeker cancelled. Re-enters at A3 under a **new
`run_id`** but the **same `trace_id`**, so the portal chains the replan visibly under the original
request.

---

## 3. Agent Deliberation Stream

The admin portal's headline feature is watching the agents deliberate. That requires a real event
schema, not log scraping.

### 3.1 Envelope

Every WebSocket frame:

```jsonc
{
  "v": 1,
  "seq": 148,                       // monotonic per connection; the client detects gaps
  "ts": "2026-08-19T10:02:31.412Z",
  "trace_id": "REQ-8F2A1C",         // the request being processed; the "room"
  "run_id": "RUN-01J...",           // one pipeline execution; replans get a new run_id
  "agent": "arbiter",
  "type": "debate.turn",
  "payload": { }
}
```

### 3.2 Event Types

| Type | Payload | Portal rendering |
|---|---|---|
| `run.started` | `{request, masked_summary, planned_agents}` | New card enters the live match stream |
| `agent.entered` | `{agent, label}` | Agent chip lights up |
| `agent.thinking` | `{note}` | Pulsing indicator |
| `agent.token` | `{delta}` | Streams Groq tokens into the bubble |
| `agent.message` | `{text, structured, confidence, latency_ms, tokens}` | Finalised bubble |
| `agent.tool_call` | `{tool, args, result_count, ms}` | Grey system line showing the real `$geoNear` |
| `debate.opened` | `{debate_id, topic, participants}` | Opens a threaded sub-panel |
| `debate.turn` | `{debate_id, turn_no, speaker, stance, claim, evidence, rebuts}` | Indented reply chain |
| `debate.closed` | `{debate_id, winner, dissent}` | Collapses with a verdict badge |
| `options.proposed` | `{options}` | Three option cards |
| `decision.proposed` | `{decision_id, chosen_option_id, justification, expires_at}` | Approve / Override / Reject bar with countdown |
| `awaiting_admin` | `{decision_id, timeout_s, autopilot}` | Pipeline visibly pauses |
| `admin.action` | `{decision_id, action, admin_id, override, note}` | Echoed to all connected admins |
| `decision.committed` | `{match_id, allocations, unmet}` | Card flips to committed |
| `privacy.reveal` | `{match_id, revealed_fields, to}` | Privacy badge flips |
| `notify.sent` | `{channel, target_masked, message}` | Dispatch line |
| `verify.result` | `{match_id, verdict}` | Verification badge |
| `replan.triggered` | `{reason, prior_run_id}` | New run chained under the same trace |
| `run.completed` | `{status, ms_total, groq_calls, tokens}` | Card settles |
| `error` | `{agent, code, fallback_used}` | Amber line; the pipeline continues |

`agent.token` is what makes the portal feel alive. It is not decoration — it is the difference
between "a system produced an answer" and "I watched it reason".

### 3.3 Representing a Debate

A debate is a first-class object keyed by `debate_id`. Turns are append-only and carry a `rebuts`
pointer forming a tree.

- Each A4 advocate emits one `debate.turn`, with `stance` derived from `recommended_share`.
- A6 emits two to four turns with `rebuts` set to the advocate turns it accepted or rejected.

The portal therefore renders a genuine threaded argument, not a flat log.

### 3.4 Event Bus

```python
class EventBus:
    def __init__(self):
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, topic="*") -> asyncio.Queue:
        q = asyncio.Queue(maxsize=1000)
        self._subs[topic].add(q)
        return q

    def unsubscribe(self, topic, q):
        self._subs[topic].discard(q)

    async def publish(self, trace_id, type_, payload, agent="system"):
        ev = build_envelope(trace_id, type_, payload, agent)
        asyncio.create_task(persist_event(ev))       # fire and forget into agent_events
        for topic in ("*", trace_id, f"org:{ev.get('org_id')}"):
            for q in list(self._subs[topic]):
                try:
                    q.put_nowait(ev)
                except asyncio.QueueFull:
                    pass                              # drop; never block the pipeline
```

Dropping on a full queue is intentional. A slow browser tab must never stall aid allocation.

### 3.5 WebSocket Endpoints

```python
@app.websocket("/ws/agents")            # admin, full stream
async def ws_agents(ws: WebSocket, trace_id: str | None = None,
                    since: int | None = None, token: str = ""):
    await require_admin(token)
    await ws.accept()
    q = bus.subscribe(trace_id or "*")
    if since is not None:
        for ev in await replay_events(trace_id, since):
            await ws.send_json(ev)                    # gap recovery from agent_events
    sender = asyncio.create_task(pump(ws, q))
    try:
        while True:
            msg = await ws.receive_json()
            if msg["op"] == "decision":
                gate.resolve(msg["decision_id"], msg)
            elif msg["op"] == "ping":
                await ws.send_json({"type": "pong"})
    finally:
        bus.unsubscribe(trace_id or "*", q)
        sender.cancel()
```

`WS /ws/org` reuses the same bus and envelope, but subscribes to the `org:{org_id}` topic and passes
every frame through the A7 org-audience projection before sending. **One bus, two audiences, no
second implementation.** It requires an `org`-role token (`POST /api/v1/org/login`).

Frames reach that topic two ways: `publish(..., org_id=...)`, which also fans out to the admin
firehose; and `publish_org()`, which emits to **one org topic only**. Per-organization copies of a
committed decision must use the latter — `publish()` would render the same card once per
organization in the admin portal. Org-scoped frames are tagged `scope: "org"` and excluded from
admin replay for the same reason. Each copy carries only that organization's own allocation.

Clients reconnect with `?since=<seq>` and replay the gap from `agent_events`.

---

## 4. MongoDB Schema

Database `pact`, accessed through Motor (async).

All geometry is GeoJSON: `{"type": "Point", "coordinates": [lng, lat]}`.

> **Coordinates are `[longitude, latitude]`, in that order.** This is the single most common
> geospatial bug. Write one unit test asserting it and never think about it again.

### 4.1 Collections

| Collection | Key fields | Indexes |
|---|---|---|
| `seekers` | `uid`, `name_enc`, `phone_hash`, `phone_enc`, `device_id`, `created_at`, `last_seen` | `uid` unique, `phone_hash` unique |
| `helpers` | `uid`, `org_id` (**nullable**), `name_enc`, `phone_hash`, `phone_enc`, `loc` (Point), `capabilities`, `status`, `fcm_token`, `created_at` | `uid` unique, `phone_hash` unique, `2dsphere: loc`, `org_id`, `status` |
| `organizations` | `name`, `type`, `group_code`, `web_user`, `web_pass_hash`, `base_loc` (Point), `service_radius_km`, `capabilities`, `reliability`, `capacity_load` | `group_code` **unique**, `web_user` unique, `2dsphere: base_loc`, `type` |
| `offers` | `owner` `{kind, id}`, `resource`, `available`, `reserved`, `loc` (Point), `eta_base_min`, `capabilities`, `updated_at` | **`2dsphere: loc`**, `{resource: 1, available: -1}`, `{"owner.id": 1, resource: 1}` unique |
| `requests` | `seeker_uid`, `source`, `raw_code`, `decoded`, `loc` (Point, exact), `loc_masked`, `line_items`, `triage`, `dedupe_key`, `status`, `created_at` | **`2dsphere: loc`**, `{status: 1, "triage.severity": -1}`, `{created_at: -1}`, `dedupe_key` |
| `matches` | `request_id`, `run_id`, `option_id`, `allocations`, `assigned_helper_id` (**nullable**), `coverage_pct`, `unmet`, `justification`, `approved_by`, `reveal`, `delivery_code`, `status` | `request_id`, `{"allocations.owner.id": 1, status: 1}`, `{created_at: -1}` |
| `agent_events` | Full envelope plus `payload` | `{trace_id: 1, seq: 1}`, `{ts: -1}`, **TTL 24 h on `ts`** |
| `sms_messages` | `direction`, `from_hash`, `raw`, `parsed`, `seq`, `crc_ok`, `status` | `{from_hash: 1, seq: 1}` **unique** (duplicate suppression), TTL 7 d |
| `admin_actions` | `decision_id`, `admin_id`, `action`, `before`, `after`, `note`, `ts` | `{ts: -1}` — **never TTL; this is the audit trail** |
| `locks` | `_id: "res:{owner_id}:{resource}"`, `run_id`, `qty`, `expires_at` | TTL on `expires_at`, 60 s |

### 4.2 Notes on Key Fields

- **`phone_hash`** — captured once at sign-up. It is the join key that lets an inbound SMS from a
  known number be matched to an existing account, and it is what makes an SMS reply possible for a
  request that originally arrived over HTTP. Unique, so one number is one account.
- **`name_enc` / `phone_enc`** — encrypted at rest, released only by the A7 redactor after an
  allocation is committed and the helper accepts. **Never** encoded into a codec payload.
- **`helpers.org_id`** — `null` means an individual volunteer, dispatched directly. Non-null means
  the helper joined an organization with its group code and is dispatched through that org's web
  portal. This one nullable field is what implements the two dispatch paths.
- **`organizations.group_code`** — uppercase, from an ambiguity-free alphabet excluding `O`, `0`,
  `I` and `1`. Unique index. Format `XXXX-NNN`, for example `RCRS-4K2`.
- **`offers.owner`** — `{kind: "org" | "individual", id}`. Because both kinds live in one
  collection with a denormalized `loc`, **the same geo query serves both dispatch paths**.
- **`matches.assigned_helper_id`** — set by the org's IT team after the org accepts. Null for
  individual-volunteer matches, which need no intermediary.
- **`locks`** — prevents two concurrent pipeline runs from double-booking the same stock.

### 4.3 The Geo Query

Find helpers within radius R of a request that hold resource X:

```python
pipeline = [
    {"$geoNear": {                                  # MUST be the first stage
        "near": {"type": "Point", "coordinates": [lng, lat]},
        "distanceField": "distance_m",
        "maxDistance": radius_km * 1000,
        "spherical": True,
        "query": {"resource": resource, "available": {"$gt": 0}},
        "key": "loc",
    }},
    {"$addFields": {
        "distance_km": {"$divide": ["$distance_m", 1000]},
        "eta_min": {"$add": [
            "$eta_base_min",
            {"$multiply": [{"$divide": ["$distance_m", 1000]}, 2.5]},   # 24 km/h field speed
        ]},
        "free": {"$subtract": ["$available", "$reserved"]},
    }},
    {"$match": {"free": {"$gt": 0}}},
    {"$lookup": {"from": "organizations", "localField": "owner.id",
                 "foreignField": "_id", "as": "org"}},
    {"$sort": {"eta_min": 1}},
    {"$limit": 8},                                  # caps candidates, therefore caps LLM tokens
]
candidates = await db.offers.aggregate(pipeline).to_list(8)
```

Radius ladder: 10 → 25 → 60 → 150 km, stopping at the first radius that yields at least three
candidates or covers the demand.

### 4.4 Stock Reservation

```python
res = await db.offers.find_one_and_update(
    {"_id": offer_id,
     "$expr": {"$gte": [{"$subtract": ["$available", "$reserved"]}, qty]}},
    {"$inc": {"reserved": qty}},
    return_document=ReturnDocument.AFTER,
)
if res is None:
    raise InsufficientStock()      # another run took it; A5 re-solves without this candidate
```

The `$expr` guard makes the check-and-reserve atomic in a single round trip.

---

## 5. Groq Integration

### 5.1 Client

> **Model availability is per-account. Verify with `client.models.list()` before
> assuming an id exists.** `llama-3.3-70b-versatile` returns 404 `model_not_found`
> on current free-tier keys and is not used by this project.

Verified working on this project's key, benchmarked on the real A2 Triage prompt:

| Model | Latency | Throughput | JSON mode | Use |
|---|---|---|---|---|
| `openai/gpt-oss-120b` | 1.26 s | 114 tok/s | yes | **Default.** Judgement: A2 triage, A6 arbiter |
| `openai/gpt-oss-20b` | 0.87 s | 253 tok/s | yes | **Fast.** Volume: A4 advocates, A9 narrator |
| `groq/compound-mini` | 1.29 s | 284 tok/s | yes | Viable alternative |
| `qwen/qwen3.6-27b` | — | — | **fails** | Rejected: JSON validation error |

All three working models produced near-identical triage output on the same input,
which is the reliability signal that matters more than any single benchmark.

```python
from groq import AsyncGroq

MODEL = "openai/gpt-oss-120b"        # judgement
MODEL_FAST = "openai/gpt-oss-20b"    # volume
client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"], max_retries=0, timeout=8.0)
_sem = asyncio.Semaphore(4)          # global in-flight cap; TPM-bound, see 5.3


async def call_json(system, user, schema, *, agent, trace_id,
                    max_tokens=400, temperature=0.2, timeout=6.0, fallback=None):
    body = dict(
        model=MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": json.dumps(user, separators=(",", ":"))}],
        response_format={"type": "json_object"},
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    for attempt in (0, 1):
        try:
            async with _sem:
                buf = []
                async with asyncio.timeout(timeout):
                    stream = await client.chat.completions.create(**body)
                    async for chunk in stream:
                        delta = chunk.choices[0].delta.content or ""
                        buf.append(delta)
                        await bus.publish(trace_id, "agent.token", {"delta": delta}, agent)
                return schema.model_validate_json("".join(buf))
        except (ValidationError, APITimeoutError, RateLimitError, APIError) as e:
            await bus.publish(trace_id, "error",
                              {"code": type(e).__name__, "attempt": attempt}, agent)
            if attempt == 0:
                await asyncio.sleep(0.35 + random.random() * 0.3)
                continue
    await bus.publish(trace_id, "error", {"fallback_used": True}, agent)
    return fallback()
```

### 5.2 Rules

| Rule | Reason |
|---|---|
| **Streaming is mandatory** | It is what makes the portal look like agents thinking, and it drops perceived latency to roughly 200 ms to first token |
| **Always Pydantic-validate** | Never `json.loads` a model response bare. JSON mode reduces malformed output; it does not eliminate it |
| **One repair retry, then fallback** | Every LLM agent has a deterministic stand-in, so the pipeline cannot die mid-demo |
| **Compact JSON in** | `separators=(",", ":")`, strip nulls, never send raw database documents — send the projected candidate view only |
| **Cap candidates at 8** | Caps A4 tokens, which is the largest single call |
| **Batch the advocates** | One call with all candidates, not N calls. Same wall-clock, eight times fewer requests against the limit |

### 5.3 Budget

Approximate per request: triage 350 tokens, advocates 600, arbiter 400, narrator 300 — about
**4 calls and 1.7k tokens per request**.

Measured free-tier limits on this project's key (from `x-ratelimit-*` response headers):

| Limit | Value | Implication |
|---|---|---|
| Requests per day | 1000 | ~250 full pipeline runs. Not the constraint |
| **Tokens per minute** | **8000** | **The binding constraint** |
| Token reset | ~600 ms rolling | Recovers fast; bursts are survivable |

At ~1.7k tokens per request, **8000 TPM allows roughly 4 pipeline runs per minute sustained**. That
is ample for a demo — you will never fire ten requests in sixty seconds on stage — but it rules out
load testing against the live API, and it is why the in-flight semaphore is 4 rather than 6.

Read the `x-ratelimit-remaining-tokens` header into a gauge and shed to the deterministic fallback
when it drops below one request's budget. Limits differ per account and change over time: re-read
the headers rather than trusting this table.

### 5.4 Keeping the Demo Fast

- Warm the client at startup with a one-token ping.
- Run A2 triage and A3 geo **concurrently** — the candidate set does not depend on triage output,
  only the weighting does.
- Pre-seed MongoDB with about a dozen helpers so `$geoNear` returns instantly.
- Provide `PACT_DEMO_LATENCY_MS` to *slow* event emission on purpose. With streaming and a 70B model
  on Groq, the real risk is that judges cannot read the debate before it finishes.

---

## 6. API Surface

This section is the **design target**. `STATUS.md` §4 lists what is actually mounted and is the
authority on that. As of the last update: the transport, admin, assignment and organization
endpoints below are built; `/session/*`, `/helpers/join`, `/helpers/me/offers`, the seeker-facing
`/requests/*` routes and the SSE stream are not.

### 6.1 App — Seeker

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/api/v1/session/signup` | `{role: "seeker", device_id, name, phone}` | `{uid, token}` — one-time, first launch only |
| GET | `/api/v1/session/me` | — | `{uid, role, name, org_id}` — restores a persisted session |
| POST | `/api/v1/session/signout` | — | Clears the device session |
| POST | `/api/v1/requests` | `{code}` or decoded selections, plus `lat`, `lng` | `202 {request_id, trace_id, status}` |
| GET | `/api/v1/requests/{id}` | — | Masked status, ETA, and post-acceptance helper contact |
| POST | `/api/v1/requests/{id}/confirm` | `{delivery_code}` | Verification result |
| POST | `/api/v1/requests/{id}/cancel` | `{reason}` | Triggers A11 |
| GET | `/api/v1/requests/{id}/stream` | SSE | Lightweight status ticks; **no agent internals** |

### 6.2 App — Helper

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/api/v1/session/signup` | `{role: "helper", device_id, name, phone, group_code?}` | `{uid, token, org_id}` |
| POST | `/api/v1/helpers/join` | `{group_code}` | `{org_id, org_name}`, or 404 leaving the helper individual |
| POST | `/api/v1/helpers/leave` | — | Clears `org_id` |
| PUT | `/api/v1/helpers/me/offers` | `[{resource, available, eta_base_min}]` | Upserts `offers` |
| GET | `/api/v1/helpers/me/assignments` | `?state=pending` | Masked assignment list |
| POST | `/api/v1/assignments/{id}/accept` | — | **Triggers `privacy.reveal`** |
| POST | `/api/v1/assignments/{id}/decline` | `{reason}` | Triggers A11 |
| POST | `/api/v1/assignments/{id}/status` | `{state, qty_delivered, note}` | Feeds A10 |

### 6.3 Web — Organization Portal

| Method | Path | Notes |
|---|---|---|
| POST | `/api/v1/org/login` | Static credentials; returns a signed cookie |
| GET | `/api/v1/org/assignments` | **Only this org's** allocations |
| POST | `/api/v1/org/assignments/{id}/accept` | Org-level acceptance |
| POST | `/api/v1/org/assignments/{id}/decline` | Triggers A11 |
| POST | `/api/v1/org/assignments/{id}/assign` | `{helper_id}` — dispatch to a named helper on the roster |
| GET | `/api/v1/org/roster` | Helpers who joined with this org's group code |
| PUT | `/api/v1/org/offers` | Manage the org's inventory |
| GET | `/api/v1/org/group-code` | The code to hand out |
| WS | `/ws/org` | Own-slice events only, org-audience projection |

### 6.4 Web — Admin Portal

| Method | Path | Notes |
|---|---|---|
| POST | `/api/v1/admin/login` | Static credentials |
| WS | `/ws/agents` | **Full deliberation stream — the headline feature** |
| GET | `/api/v1/admin/matches` | `?state=live` — primary view hydration |
| GET | `/api/v1/admin/requests` | `?status=&q=&bbox=` — the top-bar all-requests view |
| GET | `/api/v1/admin/requests/{id}/trace` | Full `agent_events` replay for one request |
| POST | `/api/v1/admin/decisions/{decision_id}/action` | `{action, option_id, allocations, note}` |
| POST | `/api/v1/admin/matches/{id}/verify` | Manual verification override |
| POST | `/api/v1/admin/replan/{request_id}` | Force A11 |
| POST | `/api/v1/admin/settings` | `{autopilot, gate_timeout_s, radius_ladder}` |
| POST | `/api/v1/admin/seed` | Idempotent demo reset. `{lat, lon, label}` re-centres the fixtures; omit to use `PACT_SEED_LAT/LON`, or Bhopal. **Re-centre before any demo** — the radius ladder stops at 150 km, and beyond it `$geoNear` returns nothing while the pipeline carries on with fixtures and `geo_live: false` |
| GET | `/api/v1/admin/seed` | Where the fixtures currently sit, plus the radius ladder |
| GET | `/api/v1/admin/stats` | Counters for the status strip |

### 6.5 Transport

| Method | Path | Notes |
|---|---|---|
| POST | `/api/v1/pact/ingest` | `{payload, transport, from_number}` — **the same codec string over HTTP** |
| POST | `/api/v1/sms/webhook` | Thin adapter calling ingest with `transport="sms"` |
| POST | `/api/v1/sms/simulate` | Admin portal SMS simulator |
| GET | `/api/v1/sms/outbox` | What would have been sent, since there is no real gateway |

### 6.6 Fate of the Existing Backend

| Existing in `backend/app/main.py` | Fate |
|---|---|
| `GET /`, `GET /api/v1/health` | Survive unchanged |
| `xor_checksum`, `parse_sms` | Survive; move verbatim into `codec/frame.py` and `sms/parser.py` |
| `RESOURCE_MAP`, `URGENCY_MAP`, `LOCATION_CODE_MAP`, `LOCATION_NAME_MAP` | Survive; move into `sms/tables.py` |
| `POST /api/v1/sms/webhook` | Survives, rewired to enqueue the pipeline instead of returning immediately |
| `POST /api/v1/crises` | **Deleted.** Removed from `main.py`; it had no callers anywhere in backend, web or android |
| `POST /api/v1/needs` | **Deleted** — folded into `POST /api/v1/requests` |
| `GET /api/v1/demo-state` | **Replaced** by `/api/v1/admin/stats` and `/api/v1/admin/seed` |
| `create_response_plan()` | **Deleted.** Its greedy logic lives on as the A5 solver skeleton and the Groq-unavailable fallback |
| `RESOURCE_PROVIDERS` | **Deleted.** Superseded by `db/seed.py`, which is centre-relative |
| `web/src/app/page.tsx` mock inventory and client-side fallback allocator | **Deleted** — the portals are WebSocket-driven |

---

## 7. Module Layout

```text
backend/
  app/
    main.py                  app factory, CORS, lifespan (Mongo, Groq warmup, seed)
    config.py                pydantic-settings: MONGO_URI, GROQ_API_KEY, PACT_ADMIN_USER/PASS,
                             GATE_TIMEOUT_S, AUTOPILOT
    deps.py                  token issue/verify, current_admin, current_org, verify_ws_token
    db/
      mongo.py               Motor client singleton
      indexes.py             ensure_indexes(), including 2dsphere and TTL
      repo_*.py              requests, helpers, organizations, offers, matches, events, sms, admin
      seed.py
      seed_data/             organizations.json, providers.json, requests.json
    bus/
      eventbus.py            in-process pub/sub
      gate.py                admin Futures
      envelope.py            seq counter and envelope builder
    llm/
      groq_client.py         AsyncGroq, call_json, streaming, retry, rate-limit gauge
      prompts.py             every system prompt as a constant
      schemas.py             Pydantic output schema per agent
    agents/
      scripted.py            the pipeline; one function, A0 -> A9 in order
      dedupe.py              A1: geohash7 + resource + 15-minute window
      solver.py              A5: the scoring model and admin-override validation
      fallbacks.py           deterministic stand-in for every LLM agent
    codec/                   see codec.md §9.2; also holds geohash encode/decode
    privacy/
      policy.py              the audience x field matrix, DATA ONLY
      redact.py              projection, free-text scrubbing, measured audit
      crypto.py              phone hashing, field encryption, masking primitives
    notify/
      dispatcher.py          the two dispatch paths
      channels.py            push | portal | sms, all writing to the outbox
    routers/
      admin.py  assignments.py  ingest.py  ws.py
  requirements.txt           fastapi, uvicorn, motor, pydantic-settings, groq,
                             python-dotenv, bcrypt, cryptography
  tests/                     test_codec, test_privacy, test_dedupe, test_notify, test_ws_org

Not built: `models/` (Pydantic lives beside its router), `sms/` (the split was
never needed -- codec/ covers it), `scripts/demo_run.py`.

web/src/app/
  login/page.tsx
  admin/page.tsx             LIVE MATCHES (primary)
  admin/requests/page.tsx    every incoming request
  admin/requests/[id]/page.tsx
  org/page.tsx  org/roster/page.tsx  org/inventory/page.tsx  org/code/page.tsx
  _components/               AgentStream, DebateThread, OptionCards, ApprovalBar,
                             MatchCard, RequestTable, MapPanel, PrivacyBadge
  _lib/                      useAgentSocket.ts (reducer over seq, reconnect with ?since=),
                             types.ts, api.ts
```

---

## 8. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Groq rate limit hit mid-demo | Every LLM agent has a deterministic fallback; `error{fallback_used}` renders as an amber line and the run continues. Record a backup video |
| Model returns malformed JSON | Pydantic validate, one repair retry, then fallback. Never parse bare |
| Arbiter invents quantities | It can only return an `option_id`, validated against the option set. The solver's numbers are what get written |
| WebSocket drops, portal goes blank | `seq` plus `?since=` replay from `agent_events`; portal shows a reconnecting state |
| Concurrent runs double-book stock | `locks` collection with TTL plus the atomic `$expr` reservation in §4.4 |
| Pipeline blocks on the admin gate forever | Autopilot with a 25 s timeout. Ship it on; toggle it off live to demo the human in the loop |
| `[lng, lat]` inversion | One unit test. This is the number one hackathon geospatial bug |
| Android team blocked on the backend | Freeze the request and response JSON early and hand them a seeded mock server |

---

## 9. Cut-Lines

Drop from the bottom up if time runs short.

1. MapLibre in the portal — replace with a static map image or a lat/lng scatter. **Cut first.**
2. The A10 verification LLM branch — keep the deterministic delivery-code check only.
3. A11 replanner — keep only the decline trigger; drop SLA timers and T1 preemption.
4. A1 dedupe — keep the geohash key, drop any LLM tiebreak.
5. Real FCM — `notify/console.py` writes to the outbox and the portal renders it.
6. Encryption at rest — keep the **masking projection**, which is the visible privacy story; drop
   field encryption.
7. The helper Android mode — ship the seeker app only and drive helpers from a seed fixture plus the
   org portal.

**Never cut:** the live WebSocket agent debate, the approve/override bar, `$geoNear`, and the
three-option arbiter choice. That quartet is the demo.

---

## 10. Build Order

1. `db/indexes.py` and `seed.py`, then `bus/eventbus.py`, `/ws/agents`, and a **fake pipeline
   emitting scripted events**. Wire the admin page to it. Get the portal visibly alive on fake
   events before writing a single real agent.
2. The codec (see `codec.md` §12).
3. Real agents, one at a time: A0, A1, A3, A5 first (all deterministic, no API key needed), then
   A2, A4, A6, and finally A7 to A9.
4. Android seeker mode, then helper mode and group-code join.
5. The organization portal, last, because it reuses the admin portal's bus and components.

Every agent added after step 1 is independently demoable and independently cuttable. That property
is worth more than any individual feature.
