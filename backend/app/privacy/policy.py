"""The audience x field matrix. Data only -- no logic lives in this file.

This is the whole point of A7 being deterministic: the policy is a table you
can read, diff, and put on a slide. A reviewer can check what an organization
is allowed to see without reading any code, and without trusting that a model
stayed discreet.

Transcribed from agents.md 2.7 and memory_draft.md 7.5 / 8.1.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Audiences
# ---------------------------------------------------------------------------
# helper_pre and helper_post are the SAME person either side of the acceptance
# transition. Splitting them into two audiences is what makes revelation a
# state change rather than a UI toggle (memory_draft.md 8.3).

ADMIN = "admin"
ORG = "org"
HELPER_PRE = "helper_pre"
HELPER_POST = "helper_post"
SEEKER = "seeker"
SMS = "sms"

AUDIENCES = (ADMIN, ORG, HELPER_PRE, HELPER_POST, SEEKER, SMS)

# ---------------------------------------------------------------------------
# Grants
# ---------------------------------------------------------------------------
# FULL    pass the value through untouched
# MASKED  replace with a lossy form (crypto.mask_*)
# OWN     pass through only when the record belongs to this audience member,
#         otherwise mask
# HIDDEN  remove the key entirely -- not null it, remove it, so its absence is
#         visible in the payload rather than looking like missing data

FULL, MASKED, OWN, HIDDEN = "full", "masked", "own", "hidden"

GRANTS: dict[str, dict[str, str]] = {
    #                     seeker_loc  seeker_contact seeker_name  helper_id  other_stock  debate   justification delivery_code  triage_internals
    ADMIN:       {"seeker_loc": FULL,   "seeker_contact": FULL,   "seeker_name": FULL,   "helper_identity": FULL,   "other_org_stock": FULL,   "debate": FULL,   "justification": FULL,    "delivery_code": FULL,   "triage_internals": FULL},
    ORG:         {"seeker_loc": MASKED, "seeker_contact": HIDDEN, "seeker_name": HIDDEN, "helper_identity": OWN,    "other_org_stock": HIDDEN, "debate": HIDDEN, "justification": FULL,    "delivery_code": HIDDEN, "triage_internals": MASKED},
    HELPER_PRE:  {"seeker_loc": MASKED, "seeker_contact": HIDDEN, "seeker_name": HIDDEN, "helper_identity": OWN,    "other_org_stock": HIDDEN, "debate": HIDDEN, "justification": FULL,    "delivery_code": HIDDEN, "triage_internals": MASKED},
    HELPER_POST: {"seeker_loc": FULL,   "seeker_contact": FULL,   "seeker_name": FULL,   "helper_identity": OWN,    "other_org_stock": HIDDEN, "debate": HIDDEN, "justification": FULL,    "delivery_code": FULL,   "triage_internals": MASKED},
    SEEKER:      {"seeker_loc": OWN,    "seeker_contact": OWN,    "seeker_name": OWN,    "helper_identity": MASKED, "other_org_stock": HIDDEN, "debate": HIDDEN, "justification": MASKED,  "delivery_code": FULL,   "triage_internals": HIDDEN},
    # SMS is plaintext over the operator network (memory_draft.md 8.4). It is
    # the strictest audience in the system and carries no personal data at all.
    SMS:         {"seeker_loc": MASKED, "seeker_contact": HIDDEN, "seeker_name": HIDDEN, "helper_identity": HIDDEN, "other_org_stock": HIDDEN, "debate": HIDDEN, "justification": MASKED,  "delivery_code": FULL,   "triage_internals": HIDDEN},
}

FIELDS = tuple(GRANTS[ADMIN].keys())

# ---------------------------------------------------------------------------
# Free-text fields
# ---------------------------------------------------------------------------
# A9 writes prose, and prose is where the field matrix has no purchase: a
# structured `lat` is easy to mask, "deliver to 23.25991, 77.41263" is not.
#
# The narrator's system prompt does say "never include the seeker's name,
# phone number, or exact coordinates" -- but that is asking a model to be
# discreet, which agents.md 2.1 gives as the exact reason A7 is deterministic.
# So every one of these fields is scrubbed by regex on the way out.

TEXT_FIELDS: frozenset[str] = frozenset({
    "message", "justification", "admin_summary", "helper_message", "sms_variant",
    "text", "claim", "reasoning", "detail", "note", "dissent", "argument",
    "masked_summary",
})

# ---------------------------------------------------------------------------
# Key-name rules -- applied recursively, at any depth
# ---------------------------------------------------------------------------
# PATHS below is exact and auditable, and that is also its weakness: it only
# redacts where it was told to look. A payload that nests the same data one
# level deeper than the table expects sails straight through.
#
# That is not hypothetical. GET /helpers/me/assignments returned the seeker's
# exact GPS to a helper who had not yet accepted, because the table covered
# "request.lat" and the row put it at "seeker.lat".
#
# So these key names are redacted WHEREVER they appear. They are unambiguous:
# a key called `phone` is a phone number in any payload shape. Ambiguous keys
# that depend on position -- `free`, `qty`, `name` -- stay in PATHS.

KEYS: dict[str, frozenset[str]] = {
    "seeker_loc": frozenset({
        "lat", "latitude", "lon", "lng", "longitude", "exact_loc", "raw_code",
    }),
    "seeker_contact": frozenset({"phone", "contact", "phone_enc", "from_number", "msisdn"}),
    "seeker_name": frozenset({"name_enc", "seeker_name", "uid", "seeker_uid"}),
    "delivery_code": frozenset({"delivery_code"}),
}

# Keys that are only sensitive inside a particular container.
#
# `name` cannot go in KEYS above: an allocation's `name` is the *helper*
# organization, which the helper is entitled to see, while `seeker.name` is the
# person they are being sent to. Same key, two different subjects. Scoping by
# the enclosing container is what separates them.
#
# This was a live leak: once sign-up existed and seekers actually had names,
# the pre-acceptance assignment list returned "Anita Sharma" in full. While the
# field was always null the tests passed vacuously.

SCOPED_KEYS: dict[str, dict[str, frozenset[str]]] = {
    "seeker_name": {
        "seeker": frozenset({"name"}),
        "request": frozenset({"name"}),
        "seekers": frozenset({"name"}),
    },
}

# ---------------------------------------------------------------------------
# Where each field actually appears
# ---------------------------------------------------------------------------
# Dotted paths into a bus envelope. "[]" means "every element of this list".
# A path that does not exist in a given event is simply skipped, so one table
# covers every event type.
#
# Keeping this list honest is the maintenance cost of a deterministic
# redactor. redact.audit() reports what it actually removed from a real
# payload, so a path that stops matching shows up as a drop in the count
# rather than as a silent leak.

PATHS: dict[str, tuple[str, ...]] = {
    "seeker_loc": (
        "request.lat", "request.lon",
        "request.decoded.latitude", "request.decoded.longitude",
        "request.decoded.geo", "request.raw_code", "request.decoded._raw",
        "args.near",                          # a3_geo's $geoNear tool_call
        "loc.coordinates", "exact_loc",
    ),
    "seeker_contact": (
        "request.phone", "request.from_number", "contact", "phone", "phone_enc",
        "request.decoded.phone",
    ),
    "seeker_name": (
        "request.name", "name", "name_enc", "seeker_name", "request.uid", "uid",
    ),
    "helper_identity": (
        "allocations[].name", "allocations[].owner_id", "allocations[].offer_id",
        "structured.candidates[].name", "structured.candidates[].owner_id",
        "structured.candidates[].offer_id",
        "options[].allocations[].name", "options[].allocations[].owner_id",
        "options[].allocations[].offer_id",
        "target_masked", "assigned_helper_id",
    ),
    "other_org_stock": (
        "structured.candidates[].free", "structured.candidates[].reliability",
        "structured.candidates[].capacity_load", "structured.candidates[].distance_km",
        "options[].allocations[].qty", "options[].score", "options[].coverage_pct",
    ),
    "debate": (
        "claim", "evidence", "dissent", "turns", "argument", "delta",
        "advocate_bids", "participants", "topic",
    ),
    "justification": ("justification", "reasoning", "admin_summary", "note"),
    "delivery_code": ("delivery_code",),
    "triage_internals": (
        "structured.severity", "structured.confidence", "structured.escalations",
        "structured.time_to_harm_hours", "structured.life_threat",
        "triage.severity", "triage.confidence", "triage.escalations",
        "confidence",
    ),
}

# ---------------------------------------------------------------------------
# Event-type visibility
# ---------------------------------------------------------------------------
# Field redaction is not sufficient on its own. An organization must never see
# that a cross-organization debate happened at all -- the existence of the
# argument is itself the disclosure (memory_draft.md 7.5). So whole event types
# are dropped before any field walk runs.

_DEBATE_TYPES = frozenset({
    "debate.opened", "debate.turn", "debate.closed",
    "options.proposed", "agent.token", "agent.thinking",
})

# The full registry from agents.md 3.2. Kept here so blocked_types() can be
# computed as a complement rather than hand-listed in two places and drifting.
ALL_TYPES = frozenset({
    "run.started", "agent.entered", "agent.thinking", "agent.token",
    "agent.message", "agent.tool_call", "debate.opened", "debate.turn",
    "debate.closed", "options.proposed", "decision.proposed", "awaiting_admin",
    "admin.action", "decision.committed", "privacy.reveal", "notify.sent",
    "verify.result", "replan.triggered", "run.completed", "error",
})

# Types each audience may receive. Admin is unrestricted, expressed as None.
VISIBLE_TYPES: dict[str, frozenset[str] | None] = {
    ADMIN: None,
    ORG: frozenset({
        "run.started", "agent.entered", "agent.message", "decision.committed",
        "privacy.reveal", "notify.sent", "verify.result", "replan.triggered",
        "run.completed", "error",
    }),
    HELPER_PRE: frozenset({
        "decision.committed", "notify.sent", "privacy.reveal", "verify.result",
    }),
    HELPER_POST: frozenset({
        "decision.committed", "notify.sent", "privacy.reveal", "verify.result",
        "replan.triggered",
    }),
    SEEKER: frozenset({
        "run.started", "decision.committed", "privacy.reveal", "verify.result",
        "run.completed",
    }),
    SMS: frozenset({"decision.committed", "verify.result"}),
}

# Agents whose output is internal deliberation regardless of the event type it
# arrives on. a4/a6 emit agent.message too, and that message is the debate.
INTERNAL_AGENTS = frozenset({"a4_advocates", "a6_arbiter", "a5_solver", "a2_triage"})

# Envelope keys every audience keeps. Everything else in the envelope is
# routing metadata that non-admin audiences have no use for.
ENVELOPE_KEEP = ("v", "seq", "ts", "trace_id", "type", "agent", "payload")


def blocked_types(audience: str) -> frozenset[str]:
    """Event types this audience will never receive. Used by the /ws/org
    filter and by the portal's privacy panel to show the boundary."""
    if audience == ADMIN:
        return frozenset()
    # Unknown audience falls back to the strictest allow-list, never to "block
    # nothing". See the matching guard in redact.project_event.
    return ALL_TYPES - VISIBLE_TYPES.get(audience, VISIBLE_TYPES[SMS])


def grant(audience: str, field: str) -> str:
    return GRANTS.get(audience, GRANTS[SMS]).get(field, HIDDEN)
