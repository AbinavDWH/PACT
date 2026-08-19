# SMS_PROTOCOL.md

This document defines the SMS fallback protocol for the Privacy-Preserving Multi-Agent Humanitarian Coordination Platform.

SMS is used as an emergency data-transfer channel when internet connectivity is unavailable or unstable.

Related documents:

| File | Purpose |
|---|---|
| `memory_draft.md` | High-level project memory, identity model, architecture, demo strategy |
| `codec.md` | Option taxonomy and the compressed payload carried by `Q` and `G` |
| `agents.md` | Agent pipeline, Groq usage, MongoDB schema, API surface |
| `sms.md` | This file — framing, checksum, sequence numbers, message types |

---

## 1. Purpose

The SMS protocol allows field workers, organizations, and coordination systems to exchange small emergency messages.

SMS is used for:

- Help-seeker requests from individuals (`Q`)
- Helper offers (`G`)
- Need requests between organizations (`N`)
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
10. Convert SMS messages into structured JSON before handing them to the agent pipeline.

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
N|001|NGO01|RA|F|300|H|16
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
| Q | **Help-seeker request (individual)** |
| G | **Helper offer (individual or organization)** |
| N | Need request (organization to organization) |
| R | Resource availability (organization to organization) |
| A | Allocation / plan assignment |
| S | Status update |
| C | Confirmation |
| D | Dispatch |
| V | Delivered |
| X | Cancel |
| M | Map marker |
| P | Polygon chunk |
| RT | Route update |
| E | Error |

`Q` and `G` carry a compressed selection payload rather than spelled-out fields. Their layout is
defined in `codec.md`. They obey the canonical frame in §4 exactly, so checksum, sequence, and
dedupe rules apply unchanged.

For MVP, prefer:

```text
Q, G, N, R, A, S, M, P, RT, C, E
```

Legacy shortcuts `D` and `V` may be supported for demo compatibility.

The long-form alias `ROUTE` is **deprecated**. Use `RT` only. Decoders may continue to accept
`ROUTE` on input but must never emit it.

---

## 6. Resource Codes

Use short resource codes.

| Code | Bit | Resource |
|---|---|---|
| F | 0 | Food kits |
| W | 1 | Water kits |
| M | 2 | Medical kits |
| D | 3 | Medical teams |
| T | 4 | Tents |
| B | 5 | Blankets |
| H | 6 | Hygiene kits |
| X | 7 | Rescue / extraction team |
| V | 8 | Evacuation transport |
| P | 9 | Power / light / charging kits |
| I | 10 | Infant and child supplies |
| S | 11 | Search for missing person |
| U | — | Unknown |

The **Bit** column is the position this resource occupies in the 12-bit needs and resources
bitfields used by `Q` and `G` messages. See `codec.md` §3.1.

**Bit positions are frozen.** A new resource takes bit 12 and upward; existing bits are never
renumbered, because the Android app and the backend decode against the same fixed layout.

### Namespace note

Resource codes and message type codes are **separate namespaces**. The letters `S`, `P`, `V` and `D`
now appear in both:

| Letter | As a message type (§5) | As a resource code (§6) |
|---|---|---|
| S | Status update | Search for missing person |
| P | Polygon chunk | Power kits |
| V | Delivered (legacy) | Evacuation transport |
| D | Dispatch (legacy) | Medical teams |

There is no ambiguity in practice, because the message type is always field 0 of the frame and a
resource code never appears there. Decoders must not share one lookup table between the two.

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
| 6 | Self-resolved (seeker no longer needs help) |
| 7 | Still waiting (seeker re-ping) |

Codes `6` and `7` are seeker-side states, sent from the app in help-seeker mode. Code `7` is what an
untouched request sends on a retry timer, and it is the trigger the replanning agent watches for.

Example:

```text
S|004|PLAN101|3|0B
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
R|002|CSR02|RA|F|200|A|06
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

### 10.1 PACK10 packed coordinates

`Q`, `G` and `M` messages from the Android app use **PACK10**, a 10-character base-36 packed
coordinate pair. It is the preferred form whenever no predefined location code applies, which is
almost always the case for an individual help-seeker.

```text
lat_token = base36( round((lat +  90) * 100000) ) padded to 5
lon_token = base36( round((lon + 180) * 100000) ) padded to 5
GEO       = lat_token + lon_token
```

Example:

```text
23.25991, 77.41263   ->   6QR6VFBQ33
```

Resolution is approximately 1.1 metres. An optional 11th character encodes GPS accuracy. The full
rationale and the accuracy table are in `codec.md` §6.

### 10.2 GEO field disambiguation

A decoder reading a location field applies these tests in order:

| Condition | Interpretation |
|---|---|
| Contains `,` or `.` | Decimal coordinates (§29 Priority 2) |
| Starts with `GEO:` | Geohash (§29 Priority 3) |
| Starts with `HX:` | Hex coordinates (§30, deprecated) |
| Length 10 or 11, all base-36 characters | **PACK10** (§10.1) |
| Length 2 to 4 and present in the location code table | Location code (§29 Priority 1) |
| Otherwise | Reject with `UNKNOWN_LOC` |

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
N|001|NGO01|RA|F|300|H|16
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
  "checksum": "16",
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
R|002|CSR02|RA|F|200|A|06
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
  "checksum": "06",
  "source": "sms"
}
```

