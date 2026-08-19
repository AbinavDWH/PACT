# PROJECT MEMORY — PACT

## IMPORTANT INSTRUCTION FOR A NEW CHAT

You are continuing a hackathon project. Read this entire document carefully and preserve all
context.

The project is for Phoenix Hacks, a 24-hour hackathon, Track 6.

The project is **PACT — a Privacy-Preserving Multi-Agent Humanitarian Coordination Platform**.

When answering future questions, always remember:

- This is a hackathon project. Prioritise MVP scope, demo impact, feasibility, and clear
  explanation.
- The system must be privacy-preserving. That is the core innovation.
- The system uses autonomous agents for coordination, powered by the Groq API.
- There are **two populations on the Android app**: people who need help, and people who want to
  help.
- There are **two web portals**: an admin portal and a helper-organization portal.
- Users never type free text. They select options, which compress to a short code.
- SMS is not just for alerts. It is an emergency data-transfer channel when the internet fails.
- OpenStreetMap and MapLibre provide maps, with offline caching in the app.
- Do not overcomplicate production-level features unless asked.

---

## 0. DOCUMENT STRUCTURE

| File | Purpose |
|---|---|
| `memory_draft.md` | This file. High-level project memory, identity model, architecture, demo strategy, hackathon plan |
| `sms.md` | Full SMS transport protocol specification |
| `codec.md` | Option taxonomy and the compressed code language |
| `agents.md` | Agent pipeline, Groq usage, MongoDB schema, API surface |

Rules:

- For SMS framing, checksums, sequence numbers, and message types, refer to `sms.md`.
- For the option taxonomy, code layout, and GPS packing, refer to `codec.md`.
- For agent behaviour, prompts, database schema, and endpoints, refer to `agents.md`.
- Keep this file high-level. Do not duplicate the detailed specifications here.
- If a specification changes, update its own file first, then update the summary here.

---

## 1. PROJECT TITLE

PACT — Privacy-Preserving Multi-Agent Humanitarian Coordination Platform

---

## 2. ABSTRACT

During natural disasters and geopolitical crises, humanitarian response is hindered by fragmented
information, limited resource visibility, duplicated efforts, and poor coordination among
governments, NGOs, CSR organizations, and volunteer groups. Existing centralized coordination
systems require organizations to share sensitive operational and resource information, which may be
restricted for privacy, logistical, or political reasons.

At the same time, the people who actually need help have no reliable channel into any of these
systems. They are counted, surveyed, and assessed — but they cannot ask.

PACT is a privacy-preserving multi-agent humanitarian coordination platform that connects
disaster-affected individuals directly to the organizations and volunteers able to help them, while
allowing those organizations to collaborate without exposing their complete internal data.
Autonomous agents assess incoming needs, discover suitable resources, and allocate them by urgency,
location, availability, and response time. When crisis conditions change, the agents reassess and
generate updated response plans.

The system works when the internet does not. Requests compress to roughly 35 characters and travel
over SMS with GPS coordinates, rendered against map tiles pre-cached on the device.

---

## 3. CORE PROBLEM

Two problems, not one. The original framing captured only the second.

### 3.1 Affected people cannot ask for help

| Problem | Impact |
|---|---|
| No channel | A trapped family has a phone but nobody to send a structured request to |
| Networks fail | Data networks collapse in disasters; SMS often survives |
| Phone calls do not scale | One operator, one caller at a time, during a mass casualty event |
| Free text does not work | Panic, language barriers, literacy, and 160-character limits |
| Accounts are a barrier | Nobody trapped in debris is going to create an account and verify an email |

### 3.2 Organizations cannot coordinate

| Problem | Impact |
|---|---|
| Fragmented information | Organizations do not know who has what |
| Limited resource visibility | Some areas receive too much aid, others receive nothing |
| Duplicated efforts | Multiple groups send the same resources to the same place |
| Poor coordination | Response is slow and inefficient |
| Privacy concerns | Organizations will not expose donors, staff, inventory, or routes |

