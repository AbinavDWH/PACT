```markdown
# Web Request Hub — Website Plan

Project: Privacy-Preserving Multi-Agent Humanitarian Coordination Platform
Hackathon: Phoenix Hacks — Track 6
Repo: https://github.com/AbinavDWH/PACT
Branch: testabi8
Last Updated: August 19, 2026
Owner: Teammate (Web Dashboard)

---

## Repo Verification Summary

- Repo: `https://github.com/AbinavDWH/PACT`
- Branch: `testabi8`
- Last STATUS.md update: August 19, 2026 — Android MVP M0–M10 code complete; Web Dashboard = Pending
- Known backend state: FastAPI with `/api/v1/health`, `/api/v1/needs`, `/api/v1/sms/webhook`, SMS parsing + XOR checksum done; Redis connection in progress
- Note: No live GitHub access in this chat. If repo changed since Aug 19, follow `REPO_CHECK.md` before starting.

---

## 1. Purpose

The web dashboard must become the place where:

1. Organizations make any request (Need / Resource Availability / Status Update).
2. Coordinators review incoming requests from all sources (Web / SMS / Android).
3. Coordinators Accept or Reject requests.
4. Accepted requests are pushed to Redis agent queues for automated processing.

This file defines the Request Hub implementation plan for the Next.js web dashboard.

---

## 2. Request Lifecycle

```text
Request arrives (Web form / SMS webhook / Android sync)
        │
        ▼
   [ PENDING ]  ← shown in Request Hub
        │
   Coordinator clicks Accept / Reject
        │
   ┌────┴──────────┐
[ ACCEPTED ]   [ REJECTED / DUP / PRIVACY ]
   │
   ▼
Pushed to Redis queue (need / resource / coordination)
   │
   ▼
[ PROCESSING → MATCHED → ALLOCATED → COMPLETED ]
```

Request statuses:

| Status | Meaning |
|---|---|
| pending | Arrived, waiting for review |
| accepted | Approved by coordinator, sent to agents |
| rejected | Rejected with reason |
| duplicate | Same org_id + seq already processed |
| processing | Agent working on it |
| matched | Resource Matching Agent found resources |
| allocated | Coordination Agent created plan |
| completed | Delivered and confirmed |

---

## 3. Pages (Next.js App Router)

| Route | Purpose | Priority |
|---|---|---|
| `/` | Dashboard overview: active crises, pending request count, agent feed | P1 |
| `/requests` | Request Hub: list all requests, Accept / Reject | P1 |
| `/requests/new` | Form to make a request (Need / Resource / Status) | P1 |
| `/plans` | Allocation plans created by Coordination Agent | P2 |
| `/map` | OpenStreetMap + MapLibre crisis and resource view | P2 |
| `/sms-simulator` | Inject SMS payloads per `sms.md` | P2 |
| `/agents` | Agent activity log | P3 |
| `/privacy` | Shared vs hidden data panel | P3 |

---

## 4. Request Hub (`/requests`) — Key Screen

### Table columns

| ID | Type | Org | Location | Resource | Qty | Urgency | Source | Status | Action |
|---|---|---|---|---|---|---|---|---|---|
| REQ-001 | Need | NGO01 | RA | Food | 300 | High | SMS | pending | Accept / Reject |
| REQ-002 | Resource | CSR02 | RA | Food | 200 | Available | Web | accepted | — |

### Features (MVP first)

- Tabs: `All | Pending | Accepted | Rejected`
- Filters: type (Need / Resource / Status), source badge (Web / SMS / Android), urgency, location
- Accept button: calls backend, backend validates (checksum, duplicate, privacy), then pushes to Redis queue
- Reject button: requires reason (invalid / duplicate / privacy violation)
- Auto-refresh: poll every 3 seconds. Do not use WebSockets for the hackathon.

### Auto-validation on Accept (backend side)

1. Checksum valid → else auto-reject with `BAD_CRC`
2. Duplicate check (`organization_id + seq`) → auto-flag `DUP`
3. Privacy filter (no donor / staff / warehouse / funding data) → else reject `PRIVACY`

Validation rules follow `sms.md` sections 26 and 31.

---

## 5. Make Request Form (`/requests/new`)

Single form with a type selector.

### Type = Need