---

## 12A. Help-Seeker Request (`Q`)

Sent by an individual using the Android app in help-seeker mode. The body is a compressed selection
payload, not spelled-out fields.

Format:

```text
Q|SEQ|UID|PAYLOAD|GEO|CRC
```

Example:

```text
Q|001|7F3K|15223C03Q0|6QR6VFBQ33|7F
```

Fields:

| Field | Meaning |
|---|---|
| `Q` | Message type |
| SEQ | Sequence number (§25) |
| UID | 4 base-36 characters, the first 4 of base36(sha256(device install id)) |
| PAYLOAD | 10 characters, layout in `codec.md` §4.1 |
| GEO | PACK10 coordinates (§10.1) or a location code |
| CRC | XOR checksum (§24) |

Total length 35 characters. Single-part by construction.

Decoded JSON:

```json
{
  "type": "seeker_request",
  "schema": 1,
  "seq": "001",
  "uid": "7F3K",
  "situation": "building_collapse",
  "people_bucket": "3-4",
  "people_est": 3,
  "injury": "serious_stable",
  "mobility": "trapped_debris",
  "urgency": "critical",
  "needs": ["water_kits", "medical_kits", "rescue_team"],
  "vulnerabilities": [],
  "latitude": 23.25991,
  "longitude": 77.41263,
  "checksum": "7F",
  "source": "sms"
}
```

A decoded `Q` **fans out into one `N`-shaped need record per set needs bit**, so it feeds the
existing organization-facing need path in §11 without changing it. The fan-out factors are in
`codec.md` §8.

`UID` occupies the position that §4 calls `ORG`. A decoder distinguishes them by message type, not
by inspecting the field.

---

## 12B. Helper Offer (`G`)

Sent by a volunteer or an organization's field staff using the app in helper mode.

Format:

```text
G|SEQ|UID|PAYLOAD|GEO|CRC
```

Examples:

```text
G|014|N001|2101Z542A|728B2FBADG|2C
G|015|H004|2400C131L|RA|26
```

The payload is 9 characters, layout in `codec.md` §4.2. Total length 34 characters with PACK10
coordinates, 26 with a location code.

Decoded JSON:

```json
{
  "type": "helper_offer",
  "schema": 2,
  "seq": "014",
  "uid": "N001",
  "org_type": "ngo",
  "resources": ["food_kits", "water_kits", "medical_kits", "hygiene_kits"],
  "capacity_bucket": "200-499",
  "capacity_est": 300,
  "service_radius_km": 50,
  "eta_hours": "2-4",
  "status": "available",
  "latitude": 28.61390,
  "longitude": 77.20900,
  "checksum": "2C",
  "source": "sms"
}
```

`G` is the app-selection form of a resource declaration. `R` (§12) remains the spelled-out
organization-to-organization form and is **not** deprecated; the backend re-emits a decoded `G` as
an `R` record for organization-facing traffic.

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
A|003|PLAN001|CSR02|F|200|RA|4|3F
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
  "checksum": "3F",
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
S|004|PLAN101|3|0B
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
  "checksum": "0B",
  "source": "sms"
}
```

Status examples:

```text
S|005|PLAN101|1|08
S|006|PLAN101|2|08
S|007|PLAN101|3|08
S|008|PLAN101|4|00
```

Meaning:

```text
Dispatched
In transit
Delivered
Blocked
```

### 14.1 Seeker status updates

A help-seeker may send a status update about their own request. The `PLAN` slot carries the
originating request reference and the `ORG` slot carries the seeker's `UID`.

```text
S|SEQ|UID|REF|STATUS|CRC
```

Example:

```text
S|041|7F3K|Q001|3|3C
```

Meaning: the seeker identified by `7F3K` confirms that request `Q001` was delivered.

Seeker-specific status codes `6` (self-resolved) and `7` (still waiting) are defined in §8.

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
S|009|PLAN101|3|06
```

