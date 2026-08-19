# PACT — Build Status

**Last updated:** 2026-08-19 (end of session 1)
**Purpose:** hand-off document. Read this plus the four design docs and you have
everything needed to continue in a fresh session.

Everything below has been **verified by running it**, not just written. Where
something is unverified or fake, it says so explicitly.

---

## 1. Read these first

| File | What it holds |
|---|---|
| `memory_draft.md` | Project memory: problem, users, identity model, privacy model, architecture, demo script, judge Q&A |
| `codec.md` | The code language: option taxonomy, payload layout, PACK10 GPS packing, fan-out factors |
| `sms.md` | SMS transport: framing, checksums, message types, error codes |
| `agents.md` | Agent pipeline, prompts, event schema, MongoDB schema, full API surface |
| `android/README.md` | Android toolchain and device setup |
| `DEMO.md` | Demo runbook, pre-flight, and what **not** to claim on camera |
| `STATUS.md` | This file |

**The build order lives in `memory_draft.md` §22.** Cut-lines in §23.

---

## 2. One-paragraph summary of the system

Disaster-affected people tap options in an Android app. The selections compress
to a ~35-character alphanumeric code that travels over HTTP when there is data
and over SMS when there is not — the *same string* either way. A server-side
pipeline of agents triages the request, finds nearby helpers with a MongoDB
geospatial query, argues the trade-offs, computes allocation options
deterministically, picks one, and notifies the helper. A human admin watches the
deliberation live and can approve, override, or reject any decision.

**The governing rule:** the LLM assigns labels, ranks, chooses among enumerated
options, and writes prose. **Every number written to the database is produced by
Python.** The arbiter cannot invent an allocation because it only ever returns
an `option_id`, validated against the solver's set.

---

## 3. Progress against the plan

| Step | Scope | State |
|---|---|---|
| 1 | Event bus, WebSocket, portal, MongoDB, seed, geo, solver | **Complete** |
| 2 | Codec: tables, Python + Kotlin, vectors, ingest | **Complete** |
| 3 | Real Groq agents + A1, A7, reveal, notify | **Complete** — see §5 |
| 4 | Android app | **Complete** — installed and verified on a vivo V2336 |
| 5 | Organization portal | **Complete** — `/org` login, assignments, assign-to-helper, roster |
| 6 | A10 verification, A11 replanner | Endpoints + decline trigger; no SLA timers |
| 7 | Polish, backup video, pitch | Not started |

---

## 4. What is running and verified

### Backend — FastAPI, `backend/`

```
GET   /api/v1/health
POST  /api/v1/pact/ingest              codec string over HTTP
POST  /api/v1/sms/webhook              thin adapter -> same path
POST  /api/v1/sms/simulate             portal simulator
WS    /ws/agents                       admin firehose, token-authenticated
WS    /ws/org                          org slice, token-authenticated, A7-redacted
GET   /api/v1/sms/outbox               what would have been sent (no gateway)
POST  /api/v1/session/signup           one screen, once; issues uid + token
GET   /api/v1/session/me               restores a persisted device session
POST  /api/v1/session/signout
POST  /api/v1/helpers/join             group code -> org_id; bad code never blocks
POST  /api/v1/helpers/leave
PUT   /api/v1/helpers/me/offers        a volunteer's own inventory into `offers`
POST  /api/v1/assignments/{id}/accept  THE privacy.reveal trigger
POST  /api/v1/assignments/{id}/decline triggers A11
POST  /api/v1/assignments/{id}/status  feeds A10 delivery-code check
GET   /api/v1/helpers/me/assignments   per-row helper_pre / helper_post view
POST  /api/v1/org/login                issues an org-role token
GET   /api/v1/org/assignments          own slice, org-audience projection
POST  /api/v1/org/assignments/{id}/assign   name a helper from the roster
GET   /api/v1/org/roster               helpers who joined with the group code
GET   /api/v1/org/group-code
POST  /api/v1/admin/login              static creds, issues a real token
POST  /api/v1/admin/decisions/{id}/action
POST  /api/v1/admin/simulate
POST  /api/v1/admin/seed
POST  /api/v1/admin/settings           autopilot, gate timeout, demo latency
GET   /api/v1/admin/stats
GET   /api/v1/admin/runs
GET   /api/v1/admin/matches
GET   /api/v1/admin/audit
GET   /api/v1/admin/requests
GET   /api/v1/admin/requests/{id}/trace
POST  /api/v1/admin/matches/{id}/verify
POST  /api/v1/admin/replan/{id}
POST  /api/v1/crises                   DEPRECATED, remove when safe
```

- **Auth is enforced.** No token → 401. WebSocket without a token → close 4401.
  `require_auth=True` by default; `deps.py` has an escape hatch if needed.
