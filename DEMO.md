# PACT — demo runbook

For recording the backup video and for presenting live. Follow it in order.

The backup video is **non-negotiable**: Groq is rate-limited to 8000 tokens per
minute, venue wifi fails, and Atlas needs network access. Record while the
system is known-good, before touching anything else.

---

## 0. Pre-flight

```bash
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
cd web && pnpm dev
```

`--host 0.0.0.0` is required or the phone cannot reach the backend, however
correct the address in `BuildConfig.API_BASE` is.

Then, with the demo's actual coordinates:

```bash
cd backend && python scripts/preflight.py --lat <lat> --lon <lon>
```

It must print **READY TO RECORD**. It checks the things that fail silently:
Mongo connected rather than merely configured, Groq budget above one run,
fixtures inside the radius ladder, auth actually enforced, and a full live run
reporting `geo_live: true` with all four LLM agents live.

If it reports fixtures too far away, reseed:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/admin/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"pact-admin"}' | python -c 'import sys,json;print(json.load(sys.stdin)["token"])')

curl -X POST http://localhost:8000/api/v1/admin/seed \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"lat": <lat>, "lon": <lon>, "label": "venue"}'
```

**Why this matters more than it looks.** The radius ladder stops at 150 km.
Beyond it `$geoNear` returns nothing, the pipeline falls back to hardcoded
candidates, and the portal still shows a debate and commits an allocation. The
demo looks identical while the one genuine database query has stopped running —
and `$geoNear` is one of the four things `memory_draft.md` §23 says never to cut.

### Settings for the recording

```bash
# Pause at the gate instead of auto-approving, so the override is demonstrable.
curl -X POST http://localhost:8000/api/v1/admin/settings \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"autopilot": false, "gate_timeout_s": 120}'

# Slow event emission so the debate is readable on camera.
curl -X POST http://localhost:8000/api/v1/admin/settings \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"demo_latency_ms": 120}'
```

`demo_latency_ms` exists because Groq at ~275 tok/s is too fast to follow. Turn
it back to 0 afterwards.

### Windows to have open

| Window | URL | Login |
|---|---|---|
| Admin portal | `http://localhost:3000/admin` | admin / pact-admin |
| Org portal | `http://localhost:3000/org` | sanjeevani / pact-org |
| Seeker phone | mirrored or filmed | — |
| **Gateway phone** | same APK, gateway mode ON | — |

The gateway handset must have a SIM, be on the same backend address, and have
gateway mode switched on **before** section 6. Check its *Received* list is
empty at the start so the arriving frame is unambiguous.

---

## 1. The problem — 30 s

Organizations cannot see each other's resources and will not share internal
data. The people who need help have no way to ask. Say it, do not show it.

## 2. A request — 45 s

On the phone: **building collapse · 3–4 people · one seriously injured ·
trapped in debris · critical · water + medical + rescue**. Send.

Point out there is **no text box anywhere**. Free text does not compress into
35 characters, and it is what identifies a person in an intercepted message.

## 3. The agents deliberate — 90 s

Switch to the admin portal.

- **Triage** reasons about severity and assigns a tier.
- **The `$geoNear` query runs visibly** — the grey `agent.tool_call` line. Say
  that this is a real database query against a live Atlas cluster, not a mock.
- **Advocates argue** for and against their candidates, with risk flags.
- **The solver proposes three options** — fastest, max coverage, least
  depleting — each with a computed score. A second `agent.tool_call` shows the
  weights and the per-candidate scores.
- **The arbiter picks one** and says which arguments it rejected.

The line worth saying out loud: *the model never produces a number.* It returns
an `option_id`, validated against the solver's set before anything is written.

## 4. Human control — 45 s

The pipeline pauses at the gate. **Override** the allocation — change a
quantity. Watch it re-enter the solver, validate against live stock, and
commit the override.

Then, if there is time, submit an impossible override (more than the supplier
holds). It is refused with `OVERRIDE_INFEASIBLE` naming the real free stock,
and the pipeline commits the arbiter's option instead. That refusal is the
point: an override is a human instruction, not a licence to write an allocation
the stock cannot support.

## 5. Privacy — 60 s

This is the headline claim, so demonstrate it rather than describing it.

- On the **helper's screen before accepting**: an approximate area (~1 km), a
  need, no name, no contact, no delivery code.
- **Accept.** The exact position, name, contact and delivery code appear.
- On the **org portal**: its own assignment and nothing else — not the other
  organizations' stock, and not even that a cross-organization debate happened.

A7 reports **measured** counts: roughly 20–25 field instances redacted with a
per-field breakdown, computed off the real payload rather than a fixed list.

## 6. Connectivity fails — 60 s

Airplane mode on the phone. Send the identical request.

It goes by **real SMS**, over the cellular network, to a second handset running
the app in gateway mode. That phone forwards the frame to
`/api/v1/sms/webhook`, and the same request appears in the portal — decoded
identically, because it is byte-for-byte the same string either way, verified
by 11 parity vectors across Python and Kotlin.

Show the gateway phone's *Received* list: the wire string that arrives is the
one that left the other handset.

Hold the 35-character payload against the 160-character limit.

Worth saying: the gateway forwards **only** PACT frames. A phone that receives
SMS also receives banking OTPs, and forwarding those would be a worse privacy
failure than anything this system defends against — so the filter refuses them,
with tests that assert the refusal.

> **Do not claim the offline map updates.** Offline MapLibre is cut-line 1 and
> was never built. `memory_draft.md` §24 step 6 still mentions it; that clause
> is wrong and must not be said on camera.

## 7. Conditions change — 30 s

The assigned helper **declines**. The replanner fires and a new deliberation
begins under the same `trace_id`, chained under the original request.

---

## What NOT to claim

Being caught overstating one thing costs more than the feature was worth.

| Do not say | The truth |
|---|---|
| "The offline map updates over SMS" | MapLibre was never built (cut-line 1) |
| "Production ready" | Demo-grade auth, no TLS, no real SMS gateway |
| "Encrypted end to end" | SMS is plaintext. PACT gives minimal disclosure and integrity, not confidentiality (`memory_draft.md` §8.4) |
| "The verification agent reasons about discrepancies" | A10's LLM branch is cut-line 2; the delivery-code check is deterministic only |
| "It replans on SLA breach" | A11 has the decline trigger only; timers are cut-line 3 |

If Groq dies mid-demo, **say so and keep going** — every agent has a
deterministic fallback, the portal shows an amber line, and the run still
commits. That is a better answer than a rehearsed one.

---

## Recording checklist

- [ ] `preflight.py` prints READY TO RECORD
- [ ] `autopilot: false`, `gate_timeout_s: 120`, `demo_latency_ms: 120`
- [ ] Phone on the same LAN, `BuildConfig.API_BASE` pointing at the LAN IP
      (preflight prints it)
- [ ] Notifications silenced on both machine and phone
- [ ] Groq budget above 3000 tokens/min at the moment you press record
- [ ] Record **section 6 (SMS) separately** if airplane mode disrupts screen
      mirroring — splice it in rather than losing the take
- [ ] Afterwards: `demo_latency_ms` back to 0, `autopilot` back to true
