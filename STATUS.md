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
| 3 | Real Groq agents | **~70%** — see §6 |
| 4 | Android app | Not started (toolchain ready) |
| 5 | Organization portal | Not started |
| 6 | A10 verification, A11 replanner | Endpoints only, no agents |
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
WS    /ws/org                          org slice (NOT yet redacted - see §6)
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

### Codec — `backend/app/codec/`, `shared/codec/`

- **75 Python tests pass.** `cd backend && python -m pytest tests/ -q`
- **7 Kotlin tests pass, 11 vectors byte-identical to Python.**
  `source android/env.sh && cd android && gradle :codec:test`
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
| A1 Dedupe | **FAKE — see §6** |
| A2 Triage | **Real Groq**, reasons over the codec selections |
| A3 Geo | **Real** `$geoNear`, radius ladder 10→25→60→150 km |
| A4 Advocates | **Real Groq**, one call with all candidates |
| A5 Solver | **Real** greedy fill, weighted by A4 fit scores |
| A6 Arbiter | **Real Groq**, `option_id` validated against the option set |
| A7 Privacy | **FAKE — see §6** |
| A8 Gate | **Real** — approve / override / reject, autopilot timeout, audited |
| A9 Narrator | **Real Groq** |
| A10 Verify | Endpoint only, no agent |
| A11 Replan | Endpoint only; no decline/SLA triggers |

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

### Step 3 gaps (~2h45m to close)

**A1 Dedupe is theatre.** It publishes a hardcoded
`"No duplicate within the 15-minute window at this geohash"` and
`duplicate: false`. It computes no geohash and checks nothing. Real dedupe
exists in `routers/ingest.py` on `(uid, seq)`, but that is a different thing —
two people reporting the same collapsed building from adjacent phones both go
through. *Est. 30 min.*

**A7 Privacy Redactor is theatre.** It publishes a fixed
`withheld: [name, phone, exact_loc]` list and **redacts nothing**. There is no
field-policy matrix and no per-audience projection. `app/privacy/` does not
exist. The privacy boundary in the portal is currently a caption, not a
mechanism. **This is the project's headline claim — prioritise it.** *Est. 1 h.*

**`privacy.reveal` never fires.** Zero publishers. `matches.reveal` exists in
the schema and nothing ever flips it, because there is no helper-accept
endpoint. The reveal-on-acceptance transition — the core of the privacy story —
is unimplemented. *Est. 45 min.*

**`notify/` does not exist.** The "two dispatch paths" (org portal vs individual
volunteer) is a string label inside the notification message, not actual
routing. *Est. 30 min.*

**`/ws/org` is unredacted.** It subscribes to the org topic but sends the full
envelope. There is a TODO in `routers/ws.py`. An organization would currently
see the cross-org debate it must never see.

### Missing modules from `agents.md` §7

`app/privacy/`, `app/notify/`, `app/models/`, `app/sms/` — none exist. Codec
logic currently lives in `app/codec/` only; the `sms/` split was never needed.

### Not started

- **Android app** (`android/app/`). Only the codec library exists.
- **Organization portal** (`/org/*` routes).
- **Offline MapLibre.**
- **Seeker/helper sign-up endpoints** (`/api/v1/session/signup`, `/helpers/join`,
  assignment accept/decline). Specified in `agents.md` §6, not implemented.
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
| Close step 3 gaps (A1, A7, reveal, notify) | 2–3 h |
| Session/signup + helper accept/decline endpoints | 2–3 h |
| Organization portal + `/ws/org` redaction | 2–3 h |
| A10 verification agent, A11 real triggers | 1–2 h |
| Android app: signup, chip screen, GPS, HTTP/SMS transport, outbox | 8–12 h |
| Offline MapLibre | 2–3 h |
| Polish, full test pass, **backup video**, pitch | 3–5 h |

**Total 20–31 hours.** For a solo build this does not fit a remaining
~14–16 coding hours. The Android app is roughly half of it and is the only path
to the airplane-mode demo moment.

**Suggested order:** close the step 3 gaps (especially A7 — it is the headline
claim), then decide on Android based on actual remaining time. A mobile-shaped
web client is a ~3 h substitute for a ~10 h app: same codec, same endpoints,
loses only "real SMS on a real phone".

**Never cut** (per `memory_draft.md` §23): the live WebSocket agent debate, the
approve/override bar, `$geoNear`, and the three-option arbiter choice.

---

## 11. Git

```
f208841 phase 2 (partial)      <- HEAD; steps 1-2 committed
179a219 Phase 1 Updated
d5a2905 Phase 1
```

**Uncommitted (the whole of step 3):**

```
 M backend/app/agents/scripted.py     agents rewired to Groq
 M backend/app/main.py                warmup, honest mode reporting
 M backend/app/routers/admin.py       matches/audit/verify/replan, auth
 M backend/app/routers/ingest.py      decoded passthrough
?? backend/app/agents/fallbacks.py    deterministic stand-ins
?? backend/app/llm/                   groq_client, prompts, schemas
```

Commit before continuing.