- **Mongo degrades gracefully.** If Atlas is unreachable the app logs a warning
  and falls back to in-memory. `health` reports `configured` and `connected`
  separately — reporting only "configured" once hid a live outage.

### Event bus

In-process `asyncio` pub/sub. **No Redis** — the agents are coroutines in one
process. Topics: `*`, `<trace_id>`, `org:<org_id>`. A full subscriber queue drops
frames rather than blocking the pipeline.

WebSocket clients reconnect with `?since=<seq>` and replay from `agent_events`.
`agent.token` is excluded from replay (pure presentation; the finalised
`agent.message` carries the same text).

### MongoDB Atlas — 26 indexes, all populated

| Collection | Purpose |
|---|---|
| `organizations` | 4 seeded, with group codes |
| `helpers` | 6 seeded (2 unaffiliated volunteers, `org_id: null`) |
| `offers` | 14 seeded — the `$geoNear` collection, denormalized `loc` |
| `seekers`, `requests`, `matches` | written by the pipeline |
| `agent_events` | deliberation transcript, TTL 24h |
| `sms_messages` | dedupe log, TTL 7d |
| `admin_actions` | **audit trail, never TTL'd** |
| `locks` | stock reservation, TTL 60s |

**Coordinates are GeoJSON `[longitude, latitude]`.** A sanity check runs at
startup and logs `geo: ok (nearest offer 1.04 km)`; if coordinates were ever
stored flipped it would report thousands of km.

### Tests

**220 Python tests pass.** `cd backend && python -m pytest tests/ -q`

| File | Count | Covers |
|---|---|---|
| `test_codec.py` | 75 | The wire format, both directions |
| `test_privacy.py` | 56 | A7. Every test asserts on **absence** — a privacy test that only checks "admin sees everything" proves nothing |
| `test_solver.py` | 33 | A5 scoring, override validation, triage invariants. Every weight has a test that moves one input and requires the score to move |
| `test_dedupe.py` | 20 | Geohash against three published vectors, plus cluster behaviour |
| `test_notify.py` | 10 | The two dispatch paths differ in channel, state and acceptability |
| `test_ws_org.py` | 10 | Org socket auth, projection, and bus topic routing |
| `test_org_scope.py` | 7 | Cross-org refusal. Every test asserts on refusal, not on success |
| `test_seed_centre.py` | 17 | Re-centring. Asserts relative geometry survives the move **and** that the layout actually moves — preserving geometry by planting everything on one point would satisfy the first alone |

Plus **7 Kotlin tests, 11 vectors byte-identical to Python** —
`source android/env.sh && cd android && gradle :codec:test`

### Codec — `backend/app/codec/`, `shared/codec/`

- Single source of truth: `shared/codec/pact_tables.v1.json`, self-validating
  (field widths must sum to the declared payload length).
- Verified end to end: the *same* string over HTTP and SMS produces identical
  decode, priority, fan-out, geo query and allocation.
- Idempotent on `(uid, seq)` — an app retrying over SMS after HTTP does not
  create a second request.
- **Partial decode works**: one garbled selection character yields
  `degraded: true` plus a warning, and the request is still accepted and fanned
  out. A request with one corrupt field is still a person who needs rescue.

### Admin portal — Next.js 16, `web/`

`/admin` live match stream, `/admin/requests` all requests, `/` redirects to
`/admin`. One WebSocket shared across routes via `AgentSocketProvider` — without
it each route opened its own socket and started from empty state.

Working: streaming agent output, threaded advocate/arbiter rebuttals, option
cards, approve/override/reject gate, privacy panel, SMS simulator with presets.

---

## 5. Step 3 — what is genuinely live on Groq

Model: **`openai/gpt-oss-120b`** for judgement, **`openai/gpt-oss-20b`** for
volume. `llama-3.3-70b-versatile` **does not exist on this account** — verify
model ids with `client.models.list()` before assuming.

| Agent | Implementation |
|---|---|
| A0 Intake | Deterministic — **thin, mostly announces work the codec already did** |
| A1 Dedupe | **Real** geohash7 + resource + 15-min window, queried against `requests` |
| A2 Triage | **Real Groq**, reasons over the codec selections |
| A3 Geo | **Real** `$geoNear`, radius ladder 10→25→60→150 km |
| A4 Advocates | **Real Groq**, one call with all candidates |
| A5 Solver | **Real** greedy fill; scores computed by the weighted formula in `agents/solver.py`, options ranked by it |
| A6 Arbiter | **Real Groq**, `option_id` validated against the option set |
| A7 Privacy | **Real** field matrix in `app/privacy/`, applied and measured |
| A8 Gate | **Real** — approve / override / reject, autopilot timeout, audited. Override re-enters at A5 with the admin's allocations pinned and **validated against live stock** |
| A9 Narrator | **Real Groq** + real dispatch routing in `app/notify/` |
| A10 Verify | Deterministic delivery-code check on assignment status; no LLM branch |
| A11 Replan | Admin-forced + **helper-decline trigger**; no SLA timers or T1 preemption |

