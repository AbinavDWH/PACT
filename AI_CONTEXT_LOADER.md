```markdown
# 🧠 AI CONTEXT LOADER — PACT

> **Repository:** https://github.com/AbinavDWH/PACT
> **Project:** Privacy-Preserving Multi-Agent Humanitarian Coordination Platform
> **Hackathon:** Phoenix Hacks — Track 6
> **Last Updated:** August 17, 2026

---

## ⚠️ MANDATORY: READ BEFORE ANSWERING ANY QUESTION

Before generating any code, answer, plan, or suggestion, you MUST:

1. Verify the current repository state.
2. Load project memory from the reference files listed below.
3. Produce a **Repo Verification Summary**.
4. Only then proceed with the user's question.

Do NOT rely only on old conversation memory. Always verify against the current repo.

---

## 1. START-SESSION REPO VERIFICATION

At the beginning of every new chat session, perform this verification before answering.

### 1.1 If you have live GitHub / browser access

Check the following:

- Latest commit on the default branch
- Latest commit date and message
- Changed files in the latest commit
- Current repository file tree
- Current content of required context files (Section 3)

Useful GitHub API endpoints:

```
https://api.github.com/repos/AbinavDWH/PACT
https://api.github.com/repos/AbinavDWH/PACT/commits?per_page=5
https://api.github.com/repos/AbinavDWH/PACT/contents
https://api.github.com/repos/AbinavDWH/PACT/contents/STATUS.md
https://api.github.com/repos/AbinavDWH/PACT/contents/backend/app/main.py
https://api.github.com/repos/AbinavDWH/PACT/contents/backend/requirements.txt
```

### 1.2 If the user has a local clone

Ask the user to run these commands from the repo root:

```bash
git fetch --all --prune
git branch --show-current
git status --short
git log --oneline --date=short --pretty=format:"%h %ad %s" -10
git diff --name-status HEAD~5 HEAD
git diff --name-status origin/main...HEAD
```

If they use GitHub CLI:

```bash
gh repo view AbinavDWH/PACT --json name,updatedAt
gh api repos/AbinavDWH/PACT/commits?per_page=5 --jq '.[] | .sha[0:7] + " " + .commit.author.date + " " + .commit.message'
```

### 1.3 If you cannot access the repo

Do NOT pretend you know the latest repo state.
Ask the user to provide:

- Latest `git log` output
- Latest changed files
- Current `STATUS.md`
- Current `backend/app/main.py`
- Current file tree

### 1.4 Verification Output (REQUIRED)

At the start of the session, output this summary before doing anything else:

```markdown
### Repo Verification Summary

