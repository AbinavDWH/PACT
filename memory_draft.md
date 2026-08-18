# PROJECT MEMORY TRANSFER FILE

## IMPORTANT INSTRUCTION FOR NEW CHAT

You are now continuing a hackathon project discussion. Read this entire document carefully and preserve all context.

The project is for Phoenix Hacks, likely a 24-hour hackathon, focused on Track 6.

The project is a **Privacy-Preserving Multi-Agent Humanitarian Coordination Platform**.

When answering future questions, always remember:

- This is a hackathon project, so prioritize MVP, demo impact, feasibility, and clear explanation.
- The system must be privacy-preserving.
- The system uses autonomous agents for coordination.
- The web dashboard is the main command center.
- The Android app is for field workers and offline/SMS fallback.
- SMS is not just for alerts; it is used as an emergency data-transfer channel when internet fails.
- OpenStreetMap + MapLibre are used for maps, with offline caching.
- Do not overcomplicate production-level features unless asked.
- Focus on hackathon-winning implementation.
- The full SMS protocol is maintained in a separate file: `sms.md`.
- This memory file should contain high-level project memory, not the full SMS protocol specification.

---

## 0. PROJECT DOCUMENT STRUCTURE

Use the following files as reference:

| File | Purpose |
|---|---|
| `memory_draft.md` | Main project memory, architecture, decisions, demo flow, hackathon strategy |
| `sms.md` | Full SMS fallback protocol specification |

Important rule:

- For SMS message format, encoding, decoding, checksum, sequence numbers, marker messages, polygon chunks, route updates, and SMS simulator behavior, refer to `sms.md`.
- Do not duplicate the full SMS protocol inside this memory file.
- If the SMS protocol changes, update `sms.md` first.

---

## 1. PROJECT TITLE

Privacy-Preserving Multi-Agent Humanitarian Coordination Platform

---

## 2. ORIGINAL ABSTRACT

During natural disasters and geopolitical crises, humanitarian response is often hindered by fragmented information, limited resource visibility, duplicated efforts, and poor coordination among governments, NGOs, CSR organizations, and volunteer groups. Existing centralized coordination systems require organizations to share sensitive operational and resource information, which may be restricted due to privacy, logistical, or political concerns.

This project proposes a privacy-preserving multi-agent humanitarian coordination platform that enables independent organizations to collaborate without exposing their complete internal data. Autonomous agents represent each participating organization and selectively exchange essential information about available resources, urgent needs, capacity, and constraints.

A Need Assessment Agent identifies critical shortages, a Resource Matching Agent discovers suitable resources, and a Coordination and Optimization Agent dynamically allocates resources based on urgency, location, availability, and response time. When crisis conditions change, the agents automatically reassess and generate updated response plans.

The proposed system aims to reduce resource duplication, improve coverage of underserved areas, accelerate response coordination, and promote transparent cross-sector collaboration while preserving organizational data autonomy.

---

## 3. CORE PROBLEM

During disasters, multiple organizations work separately:

- Government agencies
- NGOs
- CSR teams
- Hospitals
- Volunteer groups

They face these major problems:

| Problem | Impact |
|---|---|
| Fragmented information | Organizations do not know who has what resources |
| Limited resource visibility | Some areas receive too much aid, others receive nothing |
| Duplicated efforts | Multiple groups send the same resources to the same location |
| Poor coordination | Response is slow and inefficient |
| Privacy concerns | Organizations do not want to expose sensitive internal data |
| Network failure | Internet may fail during disasters |
| Field communication issues | Field workers may not have smartphones or stable internet |

The biggest problem:

Organizations need to coordinate quickly during crises, but they cannot fully trust centralized systems with their sensitive internal data.

---

## 4. PROPOSED SOLUTION

Build a privacy-preserving multi-agent coordination platform.

Each organization is represented by its own autonomous agent.

These agents:

- Keep sensitive internal data private.
- Share only necessary information.
- Detect urgent needs.
- Match needs with available resources.
- Allocate resources based on urgency, location, availability, and response time.
- Automatically replan when crisis conditions change.
- Continue coordination through SMS fallback when internet fails.

---

## 5. MAIN GOALS

The system aims to:

- Reduce duplicated humanitarian efforts.
- Improve coverage of underserved crisis areas.
- Accelerate emergency response coordination.
- Preserve organizational data autonomy.
- Enable transparent cross-sector collaboration.
- Work even when internet connectivity is weak or unavailable.
- Provide offline map awareness for field teams.

---

## 6. PRIVACY-PRESERVING MODEL

The system does not force organizations to upload all data into one central database.

Instead:

Traditional centralized system:

```text
All organizations upload full data
        │
        ▼
Central authority sees everything
        │
        ▼
Privacy, political, and security risks
```

Our system:

```text
Each organization keeps sensitive data inside its own agent/local system
        │
        ▼
Agents share only required summaries
        │
        ▼
Coordination happens without exposing complete internal data
```

---

## 7. INTERNAL DATA THAT MUST REMAIN PRIVATE

Examples of sensitive internal data:

| Internal Data Type | Example |
|---|---|
| Full resource inventory | Exact number of all stored resources |
| Donor information | Who donated, funding sources, donation amounts |
| Staff/volunteer details | Names, locations, schedules |
| Exact warehouse locations | Precise storage facility coordinates |
| Logistics routes | Private transport plans |
| Operational plans | Internal response strategies |
| Security information | Risk zones, restricted areas |
| Political/legal constraints | Sanctions, conflict-zone restrictions |
| Beneficiary data | Personal data of affected people receiving aid |

---

## 8. DATA THAT CAN BE SELECTIVELY SHARED

Agents may share only essential coordination data:

```json
{
  "organization_id": "NGO_001",
  "resource_type": "medical_kits",
  "available_quantity": 150,
  "delivery_radius_km": 50,
  "urgency_support": true,
  "approximate_region": "District North",
  "response_time_hours": 4
}
```

They should not share:

```json
{
  "donor_name": "...",
  "exact_warehouse_location": "...",
  "staff_names": "...",
  "funding_details": "...",
  "internal_operational_plan": "..."
}
```

---

## 9. AGENT ARCHITECTURE

The platform uses multiple agents.

---

### 9.1 Organization Agent

Each organization has its own agent.

Examples:

- NGO Agent
- Government Agency Agent
- Hospital Agent
- CSR Agent
- Volunteer Group Agent

Responsibilities:

- Store organization-specific data locally.
- Share only selected information.
- Respond to resource requests.
- Update availability and response status.

---

### 9.2 Need Assessment Agent

Purpose:

- Detect critical shortages.
- Parse field reports, SMS messages, alerts, and unstructured text.
- Prioritize urgent needs.

Example input:

```text
URGENT: Flood in Region A. Around 400 families need food, water and medical kits.
```

Example output:

```json
{
  "crisis_location": "Region A",
  "affected_families": 400,
  "needed_resources": [
    {
      "resource": "food_kits",
      "estimated_quantity": 400
    },
    {
      "resource": "water_kits",
      "estimated_quantity": 400
    },
    {
      "resource": "medical_kits",
      "estimated_quantity": 200
    }
  ],
  "urgency": "critical"
}
```

---

### 9.3 Resource Matching Agent

Purpose:

- Find available resources from organization agents.
- Match needs with suitable organizations.
- Avoid duplication.
- Use only shared, non-sensitive data.

Example need:

```json
{
  "resource": "medical_kits",
  "required_quantity": 300,
  "location": "Region A"
}
```

Example available resources:

```json
[
  {
    "organization_id": "NGO_001",
    "resource": "medical_kits",
    "available_quantity": 150
  },
  {
    "organization_id": "CSR_002",
    "resource": "medical_kits",
    "available_quantity": 200
  }
]
```

Match result:

```json
{
  "need_id": "NEED_001",
  "matches": [
    {
      "organization_id": "NGO_001",
      "quantity": 150
    },
    {
      "organization_id": "CSR_002",
      "quantity": 150
    }
  ],
  "total_matched": 300
}
```

---

### 9.4 Coordination and Optimization Agent

Purpose:

- Allocate resources efficiently.
- Consider urgency, location, availability, response time, and capacity.
- Generate a coordinated response plan.

Example output:

```json
{
  "response_plan_id": "PLAN_001",
  "need_id": "NEED_001",
  "allocations": [
    {
      "organization_id": "NGO_001",
      "resource": "medical_kits",
      "quantity": 150,
      "eta_hours": 3
    },
    {
      "organization_id": "CSR_002",
      "resource": "medical_kits",
      "quantity": 150,
      "eta_hours": 5
    }
  ],
  "priority": "critical",
  "status": "ready_for_dispatch"
}
```

---

### 9.5 Dynamic Replanning Agent

Purpose:

- Monitor changing crisis conditions.
- Reassess needs and resources.
- Update response plans automatically.

Example triggers:

- Road blocked
- New urgent need detected
- Resource no longer available
- Delivery delayed
- Crisis severity increased

---

## 10. FINAL SYSTEM COMPONENTS

The final system has:

1. Web Dashboard
2. Android Mobile App
3. Backend API
4. Multi-Agent Engine
5. SMS Gateway / SMS Fallback
6. OpenStreetMap + MapLibre
7. PostgreSQL + PostGIS
8. Redis Agent Communication Bus
9. Keycloak Authentication

---

## 11. HACKATHON TECH STACK

This is the confirmed stack for Phoenix Hacks.

| Component | Technology |
|---|---|
| Website frontend | Next.js + TypeScript |
| Backend for website and app | Python FastAPI |
| Database | PostgreSQL + PostGIS |
| Authentication | Keycloak |
| Queue / Agent communication | Redis |
| Agents | Python workers |
| Android app | Kotlin |
| Maps | OpenStreetMap + MapLibre |

---

## 12. ROLE OF EACH TECHNOLOGY

### Next.js + TypeScript

Used for the web dashboard.

Features:

- Crisis overview
- Needs panel
- Resource availability panel
- Allocation plans
- Agent activity logs
- Privacy controls
- Map visualization
- SMS simulator for demo

---

### Python FastAPI

Used for backend API.

Responsibilities:

- Handle web dashboard requests
- Handle Android app requests
- Receive SMS webhook payloads
- Trigger agent workflows
- Store/retrieve data from PostgreSQL + PostGIS
- Return allocation plans and status updates

---

### PostgreSQL + PostGIS