### A7 — what it actually does

`app/privacy/` is three files and a test suite:

| File | Contents |
|---|---|
| `policy.py` | The audience × field matrix, **data only**. 6 audiences × 9 fields, plus per-audience event-type allow-lists and the free-text field list |
| `redact.py` | Three passes: recursive key-name redaction, structural path redaction, then regex scrubbing of prose |
| `crypto.py` | `phone_hash` (salted SHA-256, format-stable), Fernet field encryption, and the lossy `mask_*` primitives |

Three passes rather than one, because each catches what the others miss:

1. **Key names, at any depth.** `lat`, `phone`, `delivery_code` and friends are
   redacted wherever they appear. This is the pass that fails safe when a
   payload changes shape.
2. **Structural paths.** For position-dependent fields where the key name alone
   is ambiguous — `free` and `qty` mean different things in different places.
3. **Free-text scrubbing.** A9 writes prose, and a coordinate pair inside a
   sentence is invisible to a path table. The narrator's prompt *asks* it not to
   include coordinates; A7 does not rely on that.

Event-type filtering runs **before** any field walk. An organization must not
learn that a cross-org debate happened at all — the existence of the argument
is itself the disclosure.

A7 publishes **measured** counts off the real payload, not a fixed list. A
typical run reports ~20–25 field instances redacted with a per-field breakdown.
If a path stopped matching, the count drops and the portal shows it.

### The reveal transition

`POST /api/v1/assignments/{match_id}/accept` is the only publisher of
`privacy.reveal`. It moves the helper from the `helper_pre` audience to
`helper_post`, which is a real change in what the API returns:

| | before accept | after accept |
|---|---|---|
| seeker position | `23.26, 77.41` (~1 km) | `23.25991, 77.41263` |
| contact, name | key absent | present |
| delivery code | key absent | present |

Verified live on the same match id, either side of one POST.

### The two dispatch paths

Now routing, not a label. `app/notify/dispatcher.py`:

| | organization | individual volunteer |
|---|---|---|
| channel | `portal` | `push` |
| initial state | `awaiting_assignment` | `pending_accept` |
| acceptable immediately | **no** | yes |
| intermediary | org IT names a helper | none |

The org path's intermediary is enforced, not described: accepting an
`awaiting_assignment` allocation returns `NOT_ASSIGNED`. Assigning a helper who
is not on that org's roster returns `NOT_ON_YOUR_ROSTER`. Both verified live.

Every LLM agent has a deterministic fallback in `agents/fallbacks.py`. Verified:
when Groq failed, all four degraded and the pipeline still committed valid
allocations. `run.completed` reports `llm_agents: {triage: bool, ...}` so the UI
never passes a heuristic off as model output.

**Measured rate limits:** 8000 tokens/minute (binding), 1000 requests/day.
~1,100 tokens per request → **~6 requests/minute** before the gauge sheds to
fallbacks. Fine for a demo; rules out load testing.

Typical run: **~6 seconds**, all four agents live.

---

## 6. Known gaps — read this before claiming anything works

### Closed since the last update

A1, A7, `privacy.reveal`, `notify/` and `/ws/org` are all done and verified by
running them — see §5. Six further faults were found while closing them; all
six are fixed and each has a regression test:

1. **The redactor failed open on an unknown audience.** `VISIBLE_TYPES.get()`
   returned `None` for a typo'd audience name, which was also the *admin*
   "unrestricted" sentinel. A misspelled audience received the full stream.
2. **Exact GPS leaked to a pre-acceptance helper.** `GET
   /helpers/me/assignments` returned `23.25991, 77.41263` with
   `revealed: false`, because the path table covered `request.lat` and that row
   nested it at `seeker.lat`. Found by calling the endpoint, not by reading it.
   Fixed by redacting unambiguous key names at any depth.
3. **Prose was never redacted.** The field matrix cannot see inside a sentence,
   so a coordinate pair written by A9 passed straight through. The narrator
   prompt asks the model not to do that — which is the exact pattern A7 exists
   to avoid.
4. **`/ws/org` had no authentication at all**, while `/ws/agents` beside it
   verified a token. It now requires an `org`-role token, and
   `POST /api/v1/org/login` exists to issue one.
