"""Q to N fan-out (codec.md section 8).

One seeker request becomes one sms.md-shaped need record per set needs bit, so
the new population plugs into the existing organization-facing path without
changing it.

The priority score here is a DETERMINISTIC PRIOR, not the final severity. The
triage agent may raise or lower it, but it gives the system a sane ordering even
when Groq is unavailable.
"""

from __future__ import annotations

import math
from typing import Any

from app.codec.tables import get_tables

TRAPPED_BONUS = 5


def request_to_needs(decoded: dict[str, Any]) -> list[dict[str, Any]]:
    t = get_tables()
    codes = decoded.get("_codes", {})

    people = decoded.get("people_est") or 1
    injury_code = codes.get("injury_code", "0")
    injury_rank = t.dim("injury").get("rank", {}).get(injury_code, 0)
    child_flags = sum(1 for v in decoded.get("vulnerability", [])
                      if v in ("child_under_5", "pregnant_nursing"))

    out: list[dict[str, Any]] = []
    for entry in t.bit_map("needs"):
        if entry["key"] not in decoded.get("needs", []):
            continue

        if entry.get("per_child_flag"):
            qty = max(1, child_flags) * people if child_flags else people
        elif entry.get("flat"):
            qty = int(entry["factor"])
        else:
            qty = math.ceil(people * entry["factor"])

        threshold = entry.get("double_if_injury_ge")
        if threshold is not None and injury_rank >= threshold:
            qty *= 2

        out.append({
            "resource": entry["key"],
            "code": entry["code"],
            "quantity": max(1, int(qty)),
            "urgency": decoded.get("urgency", "medium"),
            "location_code": decoded.get("location_code"),
            "latitude": decoded.get("latitude"),
            "longitude": decoded.get("longitude"),
            "source": decoded.get("source", "sms"),
            "uid": decoded.get("uid"),
        })
    return out


def priority_score(decoded: dict[str, Any]) -> int:
    t = get_tables()
    codes = decoded.get("_codes", {})

    urgency_code = codes.get("urgency_code", "M")
    weight = t.dim("urgency").get("weight", {}).get(urgency_code, 2)

    injury_code = codes.get("injury_code", "0")
    injury_rank = t.dim("injury").get("rank", {}).get(injury_code, 0)

    mobility_code = codes.get("mobility_code", "0")
    trapped = mobility_code in t.dim("mobility").get("trapped", [])

    return (weight * 10
            + injury_rank * 3
            + (TRAPPED_BONUS if trapped else 0)
            + len(decoded.get("vulnerability", [])))