The unifying problem: **coordination requires information sharing, but information sharing is
exactly what every party has a reason to resist.**

---

## 4. PROPOSED SOLUTION

A coordination platform where autonomous agents mediate between people who need help and people who
can provide it, sharing only the minimum information required to make an allocation.

The agents:

- Receive requests from affected individuals, over data or over SMS.
- Assess severity and prioritise.
- Find nearby helpers with matching resources using geospatial queries.
- Debate the trade-offs of each candidate helper.
- Compute feasible allocation options deterministically.
- Choose among those options and justify the choice.
- Redact everything not required by each audience.
- Notify the allocated helper, and replan when conditions change.

A human administrator watches the entire deliberation live and can approve, override, or reject any
allocation.

---

## 5. MAIN GOALS

- Give affected people a direct, low-bandwidth channel to request help.
- Reduce duplicated humanitarian effort.
- Improve coverage of underserved crisis areas.
- Accelerate emergency response coordination.
- Preserve organizational data autonomy.
- Work when connectivity is weak or absent.
- Make every automated decision auditable and reversible by a human.

---

## 6. USERS AND SURFACES

Four surfaces. This is the most important table in the document.

| Surface | Who uses it | Auth | Session |
|---|---|---|---|
| **App — Seeker mode** | Disaster-affected individuals | **One-time sign-up.** Role, name, phone number. Never asked again | Persists on device until sign-out |
| **App — Helper mode** | Volunteers, and field staff of CSR / NGO / INGO / government teams | **One-time sign-up**, plus an optional group code | Persists on device until sign-out |
| **Web — Organization portal** | An organization's IT / back-office / coordination team | Static username and password, one pair per organization | Signed cookie until logout |
| **Web — Admin portal** | Platform operator | Static username and password | Signed cookie until logout |

Seekers and helpers get **only the app**. Organizations and the platform operator get **only the
web**.

---

## 7. IDENTITY, ROLES, AND ORGANIZATION MEMBERSHIP

Deliberately no Keycloak, no OAuth, no email verification, no password, no password reset.

An application that demands a full account creation flow from someone trapped in a collapsed
building is the wrong product. Account infrastructure also consumes hackathon hours without
contributing anything a judge will see.

### 7.1 One-time sign-up, then never again

On first launch the user completes a single short screen:

| Field | Required | Purpose |
|---|---|---|
| Role | Yes | Seeker or helper. Determines which half of the app opens |
| Name | Yes | So a helper knows who they are looking for; so an operator can address someone by name |
| Phone number | Yes | The reply channel when data fails, and the contact revealed on acceptance |
| Group code | No | Helper mode only. Binds to an organization; skip to remain an individual volunteer |

**There is no password and no verification step.** The user taps through once and is never asked
again. The session persists on the device until they explicitly sign out.

This is a deliberate middle ground. A pure no-sign-in app cannot be replied to by SMS when the
request arrived over HTTP, and has nothing to reveal to a helper on acceptance. A full account
system costs hours and helps nobody in a disaster. One screen, once, solves both.

### 7.2 Two identities, and why they are separate

| Identity | Where it lives | What it is |
|---|---|---|
| `UID` | **On the wire**, in every `Q` and `G` frame | 4 base-36 characters, first 4 of base36(sha256(device install id)) |
| Name and phone | **Server-side only**, in MongoDB, hashed and encrypted | Captured once at sign-up; never encoded into a payload |

This separation is the point. The sign-up collects contact details so the system can actually reach
someone, but **those details never enter the codec payload and never cross the SMS network.** An
intercepted message still reveals only a situation and a location.

The UID remains:

- Pseudonymous on the wire.
- Stable across restarts; regenerated on reinstall.
- The join key between an SMS frame and the server-side record holding the contact details.

Storage: `phone_hash` for lookup, `phone_enc` and `name_enc` for retrieval. The phone hash is also
what lets an inbound SMS from a known number be matched to an existing account.

### 7.3 Group codes

Each organization has a short, human-typable code, for example `RCRS-4K2`. Uppercase, drawn from an
alphabet excluding `O`, `0`, `I` and `1` so it can be read aloud over a bad phone line.

