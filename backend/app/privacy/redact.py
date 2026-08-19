"""A7 -- the redactor. Walks a payload and applies policy.GRANTS.

Three guarantees this file is responsible for:

1. **It returns a new object.** The bus hands the same envelope dict to every
   subscriber. Mutating it in place would redact the admin's copy too, and the
   bug would look like a rendering fault rather than a privacy failure.
2. **HIDDEN removes the key.** Setting it to None leaves a hole that looks
   like missing data; removing it makes the redaction visible in the payload.
3. **It reports what it did.** `audit()` returns measured counts from the
   actual object, which is what A7 publishes. A hardcoded "withheld" list was
   the previous implementation and it was worth nothing.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from app.privacy import crypto, policy
from app.privacy.policy import FULL, HIDDEN, MASKED, OWN

_SENTINEL = object()

# ---------------------------------------------------------------------------
# Free-text scrubbing
# ---------------------------------------------------------------------------
# Coordinate pairs: "23.25991, 77.41263", "23.25991,77.41263", "lat 23.25991".
# Requires 3+ decimal places, so "80% coverage in 55.5 minutes" is left alone.
_COORD_PAIR = re.compile(
    r"[-+]?\d{1,3}\.\d{3,}\s*[,/]\s*[-+]?\d{1,3}\.\d{3,}")
_COORD_ONE = re.compile(r"[-+]?\d{1,3}\.\d{4,}")
# 8+ consecutive digits, optionally with separators: a phone number or an id.
_PHONE_LIKE = re.compile(r"(?<!\d)(?:\+?\d[\s\-]?){8,}\d(?!\d)")


def scrub_text(text: str, *, coords: bool = True, contact: bool = True) -> str:
    """Remove position and contact shapes from prose.

    Deliberately blunt. Over-redacting a narrator sentence costs a little
    readability; under-redacting one publishes a rescue target's exact
    position to an audience that has not been granted it.
    """
    if not text:
        return text
    if coords:
        text = _COORD_PAIR.sub("[approx. area]", text)
        text = _COORD_ONE.sub("[approx.]", text)
    if contact:
        text = _PHONE_LIKE.sub("[contact withheld]", text)
    return text


# ---------------------------------------------------------------------------
# Path walking
# ---------------------------------------------------------------------------

def _steps(path: str) -> list[tuple[str, bool]]:
    """"options[].allocations[].name" -> [("options", True), ("allocations", True), ("name", False)]"""
    out: list[tuple[str, bool]] = []
    for part in path.split("."):
        if part.endswith("[]"):
            out.append((part[:-2], True))
        else:
            out.append((part, False))
    return out


def _apply(node: Any, steps: list[tuple[str, bool]], fn) -> int:
    """Descend and call fn(container, key) at each leaf. Returns hit count.

    Missing intermediate keys are skipped silently: one PATHS table covers
    every event type, so most paths miss on most events.
    """
    if not isinstance(node, dict):
        return 0
    key, fanout = steps[0]
    if key not in node:
        return 0

    if len(steps) == 1:
        if fanout:
            # Terminal fan-out, e.g. "evidence[]": the list itself is the leaf.
            return fn(node, key)
        return fn(node, key)

    child = node[key]
    hits = 0
    if fanout:
        if not isinstance(child, list):
            return 0
        for item in child:
            hits += _apply(item, steps[1:], fn)
    else:
        hits += _apply(child, steps[1:], fn)
    return hits


def _remove(container: dict, key: str) -> int:
    container.pop(key, None)
    return 1


def _mask_value(container: dict, key: str) -> int:
    """Type-directed masking. The path table says *which* fields are sensitive;
    the value's own shape says *how* to blunt it."""
    v = container.get(key, _SENTINEL)
    if v is _SENTINEL or v is None:
        return 0

    if key in ("lat", "latitude"):
        container[key] = round(float(v), crypto.MASK_DECIMALS)
    elif key in ("lon", "lng", "longitude"):
        container[key] = round(float(v), crypto.MASK_DECIMALS)
    elif key in ("near", "coordinates") and isinstance(v, (list, tuple)) and len(v) >= 2:
        # GeoJSON order: [lng, lat]
        container[key] = [round(float(v[0]), crypto.MASK_DECIMALS),
                          round(float(v[1]), crypto.MASK_DECIMALS)]
    elif key in ("name", "seeker_name", "name_enc", "target_masked"):
        container[key] = crypto.mask_name(crypto.decrypt(v) if isinstance(v, str) else v)
    elif key in ("phone", "contact", "phone_enc", "from_number"):
        container[key] = crypto.mask_phone(crypto.decrypt(v) if isinstance(v, str) else v)
    elif key == "uid":
        container[key] = crypto.mask_uid(v)
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        # Coarsen a quantity or a score into a band rather than deleting it:
        # an organization can still see that a rival held "some" stock without
        # learning how much.
        container[key] = _band(v)
    elif isinstance(v, str):
        container[key] = "•" * min(len(v), 8)
    else:
        container.pop(key, None)
    return 1


