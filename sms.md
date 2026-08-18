# SMS_PROTOCOL.md

This document defines the SMS fallback protocol for the Privacy-Preserving Multi-Agent Humanitarian Coordination Platform.

SMS is used as an emergency data-transfer channel when internet connectivity is unavailable or unstable.

---

## 1. Purpose

The SMS protocol allows field workers, organizations, and coordination systems to exchange small emergency messages.

SMS is used for:

- Need requests
- Resource availability
- Allocation updates
- Status updates
- Confirmations
- Dispatch updates
- Delivery confirmations
- Cancellations
- Map marker updates
- Polygon chunks
- Route updates
- Error reporting

SMS is not used for:

- Full database synchronization
- Images
- Videos
- Map tiles
- Large inventory transfers
- Real-time tracking streams
- Sensitive personal data

---

## 2. Core Design Rules

1. Use plain ASCII text only.
2. Use `|` as the main field delimiter.
3. Keep messages under 160 characters where possible.
4. Use short codes instead of long words.
5. Use predefined location codes whenever possible.
6. Use coordinates only when a location code is unavailable.
7. Include a checksum for integrity checking.
8. Include a sequence number for duplicate detection.
9. Do not include sensitive or private data.
10. Convert SMS messages into structured JSON before pushing to Redis.

---

## 3. Protocol Modes

The system supports two modes:

### 3.1 Legacy Demo Mode

Legacy demo mode is simple and readable. It is useful for quick demonstration.

Example:

```text
N|NGO01|RegionA|food|300|H
```

Legacy messages may omit:

- Sequence number
- Checksum
- Compact resource codes
- Location codes

The backend should accept legacy messages for demo compatibility when possible.

### 3.2 Canonical Protocol Mode

Canonical mode is recommended for implementation.

Example:

```text
N|001|NGO01|RA|F|300|H|B3
```

Canonical messages include:

- Message type
- Sequence number
- Organization ID
- Short location code
- Short resource code
- Quantity
- Urgency/status code
- Checksum

---

## 4. Canonical Message Format

Most canonical messages use this structure:

```text
TYPE|SEQ|ORG|BODY|CRC
```

Fields:

| Field | Meaning |
|---|---|
| TYPE | Message type code |
| SEQ | Sequence number |
| ORG | Organization ID |
| BODY | Message-specific fields |
| CRC | Checksum |

Some message types expand the body into fixed fields.

---

## 5. Message Types

| Code | Meaning |
|---|---|
| N | Need request |
| R | Resource availability |
| A | Allocation / plan assignment |
| S | Status update |
| C | Confirmation |
| D | Dispatch |
| V | Delivered |
| X | Cancel |
| M | Map marker |
| P | Polygon chunk |
| ROUTE | Route update |
| RT | Compact route update alias |
| E | Error |

For MVP, prefer:

```text
N, R, A, S, M, P, RT, C, E
```

Legacy shortcuts `D` and `V` may be supported for demo compatibility.

---

## 6. Resource Codes

Use short resource codes.

| Code | Resource |
|---|---|
| F | Food kits |
| W | Water kits |
| M | Medical kits |
| T | Tents |
| B | Blankets |
| H | Hygiene kits |
| D | Medical teams |
| U | Unknown |

Examples:

```text
F = Food kits
M = Medical kits
T = Tents
```

The decoder should also accept common full words for demo compatibility:

```text
food = F
water = W
medical = M
medicine = M
tents = T
tent = T
blankets = B
blanket = B
```

---

## 7. Urgency Codes

| Code | Meaning |
|---|---|
| L | Low |
| M | Medium |
| H | High |
| C | Critical |

Example:

```text
H = High urgency
C = Critical urgency
```

---

## 8. Status Codes

| Code | Meaning |
|---|---|
| 0 | Assigned |
| 1 | Dispatched |
| 2 | In transit |
| 3 | Delivered |
| 4 | Blocked |
| 5 | Cancelled |

Example:

```text
S|004|PLAN101|3|A1
```

Meaning:

```text
Plan PLAN101 is delivered.
```

---

## 9. Resource Availability Status Codes

| Code | Meaning |
|---|---|
| A | Available |
| L | Limited |
| U | Unavailable |

Example:

```text
R|002|CSR02|RA|F|200|A|7C
```

Meaning:

```text
CSR02 has 200 food kits available in Region A.
```

---

## 10. Location Handling

Preferred location format is a predefined location code.