A helper who enters a valid code has `helpers.org_id` set, which:

- Routes that organization's assignments to them rather than to the open volunteer pool.
- Makes them visible on that organization's web portal roster.
- Lets the organization's IT team dispatch them by name.

A helper who enters no code has `org_id = null` and is an **individual volunteer**, matched directly
by the agent pipeline with no intermediary.

An invalid or expired code is rejected and the helper remains individual. **Never block someone from
helping because a code failed.**

### 7.4 Two dispatch paths

This is what the group code actually buys, and it changes what the notification agent does:

```text
Agent pipeline commits an allocation
   |
   +-- allocated to an ORGANIZATION
   |      -> organization's web portal
   |      -> IT team assigns a named helper from the roster
   |      -> that helper's app
   |
   +-- allocated to an INDIVIDUAL VOLUNTEER
          -> straight to their app
```

### 7.5 What the organization portal can and cannot see

The privacy thesis applied to the web tier, not an afterthought.

| The organization portal sees | The organization portal never sees |
|---|---|
| Assignments allocated to **its own** organization | Other organizations' inventory, offers, or assignments |
| The agent's justification for **its** allocation | The full cross-organization advocate debate and arbiter deliberation |
| Masked seeker location and need | Seeker identity, contact, or exact GPS before its helper accepts |
| Its own roster, group code, and inventory | The all-requests firehose |

The admin portal keeps the unrestricted view: the full deliberation stream, every request, every
organization.

### 7.6 Credentials

Admin credentials live in environment variables (`PACT_ADMIN_USER`, `PACT_ADMIN_PASS`). Per-
organization credentials live in the `organizations` seed documents. Both are hashed with bcrypt
even though they are static — it costs one line and removes an easy question from judge Q&A.

Sessions are signed cookies with no refresh flow.

**This is demo-grade authentication and should be described as such.** Real authentication is
explicitly post-hackathon work.

---

## 8. PRIVACY MODEL

The system does not require every party to upload everything into one database.

Traditional centralized system:

```text
All organizations upload full data
        |
        v
Central authority sees everything
        |
        v
Privacy, political, and security risk
```

PACT:

```text
Each party discloses only what an allocation requires
        |
        v
Agents coordinate on those minimal disclosures
        |
        v
Identity and precise location unlock only on commitment and acceptance
```

### 8.1 What stays private

| Data type | Example |
|---|---|
| Full resource inventory | Exact stored quantities of everything |
| Donor information | Who donated, funding sources, amounts |
| Staff and volunteer details | Names, locations, schedules |
| Exact warehouse locations | Precise storage coordinates |
| Logistics routes | Private transport plans |
| Operational plans | Internal response strategy |
| Political and legal constraints | Sanctions, conflict-zone restrictions |
| Beneficiary data | Personal data of people receiving aid |

### 8.2 What is selectively shared

```json
{
  "organization_id": "NGO_001",
  "resource_type": "medical_kits",
  "available_quantity": 150,
  "delivery_radius_km": 50,
  "approximate_region": "District North",
  "response_time_hours": 4
}
```

### 8.3 Revelation is a state transition

Seeker identity, contact details, and exact GPS are masked by default. They unlock between a seeker
and a helper **only after** an allocation is committed **and** the helper accepts it. Before that
moment, a helper sees a need and an approximate area.

The administrator always sees everything. An organization always sees only its own slice.

### 8.4 What the privacy model does not do

SMS is plaintext over the operator network. PACT provides **minimal disclosure and integrity**, not
confidentiality. The vocabulary in `codec.md` is designed so that an intercepted message reveals a
situation and a location but never an identity. Encryption is post-hackathon work and should be
named as such rather than implied.

---

## 9. AGENT ARCHITECTURE

Full specification in `agents.md`. Summary only here.

