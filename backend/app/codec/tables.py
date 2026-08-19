"""Loads shared/codec/pact_tables.v1.json -- the one source of truth shared with
the Kotlin app and the web simulator.

Validated at import: if declared field widths do not sum to the declared payload
length, that is a spec bug and must fail loudly at startup, not silently produce
garbage on a field boundary at 3 a.m.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

# backend/app/codec/tables.py -> repo root -> shared/codec/
_DEFAULT = Path(__file__).resolve().parents[3] / "shared" / "codec" / "pact_tables.v1.json"


@dataclass(frozen=True)
class Tables:
    raw: dict[str, Any]

    @property
    def schema_version(self) -> int:
        return self.raw["schema_version"]

    @property
    def layouts(self) -> dict[str, Any]:
        return self.raw["layouts"]

    @property
    def dimensions(self) -> dict[str, Any]:
        return self.raw["dimensions"]

    @property
    def accuracy(self) -> dict[str, float | None]:
        return self.raw["accuracy"]

    @property
    def status_codes(self) -> dict[str, str]:
        return self.raw["status_codes"]

    @property
    def location_codes(self) -> dict[str, str]:
        return self.raw["location_codes"]

    def dim(self, name: str) -> dict[str, Any]:
        d = self.dimensions[name]
        while d.get("kind") == "alias":          # resources -> needs
            d = self.dimensions[d["of"]]
        return d

    def value(self, dim: str, ch: str) -> str | None:
        """Enum label, or None when the character is not in the table."""
        d = self.dim(dim)
        v = d["values"].get(ch)
        if v is None:
            return None
        return v if isinstance(v, str) else v.get("label")

    def rep(self, dim: str, ch: str) -> int | None:
        """Integer representative for a bucket dimension."""
        v = self.dim(dim)["values"].get(ch)
        return v.get("rep") if isinstance(v, dict) else None

    def bit_map(self, dim: str) -> list[dict[str, Any]]:
        return self.dim(dim)["map"]

    def keys_from_bits(self, dim: str, value: int) -> list[str]:
        return [e["key"] for e in self.bit_map(dim) if value >> e["bit"] & 1]

    def bits_from_keys(self, dim: str, keys: list[str]) -> int:
        wanted = set(keys)
        out = 0
        for e in self.bit_map(dim):
            if e["key"] in wanted or e.get("code") in wanted:
                out |= 1 << e["bit"]
        return out


def _validate(raw: dict[str, Any]) -> None:
    for kind, layout in raw["layouts"].items():
        total = sum(f["chars"] for f in layout["fields"])
        if total != layout["length"]:
            raise ValueError(
                f"codec tables: layout {kind} declares length {layout['length']} "
                f"but its fields sum to {total}")
    for name, d in raw["dimensions"].items():
        if d.get("kind") == "bitfield":
            bits = [e["bit"] for e in d["map"]]
            if len(bits) != len(set(bits)):
                raise ValueError(f"codec tables: duplicate bit in dimension {name}")
            if max(bits) >= d["bits"]:
                raise ValueError(f"codec tables: bit {max(bits)} exceeds width in {name}")
            if 36 ** d["chars"] <= (1 << d["bits"]) - 1:
                raise ValueError(
                    f"codec tables: dimension {name} needs more than {d['chars']} chars")


@lru_cache
def get_tables(path: str | None = None) -> Tables:
    p = Path(path) if path else _DEFAULT
    raw = json.loads(p.read_text(encoding="utf-8"))
    _validate(raw)
    return Tables(raw)