Example location code table:

| Code | Actual Location |
|---|---|
| RA | Region A |
| RB | Region B |
| RC | Region C |
| D1 | District North |
| D2 | District South |

Example:

```text
RA
```

If no location code exists, use decimal coordinates:

```text
23.2599,77.4126
```

Coordinate rules:

- Latitude first, longitude second.
- Use maximum 4 decimal places.
- No spaces.
- Use `-` for negative coordinates.

Example:

```text
23.2599,77.4126
```

For approximate locations, geohash may be used with prefix `GEO:`.

Example:

```text
GEO:te7u2f
```

---

## 11. Need Request

### Legacy Format

```text
N|NGO01|RegionA|food|300|H
```

Meaning:

```text
Need
Organization: NGO01
Location: RegionA
Resource: food
Quantity: 300
Urgency: High
```

### Canonical Format

```text
N|SEQ|ORG|LOC|RESOURCE|QTY|URGENCY|CRC
```

Example:

```text
N|001|NGO01|RA|F|300|H|B3
```

Meaning:

```text
Need request
Sequence: 001
Organization: NGO01
Location: Region A
Resource: Food kits
Quantity: 300
Urgency: High
Checksum: B3
```

Decoded JSON:

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

## 12. Resource Availability

### Legacy Format

```text
R|CSR02|food|200|A
```

Meaning:

```text
Resource update
Organization: CSR02
Resource: food
Quantity: 200
Status: Available
```

### Canonical Format

```text
R|SEQ|ORG|LOC|RESOURCE|QTY|STATUS|CRC
```

Example:

```text
R|002|CSR02|RA|F|200|A|7C
```

Meaning:

```text
Resource availability
Sequence: 002
Organization: CSR02
Location: Region A
Resource: Food kits
Quantity: 200
Status: Available
Checksum: 7C
```

Decoded JSON:

```json
{
  "type": "resource",
  "seq": "002",
  "organization_id": "CSR02",
  "location_code": "RA",
  "location_name": "Region A",
  "resource": "food_kits",
  "quantity": 200,
  "status": "available",
  "checksum": "7C",
  "source": "sms"
}
```

---

## 13. Allocation / Plan Assignment

### Legacy Format

```text
PLAN001|CSR02|food|200|RegionA|ETA4
```

Meaning:

```text
Plan ID: PLAN001
Assigned organization: CSR02
Resource: food
Quantity: 200
Destination: RegionA
ETA: 4 hours
```

### Canonical Format

```text
A|SEQ|PLAN|ORG|RESOURCE|QTY|LOC|ETA|CRC
```

Example:

```text
A|003|PLAN001|CSR02|F|200|RA|4|D2
```

Meaning:

```text
Allocation message
Sequence: 003
Plan ID: PLAN001
Assigned organization: CSR02
Resource: Food kits
Quantity: 200
Destination: Region A
ETA: 4 hours
Checksum: D2
```

Decoded JSON:

```json
{
  "type": "allocation",
  "seq": "003",
  "plan_id": "PLAN001",
  "organization_id": "CSR02",
  "resource": "food_kits",
  "quantity": 200,
  "destination_code": "RA",
  "destination_name": "Region A",
  "eta_hours": 4,
  "checksum": "D2",
  "source": "sms"
}
```

---

## 14. Status Update

### Canonical Format

```text
S|SEQ|PLAN|STATUS|CRC
```

Example:

```text
S|004|PLAN101|3|A1
```

Meaning:

```text
Status update
Sequence: 004
Plan ID: PLAN101
Status: Delivered
Checksum: A1
```

Decoded JSON:

```json
{
  "type": "status",
  "seq": "004",
  "plan_id": "PLAN101",
  "status": "delivered",
  "checksum": "A1",
  "source": "sms"
}
```

Status examples:

```text
S|005|PLAN101|1|B2
S|006|PLAN101|2|C3
S|007|PLAN101|3|D4
S|008|PLAN101|4|E5
```

Meaning:

```text
Dispatched
In transit
Delivered
Blocked
```

---

## 15. Legacy Delivery Confirmation

Legacy free-text format:

```text
DELIVERED RegionA food 200
```

Meaning:

```text
Delivery confirmation
Location: Region A
Resource: food
Quantity: 200
```

Canonical replacement:

```text
S|009|PLAN101|3|A1
```

If plan ID is unknown, use:

```text
S|009|RA|F|200|3|A1
```