If plan ID is unknown, use:

```text
S|009|RA|F|200|3|42
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
  "checksum": "42",
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
C|010|PLAN101|OK|29
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
  "checksum": "29",
  "source": "sms"
}
```

### 16.1 Seeker acknowledgement variant

The backend acknowledges a `Q` request to the seeker with an extended `C` message carrying a state
code and an ETA bucket, rather than inventing a separate message type.

```text
C|SEQ|UID|REF|STATE|ETA|CRC
```

Example:

```text
C|031|7F3K|Q001|1|3|66
```

Meaning: request `Q001` from seeker `7F3K` was accepted, a helper is assigned, expected arrival is
in ETA bucket 3, which is 4 to 8 hours. ETA bucket values are defined in `codec.md` §3.2.

State codes reuse the §8 status table. A decoder distinguishes this variant from the standard `C` in
§16 by field count: 7 fields rather than 5.

---

## 17. Cancel

Format:

```text
X|SEQ|REF|REASON|CRC
```

Example:

```text
X|011|PLAN101|BLK|72
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
  "checksum": "72",
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
M|012|RA|CR|9|F300|4C
```

Example using coordinates:

```text
M|013|23.2599,77.4126|CR|9|F300|75
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
  "checksum": "75",
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
M|014|RA|CR|9|F300;W150|12
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
P|1/2|015|RA|FLOOD|23.250,77.400;23.270,77.420;23.260,77.440|N|72
```

Example chunk 2:

```text
P|2/2|016|RA|FLOOD|23.240,77.430|Y|60
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
  "checksum": "60",
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
RT|017|NGO01|RT1|23.250,77.400;23.260,77.410;23.270,77.420|6C
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

Deprecated long-form alias, accepted on input but never emitted (§5):

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
  "checksum": "6C",
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
E|018|BAD_CRC|INVALID_CHECKSUM|49
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
| UNKNOWN_CODE | Unknown selection code in a `Q` or `G` payload |
| BAD_SCHEMA | Unknown payload schema version |
| BAD_GEO | Coordinates out of range |
| TRUNCATED | Message shorter than its declared layout |
| DUP | Duplicate message |
| TOO_LONG | Message too long |
| PRIVACY | Sensitive content rejected |

Note on `UNKNOWN_CODE`: a single unrecognised selection character does **not** reject the message.
The decoder sets that one field to null and accepts the request provided urgency, location, and at
least one need decoded successfully. A request with one garbled field is still a person who needs
help. `BAD_SCHEMA`, by contrast, always rejects, because an unknown version means every field
position is untrustworthy.

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
N|001|NGO01|RA|F|300|H|16
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
C|019|001|DUP|77
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
10. Parse location code, PACK10, or coordinates (§10.2).
11. For `Q` and `G`, check the schema version, then expand the compressed payload using the shared
    tables in `codec.md`.
12. Reject invalid messages.
13. Ignore duplicates, keyed on `(organization_id or uid, seq)`.
14. Hand the valid decoded message to the agent pipeline.

---

## 27. Decoder Output Format

The SMS decoder must convert SMS into structured JSON before handing it to the agent pipeline.

Example SMS:

```text
N|001|NGO01|RA|F|300|H|16
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
  "checksum": "16",
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
N|001|NGO01|RA|F|300|H|16
```

---

## 29. Coordinate Encoding Policy

Use this priority order.

The priority depends on who is sending.

| Sender | Priority order |
|---|---|
| Organization with a pre-mapped site | Location code, then PACK10, then decimal |
| Individual help-seeker or helper (`Q`, `G`) | **PACK10 first.** Location codes rarely apply to an arbitrary position |

### Priority 1: Location Code

```text
RA
```

Shortest possible, but only meaningful for pre-mapped organization sites.

### Priority 1 for app messages: PACK10

```text
6QR6VFBQ33
```

10 characters, approximately 1.1 metre resolution, no library dependency in either Python or Kotlin.
This is the default for `Q`, `G` and `M` messages originating from the app. See §10.1 and
`codec.md` §6.

### Priority 2: Decimal Coordinates

```text
23.2599,77.4126
```

17 characters. Retained for legacy and human-authored messages. PACK10 is both shorter and more
precise, so prefer it for anything machine-generated.

### Priority 3: Geohash

```text
GEO:te7u2f
```

Use only if approximate location is acceptable.

Example:

```text
M|020|GEO:te7u2f|CR|8|F200|2E
```

### Priority 4: Hex Coordinates

**Superseded by PACK10.** See §30.

---

## 30. Hex Coordinate Format (superseded)

**Status: superseded by PACK10 (§10.1). Retained for read-only decoder compatibility. Do not emit.**

Hex coordinates are 16 characters and encode to 1.1 cm precision. PACK10 is 10 characters and
encodes to approximately 1.1 m. Since civilian GPS error is 3 to 5 metres, the extra precision is
unusable and the extra 6 characters are pure cost. There is no case in this project where hex is the
right choice.

The format is documented below only so that a decoder can still read historical messages.

Format:

```text
M|SEQ|HX:HEXCOORD|MARKER_TYPE|SEVERITY|DATA|CRC
```

Example:

```text
M|021|HX:0DDBF6D82E22A1B0|CR|9|F300|7E
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