Used for structured and spatial data.

Important because:

- Stores organizations, resources, needs, plans, and status updates.
- PostGIS enables spatial queries.
- Matching agent can find nearby resources.

Example use:

```text
Find NGOs within 50 km of Region A that have medical kits.
```

---

### Keycloak

Used for authentication and role-based access.

Roles:

- Government coordinator
- NGO admin
- CSR coordinator
- Hospital operator
- Field worker
- System admin

Hackathon note:

Keycloak can consume too much time. For MVP, it is acceptable to mock JWT authentication or use a simplified auth flow if needed.

---

### Redis

Used as the agent communication layer.

Agents can communicate through:

- Redis Streams
- Redis Pub/Sub
- Redis queues

Example flow:

```text
FastAPI receives crisis report
         │
         ▼
Push message to Redis queue
         │
         ▼
Need Assessment Agent consumes message
         │
         ▼
Push structured need to matching queue
         │
         ▼
Resource Matching Agent consumes message
         │
         ▼
Push match results to coordination queue
         │
         ▼
Coordination Agent creates response plan
```

---

### Python Workers

Used as autonomous agents.

Workers:

- Need Assessment Agent
- Resource Matching Agent
- Coordination and Optimization Agent
- Dynamic Replanning Agent
- Privacy Filter Agent

---

### Kotlin Android App

Used for field operations.

Features:

- Field reporting
- Offline mode
- Cached OpenStreetMap/MapLibre data
- SMS fallback
- Coordinate updates
- Task status confirmation
- Local queue storage

Important:

Android is the correct choice for SMS fallback because Android allows programmatic SMS sending/receiving. iOS has strong restrictions.

---

### OpenStreetMap + MapLibre

Used for maps.

- OpenStreetMap provides map data.
- MapLibre provides rendering.

Important:

- MapLibre supports vector tiles.
- Vector tiles can be cached for offline use.
- SMS cannot send map tiles.
- Map tiles must be pre-cached inside the app.
- SMS can send small coordinate updates, markers, routes, or polygon chunks.

---

## 13. WEB DASHBOARD BLUEPRINT

The web dashboard is the main coordination command center.

It is used by:

- Government coordinators
- NGO admins
- CSR coordinators
- Hospital operations teams
- Emergency control rooms

---

### Dashboard Modules

#### Crisis Overview

Shows:

- Active crisis areas
- Severity level
- Affected population
- Urgent needs

Example:

| Crisis ID | Location | Severity | Affected People | Urgent Needs |
|---|---|---|---|---|
| C-001 | Region A | Critical | 400 families | Food, water, medical kits |
| C-002 | Region B | High | 120 families | Tents, blankets |

---

#### Need Assessment Panel

Shows:

- Detected needs
- Required quantity
- Priority
- Deadline

Example:

| Need ID | Location | Resource | Required | Priority |
|---|---|---|---|---|
| N-001 | Region A | Medical kits | 300 | Critical |
| N-002 | Region A | Food kits | 400 | High |
| N-003 | Region B | Tents | 120 | Medium |

---

#### Resource Availability Panel

Shows selective resource availability from organization agents.

Example:

| Organization | Resource | Available | Delivery Radius | Status |
|---|---|---|---|---|
| NGO_001 | Medical kits | 150 | 50 km | Available |
| CSR_002 | Food kits | 600 | 80 km | Available |
| Hospital_003 | Medical teams | 5 | 30 km | Limited |

---

#### Agent Coordination Panel

Shows real-time agent activity.

Example:

```text
[10:02] Need Assessment Agent detected critical shortage in Region A.
[10:03] Resource Matching Agent found 350 medical kits available.
[10:04] Coordination Agent allocated 150 kits from NGO_001.
[10:04] Coordination Agent allocated 150 kits from CSR_002.
[10:05] Response plan PLAN_001 generated.
```

---

#### Allocation Plan Panel

Example:

| Plan ID | Need | Organization | Quantity | ETA | Status |
|---|---|---|---|---|---|
| PLAN_001 | Medical kits | NGO_001 | 150 | 3 hrs | Assigned |
| PLAN_001 | Medical kits | CSR_002 | 150 | 5 hrs | Assigned |

---

#### Map Panel

Uses OpenStreetMap + MapLibre.

Shows:

- Crisis zones
- Affected regions
- Organization locations
- Resource dispatch destinations
- Approximate delivery routes
- Underserved areas

---

#### Privacy Control Panel

Shows what is shared and what is hidden.

Example:

Shared:

```text
✔ Resource type
✔ Approximate quantity
✔ Delivery capability
✔ Approximate region
✔ Response time
```

Hidden:

```text
✘ Donor details
✘ Staff names
✘ Exact warehouse location
✘ Full inventory
✘ Funding details
✘ Internal operational plan
```

---

## 14. MOBILE APP BLUEPRINT

The mobile app is for field workers, volunteers, and response teams.

It is used when:

- Field teams need to report needs
- Internet is weak or unavailable
- Location updates are required
- Dispatch and delivery status must be confirmed
- Emergency alerts must be received

---

### App Modules

#### Field Reporting

Field workers can create a need report:

```text
Location: Region A
Resource: Food
Quantity: 300
Urgency: High
```

If internet is available:

