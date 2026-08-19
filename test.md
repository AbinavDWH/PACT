PACT — Rewrite the Design Docs for the Revised Architecture
Context
PACT is a 24-hour hackathon project: a Privacy-Preserving Multi-Agent Humanitarian Coordination Platform. Its design memory lives in memory_draft (1).md (2056 lines) and sms.md (1640 lines). The code today is one 324-line in-memory FastAPI file (backend/app/main.py) plus a single-page Next.js dashboard (web/src/app/page.tsx) — no database, no agents, no LLM, no map, no Android.

The concept has since changed materially, and the memory file no longer describes the system being built:

Dimension	memory_draft (1).md says	Actual design
Who asks for help	Organizations only (NGO/Gov/CSR field workers)	Disaster-affected individuals are a first-class population, alongside provider orgs
Database	PostgreSQL + PostGIS	MongoDB, 2dsphere + $geoNear
Agents	Unspecified Python workers over a Redis bus	Groq / llama-3.3-70b-versatile, in-process async pipeline, no Redis
Input method	Free-text field reports parsed by an LLM	Option-selection only → compressed alphanumeric code, one wire format for HTTP and SMS
Web UI	Shared command center for all orgs	Admin-only portal; requesters and providers get the Android app only
Auth	Keycloak	Deferred (device token / mock)
Building against a stale memory file is the biggest risk to a 24-hour build — every later agent session, teammate, and judge Q&A answer would derive from the wrong architecture. So this round is docs-first: make the docs describe the real system, then implement against them next round.

Decisions locked this round
App = Kotlin Android, both requester and provider modes. Web is admin-only.
Agent bus = in-process asyncio pub/sub inside FastAPI, streamed to the portal over WebSocket. No Redis anywhere.
Admin portal = live match stream is the primary view; a top-bar button opens an all-incoming-requests view.
Privacy = identity/contact/exact GPS masked by default, revealed between requester and provider only after an allocation is committed and the provider accepts. The admin always sees everything.
LLM boundary = the LLM produces labels, rankings, choices among enumerated options, and prose. Every number written to the database is produced by Python. An LLM never divides 300 kits across 4 providers.
Deliverable: four documents
Split by concern so each file has one owner and one reason to change. memory_draft.md stays high-level and points at the others — that rule already exists in the current file (§0) and is worth keeping.

1. memory_draft.md — rewrite (rename from memory_draft (1).md)
The file's own §0 refers to itself as memory_draft.md; the (1) is a download artifact and every internal cross-reference is already wrong. Rename via git mv-equivalent (it is untracked, so a plain rename) and rewrite.

Sections to replace:

§3 Core Problem, §4 Solution — add the individual-requester population. The problem is no longer only "orgs can't see each other's resources"; it is also "an affected person has no channel to reach the right helper".
§10–12 System Components / Tech Stack / Role of each technology — MongoDB replaces PostgreSQL+PostGIS; Groq+Llama replaces unspecified workers; Redis is removed; Keycloak is deferred.
§13 Web Dashboard Blueprint → Admin Portal Blueprint: live match stream primary, all-requests view secondary, agent-deliberation panel, approve/override bar.
§14 Mobile App Blueprint → two modes (Requester, Provider), chip-selection UI, no free-text field in the request flow.
§19–21 Architecture + data flows — redraw for HTTP/SMS → codec → pipeline → Mongo → admin gate → provider notify.
§25–28 MVP scope, mock list, 24-hour plan — reorder around the new cut-lines (below).
§29 Demo script, §31 Judge Q&A — rewrite for the new story; add answers for "why MongoDB not PostGIS", "why Groq", "why no free text", "what if the LLM hallucinates an allocation".
Sections to keep largely intact: §2 Abstract, §6–8 privacy model (still the core innovation), §24 advantages/disadvantages (update the PostGIS row).

2. sms.md — targeted edits, not a rewrite
sms.md remains the governing transport spec. The canonical frame TYPE|SEQ|ORG|BODY|CRC, the XOR checksum (§24), and sequence/dedupe rules (§25) are all unchanged — the new compressed payload lives inside one field, so xor_checksum() and sms.split("|") in main.py keep working.