```text
decoded request
   |
[A0  Intake Normalizer]      deterministic
[A1  Dedupe / Cluster]       deterministic
[A2  Triage]                 LLM       severity and tier
[A3  Geo Candidate Finder]   deterministic   MongoDB $geoNear
[A4  Helper Advocates]       LLM       one argument per candidate  <- the discussion
[A5  Allocation Solver]      deterministic   three feasible options
[A6  Arbiter]                LLM       picks one option, rebuts    <- the debate
[A7  Privacy Redactor]       deterministic   per-audience projection
[A8  Admin Gate]             human     approve / override / reject
[A9  Narrator + Dispatcher]  LLM + det. justification and notification
[A10 Verification]           det. + LLM delivery confirmation
[A11 Replanner Watchdog]     deterministic   re-enters at A3
```

### 9.1 The governing rule

> **The LLM produces labels, rankings, choices among enumerated options, and prose.
> Every number written to the database is produced by Python.**

An LLM never divides 300 kits across 4 providers. The solver computes the options; the arbiter only
picks one by its identifier, validated against the option set. This is the structural answer to
"what if the model hallucinates an allocation" — it cannot, because it never emits a quantity.

### 9.2 Why this split

| Task | Who does it | Why |
|---|---|---|
| Severity judgement | LLM | Weighing infants against injuries against heat against elapsed time is genuine multi-factor reasoning |
| Arguing a candidate's suitability | LLM | Produces the visible deliberation, cheaply |
| Choosing between close options | LLM | A judgement call with stated trade-offs |
| Writing the justification | LLM | Human-readable explanation is the point |
| Geospatial search | Python | `$geoNear` |
| Allocation arithmetic | Python | Auditable, correct, and fast |
| Privacy gating | Python | A deterministic policy is auditable; never trust a model with personal data |

### 9.3 Reliability

Every LLM agent has a deterministic fallback. If Groq is slow, rate-limited, or returns malformed
JSON, the pipeline emits an amber `error` event and continues with the fallback. **The demo cannot
be killed by an API.**

---

## 10. SYSTEM COMPONENTS

1. Android app — seeker mode and helper mode
2. Admin web portal
3. Organization web portal
4. FastAPI backend
5. In-process asynchronous multi-agent engine
6. Groq API — `openai/gpt-oss-120b`
7. MongoDB with `2dsphere` geospatial indexes
8. SMS fallback channel
9. OpenStreetMap and MapLibre, with offline tile caching

---

## 11. TECH STACK

| Component | Technology |
|---|---|
| Android app | Kotlin |
| Web portals | Next.js and TypeScript |
| Backend | Python, FastAPI |
| Database | **MongoDB** with `2dsphere` |
| Agents | Python `asyncio`, in-process |
| LLM | **Groq API, `openai/gpt-oss-120b`** (`gpt-oss-20b` for high-volume agents) |
| Agent bus | **In-process `asyncio` pub/sub. No Redis** |
| Live updates | WebSocket |
| Maps | OpenStreetMap and MapLibre |
| Auth | Static credentials on web; no-password role choice on the app |

### 11.1 Deliberate changes from the original plan

| Was | Now | Why |
|---|---|---|
| PostgreSQL + PostGIS | MongoDB with `2dsphere` | One service instead of two, no migrations, no schema ceremony, and `$geoNear` covers every spatial query needed. PostGIS is more powerful than this project requires |
| Redis agent bus | In-process `asyncio` pub/sub | Agents run in one FastAPI process, so a network queue between them adds infrastructure, latency, and debugging surface for no benefit. Deliberation persists to MongoDB, which also gives replay for free |
| Keycloak | Static credentials | Identity infrastructure is invisible to judges and costs hours |
| Unspecified Python workers | Groq, `openai/gpt-oss-120b` | Chosen for very high tokens per second, which is what makes streamed deliberation feel live. Model id verified against the account -- `llama-3.3-70b-versatile` is not available on free-tier keys |
| Free-text field reports | Option selection and a compressed code | Smaller, faster, unambiguous, language-independent, and it cannot leak personal data |

These are not regressions. Each removes a component that would have consumed build time without
appearing in the demonstration.

---

## 12. THE CODE LANGUAGE

