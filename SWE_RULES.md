# 📏 HACKATHON SWE RULES (ResiLink / PACT)

**Core Philosophy:** Structure for Speed, Not Perfection. 
Good SWE in a 24-hour hackathon means writing code that is *easy to change* and *easy for AI to understand*, not writing code that is "production-perfect".

## 1. 🏗️ The "Hackathon SOLID" Principles

Do not build enterprise frameworks. Apply SOLID only where it saves time.

| Principle | Hackathon Application (DO) | Time-Waster (DON'T) |
| :--- | :--- | :--- |
| **S**ingle Responsibility | One file = One job. `sms_decoder.py` only decodes. `redis_service.py` only pushes to queues. | Putting SMS parsing, DB saving, and Redis pushing inside the FastAPI route. |
| **O**pen/Closed | Use Dictionary maps for SMS types & Resource codes (`{"F": "food_kits"}`). | Writing 50-line `if/elif/else` blocks to parse SMS payloads. |
| **L**iskov Substitution | **SKIP IT.** Just ensure all Redis messages use the same base Pydantic schema. | Building deep inheritance trees for Agents. |
| **I**nterface Segregation | Keep Pydantic schemas small (`NeedSchema`, `ResourceSchema`). | One giant `Models.py` file with 30 different schemas. |
| **D**ependency Inversion | Pass `redis_client` into functions. | Hardcoding `redis.connect()` inside business logic (makes mocking impossible). |

## 2. 🚦 Architecture Boundaries (The Traffic Cop Rule)

Keep the layers strictly separated. If a layer bleeds into another, the AI will get confused and generate broken code.

1. **FastAPI (The Traffic Cop):** Validates input, checks Auth (mocked), and pushes to Redis. **NO heavy logic here.**
2. **Redis (The Mailbox):** Holds the queues. `sms_incoming`, `need_assessment`, `resource_matching`.
3. **Python Workers (The Brains):** Pull from Redis, do the matching/allocation math, and save to Postgres.
4. **PostgreSQL/PostGIS (The Filing Cabinet):** Stores the final state for the Next.js Dashboard.

## 3. 🤖 AI Token Efficiency Guide (Crucial for Free Tier)

AI context windows fill up fast. If you paste the whole repo, the AI will hallucinate or hit limits.

### ✅ DO: Feed Micro-Context
When asking the AI to write a worker, only provide:
1. The `SWE_RULES.md` (this file).
2. The specific Pydantic schema (e.g., `NeedSchema`).
3. The Redis queue name.

**Prompt Template:**
> "Act as a Python FastAPI/Redis expert. Read `sms.md` and `SWE_RULES.md`. Write the `need_assessment_worker.py`. It must pull JSON from `sms_incoming_queue`, validate it against `NeedSchema`, assign a priority, and push it to `resource_matching_queue`. Keep it under 50 lines."

### ❌ DON'T: Paste the whole backend
Never say: *"Here is my whole backend, fix the agent."* 
Instead say: *"Here is `redis_service.py` and `main.py`. The webhook isn't pushing to the queue. Fix the publish function."*

## 4. 🛑 The "Stop Coding" Triggers (Anti-Patterns)

If you find yourself doing any of these, **STOP**. You are over-engineering and will run out of time.

| 🚨 Anti-Pattern | 🟢 Hackathon Fix |
| :--- | :--- |
| Setting up real Keycloak / OAuth2 flows | **Mock it.** Hardcode a `user_role` header or use a simple dropdown in Next.js. |
| Connecting to real Twilio / Telecom SMS APIs | **Mock it.** Use the Web Dashboard SMS Simulator panel to POST directly to the webhook. |
| Writing complex Linear Programming for routing | **Mock it.** Use simple Python sorting (Urgency first) or PostGIS `ORDER BY distance LIMIT 1`. |
| Building a custom ORM or complex DB migrations | **Keep it simple.** Raw SQL or basic SQLAlchemy/SQLModel. Don't normalize the DB perfectly. |
| Caching Map Tiles dynamically via SMS | **Pre-cache it.** Just bundle a static GeoJSON of "Region A" in the Android/Web app. |

## 5. 🧪 Testing & Debugging Rules

* **No Unit Test Suites:** You don't have time for `pytest` coverage.
* **The "Happy Path" Script:** Your only test is the Demo Script. 
  1. Web Dashboard sends Need -> Agent matches -> DB updates.
  2. SMS Simulator sends `N|001|NGO01|RA|F|300|H|B3` -> Decoder parses -> Agent matches.
* **Logging over Debugging:** Use `print(f"[AGENT] Processed need: {need_id}")` generously. You won't have time to attach a step-through debugger during the pitch.

## 6. 📂 Standardized File Structure

Force the AI to write code into these exact paths to prevent mess:

```text
backend/app/
├── main.py              # FastAPI App & Routes
├── api/                 # Route handlers (Thin)
├── services/            # Redis, DB, SMS Decoder (Reusable logic)
├── agents/              # Background workers (Heavy logic)
└── schemas/             # Pydantic models (Strict typing)
```

## 7. 🚀 Immediate Next Step Execution

**Task:** Connect FastAPI to Redis & Trigger Need Assessment Agent.

**AI Prompt to execute this right now:**
> "Using `SWE_RULES.md`, generate `backend/app/services/redis_service.py` to handle pushing to `need_assessment_queue`. Then generate `backend/app/agents/need_assessment_worker.py` that listens to that queue, prints the decoded SMS JSON, and pushes a dummy match to `resource_matching_queue`. Use standard `redis` python library. Keep it simple."