Section	Edit
§5 message types	Add Q (individual request) and G (provider offer). Deprecate the long ROUTE alias; RT only
§6 resource codes	Add X rescue_team, V evac_transport, P power_kits, I infant_kits, S search_request. Existing 8 keep meaning and bit position. Note explicitly that resource codes and message-type codes are separate namespaces (S, P, V now appear in both)
§8 status codes	Add 6 self-resolved, 7 still-waiting/re-ping
§10 + §29 location	Add PACK10 as the coordinate form for Q/G/M when no pre-mapped code exists; add the GEO disambiguation table
§14 S, §16 C	Allow a requester UID in the ORG slot; add the citizen ack variant C|SEQ|UID|REF|STATE|ETA|CRC
§23 errors	Add UNKNOWN_CODE, BAD_SCHEMA, BAD_GEO, TRUNCATED
§30 hex coordinates	Mark superseded by PACK10 (16 chars vs 10, precision nobody needs); decoder keeps read-only support
§31 privacy	Add: no MSISDN/name/age in payload; UID is a 4-char pseudonymous device hash
§32 size	Q/G are single-part by construction (~35 chars); multi-part stays a P-polygon-only concern
§37 Redis integration	Delete — replace with "in-process asyncio pipeline"; dedupe TTL moves to a MongoDB TTL index
§33 examples	Add the six worked Q/G/C/S examples
Keep as-is: §4 frame, §7 urgency, §9 availability, §11–13 (N/R/A remain the org-to-org forms), §18–22 markers/polygons/routes, §24–26 checksum/sequence/validation.

3. codec.md — new: the option taxonomy and compressed code language
This is the "our own code language" spec. Human-readable source of truth; the machine-readable shared/codec/pact_tables.v1.json is generated from it next round.

Requester payload — 10 chars, fixed-position base-36 fields:

pos:   0    1    2    3    4    5    6 7 8    9
      [V]  [S]  [P]  [I]  [B]  [U]  [N N N]  [X]
       │    │    │    │    │    │    │        └ vulnerability bitfield (5 bits, 1 char)
       │    │    │    │    │    │    └───────── needs bitfield (12 bits, 3 chars)
       │    │    │    │    │    └────────────── urgency  L/M/H/C   (sms.md §7, unchanged)
       │    │    │    │    └─────────────────── mobility / trapped
       │    │    │    └──────────────────────── injury severity
       │    │    └───────────────────────────── people-count bucket
       │    └────────────────────────────────── situation type
       └─────────────────────────────────────── schema version ('1' = requester v1)
Provider payload — 9 chars: [V][O][R R R][Q][K][E][A] — version, org type, resources bitfield (same 12-bit table as needs, so matching is a bitwise AND), capacity bucket, radius bucket, ETA bucket, availability (A/L/U, sms.md §9 unchanged).

Fixed positions rather than one packed bitfield: costs ~2 chars, buys eyeball-decodable messages on stage, diffable logs, and tail-appendable forward compatibility.

GPS = PACK10, 10 chars, ~1.1 m resolution, zero library dependency either side:

lat_token = base36(round((lat +  90) * 100000))  padded to 5   # 36^5 = 60,466,176
lon_token = base36(round((lon + 180) * 100000))  padded to 5
GEO       = lat_token + lon_token
Chosen over sms.md's existing options: 7 chars shorter than decimal (§29 P2) and more precise; 1 char longer than geohash but needs no base32 alphabet agreed across Python and Kotlin; 6 chars shorter than hex (§30), whose 1.1 cm precision is meaningless against 3–5 m civilian GPS error. Optional 11th char = accuracy bucket, so the portal can draw an uncertainty circle.

Full frame and budget:

Q|SEQ|UID|PAYLOAD|GEO|CRC
Q|001|7F3K|15223C03Q0|6QR6VFBQ33|7F        ← 35 chars, 125 to spare in a 160-char SMS
decoding to: building collapse · 3–4 people · one seriously injured · trapped in debris · critical · needs water + medical + rescue · at 23.25991, 77.41263. UID = first 4 base-36 chars of sha256(device_install_id) — pseudonymous, no PII; the gateway already knows the MSISDN.