Full specification in `codec.md`. Summary only here.

Users select options. Each selection path maps to a base-36 character. A whole request becomes ten
characters, plus a ten-character packed GPS position.

```text
Q|001|7F3K|15223C03Q0|6QR6VFBQ33|7F
```

35 characters, decoding to: building collapse, 3–4 people, one seriously injured, trapped in debris,
critical urgency, needs water and medical supplies and rescue, at 23.25991, 77.41263.

Properties that matter:

- Under 40 characters, against a 160-character SMS limit — never fragments.
- GSM-7 characters only, so an SMS never downgrades to 70 characters.
- The same string travels over HTTP and over SMS. **One wire format, two transports.**
- Closed vocabulary, so no personal data can leak into it.
- Deterministic, so encoder and decoder are testable against fixed vectors shared between Python and
  Kotlin.

---

## 13. ADMIN PORTAL BLUEPRINT

The command centre, and the demonstration centrepiece.

### Live match stream — the primary view

Cards, one per request in flight. Inside each card, the agents deliberate in real time: triage
reasons about severity, advocates argue for each candidate helper, the solver proposes three named
options, the arbiter picks one and rebuts the arguments it rejected.

Groq tokens stream into the bubbles as they are generated. This is what makes the difference between
"a system produced an answer" and "I watched it reason".

### All requests — the top-bar button

Every incoming request, whether or not it has been matched. Table with filters and a map, and each
row opens that request's full deliberation trace.

### Approve, override, reject

When the arbiter proposes a decision, the pipeline pauses on an admin gate with a visible countdown.
The administrator can approve, override the allocation, or reject a helper and force a re-match. A
timeout auto-approves so the demo never stalls; the autopilot toggle can be switched off live to
demonstrate human-in-the-loop control.

### Other panels

- Privacy boundary — what is shared, what is withheld, and what unlocked on acceptance
- Map — crisis points, helper positions, allocation lines
- SMS simulator — paste a code string and watch it decode and enter the pipeline
- Statistics strip — requests, matches, coverage, unmet need

---

## 14. ORGANIZATION PORTAL BLUEPRINT

Used by an organization's IT or back-office team. Not a second admin portal — a deliberately
narrower view.

| Page | Purpose |
|---|---|
| Assignments | Allocations made to this organization. Accept or decline |
| Assign | Dispatch an accepted assignment to a named helper from the roster |
| Roster | Helpers who joined using this organization's group code |
| Inventory | The resources this organization is offering, with quantities and ETAs |
| Group code | The code to distribute to field staff |

The organization sees the justification for its own allocations, but never the cross-organization
debate and never other organizations' data. That boundary is the privacy model made visible at the
web tier.

---

## 15. ANDROID APP BLUEPRINT

### First launch, both modes

One screen, once: pick a role, enter a name and a phone number, optionally enter a group code if
helping. No password, no verification, no second visit to this screen ever. See §7.1.

### Seeker mode

- Opens straight to the request screen on every launch after the first.
- Request screen: chip groups, one row per dimension. **No text field anywhere in the flow.**
- GPS captured automatically; never blocks the send if there is no fix.
- Status view: has a helper been assigned, what is the ETA, and after acceptance, how to contact
  them.
- Confirm receipt with a delivery code.

### Helper mode

- Optional group code entry at sign-up, or later from settings, to join an organization; skip it to
  remain an individual volunteer.
- Declare what resources are available, in what quantity, within what radius.
- Receive assignments, accept or decline, update status.
- Acceptance is what unlocks the seeker's exact position and contact details.

### Both modes

- Offline OpenStreetMap tiles, pre-cached.
- SMS fallback handled entirely inside one transport function. The interface never knows which path
  a message took.
- A local outbox queues messages that failed to send and replays them when connectivity returns.

Android rather than iOS because Android permits programmatic SMS sending and receiving. iOS does
not.

---

## 16. SMS FALLBACK

SMS is a data-transfer channel, not a notification channel. Full protocol in `sms.md`.

