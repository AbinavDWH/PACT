# CODEC.md — PACT-C1 Compressed Selection Codec

This document defines PACT's **code language**: the mapping that turns a set of taps in the Android
app into a few alphanumeric characters, and back again.

It is the human-readable source of truth. The machine-readable table
`shared/codec/pact_tables.v1.json` is derived from this file, and both the Python backend and the
Kotlin app load that one file.

Related documents:

| File | Purpose |
|---|---|
| `memory_draft.md` | High-level project memory and architecture |
| `sms.md` | SMS transport protocol — framing, checksum, sequence numbers, message types |
| `agents.md` | Agent pipeline, Groq usage, MongoDB schema, API surface |
| `codec.md` | This file — option taxonomy and compressed encoding |

---

## 1. Purpose and Design Invariants

Users of the PACT app never type free text. They select options from chip groups. Each selection
path maps to a short base-36 code. That code is the payload, whether it travels over HTTP or over
SMS.

Four invariants govern the whole design.

1. **One wire format.** The app builds the same code string regardless of connectivity. Transport is
   only how it leaves the device.
2. **Framing is unchanged.** The frame stays exactly as `sms.md` §4 defines it:
   `TYPE|SEQ|...|CRC`, pipe-delimited, XOR checksum, uppercase hex. All compression happens *inside
   one field*, so existing framing and checksum code keeps working.
3. **GSM-7 only.** Every emitted character is in `0-9 A-Z | . , : -`. A real SMS therefore never
   downgrades to UCS-2, which would cut capacity from 160 characters to 70.
4. **No free text, no personal data.** No name, no age, no phone number, no note field ever crosses
   the wire.

---

## 2. Why Option Selection Instead of Free Text

| Reason | Explanation |
|---|---|
| Size | A full request fits in 35 characters instead of ~200 |
| Reliability | No parsing ambiguity, no language dependency, no spelling |
| Speed | A person in danger taps six chips; they do not compose a sentence |
| Literacy | Icon-and-chip selection works for users who cannot read the interface language |
| Privacy | A closed vocabulary cannot accidentally contain a name or a medical detail |
| Determinism | The same selections always produce the same code, so encoder and decoder can be tested against fixed vectors |

The cost is expressiveness. That cost is accepted deliberately: the taxonomy in §3 is designed to
cover the overwhelming majority of disaster requests, and anything outside it maps to the `Z`
(other/unknown) value, which the triage agent treats as needing human attention.

---

## 3. Option Taxonomy

Every dimension occupies one base-36 character unless marked otherwise. Multi-select dimensions are
bitfields.

Base-36 alphabet, used throughout:

```text
0 1 2 3 4 5 6 7 8 9 A B C D E F G H I J K L M N O P Q R S T U V W X Y Z
```

### 3.1 Help-Seeker Dimensions

#### S — Situation type (1 char)

| Code | Meaning |
|---|---|
| 0 | Flood |
| 1 | Earthquake |
| 2 | Fire |
| 3 | Cyclone / storm |
| 4 | Landslide |
| 5 | Building collapse |
| 6 | Conflict / violence |
| 7 | Epidemic / outbreak |
| 8 | Industrial / chemical |
| 9 | Accident / trauma |
| A | Displaced, no shelter |
| B | Heat wave / cold wave |
| Z | Other / unknown |

#### P — People count bucket (1 char)

`rep` is the integer the matching agent uses for quantity arithmetic.

| Code | Range | rep |
|---|---|---|
| 0 | 1 | 1 |
| 1 | 2 | 2 |
| 2 | 3–4 | 3 |
| 3 | 5–9 | 7 |
| 4 | 10–19 | 14 |
| 5 | 20–49 | 30 |
| 6 | 50–99 | 70 |
| 7 | 100–199 | 150 |
| 8 | 200–499 | 300 |
| 9 | 500+ | 750 |
| A | Unknown | 5 |

Buckets rather than an exact count: a person in a collapsed building cannot count reliably, and
allocation does not need better than bucket precision.

#### I — Injury / severity (1 char)

| Code | Meaning |
|---|---|
| 0 | None |
| 1 | Minor |
| 2 | Serious, stable |
| 3 | Critical / life-threatening |
| 4 | Unconscious |
| 5 | Fatality present |
| 9 | Unknown |