- Organization ID, or a seeker/helper `UID`
- Resource type
- Approximate quantity
- Location code or coordinates
- Urgency
- Status
- Plan ID
- Checksum

### 31.1 Rules for app messages

- Never place an MSISDN, name, or age in a payload. The gateway already knows the sending number;
  the message must not repeat it.
- `UID` is a 4-character pseudonymous device hash, not an identifier of a person. See `codec.md`
  §5.1.
- `Q` and `G` payloads use a closed vocabulary. There is no free-text field, so personal data cannot
  leak into them by accident. This is a structural privacy property, not a validation rule.
- The privacy filter may truncate PACK10 coordinates to 3 characters per axis before forwarding a
  position to a non-rescue audience.

### 31.2 What SMS privacy does not cover

SMS is plaintext over the operator network. This protocol provides **minimal disclosure and
integrity**, not confidentiality. The vocabulary is designed so that an intercepted message reveals
a situation and a location but never an identity. Encryption is out of scope for the MVP and should
be named as future work rather than implied.

Safe example:

```text
N|001|NGO01|RA|F|300|H|16
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

### 32.1 Q and G are single-part by construction

`Q` messages are 35 characters and `G` messages are 34. They cannot fragment. A `Q` or `G` frame
arriving longer than 140 characters is malformed and must be rejected with `TOO_LONG`.

**Do not implement multi-part reassembly for `Q` or `G`.** It would be dead code. Multi-part
handling remains a `P` polygon concern only (§21).

### 32.2 GSM-7 requirement

Every character emitted by this protocol must be in the set `0-9 A-Z | . , : -`, which is inside the
GSM-7 default alphabet. A single character outside it forces the whole message to UCS-2 encoding,
cutting single-part capacity from 160 characters to 70. Encoders must validate this before sending.

---

## 33. Recommended Message Examples

The `Q`, `G`, `C` and seeker `S` examples below were generated by the reference implementation.
**Their checksums are real and can be recomputed with the rule in §24.** The older examples in this
section predate that and remain illustrative, as noted at the end of §24.

### Help-seeker request

Building collapse, 3–4 people, one seriously injured, trapped in debris, critical, needs water and
medical supplies and rescue, at 23.25991, 77.41263.

```text
Q|001|7F3K|15223C03Q0|6QR6VFBQ33|7F
```

Flood, 5–9 people stranded, high urgency, needs food and water and infant supplies, child under 5
present, at 23.26100, 77.40900.

```text
Q|002|A19P|10302H0SJ1|6QR9WFBPT0|71
```

Displacement site, 200–499 people, medium urgency, needs water and tents and blankets and hygiene,
elderly present, at 28.61390, 77.20900.

```text
Q|003|C4M2|1A800M0364|728B2FBADG|65
```

### Helper offer

NGO offering food, water, medical and hygiene supplies; 200–499 units; 50 km radius; 2–4 hour ETA;
available.

```text
G|014|N001|2101Z542A|728B2FBADG|2C
```

Hospital offering medical kits and medical teams; 10–24 units; 25 km; 1–2 hours; limited; at a
pre-mapped site.

```text
G|015|H004|2400C131L|RA|26
```

### Seeker acknowledgement and status

```text
C|031|7F3K|Q001|1|3|66
S|041|7F3K|Q001|3|3C
```

### Need request

```text
N|001|NGO01|RA|F|300|H|16
```

### Resource availability

```text
R|002|CSR02|RA|F|200|A|06
```

### Allocation

```text
A|003|PLAN101|CSR02|F|200|RA|4|3E
```

### Status update

```text
S|004|PLAN101|3|0B
```

### Confirmation

```text
C|005|PLAN101|OK|2D
```

### Cancel

```text
X|006|PLAN101|BLK|74
```

### Marker using location code

```text
M|007|RA|CR|9|F300|48
```

### Marker using coordinates

```text
M|008|23.2599,77.4126|CR|9|F300|7F
```

### Polygon chunk 1

```text
P|1/2|009|RA|FLOOD|23.250,77.400;23.270,77.420;23.260,77.440|N|7F
```

### Polygon chunk 2

```text
P|2/2|010|RA|FLOOD|23.240,77.430|Y|66
```

### Route update

```text
RT|011|NGO01|RT1|23.250,77.400;23.260,77.410;23.270,77.420|6A
```

### Error

```text
E|012|BAD_CRC|INVALID_CHECKSUM|43
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
N|001|NGO01|RA|F|300|H|16
```

Expected simulator result:

```text
SMS accepted
Decoded as need request
Handed to the agent pipeline
Triage Agent processing
```

Legacy simulator input:

```text
N|NGO01|RegionA|food|300|H
```

Expected backend behavior:

```text
Accept legacy demo format
Normalize to canonical JSON
Hand to the agent pipeline
```

---

## 35. Android App SMS Behavior

The Android app runs in one of two modes, chosen once at first launch with no password: help-seeker
mode or helper mode. See `memory_draft.md` §7.

The app should:

1. Encode the user's chip selections into a payload string using the shared tables (`codec.md`).
2. Detect internet availability.
3. If internet is available, POST the payload to `/api/v1/pact/ingest`.
4. If internet is unavailable, send **the identical string** by SMS.
5. Queue locally if sending fails, and replay when connectivity returns.
6. Parse received SMS payloads.
7. Update the offline UI and the cached MapLibre map.

Important: connectivity is decided in exactly one transport function. The rest of the app never
knows which path a message took, because the payload is the same either way.

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

## 37. Backend Integration

**Redis is not used.** Agents run as `asyncio` coroutines inside the single FastAPI process, so a
network queue between them would add infrastructure and latency for no benefit. Decoded messages
enter the pipeline by direct function call.

Duplicate suppression uses a MongoDB TTL index on `(from_hash, seq)` rather than a Redis set. See
`agents.md` §4.1.

Flow:

```text
SMS received at the gateway
    |
    v