- Repo: https://github.com/AbinavDWH/PACT
- Branch: ...
- Latest commit: ...
- Latest commit date: ...
- Last STATUS.md update: ...
- Files changed since last verified session: ...
- New folders/files detected: ...
- Missing expected files: ...
- Conflicts between repo and STATUS.md: ...
- Current likely task: ...
```

---

## 2. LAST VERIFIED BASELINE

Use this baseline to detect what changed since the last known session.

**Last verified date:** August 17, 2026

**Known repo structure:**

```
backend/
├── app/
│   └── main.py
└── requirements.txt
```

**Known implemented backend features:**

- FastAPI app skeleton
- CORS middleware
- `/api/v1/health` endpoint
- `/api/v1/needs` endpoint
- `/api/v1/sms/webhook` endpoint
- Legacy SMS need parsing
- Canonical SMS need parsing
- XOR checksum validation
- Resource code mapping
- Urgency code mapping
- Location code mapping

**Known project state from STATUS.md:**

| Component | Status |
|---|---|
| Backend API | 🟢 Done |
| SMS Protocol | 🟢 Done |
| Redis Agent Bus | 🟡 In Progress |
| Multi-Agent Engine | 🔴 Pending |
| Web Dashboard | 🔴 Pending |
| Android App | 🔴 Pending |
| Database | 🟡 In Progress |

**Known immediate next step:**

> Connect FastAPI backend to Redis and trigger the Need Assessment Agent to process decoded JSON.

If the current repo contains new folders or files such as `web/`, `agents/`, `android/`, `docs/`, `scripts/`, or `.github/workflows/`, report them as updates since this baseline.

---

## 3. REQUIRED CONTEXT FILES

After repo verification, load context from these files in this order:

| Priority | File | Purpose |
|:---:|---|---|
| 1 | `STATUS.md` | Current project progress and immediate next step |
| 2 | `memory_draft.md` | Full architecture, agent design, demo flow, hackathon strategy |
| 3 | `sms.md` | Complete SMS fallback protocol specification |
| 4 | `backend/app/main.py` | Current backend implementation |
| 5 | `backend/requirements.txt` | Current backend dependencies |
| 6 | `README.md` | Project overview, if exists |
| 7 | `.github/workflows/` | CI/CD configuration, if exists |

**Override rules:**

- If `sms.md` changes → `sms.md` overrides all previous SMS-related memory.
- If `STATUS.md` changes → `STATUS.md` overrides all previous progress memory.
- If `memory_draft.md` changes → `memory_draft.md` overrides architecture memory.
- If repo code conflicts with docs → trust the repo code and report the conflict.

---

## 4. CHANGE DETECTION RULES

When verifying the repo, check especially for these important changes:

### Backend changes

```
backend/app/main.py
backend/requirements.txt
backend/app/api/
backend/app/services/
backend/app/models/
backend/app/schemas/
```

### Agent changes

```
agents/
agents/need_assessment_worker.py
agents/resource_matching_worker.py
agents/coordination_worker.py
agents/replanning_worker.py
agents/privacy_filter_worker.py
agents/sms_parser_worker.py
```

### Web dashboard changes

```
web/
web/app/
web/components/
web/lib/
```

### Android changes

```
android/
android/app/
android/app/src/main/java/
android/app/src/main/AndroidManifest.xml
```

### Documentation changes (HIGH PRIORITY)

```
STATUS.md
memory_draft.md
sms.md
README.md
```

---

## 5. CONFLICT RESOLUTION RULES

If repo content conflicts with old chat memory, use this priority:

```
1. Current repo code/files
2. STATUS.md
3. sms.md
4. memory_draft.md
5. Previous chat memory
```

---

## 6. PROJECT MEMORY RULES

After verification, remember these core rules:

### 6.1 Project type

- 24-hour hackathon MVP
- Prioritize demo impact, speed, feasibility, and clear explanation
- Do not overbuild production-level features unless asked

### 6.2 Privacy rule

Never expose donor names, staff names, exact warehouse locations, funding details, full inventory, beneficiary personal data, or internal operational plans.

### 6.3 SMS rule

SMS is an emergency data-transfer channel, not just an alert channel.
For all SMS formats, encoding, decoding, checksums, sequence numbers, marker messages, polygons, routes, and simulator behavior, refer to `sms.md`.

### 6.4 Map rule

SMS cannot send map tiles. Map tiles must be pre-cached.
SMS can only send small coordinate/marker/polygon/route updates.

### 6.5 Architecture rule

Web dashboard and Android app share the same FastAPI backend.
Heavy coordination logic should go through Redis queues and Python agent workers.

---

## 7. CURRENT PROJECT CONTEXT

**Stack:**

| Component | Technology |
|---|---|
| Web Frontend | Next.js + TypeScript |
| Backend | Python FastAPI |
| Database | PostgreSQL + PostGIS |
| Auth | Keycloak (mocked for MVP) |
| Queue / Agent Bus | Redis |
| Agents | Python workers |
| Android App | Kotlin |
| Maps | OpenStreetMap + MapLibre |

**Main demo flow:**

```
Crisis/Need Input
    │
    ▼
FastAPI Backend
    │
    ▼
Redis Queue
    │
    ▼
Need Assessment Agent
    │
    ▼
Resource Matching Agent
    │
    ▼
Coordination Agent
    │
    ▼
Response Plan
    │
    ▼
Dashboard / Android App / SMS Response
```

**SMS fallback flow:**

```
Internet failure
    │
    ▼
Android app or SMS simulator sends compact SMS payload
    │
    ▼
FastAPI SMS webhook receives SMS
    │
    ▼
SMS decoder converts SMS to JSON
    │
    ▼
JSON pushed to Redis
    │
    ▼
Agents process message
    │
    ▼
Dashboard / map / plan updated
```

---

## 8. AI RESPONSE RULES

Before answering any development question:

1. ✅ Verify repo state
2. ✅ Load `STATUS.md`
3. ✅ Load relevant reference files
4. ✅ If question involves SMS → read `sms.md` first
5. ✅ If question involves progress/status → read `STATUS.md` first
6. ✅ If question involves architecture/demo flow → read `memory_draft.md` first
7. ✅ If repo state is unclear → ask for verification output
8. ✅ If repo state conflicts with old memory → trust the repo
9. ✅ Keep suggestions hackathon-friendly
10. ✅ Prefer simple working MVP code over complex production code

---

## 9. QUICK VERIFICATION CHECKLIST

Before answering, confirm:

- [ ] Repo URL verified: `AbinavDWH/PACT`
- [ ] Latest commit checked
- [ ] Changed files checked
- [ ] `STATUS.md` checked
- [ ] `memory_draft.md` checked
- [ ] `sms.md` checked (if SMS is involved)
- [ ] `backend/app/main.py` checked (if backend work is involved)
- [ ] Conflicts detected and reported
- [ ] Current likely task identified

If any required file is missing, say:

> I could not verify `[file name]`. Please provide its latest content or run the repo verification commands.
```

---

### Where to place this file

| AI Tool | File Name | Location |
|---|---|---|
| Cursor | `.cursorrules` | Repo root |
| GitHub Copilot | `.github/copilot-instructions.md` | `.github/` folder |
| Cline / Roo Code | `.clinerules` or `AGENTS.md` | Repo root |
| Claude Code | `CLAUDE.md` | Repo root |
| Generic / Any AI | `AI_CONTEXT_LOADER.md` | Repo root |