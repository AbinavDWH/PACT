# Prompt for the next session

Copy everything in the block below as your first message.

---

```
I'm continuing PACT, a privacy-preserving multi-agent humanitarian coordination
platform for a 24-hour hackathon. Solo build.

START BY READING, in this order:
  1. STATUS.md        - build status, known gaps, traps. Read section 6 and 9 carefully.
  2. memory_draft.md  - project memory, identity model, build order (S22), cut-lines (S23)
  3. agents.md        - agent pipeline, prompts, MongoDB schema, API surface
  4. codec.md         - the option taxonomy and compressed code language
  5. sms.md           - SMS transport protocol

WHERE THINGS STAND
Steps 1 and 2 of the build order are complete and committed. Step 3 (real Groq
agents) is about 70% done and is NOT committed.

Working and verified: MongoDB Atlas with 26 indexes and seed data, real $geoNear
matching, deterministic allocation solver, in-process event bus, authenticated
WebSocket with replay, admin portal with live agent deliberation and a working
approve/override/reject gate, the full codec (75 Python tests + 7 Kotlin parity
tests, byte-identical across both languages), and four agents live on Groq
(triage, advocates, arbiter, narrator) each with a deterministic fallback.

FIRST TASK
Commit the uncommitted step 3 work before anything else. STATUS.md section 11
lists the exact files.

THEN close the step 3 gaps, in this order (STATUS.md section 6 has detail):
  1. A7 Privacy Redactor is fake - it publishes a fixed "withheld" list and
     redacts nothing. app/privacy/ does not exist. This is the project's
     headline claim, so it matters most. (~1h)
  2. privacy.reveal never fires - zero publishers. matches.reveal exists in the
     schema and nothing flips it, because there is no helper-accept endpoint.
     (~45m)
  3. A1 Dedupe is fake - hardcoded "no duplicate" message, computes no geohash,
     checks nothing. (~30m)
  4. notify/ does not exist - the two dispatch paths (org portal vs individual
     volunteer) are a string label, not routing. (~30m)

HOW I WANT YOU TO WORK
- Verify claims by running them. Do not tell me something works because it was
  written. I have caught overstated "complete" claims twice in this project.
- When I ask whether something is done, audit the code and say what is missing.
- Flag anything that is theatre - a hardcoded message that looks like real
  behaviour - rather than leaving it to be discovered later.
- Keep the design docs in sync when behaviour changes.

ENVIRONMENT NOTES THAT WILL SAVE YOU TIME
- Toolchain is entirely on E: (C: is nearly full). Run `source android/env.sh`
  before any gradle or adb work. Env vars are NOT set persistently.
- Start the backend WITHOUT --reload: it hangs on this machine and orphans
  workers that keep holding port 8000 under a dead PID.
      cd backend && python -m uvicorn app.main:app --port 8000
      cd web && pnpm dev
- To free a stuck port, kill by PID via Get-NetTCPConnection. pkill does not
  work reliably here.
- Groq: openai/gpt-oss-120b (judgement) and openai/gpt-oss-20b (volume).
  llama-3.3-70b-versatile does NOT exist on this account. 8000 tokens/minute is
  the binding limit, roughly 6 requests per minute.
- Never hand-write a checksum. Compute it. 42 doc examples and 4 UI presets were
  wrong before this was caught.

Tell me what you found in STATUS.md, then start with the commit.
```

---

## If you want a different next task

Swap the "THEN close the step 3 gaps" paragraph for one of these:

**Android app** (~8–12 h, the biggest remaining chunk):
```
THEN start step 4, the Android app. The Kotlin codec library already exists at
android/codec and its parity test passes - do not rewrite it. Build the app
module: one-time signup screen (role, name, phone), chip-selection request
screen with no text input anywhere, GPS capture, and a Transport layer that
tries HTTP and falls back to SMS with a Room outbox. Toolchain and device setup
are in android/README.md. The phone is a vivo V2336 on Android 16 with USB
debugging already authorized.
```

**Organization portal** (~2–3 h):
```
THEN build the organization portal: static login, the org's own assignments,
assign-to-a-named-helper, roster, inventory, and the group code. It reuses the
existing event bus and portal components. Critically, /ws/org currently sends
the FULL envelope - it must pass through the A7 org-audience projection so an
organization never sees the cross-org debate.
```

**Demo readiness** (~3–5 h, do this if time is short):
```
THEN prioritise demo readiness over new features: run the full flow end to end,
record a backup video, and prepare the pitch. memory_draft.md S24 has the demo
script and S25 the judge Q&A. Never cut the live agent debate, the
approve/override bar, $geoNear, or the three-option arbiter choice.
```