POST /api/v1/sms/webhook
    |
    v
Thin adapter calls POST /api/v1/pact/ingest with transport="sms"
    |
    v
Parser validates the frame and checksum (§24, §26)
    |
    v
Decoder converts the message to structured JSON (§27)
    |
    v
Duplicate check against (from_hash, seq) in MongoDB (§25)
    |
    v
In-process agent pipeline: triage, geo search, advocates,
solver, arbiter, privacy, admin gate, narrator
    |
    v
Backend sends an SMS acknowledgement if required (§16.1)
```

The same ingest path serves HTTP requests from the app. The only difference between a connected
request and an SMS request is which function delivered the string. See `agents.md` §6.5.

---

## 38. MVP Implementation Order

Implement in this order:

1. XOR checksum and frame parsing
2. `Q` help-seeker request encoding and decoding
3. `G` helper offer encoding and decoding
4. PACK10 coordinate encoding and decoding
5. Q to N fan-out
6. Status and confirmation encoding/decoding, including the seeker variants
7. Decoder to JSON, with the legacy `N` fallback chain preserved
8. SMS simulator panel in the admin portal
9. Hand decoded messages to the agent pipeline
10. Marker update encoding/decoding
11. Offline map marker update from decoded SMS

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
App messages:  PACK10 first, location code if a pre-mapped site applies
Legacy/org:    Location code first, PACK10 second, decimal third
Geohash:       optional
Hex:           superseded, read-only
```

Recommended demo seeker request:

```text
Q|001|7F3K|15223C03Q0|6QR6VFBQ33|7F
```

Recommended demo helper offer:

```text
G|014|N001|2101Z542A|728B2FBADG|2C
```

Recommended demo need message (organization to organization):

```text
N|001|NGO01|RA|F|300|H|16
```

Recommended demo marker message:

```text
M|008|23.2599,77.4126|CR|9|F300|7F
```

This keeps the SMS fallback simple, privacy-aware, demo-friendly, and feasible within a 24-hour hackathon.

---

## 40. Relationship to the Other Documents

| Need | File |
|---|---|
| Framing, checksum, sequence, message types, error codes | This file |
| Option taxonomy, payload layout, PACK10 derivation, fan-out factors | `codec.md` |
| Agent pipeline, MongoDB schema, API endpoints | `agents.md` |
| Identity model, group codes, portals, demo script | `memory_draft.md` |

If the compressed payload layout changes, update `codec.md` first, then the summaries here in §12A
and §12B.