def _band(v: float) -> str:
    n = abs(float(v))
    if n <= 1:
        return "<=1"
    for edge in (5, 10, 25, 50, 100, 250, 500):
        if n <= edge:
            return f"<={edge}"
    return ">500"


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------

def _walk_keys(node: Any, keys: frozenset[str], fn, depth: int = 0) -> int:
    """Apply fn to every matching key name at any depth.

    Recursion is bounded: a cyclic or pathological payload must not be able to
    stall the pipeline from inside the privacy tier.
    """
    if depth > 12:
        return 0
    hits = 0
    if isinstance(node, dict):
        for k in [k for k in node if k in keys]:
            hits += fn(node, k)
        for v in list(node.values()):
            if isinstance(v, (dict, list)):
                hits += _walk_keys(v, keys, fn, depth + 1)
    elif isinstance(node, list):
        for v in node:
            if isinstance(v, (dict, list)):
                hits += _walk_keys(v, keys, fn, depth + 1)
    return hits


def _walk_scoped(node: Any, container: str, keys: frozenset[str], fn,
                 depth: int = 0, inside: bool = False) -> int:
    """Apply fn to `keys`, but only inside a dict reached through `container`.

    `name` means the helper organization on an allocation and the rescue target
    under `seeker`. Only the enclosing container tells them apart.
    """
    if depth > 12:
        return 0
    hits = 0
    if isinstance(node, dict):
        if inside:
            for k in [k for k in node if k in keys]:
                hits += fn(node, k)
        for k, v in list(node.items()):
            if isinstance(v, (dict, list)):
                hits += _walk_scoped(v, container, keys, fn, depth + 1,
                                     inside or k == container)
    elif isinstance(node, list):
        for v in node:
            if isinstance(v, (dict, list)):
                hits += _walk_scoped(v, container, keys, fn, depth + 1, inside)
    return hits


def project(obj: dict[str, Any], audience: str, *,
            owned: bool = False, counts: dict[str, int] | None = None) -> dict[str, Any]:
    """Apply the field matrix to one payload dict. Returns a redacted copy.

    `owned` resolves the OWN grant: True when this record belongs to the
    audience member (their own allocation, their own request), False otherwise.

    Two passes, deliberately: unambiguous key names are redacted wherever they
    appear, then the structural paths catch position-dependent fields. The key
    pass is the one that fails safe when a payload changes shape.
    """
    out = copy.deepcopy(obj)
    for field in policy.FIELDS:
        g = policy.grant(audience, field)
        if g == FULL:
            continue
        if g == OWN:
            if owned:
                continue
            g = MASKED
        fn = _remove if g == HIDDEN else _mask_value
        n = 0
        keys = policy.KEYS.get(field)
        if keys:
            n += _walk_keys(out, keys, fn)
        for container, scoped in policy.SCOPED_KEYS.get(field, {}).items():
            n += _walk_scoped(out, container, scoped, fn)
        for path in policy.PATHS.get(field, ()):
            n += _apply(out, _steps(path), fn)
        if counts is not None and n:
            counts[field] = counts.get(field, 0) + n

    # Third pass: free text. The matrix above can only reach structured
    # fields, and A9 writes prose -- a coordinate pair inside a narrator
    # sentence is invisible to a path table.
    loc_full = policy.grant(audience, "seeker_loc") == FULL or (
        policy.grant(audience, "seeker_loc") == OWN and owned)
    contact_full = policy.grant(audience, "seeker_contact") == FULL or (
        policy.grant(audience, "seeker_contact") == OWN and owned)
    if not (loc_full and contact_full):
        scrubbed = _scrub_tree(out, coords=not loc_full, contact=not contact_full)
        if counts is not None and scrubbed:
            counts["free_text"] = counts.get("free_text", 0) + scrubbed
    return out