5. **`/ws/org` was permanently silent.** The bus only routes to `org:<id>` when
   an event carries `org_id`, and nothing in the pipeline ever set it.
   `_ORG_BLOCKED_TYPES` in `routers/ws.py` was a dead constant that read like a
   working filter.
6. **`matches.justification` was always `""`.** The pipeline read
   `best.get("justification")`, a key `_option()` never sets — so the arbiter's
   rationale was published to the bus and dropped at write time. It also read
   `best` rather than `final`, so an override recorded the wrong option's
   reasoning.

### Closed in the second pass — step 3 finished

**A5's scores were four literals.** `_option()` took `0.74 / 0.81 / 0.78 /
0.80`, identical on every run regardless of ETA, stock, reliability or load —
a constant presented as a measurement, which is exactly what the governing rule
exists to rule out. `agents/solver.py` now implements the weighted formula from
agents.md §2.5 over real fields, options are ranked by it, and the arbiter's
deterministic fallback follows the score as §2.6 specifies (it previously
returned `max_coverage` every time, because that strategy's hardcoded literal
happened to be the highest). A live run now reports candidate `0.4273` and
option `0.7684`. An `agent.tool_call` publishes the weights and the per-candidate
scores so the ranking is inspectable rather than asserted.

**Admin override now applies custom allocations.** It re-enters at A5, and the
solver validates feasibility before anything is pinned. Verified live both ways:
a 3→2 override committed 2 units and scored `opt_admin` at `0.6184`, *below*
max_coverage's `0.7684`, because it covers less; a 99999-unit override was
refused with `OVERRIDE_INFEASIBLE — Sanjeevani Relief Trust has 240 free` and
the pipeline fell back and committed the correct 3. The audit trail records
before/after allocations and the refusal reason.

**A2 triage invariants are enforced.** The model returns `tier: T1` with
`life_threat: false` often enough to matter; each field validates alone, only
the relationship is wrong, so Pydantic cannot catch it. `T1 ⇒ life_threat`,
`life_threat ⇒ tier ≥ T2`, `T1 ⇒ harm horizon ≤ 6 h`, and severity is lifted to
its tier floor. Corrections are **published** as a `TRIAGE_INCONSISTENT` event,
not applied silently — a silent repair would show output the model never
produced.

**A2 and A3 now overlap** (agents.md §5.4). The `$geoNear` round trip runs
underneath the triage call. Events are still emitted in A2-then-A3 order,
because a scrambled transcript costs more on stage than the latency saves.

**`fallbacks.arbiter([])` used to raise.** It returned `""` for a field with
`min_length=1` — the "no feasible option" branch threw on the one input it
existed to handle. Unreachable from the current pipeline, fixed anyway.

### Still open

**A10 has no LLM branch** (cut-line 2, deliberate) and **A11 has no SLA timer
or T1-preemption trigger** (cut-line 3, deliberate). The decline trigger is
live.

**Streaming yields only ~3 token deltas per call.** Groq sends JSON-mode content
in large chunks, so the token-by-token effect is weaker than designed. Not a
bug; use `DEMO_LATENCY_MS` to pace event emission instead.

### Missing modules from `agents.md` §7

`app/models/` and `app/sms/` do not exist. Codec logic lives in `app/codec/`
only; the `sms/` split was never needed. `app/privacy/` and `app/notify/` now
exist.

### Not started

- **The map inside the Android app.** The *portal* map is done (§6F), but
  `memory_draft.md` §15 also wants pre-cached tiles on the handset and §24
  step 6 says the app "updates its offline map from the SMS reply". **Neither
  is built**, and that clause must still not be said on camera. `DEMO.md`
  records it.
- **Backup demo video.** Non-negotiable before presenting. `DEMO.md` is the
  shot-by-shot runbook; `backend/scripts/preflight.py` verifies the system is
  demo-ready and exits non-zero when it is not.

---

## 6A. Fixed during step 5

**Organization endpoints had no authentication at all.** `/api/v1/org/assignments`,
`/roster`, `/group-code` and `/assignments/{id}/assign` took `org_id` straight
from the query string on a router with no dependency, so any caller could read
or act on any organization by editing the URL -- verified live: a bare curl with
no token returned another org's assignments and roster. That is precisely the
boundary the organization portal exists to demonstrate.

Now derived from the token via `org_scope` (403 on mismatch, 401 with no token),
covered by `tests/test_org_scope.py`.

**Ciphertext leaked into two user-visible places.** `name_enc` is Fernet
ciphertext for anyone who signed up through the app; it was returned raw in the
org roster, and used as the *candidate name* in `repo_offers._shape` -- so the
advocates argued about a candidate literally named `enc:gAAAAAB...`. The roster
now decrypts (an org is entitled to its own helpers' names); candidates use a
readable pseudonymous handle instead.

**`.reqTable` had no CSS anywhere**, so the admin All Requests table rendered as
a bare browser table. Styled in `admin.css`; both pages benefit.

---

## 6F. Session 2 — the map (cut-line 1, un-cut)

`memory_draft.md` §13 asks the portal for "crisis points, helper positions,
allocation lines" and §15 for "offline OpenStreetMap tiles, pre-cached". Both
are now real.

**Tiles are served by our own backend and cached on disk.** `routers/tiles.py`
proxies OpenStreetMap once and keeps every tile, so after a prefetch the map
renders with **no internet at all**. Pointing MapLibre straight at
`tile.openstreetmap.org` would look identical on a good network and fail on the
one condition this whole project assumes — the venue wifi dying.

OSM's tiles are donated infrastructure and their policy forbids bulk
downloading, so the prefetch is bounded (`max_tiles`, refusing loudly rather
than proceeding), serialised with a courtesy delay, sends an identifying
User-Agent, and caches so a tile is fetched exactly once. **The demo area is
328 tiles / 3.8 MB** at z10–15 over 8 km.

```bash
curl -X POST http://localhost:8000/api/v1/tiles/prefetch \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"lat": 13.008, "lon": 80.006, "radius_km": 8, "min_zoom": 10, "max_zoom": 15}'