It can carry: requests, offers, allocations, status updates, confirmations, cancellations, map
markers, polygon chunks, route waypoints, and errors.

It cannot carry: map tiles, images, video, full inventories, database synchronisation, or real-time
tracking.

Map tiles must be pre-cached in the app. SMS updates only what is drawn on top of them.

---

## 17. ARCHITECTURE

```text
+---------------------------+          +---------------------------+
|      ANDROID APP          |          |       WEB PORTALS         |
|                           |          |                           |
|  Seeker mode              |          |  Admin portal             |
|  Helper mode              |          |    live deliberation      |
|  chip selection           |          |    all requests           |
|  offline map              |          |    approve / override     |
|  one-time sign-up         |          |                           |
|                           |          |  Organization portal      |
|                           |          |    own assignments        |
|                           |          |    roster, inventory      |
+------+-------------+------+          +-------------+-------------+
       |             |                               |
   data up       no data                        static login
       |             |                               |
       v             v                               v
  HTTP ingest    SMS gateway              +----------+-----------+
       |             |                    |                      |
       +------+------+                    |                      |
              v                           |                      |
     +--------+-----------------------------------------+        |
     |             FastAPI backend                      |<-------+
     |  codec, privacy filter, routers, WebSocket        |
     +--------------------+-----------------------------+
                          |
              +-----------+-----------+
              v                       v
   In-process agent pipeline     Event bus (asyncio)
   A0 .. A11, Groq-backed             |
              |                       +--> WS /ws/agents  (admin, full)
              v                       +--> WS /ws/org     (org, own slice)
          MongoDB
      2dsphere geo indexes
      deliberation transcript
```

---

## 18. DATA FLOW — CONNECTED

```text
Seeker taps chips
        |
        v
App encodes selections to a code string
        |
        v
POST /api/v1/pact/ingest
        |
        v
Decoder expands the code to structured JSON
        |
        v
Agent pipeline: triage, geo search, advocates, solver, arbiter
        |
        v
Admin gate: approve, override, or auto-approve on timeout
        |
        v
MongoDB stores the match; deliberation streams to the portal
        |
        v
Organization portal or individual volunteer's app is notified
        |
        v
Helper accepts -> contact and exact position revealed both ways
```

---

## 19. DATA FLOW — NO CONNECTIVITY

```text
App detects no data connection
        |
        v
The SAME code string is sent by SMS instead of HTTP
        |
        v
Gateway delivers to POST /api/v1/sms/webhook
        |
        v
Thin adapter calls the same ingest path
        |
        v
Identical pipeline, identical result
        |
        v
Backend replies by SMS with an allocation and ETA
        |
        v
App parses it and updates the cached offline map
        |
        v
Local outbox syncs when connectivity returns
```

The two flows differ in exactly one function. That is the point of a single wire format.

---

## 20. HACKATHON MVP SCOPE

### Must build

1. Event bus and `/ws/agents`, with the admin portal rendering live events
2. The codec: tables, encoder, decoder, and cross-language test vectors
3. MongoDB schema, indexes, and seed data
4. Agent pipeline — deterministic agents first, then the Groq-backed ones
5. Admin portal: live match stream, all-requests view, approve and override
6. SMS decode path and the simulator panel
7. Android seeker mode: role choice, chip request screen, transport switch
8. Privacy boundary made visible in the portal

### Do not overbuild

- Real telecom SMS integration
- Production authentication and role-based access control
- Advanced cryptographic privacy
- A full routing engine
- Perfect visual design
- Large database seeding
- Production deployment

---

## 21. WHAT TO MOCK

| Feature | How |
|---|---|
| ~~Real SMS gateway~~ | **No longer mocked.** A second handset runs the app in gateway mode: a `SMS_RECEIVED` receiver forwards PACT frames to `/api/v1/sms/webhook`. Real cellular SMS, no vendor. The simulator panel survives as a convenience, not as the mechanism. See `android/README.md` |
| Push notification | Console notifier writing to an outbox the portal renders |
| Multiple organizations | Three or four seeded fixtures |
| Helper Android mode, if time runs short | Seeded fixtures plus the organization portal |
| Agent distribution | All agents run in one backend process |