Decoder output:

```json
{
  "type": "status",
  "seq": "009",
  "location_code": "RA",
  "location_name": "Region A",
  "resource": "food_kits",
  "quantity": 200,
  "status": "delivered",
  "checksum": "A1",
  "source": "sms"
}
```

---

## 16. Confirmation

Format:

```text
C|SEQ|REF|RESULT|CRC
```

Example:

```text
C|010|PLAN101|OK|F1
```

Meaning:

```text
Confirmation
Sequence: 010
Reference: PLAN101
Result: OK
Checksum: F1
```

Result codes:

| Code | Meaning |
|---|---|
| OK | Accepted |
| ERR | Rejected |
| DUP | Duplicate ignored |

Decoded JSON:

```json
{
  "type": "confirmation",
  "seq": "010",
  "reference": "PLAN101",
  "result": "ok",
  "checksum": "F1",
  "source": "sms"
}
```

---

## 17. Cancel

Format:

```text
X|SEQ|REF|REASON|CRC
```

Example:

```text
X|011|PLAN101|BLK|A2
```

Meaning:

```text
Cancel message
Sequence: 011
Reference: PLAN101
Reason: Blocked
Checksum: A2
```

Common reason codes:

| Code | Meaning |
|---|---|
| BLK | Blocked |
| NOSTK | No stock |
| RISK | Security risk |
| ROAD | Road issue |
| OTHER | Other |

Decoded JSON:

```json
{
  "type": "cancel",
  "seq": "011",
  "reference": "PLAN101",
  "reason": "blocked",
  "checksum": "A2",
  "source": "sms"
}
```

---

## 18. Map Marker Update

### Legacy Format

```text
M|RA|CRISIS|23.2599,77.4126|SEV9,F300|a1b2
```

Meaning:

```text
Marker message
Region: RA
Type: CRISIS
Coordinates: 23.2599,77.4126
Severity: 9
Need: 300 food kits
Checksum/signature: a1b2
```

### Canonical Format

```text
M|SEQ|LOC|MARKER_TYPE|SEVERITY|DATA|CRC
```

Example using location code:

```text
M|012|RA|CR|9|F300|A1
```

Example using coordinates:

```text
M|013|23.2599,77.4126|CR|9|F300|B4
```

Decoded JSON:

```json
{
  "type": "marker",
  "seq": "013",
  "latitude": 23.2599,
  "longitude": 77.4126,
  "marker_type": "crisis",
  "severity": 9,
  "data": {
    "resource": "food_kits",
    "quantity": 300
  },
  "checksum": "B4",
  "source": "sms"
}
```

---

## 19. Marker Type Codes

| Code | Meaning |
|---|---|
| CR | Crisis zone |
| ND | Need reported |
| RS | Resource point |
| DL | Delivery location |
| BL | Blocked route |
| SH | Shelter |
| MD | Medical point |

Example:

```text
CR = Crisis zone
ND = Need reported
RS = Resource point
```

---

## 20. Marker Data Field

The marker `DATA` field should remain compact.

Examples:

```text
F300
W150
M200
T120
```

Meaning:

```text
F300 = 300 food kits
W150 = 150 water kits
M200 = 200 medical kits
T120 = 120 tents
```

Multiple data items can be separated by `;`.

Example:

```text
F300;W150
```

Full marker example:

```text
M|014|RA|CR|9|F300;W150|C2
```

---

## 21. Polygon Chunk Messages

Use polygon chunks to transmit small crisis zone boundaries.

### Legacy Format

```text
P1/2|RA|FLOOD|23.250,77.400|23.270,77.420|23.260,77.440|e5f6
P2/2|RA|FLOOD|23.240,77.430|END|e7f8
```

### Canonical Format

```text
P|CHUNK/TOTAL|SEQ|LOC|ZONE_TYPE|POINTS|END|CRC
```

Example chunk 1:

```text
P|1/2|015|RA|FLOOD|23.250,77.400;23.270,77.420;23.260,77.440|N|E5
```

Example chunk 2:

```text
P|2/2|016|RA|FLOOD|23.240,77.430|Y|F6
```

Meaning:

```text
Polygon message
Chunk 1 of 2
Chunk 2 of 2, final chunk
END = Y means polygon is complete
```

Polygon rules:

- Use `;` to separate coordinate pairs.
- Use `,` to separate latitude and longitude.
- Use `END=Y` only for the final chunk.
- Use `END=N` for non-final chunks.
- Store chunks in buffer until the final chunk arrives.
- After final chunk, combine all points and draw polygon on offline map.