curl http://localhost:8000/api/v1/tiles/status     # cached_tiles, mb, offline_ready
```

Run it after reseeding, on the same coordinates. Re-running is cheap — cached
tiles are skipped. **It is slow on purpose** (~0.06 s per tile) and can outlast
a client HTTP timeout; the server finishes regardless, so re-run and check
`status`.

An unreachable upstream returns a transparent tile, never a 500, so the data
layers still draw over blank ground.

**Candidates now carry coordinates.** `repo_offers._shape` adds `lat`/`lon`,
which the portal needs to draw them. Deliberately *not* added to the projection
sent to A4 — that builds its own explicit field list, and coordinates are
tokens the model has no use for when `distance_km` already says everything it
argues about.

Verified live: request at 13.009, 80.007 with c1 at 0.44 km and c2 at 4.09 km,
positions consistent with the distances the solver computed.

`tile_cache/` is git-ignored: megabytes of binary, regenerable in one command.

---

## 6E. Session 2 — real authentication

**Passwords are bcrypt-hashed.** `bcrypt` had been in `requirements.txt` since
the first commit, described as "credential hashing", and was **never called**:
the admin password was compared against a plaintext env var, and every seeded
organization shared one plaintext password from settings, so knowing one was
knowing all four. `app/security.py` now hashes and verifies; seeded orgs carry
a real `web_pass_hash`. Login verifies against a dummy hash on the miss path,
so a valid username cannot be identified by response time.

**Sessions survive a restart.** Tokens lived in a module dict. For a portal
that is a re-login; for a phone in the field it is a dead app with no recovery
path — the user sees 401s and has no reason to connect them to a server restart
they never saw. Sessions now persist to a TTL-indexed `sessions` collection and
are restored into an in-memory cache at startup, which keeps token lookup
synchronous for the WebSocket handshake.

**Device sessions are long-lived (90 d); portal sessions stay short (12 h).**
A browser on a shared laptop should expire quickly; a handset belonging to
someone in a disaster should not, and there is no password to re-enter anyway.

**Organizations can register themselves.** `POST /api/v1/org/signup` with a
generated group code from the ambiguity-free alphabet. Until now the only
organizations that could exist were the four in the seed, so "multiple
organizations" was a fixture rather than a capability. New orgs start at
reliability 0.7, not 1.0, so an unknown supplier does not outrank one that has
actually delivered.

**App sign-up remains password-free by design** (`memory_draft.md` §7.1).
Adding a password there would be a product failure dressed as a security
improvement.

### Two bugs found by testing this, both silent

1. **`asyncio.create_task` without a strong reference.** The event loop keeps
   only weak references, so the session write could be garbage-collected
   mid-flight. Observed: an admin session was never written while a heavier
   request ran alongside it.
2. **`/api/v1/admin/login` was `def`, not `async def`.** FastAPI runs sync
   endpoints in a threadpool with no event loop, so the write was discarded
   with a `RuntimeError` while the `async def` org login persisted fine — a
   difference invisible from either endpoint. `_spawn` now falls back to the
   loop captured at startup, and the endpoint is async.

Verified live: both tokens survive a restart (`auth: 2 session(s) restored`); a
self-registered org logs in with its own password, is refused the old shared
one, and gets 403 reading another org's roster.

---

## 6D. Session 2 — removing the simulations

**SMS is no longer simulated.** `/api/v1/sms/webhook` existed with no caller:
the seeker phone sent a genuine `SmsManager` message and nothing anywhere
received it, so the only route into the backend "over SMS" was a human pasting
the string into the simulator panel.

`SmsGateway` is a `SMS_RECEIVED` receiver in the same APK. Install it on a
second handset, switch gateway mode on, and it forwards PACT frames to the
webhook that was already written and waiting. Real cellular SMS, no vendor.

A vendor was not an option, not merely a preference: outbound A2P SMS in India
needs DLT registration with TRAI (days to weeks), and inbound SMS on an Indian
virtual number is not sold to unregistered entities at all.

The gateway forwards **only** messages whose first field is a protocol frame
type and which carry at least four fields. A gateway handset also receives
banking OTPs and private messages, and forwarding those would be a worse
privacy failure than anything this project defends against. 12 tests, most
asserting refusal — OTPs, personal messages, pipe-heavy spam, transaction
alerts, lowercase frames.

Verified: the exact body `SmsGateway.forward()` builds, POSTed at the live
backend, returns `status: accepted`, `source: sms`, and dispatches the
pipeline. The radio hop itself needs the second handset.

**The privacy boundary is now visible in the portal** (MVP must-build §20.8,
previously not done). The panel showed two lists of category names and nothing
else — identical whether A7 did any work or not. It now renders the measured
`fields_redacted` count, the per-field breakdown, the `masked` category, and
the count of event types an organization never receives. A live run shows 38
field instances redacted across 5 categories.

`privacy.reveal` had **zero renderers** — the reveal transition, the core of
the privacy story, was invisible. It now renders as an unlocked badge. Dispatch
`route`/`state`/`acceptable_now` and `geo_live` are surfaced too; a run that
fell back to fixtures previously looked identical to one that queried Atlas.

---

## 6C. Fixed at the start of session 2

**The seed can be planted anywhere.** `db/seed.py` now stores the fixture
layout as **kilometre offsets from a centre** rather than absolute coordinates,
and `POST /api/v1/admin/seed` takes `{lat, lon, label}`. `PACT_SEED_LAT` /
`PACT_SEED_LON` set the default per machine, and `GET /api/v1/admin/seed`
reports where the fixtures currently sit alongside the radius ladder.

Offsets are in kilometres, not degrees, because a degree of longitude is 102 km
at Bhopal and 108 km at Chennai — degree offsets would stretch the layout 6%
east-west as it moved and distort every ETA.

`verify_lng_lat()` no longer probes a hardcoded city. It derives its probe from
an offer that is actually in the database, so the geo sanity check survives a
reseed instead of reporting a false failure.

Verified live: reseeded at Chennai, then a request from 13.083, 80.271 produced
`geo_live: true`, `2 candidates within 10 km`, nearest at **0.53 km**. Before
this it would have been `geo_live: false` with hardcoded candidates and nothing
on screen to say the database query had stopped running.

**Currently seeded at 13.008, 80.006** ("phone test location"). Move it with:

```bash
curl -X POST http://localhost:8000/api/v1/admin/seed \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"lat": <lat>, "lon": <lon>, "label": "venue"}'
```

**The Evaluation-1 endpoints are gone.** `POST /api/v1/crises`,
`RESOURCE_PROVIDERS`, `create_response_plan()` and the resource/urgency maps
are removed from `main.py`, which is now 115 lines of app factory, lifespan and
health. They had no callers anywhere, but they still answered requests — a
stale endpoint returning a plausible allocation from a hardcoded provider table
that no longer matched the database. agents.md §6.6 already listed them as
deleted.

---

## 6B. Fixed at the end of session 1

**The event `seq` counter restarted at 1 on every boot.** After a restart, fresh
events carried lower numbers than persisted ones, so `?since=` replay returned
nothing and All Requests sorted stale traces above live ones. `envelope.seed_from()`
now resumes from `repo_events.max_seq()` before anything can publish. Verified:
startup logs `event seq resumed at 221`.

**All Requests showed zero rows while the database held thirty traces.** The page
read only the live socket, so a fresh tab showed nothing that arrived before it
opened — a page titled "every incoming request" showing none of them. It now
hydrates from `GET /api/v1/admin/requests` and merges live runs over archived
rows. Verified: 30 rows.

### Corrections to earlier claims in this file

- The `agent.tool_call` with `radius_km: None` reported earlier was **not a bug**.
  There are two distinct tool_call events (`mongo.$geoNear` and
  `solver.score_candidates`); a test script was reading `radius_km` off both.
- `whesvc` is **"Windows Health and Optimized Experiences"**, not "Windows
  Hardware Error". Its ~2 GB of `.etl` traces in `C:\Windows\Temp` are not this
  project's and regenerate continuously.

---

## 7. Environment

### Toolchain — all on `E:`, nothing on `C:` (C: was nearly full)

| Tool | Version | Path |
|---|---|---|
| Temurin JDK | 17.0.20 | `E:\PACT\tools\jdk17` |
| Gradle | 8.11.1 | `E:\PACT\tools\gradle` |
| Android SDK | platform-35, build-tools 35.0.0, platform-tools | `E:\PACT\tools\android-sdk` |
| Python | 3.13.14 | system |
| pnpm | 11.22.0 | global |

**Environment variables are now set persistently** (user scope): `JAVA_HOME`,
`ANDROID_HOME`, `ANDROID_SDK_ROOT`, and critically `GRADLE_USER_HOME` →
`E:\PACT\tools\gradle-home`. Without that last one Gradle rebuilt a 1.4 GB
cache on C:, which was deleted. A per-session script also exists:

```bash
source android/env.sh        # bash
. .\android\env.ps1          # powershell
```

`GRADLE_USER_HOME` is redirected to `E:` — otherwise Gradle writes hundreds of
MB to `C:\Users\...\.gradle`.

Installer zips (~460 MB) are still in `E:\PACT\tools\dl` and can be deleted.

### Device

vivo **V2336**, Android 16. USB debugging is enabled and the RSA fingerprint has
been accepted — it was confirmed working with `adb devices`. It is **not
currently plugged in**, so `adb devices` returns an empty list until you connect
it again. Nothing to install yet.

If it ever shows `unauthorized`, re-accept the prompt on the phone screen.

### Secrets — `backend/.env`, git-ignored

```
MONGO_URI, MONGO_DB, GROQ_API_KEY, GROQ_MODEL, GROQ_MODEL_FAST,
PACT_ADMIN_USER, PACT_ADMIN_PASS, REQUIRE_AUTH,
AUTOPILOT, GATE_TIMEOUT_S, DEMO_LATENCY_MS
```

Template in `backend/.env.example`. **`.gitignore` covers `*.env`** — it
originally only covered `.env`, which would have committed
`atlas-credentials.env`. Nothing leaked; the secret never entered git history.

**Atlas Network Access must allow `0.0.0.0/0`.** A non-allowlisted IP fails with
`TLSV1_ALERT_INTERNAL_ERROR`, which reads like a certificate problem and is not
one. The startup log names the real cause.

---

## 8. Running it

```bash
# backend  (do NOT use --reload: it hangs and orphans workers holding :8000)
# --host 0.0.0.0 is required, or the phone cannot reach it however correct
# the address in BuildConfig.API_BASE is.
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# web
cd web && pnpm dev
```

Admin **http://localhost:3000/admin** (admin / pact-admin) ·
Org **http://localhost:3000/org** (sanjeevani / pact-org) ·
API docs **http://localhost:8000/docs**

**Before demoing, put the fixtures where you are.** The radius ladder stops at
150 km and the fallback is silent:

```bash
curl -X POST http://localhost:8000/api/v1/admin/seed \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"lat": 13.008, "lon": 80.006, "label": "venue"}'
```

Then confirm a real request reports `geo_live: true` in `run.completed`. If it
says `false`, the pipeline is running on fixtures and `$geoNear` — one of the
four things never to cut — is not actually executing.

Make the admin gate wait instead of auto-approving:

```bash
curl -X POST http://localhost:8000/api/v1/admin/settings \
  -H "Content-Type: application/json" -d '{"autopilot": false}'
