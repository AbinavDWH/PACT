# PACT — Current Development Status (Working Document)

Repository: https://github.com/AbinavDWH/PACT
Current branch: testabi8
Owner: Me (Android + coordination)
Last updated: August 19, 2026 — evening session (Request Hub build)

Purpose:
Every new AI session must read this file first.
This file represents the current truth of the project.
Do not assume missing modules are done unless listed under Completed Modules.

---

## Overview

| Area | Status | Owner | Notes |
|---|---|---|---|
| Android app | MVP Complete (M0–M10) | Me | Code-complete; still needs push + verification |
| Backend API (FastAPI) | In Progress | Teammate + me | health, needs, SMS webhook, Request Hub endpoints live |
| Redis + agent workers | Deferred | Teammate | In-memory simulated agent bus for now; clean swap point exists |
| Web dashboard | In Progress | Teammate + me | Phase 1 Request Hub page live and verified |

---

## Session start documents (read in this order)

1. `AI_CONTEXT_LOADER.md`
2. `REPO_CHECK.md`
3. `STATUS.md`
4. `SWE_RULES.md`
5. `sms.md` (if touching SMS protocol)
6. `web_plan.md` (if touching web)
7. `memory_draft.md` (background + demo strategy)

---

## Current Work Split

### Me — Android App (MVP complete, pending push/verify)

Modules:
1. App shell, architecture, theme, navigation
2. Auth + Organization setup
3. Crisis creation / selection
4. Dashboard
5. My Requests + Create Request
6. Offline-first storage, sync, conflict rules
7. SMS fallback: encoder/decoder, XOR checksum, simulator
8. Map: offline marker storage, crisis marker rendering, sync
9. Field Report with image + offline queue + status
10. Settings, sync center, diagnostics

Current status:
All M0–M10 code-complete (see Android progress list below). Push + verify still pending.

### Teammate — Backend API + Redis + Agents

Backend (FastAPI):
- [x] GET /api/v1/health
- [x] POST /api/v1/needs
- [x] POST /api/v1/sms/webhook — decodes legacy + canonical N; R and S added Aug 19
- [x] Request Hub endpoints — built + verified Aug 19 evening (section below)

Redis + agent pipeline:
- [ ] Connect Redis — deferred by decision; in-memory simulation used instead
- [ ] need_assessment_queue
- [ ] resource_matching_queue
- [ ] coordination_queue

Integration contract:
- `/api/v1/needs` must stay live; Android offline-to-online demo depends on it
- `/api/v1/sms/webhook` should return decoded JSON matching sms.md section 27

### Web Dashboard

See Web Dashboard Progress below.

---

## Backend Request Hub — DONE (Aug 19 evening session)

Single-file `backend/app/main.py` (additive — `/needs`, `/sms/webhook` response shapes only gained fields; Android unaffected). No Redis: in-memory store + simulated agent bus with a clean swap point.

Endpoints (all verified live):
- [x] GET /api/v1/requests?status=&type=&source=
- [x] POST /api/v1/requests (generic: need | resource | status)
- [x] POST /api/v1/requests/{id}/accept — validate then route to queue
- [x] POST /api/v1/requests/{id}/reject — body: { reason }
- [x] GET /api/v1/plans
- [x] GET /api/v1/agent-activity
- [x] GET/POST /api/v1/config/auto-accept (demo insurance toggle)

Behavior:
- Accept validation order: XOR checksum -> duplicate (org+seq) -> privacy filter (sms.md sections 26, 31)
- Accept triggers simulated pipeline: processing -> matched -> allocated, generating a plan
  (greedy allocation from seeded org inventories, fastest ETA first)
- All three sources flow into one hub: web form, SMS webhook, Android sync (via /needs)
- Seed data: 3 orgs (NGO01/CSR02/GOV03), 5 pending requests (mixed sources), 1 delivered plan
- Server restart resets state to seed — use this as the demo reset button

Verified: curl smoke tests all passed (accept -> pipeline -> PLAN-101; duplicate guard 409;
legacy R webhook -> REQ-006; /needs android -> REQ-007).

Deliberately not built: persistence (PostgreSQL), real Redis, auth.

---

## Web Dashboard Progress (W modules)

Stack: Next.js App Router + Tailwind in `web/` (re-scaffolded with create-next-app Aug 19).
Backend URL: http://localhost:8000 (override with NEXT_PUBLIC_API_URL in web/.env.local).

- [x] W1 — Request Hub page `/requests`: table, tabs (All/Pending/Accepted/Rejected),
      Accept/Reject, source/urgency/status badges, canonical SMS preview under each ID,
      3s polling, agent activity feed panel, unreachable-backend banner — VERIFIED rendering
- [ ] W2 — New Request `/requests/new`: Need | Resource | Status selector, dropdowns mapped
      to sms.md codes, LIVE canonical SMS preview (P1 — next task)