Decoded polygon JSON:

```json
{
  "type": "polygon",
  "seq": "016",
  "chunk": 2,
  "total_chunks": 2,
  "location_code": "RA",
  "location_name": "Region A",
  "zone_type": "flood",
  "points": [
    [77.400, 23.250],
    [77.420, 23.270],
    [77.440, 23.260],
    [77.430, 23.240]
  ],
  "complete": true,
  "checksum": "F6",
  "source": "sms"
}
```

Important:

For GeoJSON compatibility, store coordinates as:

```text
[longitude, latitude]
```

But in SMS text, keep:

```text
latitude,longitude
```

The decoder should convert to GeoJSON order.

---

## 22. Route Update

### Canonical Format

```text
RT|SEQ|ORG|ROUTE_ID|POINTS|CRC
```

Example:

```text
RT|017|NGO01|RT1|23.250,77.400;23.260,77.410;23.270,77.420|A3
```

Meaning:

```text
Route update
Sequence: 017
Organization: NGO01
Route ID: RT1
Waypoints: three coordinate points
Checksum: A3
```

Alternative route type:

```text
ROUTE|017|NGO01|RT1|23.250,77.400;23.260,77.410;23.270,77.420|A3
```

Decoded JSON:

```json
{
  "type": "route",
  "seq": "017",
  "organization_id": "NGO01",
  "route_id": "RT1",
  "points": [
    [77.400, 23.250],
    [77.410, 23.260],
    [77.420, 23.270]
  ],
  "checksum": "A3",
  "source": "sms"
}
```

Route rules:

- Use `;` to separate waypoints.
- Use latitude,longitude order in SMS.
- Convert to GeoJSON `[longitude, latitude]` after decoding.
- Keep routes small.
- Do not send full navigation paths over SMS.

---

## 23. Error Message

Format:

```text
E|SEQ|CODE|MSG|CRC
```

Example:

```text
E|018|BAD_CRC|INVALID_CHECKSUM|F1
```

Meaning:

```text
Error message
Sequence: 018
Error code: BAD_CRC
Message: Invalid checksum
Checksum: F1
```

Common error codes:

| Code | Meaning |
|---|---|
| BAD_CRC | Checksum failed |
| BAD_FMT | Invalid format |
| UNKNOWN_TYPE | Unknown message type |
| UNKNOWN_RES | Unknown resource code |
| UNKNOWN_LOC | Unknown location code |
| DUP | Duplicate message |
| TOO_LONG | Message too long |
| PRIVACY | Sensitive content rejected |

---

## 24. Checksum Rule

Every canonical SMS message should include a checksum.

The checksum is the last field.

Example message before checksum:

```text
N|001|NGO01|RA|F|300|H
```

Final message:

```text
N|001|NGO01|RA|F|300|H|B3
```

Checksum rules:

- Use 2 uppercase hex characters.
- Calculate checksum over the message before the final checksum field.
- If checksum validation fails, reject the message.
- Do not push rejected messages into the agent queue.

For hackathon MVP, use a simple XOR checksum.

Example:

```python
def xor_checksum(text: str) -> str:
    value = 0
    for char in text:
        value ^= ord(char)
    return format(value, "02X")
```

Example usage:

```python
message = "N|001|NGO01|RA|F|300|H"
checksum = xor_checksum(message)
final_message = f"{message}|{checksum}"
```

Note:

Example checksums in this document may be illustrative. The implementation should calculate checksums dynamically.

---

## 25. Sequence Numbers

Every canonical message must contain a sequence number.

Recommended format:

```text
001
002
003
...
999
```

If more messages are needed, use 4 digits:

```text
0001
0002
```

Duplicate protection rule:

Store:

```text
organization_id + sequence_number
```

If the same combination is received again, ignore it.

Optional confirmation for duplicate:

```text
C|019|001|DUP|B2
```

Meaning:

```text
Message 001 was already processed.
```

---

## 26. Decoder Validation Rules

When an SMS is received, the decoder must:

1. Trim whitespace.
2. Split by `|`.
3. Detect legacy or canonical format.
4. Check minimum field count.
5. Validate checksum if present.
6. Validate message type.
7. Map short codes to full values.
8. Convert quantity to integer.
9. Convert severity to integer.
10. Parse location code or coordinates.
11. Reject invalid messages.
12. Ignore duplicates.
13. Push valid message to Redis queue.