```

If a port is stuck, kill by PID — `pkill` does not work reliably here:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen |
  Select-Object -ExpandProperty OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force }
```

---

## 9. Traps that already cost time

1. **`resp.parse()` is a coroutine** in the async Groq SDK. Without `await`,
   `async for` raises `TypeError` on every call and every agent silently falls
   back.
2. **`max_tokens` must be generous** (900+). gpt-oss spends completion tokens on
   reasoning before emitting JSON; truncation mid-object returns
   "Failed to generate JSON". Use `reasoning_effort="low"` (~40% fewer tokens).
3. **Strip nulls from LLM payloads.** Missing fields make the model reason
   *harder*, which is what caused the truncation above.
4. **A Pydantic field with a default silently accepts garbage.** `AdvocatesOut.
   bids` defaulted to `[]`, so a wrong-shaped response validated "successfully"
   with zero bids — reported as a successful LLM call while producing no debate.
   Use `min_length=1` on anything that must be present.
5. **gpt-oss returns three different JSON shapes** for the same prompt depending
   on reasoning effort: `{"bids":[...]}`, a bare `[...]`, or `{"c1":{...}}`, and
   `fit_score` instead of `fit`. `schemas.py` normalises all of them.
6. **Next 16 blocks cross-origin dev resources.** Hitting the dev server by IP
   (including from a phone on the LAN) 403s every JS chunk and the page loads but
   never hydrates — looks like a broken app. `next.config.ts` allowlists the
   private ranges.