```text
App sends report to FastAPI backend
```

If internet is unavailable:

```text
App converts report into SMS fallback payload
```

---

#### Offline Mode

The app stores:

- Cached OpenStreetMap/MapLibre tiles or vector tiles
- Crisis zone GeoJSON
- Recent needs
- Assigned tasks
- Organization data
- SMS fallback queue
- Local status updates

---

#### SMS Fallback Mode

If internet fails, the app uses SMS for critical data transfer.

Legacy demo example:

```text
N|NGO01|RegionA|food|300|H
```

Canonical example:

```text
N|001|NGO01|RA|F|300|H|B3
```

The full SMS format, field rules, checksum rules, and decoder behavior are defined in:

```text
sms.md
```

---

#### Offline Map Updates via SMS

SMS can send compact coordinate updates.

Legacy demo example:

```text
M|RA|CRISIS|23.2599,77.4126|SEV9,F300|a1b2
```

Canonical example:

```text
M|001|23.2599,77.4126|CR|9|F300|B4
```

The app parses this and adds a marker to the cached offline map.

Full marker message rules are defined in:

```text
sms.md
```

---

#### Task Status Updates

Field teams can confirm:

```text
DISPATCHED
IN_TRANSIT
DELIVERED
BLOCKED
```

Legacy SMS example:

```text
DELIVERED RegionA medical 150
```

Canonical SMS example:

```text
S|004|PLAN101|3|A1
```

Full status message rules are defined in:

```text
sms.md
```

---

## 15. SMS FALLBACK AS DATA TRANSFER

Important decision:

SMS is not only for alerts. It is used as an emergency data-transfer channel for the application when internet fails.

The full SMS encode/decode protocol is maintained in a separate file:

```text
sms.md
```

This memory file should only describe the role of SMS at a high level. The complete SMS message specification, encoding rules, decoding rules, checksum rules, sequence rules, and examples should be kept in `sms.md`.

SMS can transfer:

- Need requests
- Resource availability
- Confirmation messages
- Task status
- Small coordinates
- Allocation IDs
- Priority levels
- Short encoded payloads
- Marker updates
- Polygon chunks
- Route waypoints
- Error reports

SMS cannot transfer:

- Full database
- Images
- Videos
- Map tiles
- Large inventory
- Real-time tracking streams
- Sensitive personal data

---

## 16. SMS PROTOCOL DESIGN

The detailed SMS protocol has been moved to:

```text
sms.md
```

High-level SMS design:

- Use short pipe-delimited messages.
- Use compact codes for needs, resources, status, markers, polygons, and routes.
- Use SMS only for small emergency payloads.
- Use checksum and sequence numbers in canonical mode.
- Support legacy demo payloads for presentation compatibility.
- Convert SMS into structured JSON before pushing to Redis.
- Do not include sensitive or private data in SMS.

Example legacy need message:

```text
N|NGO01|RegionA|food|300|H
```

Example canonical need message:

```text
N|001|NGO01|RA|F|300|H|B3
```

Example legacy marker message:

```text
M|RA|CRISIS|23.2599,77.4126|SEV9,F300|a1b2
```

Example canonical marker message:

```text
M|001|23.2599,77.4126|CR|9|F300|B4
```

Example canonical status message:

```text
S|004|PLAN101|3|A1
```

For all message types, field definitions, checksum rules, duplicate handling, and decoder validation rules, refer to:

```text
sms.md
```

---

## 17. COORDINATE ENCODING FOR SMS

Coordinate encoding rules are maintained in:

```text
sms.md
```

High-level recommendation for hackathon MVP:

- Use location codes when available.
- Use rounded 4-decimal coordinates when coordinates are required.
- Use geohash only if approximate location is acceptable.
- Do not use hex coordinates by default.

Example location code:

```text
RA
```

Example decimal coordinate:

```text
23.2599,77.4126
```

Example marker message:

```text
M|001|23.2599,77.4126|CR|9|F300|B4
```

Coordinate priority order:

```text
Location code first
Decimal coordinates second
Geohash optional
Hex not default
```

For full coordinate encoding policy, including optional hex coordinate format, refer to:

```text
sms.md
```

---

## 18. OPENSTREETMAP + MAPLIBRE STRATEGY

Important rule:

SMS cannot send OpenStreetMap tiles. Map tiles or vector tiles must be pre-cached inside the app.

---

### Normal Internet Mode

```text
App/Web downloads OSM/MapLibre tiles
        │
        ▼
Displays crisis zones, markers, routes
        │
        ▼
Receives real-time updates from backend
```

---

### Offline Mode

```text
App uses cached map tiles/vector tiles
        │
        ▼
Shows stored crisis zones and markers
        │
        ▼
Receives small coordinate updates via SMS
        │
        ▼
Parses SMS and updates local map layer
```

---

### What SMS Can Update on Offline Map

SMS can send:

- Single point coordinates
- Marker type
- Severity
- Small status codes
- Simplified polygon chunks
- Route waypoints

SMS cannot send:

- Map tiles
- Large GeoJSON files
- High-resolution imagery
- Full map packages

---

## 19. FINAL SYSTEM ARCHITECTURE