- [ ] W3 — Plans panel `/plans`: plan list + allocations table (backend data already exists) (P2)
- [ ] W4 — SMS simulator `/sms-simulator`: payload textarea -> POST /sms/webhook -> decoded JSON (P2)
- [ ] W5 — Dashboard overview `/`, FilterBar, privacy panel `/privacy` (P3 / optional)

---

## Integration Dependencies

| Depends on | Direction | What is needed | Status |
|---|---|---|---|
| Android -> backend | POST /api/v1/needs | Must stay live for offline-to-online sync | LIVE, verified Aug 19 |
| Web hub -> backend | /api/v1/requests, accept, reject, plans, agent-activity | Request Hub endpoints | LIVE, verified Aug 19 |
| Web form -> backend | POST /api/v1/requests | Generic request creation | Endpoint ready; form pending (W2) |
| Backend -> Redis | Agent queues | Deferred; swap point = publish_to_agent_bus in main.py | Deferred |
| Web -> Android | None | Web only consumes backend | OK |

---

## Android App Progress (M modules)

- [x] M0 — App shell: Gradle, theme, navigation, screen skeletons, README, .gitignore
- [x] M1 — Architecture: Result wrapper, ApiException, ApiClient, SyncWorker stub, SyncEngine stub, ConnectivityMonitor
- [x] M2 — Auth + Organization setup: AuthRepository, mock login, OrganizationRepository, OrgProfile
- [x] M3 — Crisis: CrisisRepository, Crisis, CreateCrisal, SelectCrisis, active_crisis.json local fallback (Firebase optional for demo)
- [x] M4 — Dashboard: Dashboard, DashboardItem, stats
- [x] M5 — Requests: Request, RequestForm, RequestList, RequestDetail, RequestMapper
- [x] M6 — Offline-first: local DB, pending_operations, SyncQueue, SyncEngine, ConflictResolver, SyncRepository
- [x] M7 — SMS fallback: SmsCodes, Checksum, SmsMessageBuilder, SmsMessageParser, SmsSimulator
- [x] M8 — Map: MapMarker, OfflineMarkerStore, CrisisMap, marker sync
- [x] M9 — Field Report: FieldReportForm, image handling, offline report queue, report status
- [x] M10 — Settings: Sync Center, Diagnostics, full sync button, clear local data, README update

Android status: MVP code-complete locally. Push + verification still pending.

---

## Next Actions (ordered)

1. Web W2: `/requests/new` form + live SMS preview (immediate next)
2. Web W3: `/plans` panel (small — GET /api/v1/plans already exists)
3. Web W4: SMS simulator (unlocks demo step 8 for judges)
4. Android: push + verify M6–M10 (still pending!)
5. Android: run offline-to-online demo against live /api/v1/needs (dependency now satisfied)
6. Commit + push: backend/app/main.py, web/ (after .gitignore fix), updated docs
7. Later: Redis swap, Postgres persistence, Docker compose, Firebase, real map layer

---

## Completed Modules (Current Truth)

M0, M1, M2, M3 (demo mode), M4, M5, M6, M7, M8, M9, M10
Backend Request Hub (endpoints + validation + simulated agent bus)
Web W1 — Request Hub page

---

## Remaining Work After MVP

- Web W2–W5
- Real Redis workers replacing the in-memory simulation
- PostgreSQL persistence for requests/plans/organizations
- Android M6–M10 push + verification
- End-to-end offline-to-online verification
- Docker compose (optional)
- Firebase (optional)
- Real map layer (optional)
- Teammate API contract verification against sms.md

---

## Demo Readiness (mapped to memory_draft.md demo script)

| Demo step | Status |
|---|---|
| 2. Crisis/need input | Pending W2 form (curl works meanwhile) |
| 3–6. Live agent pipeline on Accept | READY (agent feed on /requests) |
| 4. Show allocation plans | Data ready; panel pending W3 |
| 7. Privacy | READY (auto-reject PRIVACY / BAD_CRC / DUP on accept) |
| 8. SMS fallback | Backend decodes legacy+canonical N/R/S; simulator pending W4 |
| 9. Offline map (Android) | Code complete; pending push/verify |
| 10. Dynamic replanning | Talking point only |

---

## Hard Boundaries (Do Not Cross)

Do not use Firebase Auth
Do not use Google Maps
Do not use PostgreSQL for M6 offline storage
Do not use WorkManager as the primary sync engine
Do not use DataStore as the primary offline database
Do not create production billing logic
Do not create real SMS gateway integration

---

## Known Risks / Notes

- Backend state is in-memory: restart = reset to seed (demo reset button; hackathon-acceptable)
- Android should send source="android" in /needs body for correct hub badge — verify during M10 check
- Legacy R SMS carries no location; backend defaults to RA (commented)
- web/.env.local is gitignored; default API URL (localhost:8000) works without it
- Checksums are computed dynamically — do not hardcode expected values from sms.md examples