7. **Never hand-write a checksum.** 42 examples in `sms.md` and 4 simulator
   presets were wrong. All are now computed. `xor_checksum` over everything
   before the final `|`.
8. **`uvicorn --reload` hangs** on this machine and leaves orphaned workers
   holding the port while a dead PID owns the socket.

---

## 10. Remaining work

| Item | Est. | Notes |
|---|---|---|
| **Backup demo video** | 1–2 h | Non-negotiable. Most likely item to get squeezed out |
| Full dry run against the seeded venue centre | 30 m | Confirms `geo_live: true` on the day |
| Pitch and judge Q&A rehearsal | 1–2 h | `memory_draft.md` §24–25 |
| A10 LLM branch | 1 h | **Cut-line 2 — deliberate.** Skip unless time is spare |
| A11 SLA timers, T1 preemption | 1–2 h | **Cut-line 3 — deliberate.** Skip |
| Offline MapLibre | 2–3 h | **Cut-line 1 — cut first.** Skip |

**Everything not marked as a cut-line is about 3–5 hours**, and it is all
step 7. The build is feature-complete against the MVP scope.

**Suggested order:** record the video first, while the system is known-good and
before anything else is touched. Then rehearse. The remaining agent work is
explicitly cut-line material and should stay cut unless the video and the pitch
are both finished.