def _scrub_tree(node: Any, *, coords: bool, contact: bool, depth: int = 0) -> int:
    if depth > 12:
        return 0
    hits = 0
    if isinstance(node, dict):
        for k, v in list(node.items()):
            if isinstance(v, str) and k in policy.TEXT_FIELDS:
                cleaned = scrub_text(v, coords=coords, contact=contact)
                if cleaned != v:
                    node[k] = cleaned
                    hits += 1
            elif isinstance(v, (dict, list)):
                hits += _scrub_tree(v, coords=coords, contact=contact, depth=depth + 1)
    elif isinstance(node, list):
        for v in node:
            if isinstance(v, (dict, list)):
                hits += _scrub_tree(v, coords=coords, contact=contact, depth=depth + 1)
    return hits


def project_event(ev: dict[str, Any], audience: str, *,
                  owned: bool = False) -> dict[str, Any] | None:
    """One bus envelope -> one audience's view, or None if the whole event is
    withheld.

    Dropping the event type comes first. Field redaction alone would still
    leak the *existence* of a cross-organization debate, and per
    memory_draft.md 7.5 that existence is itself a disclosure.
    """
    if audience == policy.ADMIN:              # unrestricted, and only by name
        return ev
    # Fail closed. `VISIBLE_TYPES.get()` returning None for an unknown audience
    # used to be indistinguishable from admin's unrestricted sentinel, so a
    # typo in an audience name handed out the full deliberation stream.
    allowed = policy.VISIBLE_TYPES.get(audience)
    if allowed is None:
        allowed = policy.VISIBLE_TYPES[policy.SMS]
    if ev.get("type") not in allowed:
        return None
    if ev.get("agent") in policy.INTERNAL_AGENTS and ev.get("type") == "agent.message":
        return None

    out = {k: ev[k] for k in policy.ENVELOPE_KEEP if k in ev}
    out["payload"] = project(ev.get("payload") or {}, audience, owned=owned)
    out["redacted_for"] = audience
    return out


def project_record(doc: dict[str, Any], audience: str, *,
                   owned: bool = False) -> dict[str, Any]:
    """Same matrix over a database document (a request, a match). Mongo's
    _id and internal bookkeeping are dropped for every non-admin audience."""
    out = project(doc, audience, owned=owned)
    if audience != policy.ADMIN:
        for k in ("_id", "raw_code", "decoded", "loc", "run_id", "option_id"):
            out.pop(k, None)
    return out


# ---------------------------------------------------------------------------
# Measurement -- what A7 publishes
# ---------------------------------------------------------------------------

def audit(obj: dict[str, Any], audience: str, *, owned: bool = False) -> dict[str, Any]:
    """Run the projection and report what it actually removed from THIS object.

    Every number here is counted off the real payload. That is the difference
    between this and the fixed `withheld: [name, phone, exact_loc]` list it
    replaces: if the redactor stopped matching a path, the count drops and the
    portal shows it.
    """
    counts: dict[str, int] = {}
    project(obj, audience, owned=owned, counts=counts)

    withheld = [f for f in policy.FIELDS if policy.grant(audience, f) == HIDDEN]
    masked = [f for f in policy.FIELDS
              if policy.grant(audience, f) == MASKED
              or (policy.grant(audience, f) == OWN and not owned)]
    shared = [f for f in policy.FIELDS
              if policy.grant(audience, f) == FULL
              or (policy.grant(audience, f) == OWN and owned)]

    return {
        "audience": audience,
        "shared": shared,
        "withheld": withheld,
        "masked": masked,
        "fields_touched": sum(counts.values()),
        "by_field": counts,
        "event_types_blocked": sorted(policy.blocked_types(audience)),
    }


def audit_all(obj: dict[str, Any], audiences=("helper_pre", "org", "sms")) -> dict[str, Any]:
    """The per-audience projection A7 reports for one committed allocation."""
    return {a: audit(obj, a) for a in audiences}