```text
┌──────────────────────────────────────────────────────────────┐
│                         USERS                                │
│                                                              │
│ Government / NGOs / CSR / Hospitals / Volunteers / Field Team│
└──────────────┬───────────────────────────────┬───────────────┘
               │                               │
               ▼                               ▼
┌──────────────────────────────┐   ┌──────────────────────────────┐
│        WEB DASHBOARD         │   │        ANDROID APP           │
│                              │   │                              │
│ - Crisis overview            │   │ - Field reporting            │
│ - Need list                  │   │ - Offline mode               │
│ - Resource visibility        │   │ - SMS fallback               │
│ - Allocation plans           │   │ - Cached MapLibre map        │
│ - Agent activity logs        │   │ - Location updates           │
│ - Privacy controls           │   │ - Status confirmation        │
│ - OpenStreetMap dashboard    │   │ - Emergency alerts           │
└──────────────┬───────────────┘   └──────────────┬───────────────┘
               │                                  │
               │ Internet Available               │ Internet Available
               │                                  │
               ▼                                  ▼
┌──────────────────────────────────────────────────────────────┐
│                    FastAPI Backend Server                    │
│                                                              │
│ - Authentication                                             │
│ - Data sync                                                  │
│ - Agent communication                                        │
│ - SMS gateway handler                                        │
│ - Privacy filter                                             │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                     Redis Agent Bus                          │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                  Multi-Agent Coordination Engine             │
│                                                              │
│ Need Assessment Agent                                        │
│ Resource Matching Agent                                      │
│ Coordination and Optimization Agent                          │
│ Dynamic Replanning Agent                                     │
│ Privacy Filter Agent                                         │
└──────────────┬───────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│                    Organization Agents                       │
│                                                              │
│ NGO Agent | Government Agent | Hospital Agent | CSR Agent    │
│ Volunteer Agent | Logistics Agent                            │
└──────────────────────────────────────────────────────────────┘
               │
               │ Internet Down
               ▼
┌──────────────────────────────────────────────────────────────┐
│                       SMS Gateway                            │
│                                                              │
│ - Field need reporting                                       │
│ - Resource confirmation                                      │
│ - Assignment alerts                                          │
│ - Dispatch/delivery status                                   │
│ - Compact coordinate updates                                 │
└──────────────────────────────────────────────────────────────┘
```

---

## 20. DATA FLOW: NORMAL INTERNET MODE

```text
Field App or Web Dashboard reports need
         │
         ▼
FastAPI receives request
         │
         ▼
Message pushed to Redis queue
         │
         ▼
Need Assessment Agent processes need
         │
         ▼
Resource Matching Agent finds resources using PostGIS
         │
         ▼
Coordination Agent creates allocation plan
         │
         ▼
PostgreSQL stores plan
         │
         ▼
Web Dashboard displays plan
         │
         ▼
Assigned organization receives task in app
```

---

## 21. DATA FLOW: INTERNET FAILURE MODE

```text
Field App loses internet
         │
         ▼
App switches to SMS fallback mode
         │
         ▼
App converts request into compact SMS payload
         │
         ▼
SMS sent to coordination gateway number
         │
         ▼
FastAPI backend receives SMS webhook
         │
         ▼
SMS parser converts payload into structured JSON
         │
         ▼
Message pushed to Redis queue
         │
         ▼
Agents process need and generate response plan
         │
         ▼
Backend sends SMS response to app/organization
         │
         ▼
App parses SMS and updates offline UI/map
         │
         ▼
When internet returns, app syncs local queue with backend
```

Full SMS parsing and encoding rules are defined in:

```text
sms.md
```

---

## 22. EXAMPLE SMS DATA FLOW

The full canonical SMS protocol is defined in:

```text
sms.md
```

The following is a high-level demo flow.

---

### Step 1: Field Worker Reports Need

App form:

```text
Location: Region A
Resource: Food
Quantity: 300
Urgency: High
```

Legacy SMS payload:

```text
N|NGO01|RegionA|food|300|H
```

Canonical SMS payload:

```text
N|001|NGO01|RA|F|300|H|B3
```

---

### Step 2: Backend Parses SMS

Example decoded JSON:

```json
{
  "type": "need",
  "seq": "001",
  "organization_id": "NGO01",
  "location_code": "RA",
  "location_name": "Region A",
  "resource": "food_kits",
  "quantity": 300,
  "urgency": "high",
  "checksum": "B3",
  "source": "sms"
}
```

---

### Step 3: Need Assessment Agent Prioritizes

```json
{
  "need_id": "NEED_101",
  "location": "Region A",
  "resource": "food_kits",
  "required_quantity": 300,
  "priority": "high"
}
```

---

### Step 4: Resource Matching Agent Finds Resources

```json
{
  "need_id": "NEED_101",
  "matches": [
    {
      "organization_id": "CSR02",
      "resource": "food_kits",
      "available_quantity": 200
    },
    {
      "organization_id": "GOV03",
      "resource": "food_kits",
      "available_quantity": 100
    }
  ]
}
```

---

### Step 5: Coordination Agent Creates Plan

```json
{
  "plan_id": "PLAN_101",
  "allocations": [
    {
      "organization_id": "CSR02",
      "resource": "food_kits",
      "quantity": 200,
      "eta_hours": 4
    },
    {
      "organization_id": "GOV03",
      "resource": "food_kits",
      "quantity": 100,
      "eta_hours": 6
    }
  ]
}
```