#### B — Mobility / trapped status (1 char)

| Code | Meaning |
|---|---|
| 0 | Free and mobile |
| 1 | Free but immobile |
| 2 | Stranded, cannot leave |
| 3 | Trapped in debris |
| 4 | Trapped by water |
| 5 | Trapped in vehicle |
| 6 | Underground / collapsed structure |
| 9 | Unknown |

#### U — Urgency (1 char)

Unchanged from `sms.md` §7 and reused verbatim.

| Code | Meaning |
|---|---|
| L | Low |
| M | Medium |
| H | High |
| C | Critical |

#### N — Needs (multi-select bitfield, 12 bits, 3 chars)

12 bits gives values 0–4095. Three base-36 characters hold 0–46655, so 3 chars is sufficient with
room to grow to 15 bits later without changing the layout width.

| Bit | Code | Need | Canonical resource key |
|---|---|---|---|
| 0 | F | Food | `food_kits` |
| 1 | W | Drinking water | `water_kits` |
| 2 | M | Medical supplies | `medical_kits` |
| 3 | D | Medical personnel on site | `medical_teams` |
| 4 | T | Shelter / tents | `tents` |
| 5 | B | Blankets / clothing | `blankets` |
| 6 | H | Hygiene / sanitation | `hygiene_kits` |
| 7 | X | Rescue / extraction | `rescue_team` |
| 8 | V | Evacuation transport | `evac_transport` |
| 9 | P | Power / light / charging | `power_kits` |
| 10 | I | Infant and child supplies | `infant_kits` |
| 11 | S | Search for missing person | `search_request` |

Bits 0–6 correspond exactly to the resource codes already defined in `sms.md` §6. Bits 7–11 are the
new codes added there for this design. **Bit positions are frozen** — appending a new need means
taking bit 12, never renumbering.

#### X — Vulnerability flags (multi-select bitfield, 5 bits, 1 char)

5 bits gives 0–31, which fits in a single base-36 character.

| Bit | Meaning |
|---|---|
| 0 | Child under 5 |
| 1 | Pregnant / nursing |
| 2 | Elderly |
| 3 | Disability |
| 4 | Chronic illness / requires medication |

### 3.2 Helper Dimensions

#### O — Organization type (1 char)

| Code | Meaning |
|---|---|
| 0 | Government |
| 1 | NGO |
| 2 | International NGO / UN agency |
| 3 | CSR / corporate |
| 4 | Hospital / clinic |
| 5 | Volunteer group |
| 6 | Faith-based organization |
| 7 | Logistics / transport |
| 8 | Military / civil defence |
| 9 | Individual donor / volunteer |
| A | Other |

Code `9` is what an unaffiliated individual volunteer sends — the app selects it automatically when
no group code has been entered. See `memory_draft.md` for the group-code membership model.

#### R — Resources offered (multi-select bitfield, 12 bits, 3 chars)

**The same table as N in §3.1.** One table, two directions. This is deliberate: matching a need
against an offer is then a bitwise AND, and there is no second mapping to keep in sync.

#### Q — Capacity bucket (1 char)

| Code | Units | rep |
|---|---|---|
| 0 | 1–9 | 5 |
| 1 | 10–24 | 15 |
| 2 | 25–49 | 35 |
| 3 | 50–99 | 75 |
| 4 | 100–199 | 150 |
| 5 | 200–499 | 300 |
| 6 | 500–999 | 750 |
| 7 | 1000–2499 | 1500 |
| 8 | 2500–4999 | 3500 |
| 9 | 5000+ | 7500 |
| A | Unknown | 0 |

#### K — Service radius bucket (1 char)

| Code | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|---|
| km | <2 | 5 | 10 | 25 | 50 | 100 | 250 | 500 | 1000 | Any / national |

#### E — ETA bucket (1 char)

| Code | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|---|
| hours | <1 | 1–2 | 2–4 | 4–8 | 8–12 | 12–24 | 24–48 | 48–72 | 72–168 | >168 |

#### A — Availability status (1 char)

Unchanged from `sms.md` §9 and reused verbatim.

