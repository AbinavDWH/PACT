# Prompt for the next session

Copy the block below as your first message in a new session.

---

```
I'm continuing PACT, a privacy-preserving multi-agent humanitarian coordination
platform, for a 24-hour hackathon. Solo build.

READ FIRST, in this order:
  1. STATUS.md        - build status. Sections 6 (open gaps) and 9 (traps) matter most.
  2. memory_draft.md  - project memory, identity model, build order (S22), cut-lines (S23)
  3. agents.md        - agent pipeline, prompts, MongoDB schema, API surface
  4. codec.md         - option taxonomy and the compressed code language
  5. sms.md           - SMS transport protocol

WHERE THINGS STAND
Steps 1 to 5 of the seven-step build order are complete and verified by running
them, not just by writing them:

  1 Event bus, WebSocket, admin portal, MongoDB Atlas, real $geoNear, real solver
  2 Codec - Python and Kotlin, 11 parity vectors byte-identical across both
  3 Real Groq agents (triage, advocates, arbiter, narrator) each with a
    deterministic fallback, plus A1 dedupe, A7 privacy, privacy.reveal, notify
  4 Android app - installed and driven on a physical vivo V2336: real GPS,
    on-device encoding, HTTP ingest, and SMS fallback with data off
  5 Organization portal at /org - login, assignments, assign-to-helper, roster

203 Python tests and 7 Kotlin tests pass.

WHAT REMAINS
  6 A10 verification LLM branch, A11 SLA timers   (both deliberate cut-lines)
    Offline MapLibre                              (cut-line 1)
  7 Polish, full test pass, BACKUP DEMO VIDEO, pitch

FIRST TASK
Commit the uncommitted work before anything else - it is all of step 5 plus
several fixes. STATUS.md section 11 lists the files.

THEN, in this order:
  1. Reseed near where the demo will actually happen. db/seed.py centres on
     Bhopal; a request from anywhere else falls outside the 150 km radius ladder
     and $geoNear silently returns nothing, so the pipeline uses fixtures with
     geo_live: false. The geo query is one of the four things never to cut.
     Best fix: make the seed centre a parameter on POST /api/v1/admin/seed.
  2. Remove POST /api/v1/crises and the dead RESOURCE_PROVIDERS dict and
     create_response_plan() in main.py. Nothing calls any of them.
  3. Record the backup demo video. Non-negotiable, and it is the item most
     likely to get squeezed out at the end.

HOW I WANT YOU TO WORK
- Verify claims by running them. Do not tell me something works because it was
  written. I have caught overstated "complete" claims in this project more than
  once, and each time the audit found real defects.
- When I ask whether something is done, audit the code and say what is missing
  rather than summarising the docs.
- Flag anything that is theatre - a hardcoded value or message that looks like
  real behaviour. Several were found and fixed this way: hardcoded solver
  scores, a dedupe agent that checked nothing, a privacy agent that redacted
  nothing, and org endpoints with no authentication at all.
- Prefer tests that assert on refusal or absence. A privacy test that only
  checks "the admin sees everything" would have passed against a broken
  redactor.
- Keep the design docs and STATUS.md in sync when behaviour changes.

ENVIRONMENT
- Toolchain is entirely on E: (C: is nearly full). JAVA_HOME, ANDROID_HOME,
  ANDROID_SDK_ROOT and GRADLE_USER_HOME are set persistently; android/env.sh
  also exists for a shell that lacks them.
- Start the backend WITHOUT --reload: it hangs on this machine and orphans
  workers that keep holding port 8000 under a dead PID.
      cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
      cd web && pnpm dev
  Use --host 0.0.0.0 or the phone cannot reach it.
- Free a stuck port by PID via Get-NetTCPConnection; pkill is unreliable here.
- Groq: openai/gpt-oss-120b (judgement), openai/gpt-oss-20b (volume).
  llama-3.3-70b-versatile does NOT exist on this account. 8000 tokens/minute is
  the binding limit, roughly 6 pipeline runs per minute.
- Admin portal http://localhost:3000/admin  (admin / pact-admin)
  Org portal   http://localhost:3000/org    (sanjeevani / pact-org)

Tell me what you found in STATUS.md, then start with the commit.
```

---

## Swap the "THEN" block for a different focus

**If you want the remaining agents finished** (~1–2 h):
```
THEN finish step 6: give A10 its LLM branch for free-text delivery discrepancies,
and add A11's SLA timer and T1-preemption triggers. Both are currently marked as
deliberate cut-lines in memory_draft.md S23, so treat this as un-cutting them
rather than as unfinished work.
```

**If you want the offline map** (~2–3 h, cut-line 1):
```
THEN add offline MapLibre: crisis points and helper positions in the admin
portal, and pre-cached tiles in the Android app so a marker can be drawn from an
SMS coordinate update with no data connection. This is the first thing
memory_draft.md S23 says to cut, so do it only if the demo is otherwise ready.
```

**If time is short — the right default** (~3–5 h):
```
THEN go straight to demo readiness. Run the full flow end to end, reseed near
the venue, record a backup video, and prepare the pitch. memory_draft.md S24 has
the demo script and S25 the judge Q&A. Never cut the live agent debate, the
approve/override bar, $geoNear, or the three-option arbiter choice.
```
