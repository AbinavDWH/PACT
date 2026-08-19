# PACT — Build Status

**Last updated:** 2026-08-19
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
| 4 | Android app | Not started (toolchain ready) |
| 5 | Organization portal | Backend + `/ws/org` done; no `/org/*` UI |
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

**194 Python tests pass.** `cd backend && python -m pytest tests/ -q`

| File | Count | Covers |
|---|---|---|
| `test_codec.py` | 75 | The wire format, both directions |
| `test_privacy.py` | 56 | A7. Every test asserts on **absence** — a privacy test that only checks "admin sees everything" proves nothing |
| `test_solver.py` | 33 | A5 scoring, override validation, triage invariants. Every weight has a test that moves one input and requires the score to move |
| `test_dedupe.py` | 20 | Geohash against three published vectors, plus cluster behaviour |
| `test_notify.py` | 10 | The two dispatch paths differ in channel, state and acceptability |
| `test_ws_org.py` | 10 | Org socket auth, projection, and bus topic routing |

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

**The event `seq` counter resets on process restart.** It is in-process
(`bus/envelope.py`), so after a restart fresh events carry lower seq numbers
than persisted ones. This breaks `?since=` replay ordering and makes
`/admin/requests` list stale traces first. Cosmetic for a single-session demo,
wrong across a restart. *Est. 20 min — seed the counter from the max persisted
seq at startup.*

**A10 has no LLM branch** (cut-line 2, deliberate) and **A11 has no SLA timer
or T1-preemption trigger** (cut-line 3, deliberate). The decline trigger is
live.

**No `/org/*` portal UI.** The backend and the redacted socket are done; the
Next.js routes are not built.

### Missing modules from `agents.md` §7

`app/models/` and `app/sms/` do not exist. Codec logic lives in `app/codec/`
only; the `sms/` split was never needed. `app/privacy/` and `app/notify/` now
exist.

### Not started

- **Android app** (`android/app/`). Only the codec library exists — verified:
  `gradle :codec:test --rerun-tasks` prints `parity OK: 11 vectors`.
- **Organization portal UI** (`/org/*` Next.js routes). The backend and the
  redacted socket are done.
- **Offline MapLibre.**
- **Backup demo video.** Non-negotiable before presenting.

### Other

- `POST /api/v1/crises` is a deprecated Evaluation-1 endpoint still mounted.
- Streaming yields only ~3 token deltas per call. Groq sends JSON-mode content
  in large chunks, so the "watch it think" effect is weaker than designed. Use
  `DEMO_LATENCY_MS` to pace event emission instead.
- Triage occasionally returns `tier: T1` with `life_threat: false` — internally
  inconsistent model output. Harmless today; would need a validator to enforce.

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

**Environment variables were NOT set persistently.** Source per session:

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
cd backend && python -m uvicorn app.main:app --port 8000

# web
cd web && pnpm dev
```

Portal **http://localhost:3000/admin** · API docs **http://localhost:8000/docs**

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

| Item | Est. |
|---|---|
| Session/signup (`/session/signup`, `/helpers/join`) | 1–2 h |
| Portal UI for the privacy panel, reveal badge and dispatch route | 1–2 h |
| Organization portal `/org/*` Next.js routes | 2–3 h |
| `seq` counter seeded from Mongo at startup (§6) | 20 m |
| Android app: signup, chip screen, GPS, HTTP/SMS transport, outbox | 8–12 h |
| Offline MapLibre | 2–3 h |
| Polish, full test pass, **backup video**, pitch | 3–5 h |

**Total 16–28 hours.** The Android app is roughly half of it and is the only
path to the airplane-mode demo moment.

**Suggested order:** the portal UI first — A7, the reveal transition and the
two dispatch paths are all live in the backend and none of them are visible on
screen yet, which is the cheapest large gain available. Then decide on Android
based on actual remaining time. A mobile-shaped web client is a ~3 h substitute
for a ~10 h app: same codec, same endpoints, loses only "real SMS on a real
phone".

**Never cut** (per `memory_draft.md` §23): the live WebSocket agent debate, the
approve/override bar, `$geoNear`, and the three-option arbiter choice.

---

## 11. Git

Branch `workAbe`.

```
496c34a phase 3 start          Groq agents, fallbacks, llm/
f208841 phase 2 (partial)      codec
179a219 Phase 1 Updated
d5a2905 Phase 1
```

Step 3 is committed. The A1/A7/reveal/notify work lands on top of `496c34a`.

New modules:

```
backend/app/privacy/      policy.py, redact.py, crypto.py
backend/app/notify/       dispatcher.py, channels.py
backend/app/agents/dedupe.py
backend/app/routers/assignments.py
backend/tests/            test_privacy.py, test_dedupe.py, test_notify.py, test_ws_org.py
```