| Code | Meaning |
|---|---|
| A | Available |
| L | Limited |
| U | Unavailable |

---

## 4. Payload Layout

Fixed-position single-character fields, **not** a whole-message packed bitfield.

A packed bitfield would save roughly two characters. Fixed positions instead buy: messages that can
be read by eye during a demo, logs that diff usefully, and forward compatibility by appending new
positions at the tail. At 35 characters against a 160-character limit, two characters are not worth
the debugging cost.

### 4.1 Help-Seeker Payload — 10 characters

```text
pos:   0    1    2    3    4    5    6 7 8    9
      [V]  [S]  [P]  [I]  [B]  [U]  [N N N]  [X]
       |    |    |    |    |    |    |        |
       |    |    |    |    |    |    |        +-- vulnerability bitfield (5 bits, 1 char)
       |    |    |    |    |    |    +----------- needs bitfield (12 bits, 3 chars)
       |    |    |    |    |    +---------------- urgency  L/M/H/C
       |    |    |    |    +--------------------- mobility / trapped
       |    |    |    +-------------------------- injury severity
       |    |    +------------------------------- people count bucket
       |    +------------------------------------ situation type
       +----------------------------------------- schema version ('1' = seeker v1)
```

### 4.2 Helper Payload — 9 characters

```text
pos:   0    1    2 3 4    5    6    7    8
      [V]  [O]  [R R R]  [Q]  [K]  [E]  [A]
       |    |    |        |    |    |    |
       |    |    |        |    |    |    +-- availability A/L/U
       |    |    |        |    |    +------- ETA bucket
       |    |    |        |    +------------ service radius bucket
       |    |    |        +----------------- capacity bucket
       |    |    +-------------------------- resources bitfield (12 bits, 3 chars)
       |    +------------------------------- organization type
       +------------------------------------ schema version ('2' = helper v1)
```

Position 0 is the schema version. A decoder seeing an unknown version returns `BAD_SCHEMA` rather
than silently misreading every subsequent position. This is the single most important field in the
layout.

### 4.3 Optional Helper Extension

If per-resource quantities are ever needed, append pairs of `<resource-code><capacity-bucket>`, two
characters each:

```text
2101Z542A F5 W4
```

Decoder rule: length greater than 9 means parse the tail in pairs. **Not needed for the MVP** — the
single capacity bucket in position 5 is sufficient.

---

## 5. Frame Layouts

```text
Q|SEQ|UID|PAYLOAD|GEO|CRC        Help-seeker request        (new type)
G|SEQ|UID|PAYLOAD|GEO|CRC        Helper offer               (new type)
C|SEQ|UID|REF|STATE|ETA|CRC      Backend acknowledgement    (extends sms.md §16)
S|SEQ|UID|REF|STATUS|CRC         Status update              (sms.md §14, extended codes)
```

### 5.1 UID

`UID` is 4 base-36 characters: the first 4 characters of the base-36 encoding of
`sha256(device_install_id)`.

- 1,679,616 possible values — enough to disambiguate, not enough to identify.
- Pseudonymous. Contains no phone number, no name, no device serial.
- Stable across app restarts; changes on reinstall.

The app does collect a name and phone number, once, at first launch. **Those never appear in a
payload.** They live server-side only, hashed and encrypted, and the `UID` is the join key between
a wire message and that server-side record. See `memory_draft.md` §7.2.

This separation is what keeps the privacy property intact: the user is reachable, but an
intercepted message still reveals only a situation and a location.

The SMS gateway already knows the sending MSISDN, so the payload never has to carry it.

### 5.2 Character Budget

| Segment | Characters |
|---|---|
| TYPE + `\|` | 2 |
| SEQ (3) + `\|` | 4 |
| UID (4) + `\|` | 5 |
| PAYLOAD (10) + `\|` | 11 |
| GEO (10) + `\|` | 11 |
| CRC | 2 |
| **Total, seeker request** | **35** |
| **Total, helper offer** | **34** |
| **Headroom in one 160-char GSM-7 SMS** | **125** |

The target was under 100 characters. At 35 we are 78% under budget. That headroom is deliberate: it
absorbs an operator-prefixed short code, the optional accuracy character, and a future 2-character
signature field, and still never fragments into a multi-part SMS.

