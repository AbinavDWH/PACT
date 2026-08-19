"""Structured outputs, one per LLM agent (agents.md section 2).

Every response is validated against these before anything downstream sees it.
JSON mode reduces malformed output; it does not eliminate it, so nothing here
is ever parsed with a bare json.loads.

Note what these schemas do NOT contain: allocation quantities. The solver
produces those in Python. The arbiter can only name an option that already
exists, which is why `chosen_option_id` is a string that gets validated against
the option set rather than a list of allocations.
"""

from __future__ import annotations

from typing import Literal

from typing import Any

from pydantic import (BaseModel, Field, ValidationInfo, field_validator,
                      model_validator)


class LineItem(BaseModel):
    resource: str
    quantity: int = Field(ge=0)
    rationale: str = ""


class TriageOut(BaseModel):
    severity: int = Field(ge=0, le=100)
    tier: Literal["T1", "T2", "T3", "T4"]
    life_threat: bool = False
    time_to_harm_hours: int = Field(default=24, ge=0, le=720)
    escalations: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning: str = ""

    @field_validator("reasoning")
    @classmethod
    def _trim(cls, v: str) -> str:
        words = v.split()
        return " ".join(words[:45])          # prompt says <= 40; allow slight overrun


class Bid(BaseModel):
    cand_id: str
    # gpt-oss frequently emits `fit_score`; accept both rather than discard a
    # perfectly good answer over a key name.
    fit: int = Field(ge=0, le=100, validation_alias="fit", alias_priority=1)
    argument: str = ""
    risk_flags: list[str] = Field(default_factory=list)
    recommended_share: Literal["full", "partial", "none"] = "partial"

    @field_validator("argument")
    @classmethod
    def _trim(cls, v: str) -> str:
        return " ".join(v.split()[:35])


class AdvocatesOut(BaseModel):
    # min_length=1 is load-bearing. With a default of [], a wrong-shaped
    # response validated "successfully" with zero bids -- reported as a
    # successful model call while silently producing no debate at all.
    bids: list[Bid] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: Any) -> Any:
        """gpt-oss returns three different shapes depending on reasoning effort:
        {"bids": [...]}, a bare [...], or {"c1": {...}, "c2": {...}}.
        Normalise all three rather than fight the model."""
        if isinstance(data, list):
            data = {"bids": data}
        elif isinstance(data, dict) and "bids" not in data:
            keyed = {k: v for k, v in data.items() if isinstance(v, dict)}
            if keyed:
                data = {"bids": [{**v, "cand_id": v.get("cand_id", k)}
                                 for k, v in keyed.items()]}
        if isinstance(data, dict) and isinstance(data.get("bids"), list):
            out = []
            for b in data["bids"]:
                if not isinstance(b, dict):
                    continue
                b = dict(b)
                if "fit" not in b:
                    for alt in ("fit_score", "score", "rating"):
                        if alt in b:
                            b["fit"] = b[alt]
                            break
                out.append(b)
            data = {**data, "bids": out}
        return data


class DebateTurn(BaseModel):
    speaker: str = "arbiter"
    claim: str = ""
    rebuts: str | None = None


class ArbiterOut(BaseModel):
    chosen_option_id: str = Field(min_length=1)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    turns: list[DebateTurn] = Field(default_factory=list)
    justification: str = ""
    dissent: str = ""

    @field_validator("turns")
    @classmethod
    def _cap(cls, v: list[DebateTurn]) -> list[DebateTurn]:
        return v[:4]


class NarratorOut(BaseModel):
    admin_summary: str = ""
    helper_message: str = ""
    sms_variant: str = ""

    @field_validator("sms_variant")
    @classmethod
    def _ascii_and_short(cls, v: str) -> str:
        # Must survive GSM-7 and fit one SMS alongside a header.
        cleaned = "".join(c for c in v if ord(c) < 128)
        return cleaned[:110]

    @field_validator("helper_message")
    @classmethod
    def _cap(cls, v: str) -> str:
        return v[:200]