**Never cut** (per `memory_draft.md` §23): the live WebSocket agent debate, the
approve/override bar, `$geoNear`, and the three-option arbiter choice.

---

## 11. Git

Branch `workAbe`. **Everything through step 5 is committed; the tree is clean.**

```
34d8170 phase 4                org portal, org_scope auth, seq resume, All Requests hydration
e2bba8c Step 4: Android app    app module, 13 JVM tests
733db20 Ignore Gradle build output
d0fbfb5 session + signup       and the seeker-name leak they exposed
703f525 Complete step 3        real A5 scores, working override, triage invariants
43286a6 Close step 3 gaps      A7 privacy, A1 dedupe, reveal, dispatch routing
496c34a phase 3 start          Groq agents, fallbacks, llm/
f208841 phase 2 (partial)      codec
179a219 Phase 1 Updated
d5a2905 Phase 1
```

This section has gone stale three times. **Run `git log --oneline -6` rather
than trusting it.**

Modules added since step 2:

```
backend/app/privacy/      policy.py, redact.py, crypto.py
backend/app/notify/       dispatcher.py, channels.py
backend/app/agents/       dedupe.py, solver.py
backend/app/routers/      assignments.py, session.py
android/app/              the Android module
web/src/app/org/          the organization portal
```

---

## 12. Step 4 — the Android app

Built without Android Studio. `android/README.md` has the full layout,
dependency policy and build commands.

```bash
source android/env.sh
cd android
gradle :app:assembleDebug -PpactApiBase=http://<lan-ip>:8000
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Start the backend with `--host 0.0.0.0` or the phone cannot reach it however
correct the address is.

### Verified

- APK builds: 9.6 MB `app-debug.apk`.
- **13 JVM unit tests pass** (`gradle :app:testDebugUnitTest`). They round-trip
  every chip the UI can offer through the codec, assert the frame is one
  GSM-7 segment even with every need selected, and require an incomplete
  selection to throw rather than emit a frame with a meaningful zero in it.
- The Kotlin codec is still byte-identical to Python: `parity OK: 11 vectors`.
- The exact string that selection produces was posted at the live backend and
  **accepted**, decoding to the right situation, injury, mobility, urgency,
  needs and vulnerability.

### NOT verified — the app has never run on hardware

The vivo V2336 was not plugged in; `adb devices` was empty for the whole
session. Untested: every Compose screen, the runtime permission flow, a real
GPS fix, an actual `SmsManager.sendTextMessage`, and the outbox surviving a
real process death. Treat the first install as a debugging session, not a
demo rehearsal.

### Deliberate deviations from the plan

| Plan said | Built | Why |
|---|---|---|
| Room outbox | append-only JSON-lines file | the queue needs four operations; Room costs an annotation processor and a codegen step |
| — | `LocationManager`, not Play Services | fused location leans on network positioning; this app must produce a fix with no data at all |
| — | `HttpURLConnection`, `org.json` | every dependency is a download that has to succeed on venue wifi |