- Organization (dropdown: NGO01, CSR02, GOV03…)
- Location (dropdown mapped to codes: RA / RB / RC / D1 / D2)
- Resource (dropdown mapped to codes: F / W / M / T / B / H / D)
- Quantity (number)
- Urgency (radio: L / M / H / C)

### Type = Resource Availability

- Same fields plus Status (A = Available / L = Limited / U = Unavailable)

### Type = Status Update

- Plan ID
- Status code (0 Assigned, 1 Dispatched, 2 In transit, 3 Delivered, 4 Blocked, 5 Cancelled)

### Behavior

On submit:

1. POST request to backend.
2. Request appears as `pending` in the Request Hub.
3. Show live preview of the equivalent canonical SMS below the form.

Example live preview:

```text
N|001|NGO01|RA|F|300|H|B3
```

This visually ties the web dashboard to the SMS protocol and is a strong demo moment.

---

## 6. Backend Endpoints Required

Existing and confirmed:

```text
GET  /api/v1/health
POST /api/v1/needs
POST /api/v1/sms/webhook
```

New endpoints needed from teammate:

```text
GET  /api/v1/requests?status=pending&type=need&source=sms
POST /api/v1/requests                  # generic: need | resource | status
POST /api/v1/requests/{id}/accept      # validate then push to Redis
POST /api/v1/requests/{id}/reject      # body: { reason }
GET  /api/v1/plans
GET  /api/v1/agent-activity
```

### New database table: `requests`

```text
id
type
seq
organization_id
location_code
resource
quantity
urgency
status          -- pending / accepted / rejected / duplicate / processing / matched / allocated / completed
source          -- web / sms / android
payload         -- JSONB
checksum
created_at
reviewed_at
reject_reason
```

### Redis queue on Accept

| Request type | Queue |
|---|---|
| Need (N) | `need_assessment_queue` |
| Resource (R) | `resource_matching_queue` |
| Status (S) | `coordination_queue` |

---

## 7. Frontend Components

```text
web/app/
├── requests/
│   ├── page.tsx                # Request Hub
│   └── new/page.tsx            # Make Request form
├── components/
│   ├── RequestTable.tsx
│   ├── RequestRow.tsx          # Accept / Reject buttons
│   ├── RequestForm.tsx
│   ├── SourceBadge.tsx         # Web / SMS / Android
│   ├── UrgencyBadge.tsx
│   ├── FilterBar.tsx
│   └── SmsPreview.tsx          # live canonical SMS preview
└── lib/
    ├── api.ts                  # fetch helpers
    └── types.ts                # Request, Plan types
```

---

## 8. Build Order

| Phase | Time | Deliverable |
|---|---|---|
| 1 | ~3h | `/requests` list + Accept / Reject wired to backend + Redis push |
| 2 | ~2h | `/requests/new` form (need + resource + status) |
| 3 | ~2h | Filters + source badges + 3s polling refresh |
| 4 | ~2h | `/plans` panel showing results of accepted requests |
| 5 | optional | SMS simulator, map panel, privacy panel, agent feed |

### Hackathon shortcuts (allowed)

- Mock JWT / hardcoded user roles.
- Polling every 3 seconds instead of WebSocket / SSE.
- Seed 3 fake organizations and 5 pending requests so the demo table is never empty.
- Optional toggle: "Auto-accept web requests" so judges do not wait for manual clicks.

---

## 9. Demo Flow (judge-facing)

1. Open Request Hub. Show 2 pending SMS requests already arrived.
2. Click Accept on a need. Agent feed shows Need Assessment Agent processing.
3. Switch to Make Request. Submit a new resource availability live.
4. Show Plans panel. Coordination Agent allocated using the accepted data.
5. Say: "Every request — from web, SMS, or the Android app — flows through the same privacy-checked acceptance pipeline."

---

## 10. Integration Dependencies

- `/api/v1/needs` must stay live for Android M10 sync worker.
- Request Hub must accept requests from all three sources: web form, SMS webhook, Android sync.
- SMS payloads follow `sms.md` canonical format.
- Do not add real telecom SMS integration for MVP. Use the SMS simulator panel.

---

## 11. DO THIS NOW

Teammate: create `GET /api/v1/requests` and `POST /api/v1/requests/{id}/accept` in FastAPI, with Redis push on accept.
Web: build `/requests` page against those two endpoints first. Everything else waits until that works.

```

---