---

## 6. GPS Encoding — PACK10

### 6.1 The Scheme

```text
lat_token = base36( round((lat +  90) * 100000) ) padded to 5    # range 0 .. 18,000,000
lon_token = base36( round((lon + 180) * 100000) ) padded to 5    # range 0 .. 36,000,000
GEO       = lat_token + lon_token                                # exactly 10 characters
```

36^5 = 60,466,176, so both ranges fit in 5 characters with headroom.

Decoding:

```text
lat = int(GEO[0:5], 36) / 100000 - 90
lon = int(GEO[5:10], 36) / 100000 - 180
```

Resolution is 1e-5 degrees, approximately 1.1 metres.

### 6.2 Why PACK10

| Scheme | Chars | Precision | Dependency | Reversible |
|---|---|---|---|---|
| Location code `RA` (sms.md §29 P1) | 2 | Region-level | Shared table | No |
| Decimal 4dp (sms.md §29 P2) | 17 | ~11 m | None | Yes |
| Geohash-8 / 9 (sms.md §29 P3) | 8 / 9 | 19 m / 4.8 m | Base32 geohash library both sides | Lossy |
| Hex 1e-7 (sms.md §30) | 16 | 1.1 cm | None | Yes |
| **PACK10** | **10** | **~1.1 m** | **None** | **Yes** |

Help-seekers are individuals at arbitrary coordinates, so predefined location codes are inapplicable
to them; those survive only for helper organizations with a pre-mapped depot.

Against decimal coordinates, PACK10 saves 7 characters (41%) and is more precise. Against geohash it
costs one extra character but requires no library on either side — `Long.toString(n, 36)` in Kotlin
and `int(s, 36)` in Python are both built in, which removes an entire class of cross-language
alphabet-mismatch bug. Against hex, it is 6 characters shorter, and hex's 1.1 cm precision is
meaningless against 3–5 m civilian GPS error.

1.1 m is building-corner precision, which is the resolution a search-and-rescue team actually needs.

### 6.3 Optional Accuracy Character

An 11th character may be appended to encode GPS fix quality. Recommended.

| Code | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 9 |
|---|---|---|---|---|---|---|---|---|
| Accuracy | <5 m | <10 m | <25 m | <50 m | <100 m | <500 m | <1 km | Unknown / last known |

It lets the admin portal draw an uncertainty circle, and lets triage discount a fix taken indoors.

### 6.4 GEO Field Disambiguation

The decoder examines the GEO field in this order:

| Condition | Interpretation |
|---|---|
| Contains `,` or `.` | Decimal coordinates (sms.md §29 P2) |
| Starts with `GEO:` | Geohash (sms.md §29 P3) |
| Starts with `HX:` | Hex coordinates (sms.md §30, deprecated) |
| Length 10 or 11, all base-36 | **PACK10** (with optional accuracy char) |
| Length 2–4 and present in the location code table | Location code (sms.md §29 P1) |
| Otherwise | Error `UNKNOWN_LOC` |

---

## 7. Worked Examples

Every frame below was generated by the reference implementation. **Checksums are real, not
illustrative** — they can be recomputed with the XOR rule in `sms.md` §24.

### Example 1 — "Trapped in a collapsed building, 4 of us, one badly hurt, need medical and water"

| UI selection | Dimension | Code |
|---|---|---|
| Building collapse | S | `5` |
| 3–4 people | P | `2` |
| One seriously injured, stable | I | `2` |
| Trapped in debris | B | `3` |
| Critical | U | `C` |
| Water + Medical supplies + Rescue | N | bits 1,2,7 = 2+4+128 = 134 → `03Q` |
| None | X | `0` |

Payload `15223C03Q0`, position 23.25991, 77.41263 → `6QR6VFBQ33`

```text
Q|001|7F3K|15223C03Q0|6QR6VFBQ33|7F
```

35 characters. Decoded:

```json
{
  "status": "accepted",
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

### Example 2 — Flood, family of 6 stranded on a roof, food + water + baby supplies, toddler present

Payload `10302H0SJ1` — flood `0`, 5–9 people `3`, no injury `0`, stranded `2`, high `H`,
needs bits 0,1,10 = 1+2+1024 = 1027 → `0SJ`, vulnerability bit 0 → `1`.

```text
Q|002|A19P|10302H0SJ1|6QR9WFBPT0|71
```

35 characters. Position 23.26100, 77.40900.

### Example 3 — Displacement site, 200–499 people, tents + blankets + hygiene + water, elderly present

Payload `1A800M0364` — displaced `A`, 200–499 `8`, no injury `0`, free and mobile `0`, medium `M`,
needs bits 1,4,5,6 = 2+16+32+64 = 114 → `036`, vulnerability bit 2 → `4`.

```text
Q|003|C4M2|1A800M0364|728B2FBADG|65
```

35 characters. Position 28.61390, 77.20900.

Fan-out for the matching agent at `people_est` 300: 300 water kits, 75 tents, 300 blankets,
150 hygiene kits.

### Example 4 — NGO offers food, water, medical, hygiene; 200–499 units; 50 km; 2–4 h; available

Payload `2101Z542A` — NGO `1`, resources bits 0,1,2,6 = 1+2+4+64 = 71 → `01Z`, capacity `5`,
radius `4`, ETA `2`, available `A`.

```text
G|014|N001|2101Z542A|728B2FBADG|2C
```

34 characters.

### Example 5 — Hospital offers medical kits and medical teams; 10–24; 25 km; 1–2 h; limited; pre-mapped depot

Payload `2400C131L` — hospital `4`, resources bits 2,3 = 12 → `00C`, capacity `1`, radius `3`,
ETA `1`, limited `L`. GEO uses a location code instead of PACK10.

```text
G|015|H004|2400C131L|RA|26
```

26 characters.

### Example 6 — Acknowledgement and status update

```text
C|031|7F3K|Q001|1|3|66
S|041|7F3K|Q001|3|3C
```

22 and 20 characters. The first tells the seeker their request was accepted with a helper ETA in
bucket 3 (4–8 hours). The second is the seeker confirming they were helped.

---

## 8. Q to N Fan-Out

This is what lets the new seeker population plug into the existing organization-facing `N` path in
`sms.md` §11 without changing it.

One `Q` message becomes one need record per set needs bit. Quantity is `people_est x factor`,
rounded up.

| Need | Factor | Need | Factor |
|---|---|---|---|
| F food_kits | 1.0 | X rescue_team | 1 (flat) |
| W water_kits | 1.0 | V evac_transport | 0.1 |
| M medical_kits | 0.5, doubled if I >= 3 | P power_kits | 0.1 |
| D medical_teams | 1 flat, doubled if I >= 3 | I infant_kits | 1 per child flag |
| T tents | 0.25 | S search_request | 1 (flat) |
| B blankets | 1.0 | H hygiene_kits | 0.5 |

Priority score handed to the triage agent as a prior:

```text
score = urgency_weight(U) * 10
      + injury(I) * 3
      + trapped_bonus(B in {3,4,5,6} -> 5)
      + popcount(X)