All emitted characters are 0-9 A-Z | . , : - — inside GSM-7, so a real SMS never downgrades to UCS-2 (70 chars).

The doc must also carry: the full value table for every dimension (situation ×12, people ×11 with integer representatives, injury ×7, mobility ×8, needs ×12 bits, vulnerability ×5 bits, org type ×11, capacity ×11, radius ×10, ETA ×10); the Q → N fan-out table (one Q becomes one sms.md-shaped need record per set bit, quantity = people_est × factor) so the new requester flow plugs into the existing org-facing N path without changing it; and the failure-mode table — unknown code char (partial-decode and still accept: a request with one garbled field is still a person needing rescue), bad schema version, bad CRC, truncation, duplicate (uid, seq), out-of-range GPS, no-GPS-fix (send last known with accuracy 9, never block the send).

4. agents.md — new: agent pipeline, Groq, MongoDB, API surface
Pipeline (det. = deterministic Python, no LLM):

decoded → A0 Intake (det) → A1 Dedupe (det) → A2 Triage (LLM) → A3 Geo Candidates (det, $geoNear)
        → A4 Provider Advocates (LLM, parallel — this is the "discussion")
        → A5 Allocation Solver (det — emits 3 named options: fastest / max-coverage / least-depleting)
        → A6 Arbiter (LLM — picks an existing option_id, may not invent quantities)
        → A7 Privacy Redactor (det) → A8 Admin Gate (human, asyncio.Future + timeout autopilot)
        → A9 Narrator (LLM) → A10 Verification (det + LLM) → A11 Replanner (det trigger, re-enters at A3)
Per agent the doc gives: input/output JSON schema, LLM-or-not with justification, and the Groq system prompt. The A5/A6 split is the load-bearing design choice — the solver computes the options, the arbiter only chooses one by option_id, validated against the option set. That is also the answer to "what if the LLM hallucinates an allocation".

Agent-discussion event schema — every WebSocket frame: {v, seq, ts, trace_id, run_id, agent, type, payload}. Event types: run.started, agent.entered, agent.thinking, agent.token (streams Groq tokens — this is what makes it look alive), agent.message, agent.tool_call (renders the actual $geoNear call, proving it hit the DB), debate.opened / debate.turn / debate.closed, options.proposed, decision.proposed, awaiting_admin, admin.action, decision.committed, privacy.reveal, notify.sent, verify.result, replan.triggered, run.completed, error. A debate is a first-class object; turns carry a rebuts pointer forming a tree, so the portal renders a threaded argument rather than a log. Client reconnects with ?since=<seq> and replays from agent_events.

Admin interrupt: gate.await_admin() parks on an asyncio.Future keyed by decision_id, resolved by either POST /api/v1/admin/decisions/{id}/action or an inbound WS frame. Timeout → autopilot auto-approve (ship autopilot ON, toggle it OFF live to demo human-in-the-loop). Override re-enters at A5 with pinned allocations; reject re-enters at A3 with the provider excluded.

MongoDB — collections requesters, providers, offers, requests, matches, agent_events (TTL 24h), sms_messages (dedupe unique index on (from_hash, seq)), admin_actions (never TTL — audit), locks (TTL 60s, prevents concurrent runs double-booking stock). offers carries a denormalized loc Point so $geoNear runs on the inventory collection directly. The doc must state coordinates are [lng, lat] and carry the exact aggregation pipeline for "providers within R of this request holding resource X", with a radius ladder 10 → 25 → 60 → 150 km.

Groq — llama-3.3-70b-versatile, AsyncGroq, response_format={"type":"json_object"} plus Pydantic validation (never bare json.loads), streaming mandatory, global asyncio.Semaphore(6), 8s timeout, one repair retry, then a deterministic fallback for every LLM agent so the pipeline never dies mid-demo. Budget ≈ 4 calls / 1.7k tokens per request → ~7 requests/min sustainable on free tier; cap candidates at 8 to cap tokens; send advocates one call containing all candidates rather than N calls.

