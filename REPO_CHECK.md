## Repo Verification Summary

- Repo: `https://github.com/AbinavDWH/PACT`
- Branch: not verified from this chat
- Latest commit: not verified from this chat
- Latest commit date: not verified from this chat
- Last known `STATUS.md` update: August 17, 2026
- Known backend state: FastAPI + SMS parsing done
- Known Android state from you: Android Studio project exists, currently only Hello World
- Missing expected Android files:
  - home navigation
  - field report screen
  - API client
  - offline queue
  - SMS encoder
  - SMS decoder
  - map screen
  - status update screen
- Conflicts:
  - Old `STATUS.md` says Android App pending.
  - You say Android project exists with Hello World.
- Current likely task:
  - Create repo-check rules and update `STATUS.md` with a specific Android-only execution plan.

---

# File 1: `REPO_CHECK.md`

Save this as:

```text
REPO_CHECK.md
```

```md
# 🔎 Repo Check Rules — PACT / ResiLink

Repo: https://github.com/AbinavDWH/PACT  
Project: Privacy-Preserving Multi-Agent Humanitarian Coordination Platform  
Hackathon: Phoenix Hacks — Track 6

This file defines the mandatory repository verification process before any coding, planning, or status update.

---

## 1. Mandatory Rule

Before answering any development question or starting any task:

1. Check the GitHub repository.
2. Check the current branch.
3. Check the latest commit.
4. Check required files, folders, and functions.
5. Compare repo state with `STATUS.md`.
6. Update `STATUS.md` with one specific `DO THIS NOW` task.
7. Only then start implementation.

Do not rely only on old chat memory.

---

## 2. GitHub Web / Browser Checks

If the AI tool has web search or browser access, check these URLs:

### Repo Home

```text
https://github.com/AbinavDWH/PACT
```

### Latest commits

```text
https://github.com/AbinavDWH/PACT/commits/main
```

### STATUS.md

```text
https://github.com/AbinavDWH/PACT/blob/main/STATUS.md
```

### Backend folder

```text
https://github.com/AbinavDWH/PACT/tree/main/backend
```

### Backend main.py

```text
https://github.com/AbinavDWH/PACT/blob/main/backend/app/main.py
```

### Android folder

```text
https://github.com/AbinavDWH/PACT/tree/main/android
```

### Android app source

```text
https://github.com/AbinavDWH/PACT/tree/main/android/app/src/main
```

### GitHub code search examples

Search for MainActivity:

```text
https://github.com/search?q=repo%3AAbinavDWH%2FPACT+MainActivity&type=code
```

Search for encodeNeed:

```text
https://github.com/search?q=repo%3AAbinavDWH%2FPACT+encodeNeed&type=code
```

Search for xor_checksum:

```text
https://github.com/search?q=repo%3AAbinavDWH%2FPACT+xor_checksum&type=code
```

Note: If the repository is private, public web search may not show results. Use authenticated GitHub CLI or local Git commands.

---

## 3. GitHub CLI Checks

If GitHub CLI is installed and authenticated:

```bash
gh repo view AbinavDWH/PACT --json name,updatedAt,defaultBranchRef
```

Check latest commits:

```bash
gh api repos/AbinavDWH/PACT/commits?per_page=5 \
  --jq '.[] | .sha[0:7] + " " + .commit.author.date + " " + .commit.message'
```

Check repo root contents:

```bash
gh api repos/AbinavDWH/PACT/contents \
  --jq '.[].name'
```

Check STATUS.md:

```bash
gh api repos/AbinavDWH/PACT/contents/STATUS.md \
  --jq '.content' | base64 --decode
```

Check backend main.py:

```bash
gh api repos/AbinavDWH/PACT/contents/backend/app/main.py \
  --jq '.content' | base64 --decode
```

Check Android app source folder:

```bash
gh api repos/AbinavDWH/PACT/contents/android/app/src/main \
  --jq '.[].name'
```

---

## 4. Local Git Checks

Run from the repository root:

```bash
git fetch --all --prune
git branch --show-current
git status --short
git log --oneline --date=short --pretty=format:"%h %ad %s" -10
```

Check changed files:

```bash
git diff --name-status HEAD~5 HEAD
git diff --name-status origin/main...HEAD
```

---

## 5. Android Package Detection

The Android package path can differ by machine. Detect it before checking Kotlin files.

```bash
NAMESPACE=$(grep -E "namespace" android/app/build.gradle.kts | sed -E 's/.*"(.+)".*/\1/')
PKG_DIR=android/app/src/main/java/$(echo $NAMESPACE | tr '.' '/')

echo "NAMESPACE=$NAMESPACE"
echo "PKG_DIR=$PKG_DIR"
```

Check package folder:

```bash
ls -la $PKG_DIR
```

Expected minimum file:

```text
MainActivity.kt
```

---

## 6. Required File Checks

### Root files

Check that these exist:

```bash
ls -la STATUS.md
ls -la REPO_CHECK.md
ls -la memory_draft.md
ls -la sms.md
ls -la AI_CONTEXT_LOADER.md
```

### Backend files

```bash
ls -la backend/app/main.py
ls -la backend/requirements.txt
```

### Android files

```bash
ls -la android/app/build.gradle.kts
ls -la android/settings.gradle.kts
find android/app/src/main -type f \( -name "*.kt" -o -name "*.xml" \)
```

---

## 7. Required Function Checks

### Android MainActivity

```bash
grep -R "class MainActivity" -n android/app/src/main
grep -R "fun onCreate" -n android/app/src/main || true
grep -R "setContent" -n android/app/src/main || true
```

### Android Field Report

```bash
grep -R "data class FieldReport" -n android/app/src/main || true
grep -R "FieldReportScreen" -n android/app/src/main || true
grep -R "fun submitReport" -n android/app/src/main || true
```

### Android API client

```bash
grep -R "api/v1/needs" -n android/app/src/main || true
grep -R "postNeed" -n android/app/src/main || true
grep -R "submitNeed" -n android/app/src/main || true
```

### Android SMS encoder

```bash
grep -R "fun encodeNeed" -n android/app/src/main || true
grep -R "fun xorChecksum" -n android/app/src/main || true
grep -R "fun resourceCode" -n android/app/src/main || true
grep -R "fun urgencyCode" -n android/app/src/main || true
grep -R "fun locationCode" -n android/app/src/main || true
```

### Android SMS decoder

```bash
grep -R "fun decode" -n android/app/src/main || true
grep -R "fun validateChecksum" -n android/app/src/main || true
grep -R "fun parseNeed" -n android/app/src/main || true
grep -R "fun parseMarker" -n android/app/src/main || true
grep -R "fun parseStatus" -n android/app/src/main || true
```

### Backend SMS parser

```bash
grep -R "xor_checksum" -n backend/app || true
grep -R "sms/webhook" -n backend/app || true
grep -R "need" -n backend/app || true
```

---

## 8. Build Checks

### Android build

```bash
cd android
./gradlew clean
./gradlew :app:assembleDebug
cd ..
```

Expected result:

```text
BUILD SUCCESSFUL
```

### Backend run check

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Expected health endpoint:

```text
http://localhost:8000/api/v1/health
```