---

### Step 6: SMS Response Sent Back

Legacy allocation response:

```text
PLAN101|CSR02|food|200|RegionA|ETA4
PLAN101|GOV03|food|100|RegionA|ETA6
```

Canonical allocation response:

```text
A|002|PLAN101|CSR02|F|200|RA|4|D2
A|003|PLAN101|GOV03|F|100|RA|6|E7
```

For canonical allocation message structure, refer to `sms.md`.

---

## 23. PRIVACY FILTER AGENT

The Privacy Filter Agent ensures sensitive data is not exposed.

Before sharing data to web dashboard, other agents, or SMS:

- Remove donor details
- Remove staff names
- Remove exact warehouse locations if sensitive
- Remove funding details
- Remove internal operational plans
- Round coordinates if needed
- Use organization IDs instead of full identity where possible
- Add signature/checksum for message integrity

For SMS privacy rules, refer to:

```text
sms.md
```

---

## 24. ADVANTAGES AND DISADVANTAGES

### Web Dashboard

Advantages:

| Advantage | Explanation |
|---|---|
| Easy to deploy | No installation required |
| Works on many devices | Laptop, desktop, tablet |
| Best for monitoring | Large dashboard view |
| Faster hackathon development | Easier than full native app |
| Good visualization | Maps, tables, charts, logs |

Disadvantages:

| Disadvantage | Explanation |
|---|---|
| Needs internet | Limited without connectivity |
| Not ideal for field workers | Field teams need mobile |
| Weaker offline support | Not as strong as native Android app |

---

### Android App

Advantages:

| Advantage | Explanation |
|---|---|
| Best for field reporting | Quick reporting by field workers |
| Offline support | Can cache maps and data |
| SMS fallback | Works during internet failure |
| GPS/location support | Can capture coordinates |
| Native SMS access | Android allows SMS sending/receiving |

Disadvantages:

| Disadvantage | Explanation |
|---|---|
| Harder to build | Takes more time than web |
| Installation required | Users must install app |
| Storage usage | Offline maps need device storage |
| Android permissions | SMS/location permissions must be handled |

---

### SMS Fallback

Advantages:

| Advantage | Explanation |
|---|---|
| Works without internet | Useful in disaster zones |
| Works on basic networks | SMS often survives when data fails |
| Low bandwidth | Small messages only |
| Good for emergency data | Needs, status, coordinates |

Disadvantages:

| Disadvantage | Explanation |
|---|---|
| 160-character limit | Must compress data |
| Slow delivery | SMS may be delayed |
| Not secure by default | Needs encoding/signature |
| Cannot send large data | No maps, images, or full sync |

---

### OpenStreetMap + MapLibre

Advantages:

| Advantage | Explanation |
|---|---|
| Free and open | No expensive licensing |
| Offline possible | Vector tiles can be cached |
| Customizable | Markers, zones, routes |
| Good crisis visualization | Helps coordinators understand areas |

Disadvantages:

| Disadvantage | Explanation |
|---|---|
| Tiles cannot be sent via SMS | Must be pre-cached |
| Offline storage needed | Requires device memory |
| Map data may be incomplete | Some regions may lack detail |

---

### Multi-Agent Architecture

Advantages:

| Advantage | Explanation |
|---|---|
| Preserves privacy | Sensitive data stays local |
| Scalable | More organizations can join |
| Flexible | Each agent follows its own constraints |
| Faster coordination | Automated matching/allocation |
| Dynamic replanning | Adapts to crisis changes |

Disadvantages:

| Disadvantage | Explanation |
|---|---|
| More complex | Harder than simple CRUD app |
| Debugging harder | Multiple agents and queues |
| Needs message standards | Agents must follow common format |
| Hackathon time pressure | Must simplify for MVP |

---

## 25. HACKATHON MVP SCOPE

For a 24-hour hackathon, build only these core features.

### Must Build

1. Next.js web dashboard
2. Crisis overview panel
3. Need input panel
4. Resource availability panel
5. Agent matching/allocation logic
6. Privacy shared/hidden panel
7. OpenStreetMap/MapLibre view
8. SMS simulator panel
9. FastAPI backend
10. Redis-based agent flow
11. PostGIS basic spatial query
12. Android app demo screen with offline map concept

---

### Do Not Overbuild

Avoid spending too much time on:

- Full production Keycloak setup
- Real telecom SMS integration
- Full native Android production app
- Advanced cryptographic privacy
- Complex routing engine
- Full authentication RBAC
- Perfect UI/UX
- Large database seeding
- Real-time production deployment

---

## 26. HACKATHON PRIORITY ORDER

### Priority 1: Core Demo

```text
Crisis report enters system
        │
        ▼
Need Assessment Agent parses it
        │
        ▼
Resource Matching Agent finds resources
        │
        ▼
Coordination Agent creates allocation plan
        │
        ▼
Dashboard displays result
```

This must work first.

---

### Priority 2: Privacy Demo

```text
Show shared data vs hidden data
```

This is the main innovation from the abstract.

---

### Priority 3: SMS Fallback Demo

```text
Show offline/SMS mode
        │
        ▼
SMS payload is parsed
        │
        ▼
Agent updates response plan
```