```

This score is a **deterministic prior**, not the final severity. The triage agent (see `agents.md`)
may raise or lower it, but it gives the system a sane ordering even when the LLM is unavailable.

---

## 9. Module Design

### 9.1 Single Source of Truth

```text
shared/codec/pact_tables.v1.json      <-- hand-maintained, committed, the authority
shared/codec/vectors.json             <-- cross-language parity fixtures
```

Structure of `pact_tables.v1.json`:

```json
{
  "schema_version": 1,
  "dimensions": {
    "situation": { "chars": 1, "values": { "0": "flood", "1": "earthquake" } },
    "people":    { "chars": 1, "values": { "0": { "label": "1", "rep": 1 } } },
    "needs":     { "kind": "bitfield", "bits": 12, "chars": 3,
                   "map": [ { "bit": 0, "code": "F", "key": "food_kits", "factor": 1.0 } ] }
  },
  "layouts": {
    "Q": ["version","situation","people","injury","mobility","urgency","needs","vulnerability"],
    "G": ["version","orgtype","resources","capacity","radius","eta","availability"]
  },
  "location_codes": { "RA": "Region A", "RB": "Region B", "RC": "Region C" }
}
```

Distribution, with no build system required:

| Consumer | Mechanism |
|---|---|
| Python | `tables.py` loads the JSON at import and validates that field widths sum to the declared payload length |
| Kotlin | A Gradle `Copy` task syncs the same file into `app/src/main/assets/`; `Tables.kt` parses it once at startup |
| TypeScript | `import tables from "shared/codec/pact_tables.v1.json"` — Next.js resolves JSON natively |

Code generation into Kotlin constants is an optional later hardening step. For the MVP, ship the
runtime-JSON path: a 5-line Gradle copy task eliminates a codegen step that can silently drift.

### 9.2 Python Layout

```text
backend/app/codec/
├── __init__.py       re-exports encode/decode/xor_checksum
├── base36.py         b36_encode(n, width) -> str ; b36_decode(s) -> int
├── geo.py            encode_geo(lat, lon, acc) -> str ; decode_geo(token)
├── tables.py         load_tables() (cached) ; Tables.value(dim, ch) ; Tables.bits(dim, code)
├── payload.py        encode_payload(kind, sel) ; decode_payload(kind, payload)
├── frame.py          xor_checksum(text) ; frame(type, *parts) ; unframe(sms)
├── pact_codec.py     encode_request / encode_offer / decode
├── fanout.py         request_to_needs(decoded) ; priority_score(decoded)
└── errors.py         CodecError + the sms.md §23 error code enum
```

Signatures:

```python
def encode_request(sel: RequestSelection, lat: float, lon: float, uid: str, seq: int,
                   accuracy_m: float | None = None) -> str: ...

def encode_offer(sel: OfferSelection, uid: str, seq: int,
                 lat: float | None = None, lon: float | None = None,
                 location_code: str | None = None) -> str: ...

def decode(sms: str) -> dict: ...        # returns {"status": "accepted"|"error", ...}; never raises