---

## 27. Decoder Output Format

The SMS decoder must convert SMS into structured JSON before pushing to Redis.

Example SMS:

```text
N|001|NGO01|RA|F|300|H|B3
```

Decoder output:

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

All decoded SMS messages must include:

```json
"source": "sms"
```

This helps the backend distinguish SMS inputs from web dashboard inputs.

---

## 28. Encoder Rules

The encoder must:

1. Accept structured JSON.
2. Replace long values with mapped codes.
3. Reduce location names to location codes.
4. Reduce resource names to resource codes.
5. Reduce urgency values to urgency codes.
6. Build pipe-delimited string.
7. Calculate checksum.
8. Return final SMS string.

Example input:

```json
{
  "type": "need",
  "organization_id": "NGO01",
  "location": "Region A",
  "resource": "food_kits",
  "quantity": 300,
  "urgency": "high"
}
```

Encoded output:

```text
N|001|NGO01|RA|F|300|H|B3
```

---

## 29. Coordinate Encoding Policy

Use this priority order.

### Priority 1: Location Code

```text
RA
```

Best for demo and shortest message size.

### Priority 2: Decimal Coordinates

```text
23.2599,77.4126
```

Best when an exact point is needed and location code is unavailable.

Recommended for hackathon MVP.

### Priority 3: Geohash

```text
GEO:te7u2f
```

Use only if approximate location is acceptable.

Example:

```text
M|020|GEO:te7u2f|CR|8|F200|C3
```

### Priority 4: Hex Coordinates

Hex coordinates are optional and not recommended by default.

Use hex only if:

- Binary SMS is available.
- Both encoder and decoder support it.
- Message size must be aggressively minimized.
- Debugging complexity is acceptable.

---

## 30. Optional Hex Coordinate Format

Hex coordinate format is optional.

Format:

```text
M|SEQ|HX:HEXCOORD|MARKER_TYPE|SEVERITY|DATA|CRC
```

Example:

```text
M|021|HX:0DDBF6D82E22A1B0|CR|9|F300|A1
```

Encoding rule:

```text
lat_int = round(latitude * 10000000)
lon_int = round(longitude * 10000000)

lat_hex = 8 uppercase hex characters
lon_hex = 8 uppercase hex characters

hex_coord = lat_hex + lon_hex
```

Example:

```text
latitude = 23.2599
longitude = 77.4126

lat_int = 232599000
lon_int = 774126000

lat_hex = 0DDBF6D8
lon_hex = 2E22A1B0

hex_coord = 0DDBF6D82E22A1B0
```

Decoding rule:

```text
lat_hex = first 8 characters
lon_hex = next 8 characters

latitude = int(lat_hex, 16) / 10000000
longitude = int(lon_hex, 16) / 10000000
```

Hex coordinate policy:

- Do not use hex coordinates in the main demo unless necessary.
- Use decimal coordinates for readability.
- Use hex only as an optional advanced mode.

---

## 31. Privacy Rules for SMS

SMS messages must not contain sensitive data.

Do not send:

- Donor names
- Funding details
- Staff names
- Volunteer names
- Beneficiary personal data
- Exact warehouse locations if sensitive
- Private logistics routes
- Internal operational plans
- Full inventory data
- Security-sensitive details

Only send:

- Organization ID
- Resource type
- Approximate quantity
- Location code or approximate coordinates
- Urgency
- Status
- Plan ID
- Checksum

Safe example:

```text
N|001|NGO01|RA|F|300|H|B3
```

Unsafe example:

```text
N|NGO01|John Smith|Warehouse 5|Donor XYZ|food|300|H
```

Reject unsafe SMS content if detected.

---

## 32. SMS Size Rules

Target message size:

```text
< 160 characters
```

Hard limit for hackathon MVP:

```text
160 characters
```

If message exceeds limit:

1. Split polygon messages into chunks.
2. Reduce coordinate precision.
3. Use location codes.
4. Remove optional fields.
5. Reject overly large messages.

Do not send multi-part SMS unless required for polygon chunks.

---

## 33. Recommended Message Examples

### Need request

```text
N|001|NGO01|RA|F|300|H|B3
```

### Resource availability

```text
R|002|CSR02|RA|F|200|A|7C
```

### Allocation

```text
A|003|PLAN101|CSR02|F|200|RA|4|D2
```