This is a strong wow factor.

Full SMS payload format is defined in:

```text
sms.md
```

---

### Priority 4: Offline Map Demo

```text
Show cached map
        │
        ▼
SMS coordinate update adds marker
```

This is optional but impressive.

---

## 27. WHAT TO FAKE OR MOCK FOR HACKATHON

To save time, these can be simulated:

| Feature | How to Mock |
|---|---|
| Real SMS gateway | Use SMS simulator panel in web dashboard |
| Real Android SMS listener | Use demo input box that simulates received SMS |
| Complex optimization | Use simple Python rules or PostGIS nearest query |
| Full Keycloak auth | Use hardcoded JWT/mock user roles initially |
| Full offline map download | Use one pre-cached region only |
| Multiple organizations | Use 3 fake organizations |
| Agent distribution | Run all Python agents as workers on one backend |

---

## 28. RECOMMENDED 24-HOUR PLAN

### Hours 1-4: Setup

- Create repository.
- Set up Next.js frontend.
- Set up FastAPI backend.
- Set up PostgreSQL + PostGIS.
- Set up Redis.
- Create dummy organizations and resources.

---

### Hours 5-10: Backend Agent Logic

- Create Need Assessment Agent.
- Create Resource Matching Agent.
- Create Coordination Agent.
- Connect agents with Redis queues.
- Store plans in PostgreSQL.

---

### Hours 11-17: Web Dashboard

- Build crisis overview.
- Build need panel.
- Build resource panel.
- Build allocation panel.
- Build agent activity feed.
- Build privacy shared/hidden panel.
- Add MapLibre/OpenStreetMap view.

---

### Hours 18-21: SMS + Android Demo

- Implement SMS payload encoder/decoder according to `sms.md`.
- Build SMS simulator in web dashboard.
- Prepare Android app demo screen.
- Show offline map marker update via SMS payload.

---

### Hours 22-24: Demo and Pitch

- Test full flow.
- Record backup demo video.
- Prepare pitch.
- Practice judge Q&A.
- Stop coding before presentation.

---

## 29. DEMO SCRIPT

### Step 1: Show the Problem

Say:

```text
During disasters, organizations do not have clear visibility of resources. They also cannot share all internal data because of privacy, security, and political concerns.
```

---

### Step 2: Show Crisis Input

Enter crisis report:

```text
URGENT: Flood in Region A. Around 400 families need food, water and medical kits.
```

---

### Step 3: Need Assessment Agent

Dashboard displays:

```text
Need Assessment Agent detected:
- Food kits: 400 required
- Water kits: 400 required
- Medical kits: 200 required
```

---

### Step 4: Organization Agents

Dashboard displays:

```text
NGO_001: 150 medical kits available
CSR_002: 200 medical kits available
Hospital_003: 5 medical teams available
```

---

### Step 5: Resource Matching Agent

Dashboard displays:

```text
Resource Matching Agent matched:
Need: 300 medical kits
Available: NGO_001 + CSR_002
```

---

### Step 6: Coordination Agent

Dashboard displays:

```text
Coordination Agent assigned:
NGO_001: 150 medical kits
CSR_002: 150 medical kits
Priority: Critical
```

---

### Step 7: Privacy Panel

Say:

```text
The system coordinates resources without revealing donor details, staff information, exact warehouse locations, or full internal inventory.
```

---

### Step 8: SMS Fallback

Switch to offline mode.

Say:

```text
Now the internet is down. The field app switches to SMS fallback.
```

Send legacy SMS payload:

```text
N|NGO01|RegionA|food|300|H
```

Or canonical SMS payload:

```text
N|001|NGO01|RA|F|300|H|B3
```

Backend parses it and updates plan.

For full SMS format, refer to:

```text
sms.md
```

---

### Step 9: Offline Map Update

Send legacy SMS coordinate payload:

```text
M|RA|CRISIS|23.2599,77.4126|SEV9,F300|a1b2
```

Or canonical SMS coordinate payload:

```text
M|001|23.2599,77.4126|CR|9|F300|B4
```

Android app/demo adds marker to cached MapLibre map.

Say:

```text
Even without internet, the app receives critical coordinate updates via SMS and displays them on the offline map.
```

---

### Step 10: Dynamic Replanning

Add new update:

```text
Region B now urgently needs tents.
```

System updates priority.

Say:

```text
When crisis conditions change, agents automatically reassess and generate updated response plans.
```

---

## 30. PITCH SUMMARY

Use this pitch:

```text
Our platform is a privacy-preserving multi-agent humanitarian coordination system. During disasters, governments, NGOs, CSR teams, and hospitals often cannot coordinate effectively because information is fragmented and organizations do not want to expose sensitive internal data.

Our solution uses autonomous agents. Each organization has its own agent that keeps sensitive data private but shares only the minimum necessary information. The Need Assessment Agent identifies urgent shortages, the Resource Matching Agent finds suitable resources using PostGIS spatial queries, and the Coordination Agent creates optimized allocation plans.

The web dashboard acts as the command center, while the Android app supports field workers. If internet connectivity fails, the app switches to SMS fallback mode and transfers compact encoded data packets. OpenStreetMap and MapLibre provide offline-aware crisis visualization.

This reduces duplication, improves coverage of underserved areas, accelerates response coordination, and enables transparent collaboration while preserving organizational data autonomy.
```