def encode_geo(lat: float, lon: float, accuracy_m: float | None = None) -> str: ...
def decode_geo(token: str) -> tuple[float, float, float | None] | None: ...
def xor_checksum(text: str) -> str: ...  # byte-identical to the existing implementation
```

Decoder dispatch order: `Q` → `G` → legacy 6-field `N` → canonical 8-field `N` → other `sms.md`
types → `UNKNOWN_TYPE`. The legacy branches are preserved verbatim so nothing that works today
regresses.

### 9.3 Kotlin Mirror

```text
android/app/src/main/java/org/pact/codec/
├── Base36.kt      encode(n: Long, width: Int): String ; decode(s: String): Long
├── GeoCodec.kt    encode(lat, lon, accM): String ; decode(tok): GeoPoint?
├── Tables.kt      load(ctx) ; label(dim, ch): String?
├── Payload.kt     encodePayload(kind: Char, sel: Selection): String
├── SmsFrame.kt    xorChecksum(t: String): String ; frame(type: Char, vararg p: String): String
├── PactCodec.kt   encodeRequest(...) ; encodeOffer(...) ; decode(sms): DecodeResult
└── Transport.kt   suspend fun send(payload: String)
```

`Transport.send` is the **only** place in the app where connectivity is considered. It tries
`POST /api/v1/pact/ingest`; on timeout or no network it calls
`SmsManager.sendTextMessage(gateway, null, payload, sentPI, null)` and persists to a Room outbox for
replay when data returns. The UI never knows which path was taken.

The request screen is literally the §3.1 tables rendered as chip groups — one row of single-select
chips per dimension, multi-select chip groups for needs and vulnerabilities. **There is no
`EditText` anywhere in the request flow.**

### 9.4 Parity Testing

`shared/codec/vectors.json` holds roughly 30 rows of
`{selection, lat, lon, seq, uid, expected_sms}`, including all six worked examples above.

- Python runs them under pytest.
- Kotlin runs them in a JVM unit test reading the same file from assets.

Any encoder divergence between the two languages fails immediately in CI instead of at demo time.
This costs about twenty minutes to set up and is the single highest-value test in the project.

---

## 10. Failure Modes

| Failure | Detection | Decoder behaviour | Recovery |
|---|---|---|---|
| Unknown code character | Table lookup miss | Emit `UNKNOWN_CODE`, set that field to `null`, but **still accept the message** if urgency, geo, and at least one need decoded | Partial decode is deliberate. A request with one garbled field is still a person who needs rescue. The portal flags it `degraded` |
| Unknown schema version | Position 0 not in `{1,2}` | Reject, `BAD_SCHEMA` | Reply `E\|SEQ\|BAD_SCHEMA\|...`; app prompts the user to update |
| Bad checksum | Recompute XOR over everything before the final `\|` | Reject per `sms.md` §24; do not enqueue to the pipeline | Reply `E\|SEQ\|BAD_CRC\|...`; the app retries once, then falls back to a plain-language SMS to a human operator number |
| Truncated message | Field count below expected, or payload length not 10/9, or GEO length not in `{2,3,4,10,11}` | Reject, `TRUNCATED` | Truncation almost always fails CRC too, so CRC is the primary net |
| Duplicate sequence | Dedupe on `(uid, seq)`, MongoDB TTL index, 24 h | Drop silently, reply `C\|SEQ\|<seq>\|DUP\|...` per `sms.md` §25 | Idempotent, so the app's retry-until-acknowledged loop is safe |
| Sequence reset after reinstall | Seq restarts at 001 | The dedupe key includes UID, and UID changes on reinstall | Acceptable. A genuine 999-wrap within 24 h is out of scope |
| Multi-part message | Not applicable — `Q`/`G` are ~35 chars, single-part by construction | A `Q`/`G` frame over 140 chars is rejected `TOO_LONG` | **Do not build reassembly for Q/G.** Multi-part remains a `P` polygon concern only (`sms.md` §21) |
| Out-of-range GPS | `abs(lat) > 90` or `abs(lon) > 180` after decode | `BAD_GEO`, coordinates nulled, **message still accepted** | Portal shows it in a "location unknown" tray; the operator can call the MSISDN |
| No GPS fix at send time | App side | Send last known position with accuracy character `9`, or `--` if never fixed | **Never block the send on a GPS fix.** A request with no coordinates still beats no request |
| Lowercase or padded input from a gateway | Before parse | `.strip().upper()` on the whole frame; base-36 is case-insensitive | Transparent |
| Table drift between Python and Kotlin | `vectors.json` parity test | Build fails | Caught before the demo, not during it |

---

## 11. Privacy Properties

The codec contributes directly to the privacy model described in `memory_draft.md`.

| Property | How the codec provides it |
|---|---|
| No personal data on the wire | Closed vocabulary; no free-text field exists to leak into |
| Pseudonymous sender | 4-character UID derived from a device hash, not a phone number |
| Contact details stay off the wire | Name and phone are collected once at sign-up but live only in the database, encrypted, and are released only on helper acceptance |
| Minimal disclosure | Buckets rather than exact counts; the wire carries only what allocation needs |
| Coarse location on demand | PACK10 can be truncated to 3 characters per axis by the privacy filter before reaching a non-rescue audience |
| Integrity | XOR checksum per `sms.md` §24 detects corruption in transit |

The codec does **not** provide confidentiality. SMS is plaintext over the operator network. This is
accepted for the MVP and is why the vocabulary is designed so that an intercepted message reveals a
situation and a location but never an identity.

---

## 12. Implementation Order

| Step | Task | Estimate |
|---|---|---|
| 1 | Write `pact_tables.v1.json` and `vectors.json` with the six worked examples | 45 min |
| 2 | Python `base36.py`, `geo.py`, `frame.py`, plus pytest against the vectors | 45 min |
| 3 | Python `payload.py` and `pact_codec.decode`, including the legacy fallback chain | 60 min |
| 4 | `fanout.py`, feeding the agent pipeline | 30 min |
| 5 | Kotlin mirror plus the JVM parity test on the same vectors | 60 min |
| 6 | Android chip-group request screen and `Transport.send` | 60 min |
| 7 | Admin portal SMS simulator: paste a `Q` string, watch it decode and fan out | 30 min |

---

## 13. Demo Note

The beat that lands with judges:

> Show the app. Tap six chips. Hold up the resulting **35 characters** next to the 160-character SMS
> limit. Then switch the phone to airplane mode and send the identical string over SMS instead of
> HTTP, and watch the same request appear in the portal.

One wire format, two transports. That is the whole point of this document.