---

## 22. BUILD ORDER

1. **Hours 1–4.** MongoDB indexes and seed data. Event bus, `/ws/agents`, and a fake pipeline
   emitting scripted events. Wire the admin page to it. **Get the portal visibly alive on fake
   events before writing a single real agent.**
2. **Hours 5–9.** The codec: tables and vectors, then Python encode and decode with tests, then the
   fan-out into needs.
3. **Hours 10–15.** Real agents, one at a time. The deterministic ones first — intake, dedupe, geo,
   solver — since they need no API key. Then triage, advocates, arbiter, and finally privacy,
   gate, and narrator.
4. **Hours 16–19.** Android seeker mode: role choice, chip screen, transport switch, Kotlin codec
   mirror with the shared test vectors.
5. **Hours 20–21.** Organization portal, reusing the admin portal's bus and components.
6. **Hours 22–24.** Test the full flow. Record a backup video. Prepare the pitch. **Stop coding
   before the presentation.**

Every agent added after step 1 is independently demonstrable and independently cuttable. That
property is worth more than any individual feature.

---

## 23. CUT-LINES

Drop from the bottom up.

1. MapLibre in the portal — replace with a static map or a scatter plot. **Cut first.**
2. The verification agent's LLM branch — keep the deterministic delivery-code check.
3. The replanner — keep only the decline trigger.
4. Dedupe — keep the geohash key, drop any model tiebreak.
5. Real push notification — console notifier.
6. Encryption at rest — keep the masking projection, which is the visible privacy story.
7. Helper mode in the app — ship seeker mode only, drive helpers from fixtures.

**Never cut:** the live agent debate over WebSocket, the approve and override bar, the geospatial
query, and the three-option arbiter choice. That quartet is the demonstration.

---

## 24. DEMO SCRIPT

**1. The problem.** During disasters, organizations cannot see each other's resources and will not
share their internal data. Meanwhile the people who need help have no way to ask.

**2. A request.** Open the app. Tap six chips: building collapse, three to four people, one
seriously injured, trapped in debris, critical, needs medical and water and rescue. Send.

**3. The agents deliberate.** Switch to the admin portal. The triage agent reasons about severity
and assigns tier T1. The geospatial query runs, visibly. Four helper advocates argue for and against
their candidates. The solver proposes three options: fastest, maximum coverage, least depleting. The
arbiter picks one and explains which arguments it rejected.

**4. Human control.** The pipeline pauses. Override the allocation. Watch it re-solve and commit the
override.

**5. Privacy.** Show the privacy boundary. The helper saw an approximate area and a need. Only now
that they have accepted does the exact position unlock. Show the organization portal — it sees its
own assignment and nothing else, not even that other organizations were considered.

**6. Connectivity fails.** Put the phone in airplane mode. Send the identical request. It goes by
SMS. Hold up the 35-character payload against the 160-character limit. The same request appears in
the portal, and the app updates its offline map from the SMS reply.

**7. Conditions change.** The assigned helper declines. The replanner fires automatically and a new
deliberation begins under the same request.

---

## 25. JUDGE QUESTIONS

**Why not a centralized database?** Centralized systems require organizations to expose complete
internal data, which is exactly what they refuse to do. Agents coordinate on minimal disclosures
instead.

**How is privacy preserved?** Three mechanisms. A closed vocabulary that cannot contain personal
data. A deterministic redaction policy applied per audience. And revelation as a state transition —
identity and exact position unlock only on commitment and acceptance.

**What if the language model hallucinates an allocation?** It structurally cannot. The solver
computes the options in Python; the arbiter can only return the identifier of an existing option,
validated before anything is written. No number in the database originates from the model.

**What happens if the Groq API fails mid-demonstration?** Every model-backed agent has a
deterministic fallback. The portal shows an amber warning and the pipeline continues. You can watch
it happen.