---

## 31. JUDGE QUESTIONS AND ANSWERS

### Question 1: Why not use a centralized database?

Answer:

Centralized systems require organizations to expose complete internal data. Our multi-agent model allows coordination while preserving privacy. Organizations share only essential information.

---

### Question 2: How is privacy preserved?

Answer:

Each organization agent keeps sensitive data local. Only selective summaries are shared, such as resource type, approximate quantity, delivery capability, and response time. Donor details, staff data, funding details, and exact warehouse locations remain hidden.

---

### Question 3: Why SMS?

Answer:

During disasters, internet and data networks may fail. SMS can still work. We use SMS as a fallback data channel for small critical messages like needs, confirmations, status updates, and coordinate updates.

The full SMS protocol is defined in:

```text
sms.md
```

---

### Question 4: Can SMS transfer the whole app data?

Answer:

No. SMS is only for small emergency payloads. It cannot transfer full databases, images, or map tiles. When internet returns, the app syncs offline data with the backend.

---

### Question 5: How do offline maps work?

Answer:

Map tiles or vector tiles are pre-cached inside the app. SMS sends only small coordinate or marker updates. The app parses the SMS and updates the cached MapLibre/OpenStreetMap view.

---

### Question 6: Why Android/Kotlin?

Answer:

Android allows programmatic SMS sending and receiving, which is required for SMS fallback. iOS has strong restrictions on SMS access.

---

### Question 7: Why PostGIS?

Answer:

PostGIS allows spatial queries such as finding available resources near a crisis zone. This helps the Resource Matching Agent make location-aware decisions.

---

### Question 8: Why Redis?

Answer:

Redis acts as the agent communication bus. Agents can asynchronously publish and consume messages, making the system scalable and responsive.

---

### Question 9: Is this production-ready?

Answer:

The hackathon MVP demonstrates the architecture and core coordination flow. For production, we would add real SMS gateway integration, hardened authentication with Keycloak, encryption, audit logs, advanced routing, and field-tested offline synchronization.

---

### Question 10: What is the main innovation?

Answer:

The main innovation is privacy-preserving coordination. Organizations can collaborate during crises without exposing sensitive internal data, and the system remains resilient through SMS fallback and offline map support.

---

## 32. IMPORTANT DECISIONS ALREADY MADE

These decisions should be remembered:

- The main platform is a web dashboard, not only a mobile app.
- The mobile app is Android/Kotlin, mainly for field workers.
- SMS fallback is used as data transfer, not only notifications.
- SMS cannot transfer map tiles.
- Offline maps must be pre-cached.
- SMS can transfer compact coordinates and marker updates.
- MapLibre is preferred for map rendering.
- PostGIS is used for spatial matching.
- Redis is used for agent communication.
- Python workers are used as agents.
- Keycloak is included but may be mocked/simplified during hackathon if time is short.
- The biggest innovation is privacy-preserving multi-agent coordination.
- The biggest wow factor is SMS fallback during internet failure.
- The hackathon MVP should prioritize demo flow over production perfection.
- The full SMS protocol is maintained in a separate file: `sms.md`.
- This memory file should contain only high-level project memory and should not store the full SMS protocol.
- If SMS protocol details are required, always refer to `sms.md`.

---

## 33. POSSIBLE NEXT DEVELOPMENT TASKS

If continuing development, work in this order.

---

### Task 1: Database Schema

Create PostgreSQL + PostGIS tables:

- organizations
- organization_agents
- resources
- resource_availability
- crises
- needs
- need_items
- matches
- response_plans
- allocations
- status_updates
- sms_messages
- audit_logs
- privacy_rules

---

### Task 2: FastAPI Backend

Create endpoints:

```text
POST /api/crises
POST /api/needs
GET  /api/resources
POST /api/match
POST /api/allocate
POST /api/sms/webhook
GET  /api/plans
POST /api/status
GET  /api/agent-activity
```

---

### Task 3: Redis Agent Queues

Queues:

```text
crisis_reports
need_assessment_queue
resource_matching_queue
coordination_queue
replanning_queue
sms_incoming_queue
sms_outgoing_queue
```

---

### Task 4: Python Agents

Create workers:

```text
need_assessment_worker.py
resource_matching_worker.py
coordination_worker.py
replanning_worker.py
privacy_filter_worker.py
sms_parser_worker.py
```

The SMS parser worker should follow the protocol defined in:

```text
sms.md
```

---

### Task 5: Next.js Dashboard

Pages:

```text
Dashboard
Crises
Needs
Resources
Plans
Agents
Map
Privacy
SMS Simulator
```

---

### Task 6: Android App

Screens:

```text
Login / Organization selection
Field report form
Offline map
Task assignment
Status update
SMS fallback mode
Sync queue
```

---

## 34. FINAL ONE-LINE PROJECT SUMMARY

A privacy-preserving multi-agent humanitarian coordination platform where autonomous agents coordinate resources across governments, NGOs, CSR teams, and hospitals without exposing sensitive internal data, using a web dashboard, Android field app, SMS fallback, PostGIS spatial matching, and offline OpenStreetMap/MapLibre visualization.

---

## END OF MEMORY FILE