API surface — requester endpoints, provider endpoints, admin endpoints + WS /ws/agents, and POST /api/v1/pact/ingest (the same codec string over HTTP; /api/v1/sms/webhook becomes a thin adapter calling it with transport="sms" — this is what "one wire format" means concretely).

Fate of the current backend, to record explicitly:

Existing	Fate
GET /, GET /api/v1/health	survive
xor_checksum, parse_sms, RESOURCE_MAP, URGENCY_MAP, LOCATION_*	survive, move verbatim into codec/ + sms/
POST /api/v1/sms/webhook	survives, rewired to enqueue the pipeline
POST /api/v1/crises, POST /api/v1/needs	deleted — folded into POST /api/v1/requests
GET /api/v1/demo-state	replaced by /api/v1/admin/stats + /api/v1/admin/seed
create_response_plan(), RESOURCE_PROVIDERS	deleted as runtime; the greedy logic becomes the A5 solver skeleton and the Groq-down fallback. RESOURCE_PROVIDERS becomes seed_data/providers.json
page.tsx mock inventory + client-side fallback allocator	deleted — portal becomes WS-driven
5. README.md — refresh
Current "Deliberately deferred" list names Redis/PostGIS, which are now permanently out. Update the stack line, the run instructions (Mongo + GROQ_API_KEY), and the demo script.

Implementation roadmap (next round, for reference)
Recorded in memory_draft.md §28 so the build order survives this session:

db/indexes.py + seed.py → bus/eventbus.py + /ws/agents + a fake pipeline emitting scripted events → wire page.tsx to it. Get the portal visibly alive on fake events first; then swap in real agents one at a time, each independently demoable and independently cuttable.
Codec: pact_tables.v1.json + vectors.json → Python base36/geo/frame + pytest against the vectors → payload/decode → fanout.
Kotlin codec mirror + JVM parity test reading the same vectors.json (20 minutes, saves three hours of 3 a.m. table-drift debugging).
Real agents A2→A6, then A7–A9.
Android chip-group request screen + Transport.send HTTP/SMS switch.
Cut-lines, drop from the bottom up: MapLibre in the portal → A10 verification LLM branch → A11 replanner (keep only the decline trigger) → A1 dedupe LLM tiebreak → real FCM (console notifier) → encryption at rest (keep the masking projection, that is the visible privacy story) → the Provider Android app (ship Requester only; drive providers from a seed fixture + a portal button). Never cut: the live WS agent debate, the approve/override bar, $geoNear, and the three-option arbiter choice. That quartet is the demo.

Files touched this round
File	Action
memory_draft (1).md → memory_draft.md	rename + rewrite
sms.md	targeted section edits per the table above
codec.md	new
agents.md	new
README.md	refresh
No code changes this round.

Verification
Docs-only, so verification is consistency checking rather than tests:

No stale stack references — grep -riE "postgres|postgis|redis|keycloak" *.md returns only deliberate historical/"why not" mentions, never live-architecture claims.
Cross-references resolve — every sms.md / codec.md / agents.md pointer names a section that exists. No file references memory_draft.md by the old (1) name.
Codec arithmetic checks out by hand — verify PACK10 round-trips on the worked example: base36(round((23.25991+90)*100000)) → 6QR6V, and decoding 6QR6V returns 23.25991. Verify each worked example's needs bitfield sums to the stated base-36 triple, and that the XOR checksum in each example is actually recomputed rather than illustrative (sms.md §24 already warns its own example checksums are illustrative — the new examples must not repeat that).
Char budget holds — every example frame is ≤ 40 chars and uses only GSM-7 characters.
Namespace collisions called out — S, P, V now exist as both message types and resource codes; confirm sms.md §6 says so explicitly.
Round-trip read — a fresh reader given only these four files can answer: who are the two user populations, what happens when a user taps six chips with no signal, which component computes the allocation quantities, and what the admin sees. If any answer requires this conversation, the docs are incomplete.