"""Groq client (agents.md section 5).

Three properties matter more than anything else here:

1. Streaming is mandatory. The token deltas are what make the portal look like
   agents thinking rather than a spinner followed by an answer.
2. Every response is Pydantic-validated. JSON mode reduces malformed output; it
   does not eliminate it.
3. Every call has a deterministic fallback. If Groq is slow, rate-limited, or
   returns garbage, the pipeline emits an amber error event and continues. The
   demo cannot be killed by an API.

Free tier measured at 8000 tokens/minute, which binds long before the 1000
requests/day limit. The semaphore and the token gauge are sized for that.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, ValidationError

from app.bus.eventbus import bus
from app.config import get_settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_client = None
_sem: asyncio.Semaphore | None = None

# Updated from x-ratelimit-* response headers. When remaining tokens drop below
# one call's budget we shed to the fallback rather than eating a 429.
_gauge = {"remaining_tokens": None, "remaining_requests": None, "checked_at": 0.0}
SHED_BELOW_TOKENS = 1200


def _get_client():
    global _client, _sem
    if _client is None:
        from groq import AsyncGroq
        s = get_settings()
        _client = AsyncGroq(api_key=s.groq_api_key, max_retries=0, timeout=20.0)
        _sem = asyncio.Semaphore(s.groq_max_inflight)
    return _client


def stats() -> dict[str, Any]:
    return dict(_gauge)


def _should_shed() -> bool:
    rt = _gauge["remaining_tokens"]
    return rt is not None and rt < SHED_BELOW_TOKENS


def _note_headers(headers) -> None:
    try:
        rt = headers.get("x-ratelimit-remaining-tokens")
        rr = headers.get("x-ratelimit-remaining-requests")
        if rt is not None:
            _gauge["remaining_tokens"] = int(float(rt))
        if rr is not None:
            _gauge["remaining_requests"] = int(float(rr))
        _gauge["checked_at"] = time.time()
    except Exception:
        pass


async def call_json(
    system: str,
    user: dict[str, Any],
    schema: type[T],
    *,
    agent: str,
    trace_id: str,
    run_id: str | None = None,
    fallback: Callable[[], T],
    fast: bool = False,
    max_tokens: int = 900,
    temperature: float = 0.2,
    timeout: float = 25.0,
    reasoning_effort: str | None = "low",
    stream_tokens: bool = True,
) -> tuple[T, bool]:
    """Returns (result, used_llm).

    used_llm is False when the deterministic fallback produced the value, so the
    caller can label it honestly in the UI instead of passing off a heuristic as
    model output.
    """
    s = get_settings()
    if not s.groq_enabled:
        return fallback(), False

    if _should_shed():
        await bus.publish(trace_id, "error",
                          {"code": "RATE_LIMIT_SHED", "fallback_used": True,
                           "remaining_tokens": _gauge["remaining_tokens"]},
                          agent=agent, run_id=run_id)
        return fallback(), False

    client = _get_client()
    model = s.groq_model_fast if fast else s.groq_model
    # Strip nulls and empties: they cost tokens and, worse, make the model
    # reason harder about missing data -- which is what pushed gpt-oss past
    # max_tokens and produced truncated JSON.
    payload = {k: v for k, v in user.items() if v is not None and v != [] and v != ""}
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, separators=(",", ":"),
                                                       default=str)}]

    for attempt in (0, 1):
        try:
            assert _sem is not None
            async with _sem:
                buf: list[str] = []
                async with asyncio.timeout(timeout):
                    kwargs: dict[str, Any] = dict(
                        model=model, messages=messages,
                        response_format={"type": "json_object"},
                        temperature=temperature, max_tokens=max_tokens, stream=True)
                    if reasoning_effort:
                        # gpt-oss spends completion tokens on reasoning before
                        # the JSON. "low" cuts that ~40%, which matters against
                        # an 8000 tokens/minute ceiling.
                        kwargs["reasoning_effort"] = reasoning_effort
                    resp = await client.chat.completions.with_raw_response.create(**kwargs)
                    _note_headers(resp.headers)
                    # In the async SDK, parse() is itself a coroutine; without
                    # the await this yields a coroutine object and `async for`
                    # raises TypeError on every single call.
                    stream = await resp.parse()
                    async for chunk in stream:
                        delta = chunk.choices[0].delta.content or ""
                        if not delta:
                            continue
                        buf.append(delta)
                        if stream_tokens:
                            await bus.publish(trace_id, "agent.token", {"delta": delta},
                                              agent=agent, run_id=run_id)
                text = "".join(buf)
            return schema.model_validate_json(text), True

        except ValidationError as e:
            await bus.publish(trace_id, "error",
                              {"code": "SCHEMA_INVALID", "attempt": attempt,
                               "detail": str(e)[:200]},
                              agent=agent, run_id=run_id)
            if attempt == 0:
                # One repair attempt, telling the model exactly what broke.
                messages.append({"role": "assistant", "content": "".join(buf)[:600]})
                messages.append({"role": "user", "content":
                                 f"That failed validation: {str(e)[:300]}. "
                                 "Return corrected JSON only."})
                continue

        except Exception as e:
            code = type(e).__name__
            await bus.publish(trace_id, "error", {"code": code, "attempt": attempt,
                                                  "detail": str(e)[:200]},
                              agent=agent, run_id=run_id)
            if attempt == 0 and code not in ("NotFoundError", "AuthenticationError"):
                await asyncio.sleep(0.35 + random.random() * 0.3)
                continue
            break

    await bus.publish(trace_id, "error", {"code": "FALLBACK", "fallback_used": True},
                      agent=agent, run_id=run_id)
    return fallback(), False


async def warmup() -> bool:
    """One tiny call at startup so the first real request is not paying for TLS
    and connection setup while a judge watches."""
    s = get_settings()
    if not s.groq_enabled:
        return False
    try:
        client = _get_client()
        r = await client.chat.completions.with_raw_response.create(
            model=s.groq_model, messages=[{"role": "user", "content": "ok"}],
            max_tokens=1)
        _note_headers(r.headers)
        log.info("groq: warm (%s, %s tokens/min remaining)",
                 s.groq_model, _gauge["remaining_tokens"])
        return True
    except Exception as e:
        log.warning("groq: warmup failed (%s) -- agents will use fallbacks",
                    type(e).__name__)
        return False