**Why MongoDB rather than PostGIS?** `2dsphere` and `$geoNear` cover every spatial query this system
performs. MongoDB is one service instead of two, with no migrations. PostGIS is more powerful than
this project needs, and that power costs setup time we would rather spend on agents.

**Why no Redis?** The agents run in one process. A network queue between coroutines in the same
process adds infrastructure and latency for no benefit. Deliberation persists to MongoDB, which also
provides replay.

**Why such a minimal sign-in on the app?** Because someone trapped in a collapsed building will not
work through a registration flow, verify an email, or remember a password. One screen, once: role,
name, phone. That is the least we can collect and still be able to reach the person, and it is never
asked again.

**Then how is it still private?** Because the contact details never leave the database. The wire
identity is a 4-character hash of the device installation, carried in every SMS frame. Name and
phone are encrypted at rest and released to a helper only after an allocation is committed and that
helper accepts. Intercept a message and you learn a situation and a location, never a person.

**Why option selection instead of free text?** Size, speed, reliability, literacy, and privacy. 35
characters instead of 200, no parsing ambiguity, no language dependency, and a closed vocabulary
cannot leak a name.

**Why SMS?** Data networks fail in disasters; SMS frequently survives on 2G. Our requests are small
enough to fit in a single message.

**Can SMS transfer everything?** No. Small payloads only. Map tiles are pre-cached; SMS updates only
what is drawn over them.

**Why Android?** Android permits programmatic SMS sending and receiving. iOS restricts it.

**Is this production-ready?** No, and we would not claim so. It demonstrates the architecture and
the full coordination flow. Production needs a real SMS gateway, real authentication, encryption at
rest and in transit, audit retention, and field-tested offline synchronisation.

**What is the main innovation?** Privacy-preserving coordination that includes the affected person
as a first-class participant, remains resilient when the internet fails, and keeps a human in
control of every automated decision.

---

## 26. DECISIONS ALREADY MADE

- There are two app populations: people who need help, and people who help.
- The app has a one-time sign-up: role, name, phone number. No password, no verification. The user
  is never asked again, and the session persists until explicit sign-out.
- Name and phone live server-side only, hashed and encrypted. They never enter a codec payload and
  never cross the SMS network. The wire identity stays the pseudonymous device-derived `UID`.
- The web has two portals, both behind static credentials: admin, and organization.
- Helpers join an organization with a group code; without one they are individual volunteers.
- Those two cases produce two different dispatch paths.
- The organization portal sees only its own slice. The admin sees everything.
- Users never type free text. Selections compress to a short code.
- One wire format serves both HTTP and SMS.
- MongoDB with `2dsphere` replaces PostgreSQL and PostGIS.
- The agent bus is in-process `asyncio`. Redis is not used.
- Agents run on Groq with `openai/gpt-oss-120b` for judgement and `openai/gpt-oss-20b` for
  high-volume calls. Model ids were verified against the account with `models.list()`;
  `llama-3.3-70b-versatile` is not available on free-tier keys.
- Free-tier Groq is capped at 8000 tokens per minute, which allows roughly 4 pipeline runs per
  minute. Ample for a demo, but it rules out load testing against the live API.
- The LLM never produces a number that reaches the database.
- Every LLM agent has a deterministic fallback.
- Seeker identity and exact position unlock only on commitment and acceptance.
- The admin can approve, override, or reject any allocation.
- Map tiles are pre-cached; SMS cannot carry them.
- Authentication is demo-grade and is described as such.
- The biggest innovation is privacy-preserving coordination that includes the affected person.
- The biggest demonstration moment is watching the agents debate, then switching to airplane mode
  and getting the same result over SMS.

---

## 27. ONE-LINE SUMMARY

PACT is a privacy-preserving multi-agent humanitarian coordination platform where disaster-affected
people request help by tapping a few options that compress to a 35-character code, autonomous Groq-
backed agents debate and allocate resources from NGOs, CSR teams, aid groups and volunteers without
exposing anyone's internal data, a human administrator watches the deliberation live and can
override any decision, and the whole flow works identically over SMS when the internet is gone.
