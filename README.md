# PACT

Privacy-Preserving Multi-Agent Humanitarian Coordination Platform.

Disaster-affected people request help by tapping a few options that compress to a 35-character code.
Autonomous agents debate and allocate resources from NGOs, CSR teams, aid groups and volunteers
without exposing anyone's internal data. A human administrator watches the deliberation live and can
override any decision. The whole flow works identically over SMS when the internet is gone.

## Documents

The design is specified across four files. Read them in this order.

| File | Contents |
|---|---|
| [memory_draft.md](memory_draft.md) | Project memory: problem, users, identity model, privacy model, architecture, demo script, judge Q&A |
| [codec.md](codec.md) | The code language: option taxonomy, payload layout, PACK10 GPS packing |
| [sms.md](sms.md) | SMS transport protocol: framing, checksums, message types, error codes |
| [agents.md](agents.md) | Agent pipeline, Groq usage, MongoDB schema, full API surface |

## Stack

| Component | Technology |
|---|---|
| Android app | Kotlin — seeker mode and helper mode, one-time sign-up |
| Web portals | Next.js and TypeScript — admin portal and organization portal |
| Backend | Python, FastAPI |
| Database | MongoDB with `2dsphere` geospatial indexes |
| Agents | Python `asyncio`, in-process, no Redis |
| LLM | Groq API, `llama-3.3-70b-versatile` |
| Live updates | WebSocket |
| Maps | OpenStreetMap and MapLibre, offline tile caching |

## Status

**Step 1 of the build order is complete** (see [memory_draft.md](memory_draft.md) §22). The admin
portal is alive on a real WebSocket event stream, driven by a scripted pipeline that emits the
complete event vocabulary from [agents.md](agents.md) §3.2. Real Groq agents replace the scripted
ones behind that same stream without any frontend change.

Working today:

- In-process async event bus with `/ws/agents` and `/ws/org` (no Redis)
- Scripted 10-agent pipeline: intake, dedupe, triage, geo search, advocate debate, three-option
  solver, arbiter, privacy redaction, admin gate, narrator
- Admin portal live match stream with streaming agent output, threaded rebuttals, and option cards
- Working approve / override / reject gate, plus autopilot timeout
- All-requests view; state shared across routes by one socket
- Visible privacy boundary: shared versus withheld fields
- Legacy and canonical `N` SMS decoding with XOR checksum validation

Not yet implemented:

- MongoDB persistence and `$geoNear` matching (Atlas cluster pending)
- Real Groq agents (`GROQ_API_KEY` pending)
- The `Q` and `G` compressed codec
- Organization portal
- The Kotlin Android app
- Offline MapLibre rendering

## Run locally

Backend:

```powershell
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

Web:

```powershell
cd web
pnpm dev
```

Open `http://localhost:3000`. The web app targets `http://localhost:8000` by default; set
`NEXT_PUBLIC_API_BASE_URL` to point elsewhere.

### Environment

Once the agent pipeline lands, the backend will additionally require:

```text
MONGO_URI          MongoDB connection string
GROQ_API_KEY       Groq API key
PACT_ADMIN_USER    Admin portal username
PACT_ADMIN_PASS    Admin portal password
```

## Demo

1. Submit a request and watch the agents triage, search, argue, and allocate.
2. Override an allocation from the admin portal to show human-in-the-loop control.
3. Show the privacy boundary: what was shared, what was withheld, what unlocked on acceptance.
4. Switch the phone to airplane mode and send the identical request over SMS.

Full script in [memory_draft.md](memory_draft.md) §24.