### Status update

```text
S|004|PLAN101|3|A1
```

### Confirmation

```text
C|005|PLAN101|OK|F1
```

### Cancel

```text
X|006|PLAN101|BLK|A2
```

### Marker using location code

```text
M|007|RA|CR|9|F300|A1
```

### Marker using coordinates

```text
M|008|23.2599,77.4126|CR|9|F300|B4
```

### Polygon chunk 1

```text
P|1/2|009|RA|FLOOD|23.250,77.400;23.270,77.420;23.260,77.440|N|E5
```

### Polygon chunk 2

```text
P|2/2|010|RA|FLOOD|23.240,77.430|Y|F6
```

### Route update

```text
RT|011|NGO01|RT1|23.250,77.400;23.260,77.410;23.270,77.420|A3
```

### Error

```text
E|012|BAD_CRC|INVALID_CHECKSUM|F1
```

---

## 34. SMS Simulator Requirements

The web dashboard should include an SMS simulator panel.

The simulator should allow users to:

1. Enter an SMS payload.
2. Send it to the backend.
3. View decoded JSON.
4. View validation errors.
5. View agent response.
6. Update dashboard state.
7. Update map markers if applicable.

Example simulator input:

```text
N|001|NGO01|RA|F|300|H|B3
```

Expected simulator result:

```text
SMS accepted
Decoded as need request
Pushed to Redis queue
Need Assessment Agent processing
```

Legacy simulator input:

```text
N|NGO01|RegionA|food|300|H
```

Expected backend behavior:

```text
Accept legacy demo format
Normalize to canonical JSON
Push to Redis queue
```

---

## 35. Android App SMS Behavior

The Android app should:

1. Detect internet availability.
2. If internet is available, send data to FastAPI backend.
3. If internet is unavailable, convert message to SMS payload.
4. Queue SMS locally if sending fails.
5. Parse received SMS payloads.
6. Update offline UI.
7. Update cached MapLibre map.
8. Sync local queue when internet returns.

Important:

Android is required because Android allows programmatic SMS sending and receiving. iOS has strong SMS restrictions.

---

## 36. Offline Map Behavior

SMS cannot send map tiles.

Map tiles or vector tiles must be pre-cached inside the app.

Offline map flow:

```text
App uses cached map tiles
        |
        v
App receives SMS coordinate update
        |
        v
App parses SMS
        |
        v
App adds marker, polygon, or route
        |
        v
App updates cached map view
```

SMS can update:

- Single point coordinates
- Marker type
- Severity
- Small status codes
- Polygon chunks
- Route waypoints

SMS cannot update:

- Map tiles
- Large GeoJSON files
- High-resolution imagery
- Full map packages

---

## 37. Redis Integration

Valid decoded SMS messages should be pushed to Redis queues.

Example queues:

```text
sms_incoming_queue
need_assessment_queue
resource_matching_queue
coordination_queue
replanning_queue
sms_outgoing_queue
```

Example flow:

```text
SMS received
    |
    v
SMS parser validates message
    |
    v
Decoder converts SMS to JSON
    |
    v
Message pushed to sms_incoming_queue
    |
    v
Need Assessment Agent consumes message
    |
    v
Resource Matching Agent processes need
    |
    v
Coordination Agent creates plan
    |
    v
Backend sends SMS response if required
```

---

## 38. MVP Implementation Order

Implement in this order:

1. Need request encoding/decoding
2. Resource availability encoding/decoding
3. Allocation encoding/decoding
4. Status update encoding/decoding
5. Marker update encoding/decoding
6. XOR checksum
7. SMS simulator panel
8. Decoder to JSON
9. Push decoded message to Redis queue
10. Offline map marker update from decoded SMS

Do not prioritize these first:

- Full binary SMS
- Hex coordinate encoding
- Advanced cryptography
- Complex multi-part reconstruction
- Production telecom gateway integration
- Full routing engine

---

## 39. Final SMS Strategy

Use:

```text
Short text protocol + mapped codes + pipe delimiter + checksum
```

Use coordinate strategy:

```text
Location code first, decimal coordinates second, geohash optional, hex not default
```

Recommended demo need message:

```text
N|001|NGO01|RA|F|300|H|B3
```

Recommended demo marker message:

```text
M|008|23.2599,77.4126|CR|9|F300|B4
```

This keeps the SMS fallback simple, privacy-aware, demo-friendly, and feasible within a 24-hour hackathon.