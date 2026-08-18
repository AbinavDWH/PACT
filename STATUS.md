
```md
# 🚦 ResiLink - Project Status

Project: Privacy-Preserving Multi-Agent Humanitarian Coordination Platform  
Hackathon: Phoenix Hacks — Track 6  
Repo: https://github.com/AbinavDWH/PACT  
Last Updated: August 18, 2026  
Overall MVP Progress: 🟡 In Progress — Backend SMS parsing done, Android Hello World exists, Android module execution starting.

---

## 🔎 Repo Verification Summary

Before doing any work, follow:

```text
REPO_CHECK.md
```

Required check:

```bash
git fetch --all --prune
git branch --show-current
git status --short
git log --oneline --date=short -5
```

Required GitHub web checks:

```text
https://github.com/AbinavDWH/PACT
https://github.com/AbinavDWH/PACT/commits/main
https://github.com/AbinavDWH/PACT/blob/main/STATUS.md
https://github.com/AbinavDWH/PACT/tree/main/android/app/src/main
```

Required Android package detection:

```bash
NAMESPACE=$(grep -E "namespace" android/app/build.gradle.kts | sed -E 's/.*"(.+)".*/\1/')
PKG_DIR=android/app/src/main/java/$(echo $NAMESPACE | tr '.' '/')

echo "NAMESPACE=$NAMESPACE"
echo "PKG_DIR=$PKG_DIR"
```

---

## 👥 Current Work Split

| Area | Owner | Status | Specific Focus |
|---|---|---|---|
| Android App | Me | 🟡 In Progress | Hello World exists. Start module-based Android MVP build. |
| Backend API + Redis + Agents | Teammate | 🟡 In Progress | Connect FastAPI to Redis and trigger Need Assessment Agent. |
| Web Dashboard | Teammate | 🔴 Pending | Dashboard panels, SMS simulator, map panel. |
| Database / PostGIS | Teammate | 🟡 In Progress | Schema and spatial queries. |
| SMS Protocol | Shared / Backend | 🟢 Done | Canonical and legacy parsing, XOR checksum implemented. |

---

## 🎯 SPECIFIC DO THIS NOW

Current Active Module:

```text
M0 — Repo + Hello World Verification
```

Owner:

```text
Me / Android app only
```

Do not start M1 until M0 is complete.

---

## ✅ M0 Task Checklist

### 1. Check repo state

```bash
git fetch --all --prune
git branch --show-current
git status --short
git log --oneline --date=short -5
```

### 2. Detect Android package path

```bash
NAMESPACE=$(grep -E "namespace" android/app/build.gradle.kts | sed -E 's/.*"(.+)".*/\1/')
PKG_DIR=android/app/src/main/java/$(echo $NAMESPACE | tr '.' '/')

echo "NAMESPACE=$NAMESPACE"
echo "PKG_DIR=$PKG_DIR"
```

### 3. Check MainActivity file exists

```bash
find android/app/src/main -type f -name "MainActivity.kt"
```

Expected output:

```text
android/app/src/main/java/<package>/MainActivity.kt
```

### 4. Check MainActivity function exists

```bash
grep -R "class MainActivity" -n android/app/src/main
grep -R "fun onCreate" -n android/app/src/main || true
grep -R "setContent" -n android/app/src/main || true
```

Expected: at least one match for `class MainActivity`.

### 5. Build Android app

```bash
cd android
./gradlew clean
./gradlew :app:assembleDebug
cd ..
```

Expected:

```text
BUILD SUCCESSFUL
```

### 6. Run app

Open Android Studio:

```text
File → Open → android/
```

Run the app on emulator or device.

Expected:

```text
Hello World screen opens.
```

### 7. Commit M0 verification

```bash
git checkout -b feature/android-m0-repo-check
git add STATUS.md REPO_CHECK.md
git commit -m "docs: add repo check rules and M0 Android status"
git push origin feature/android-m0-repo-check
```

### 8. Verify on GitHub

Check these pages:

```text
https://github.com/AbinavDWH/PACT/blob/main/STATUS.md
https://github.com/AbinavDWH/PACT/blob/main/REPO_CHECK.md
https://github.com/AbinavDWH/PACT/tree/main/android/app/src/main
```

Or with GitHub CLI:

```bash
gh api repos/AbinavDWH/PACT/contents/STATUS.md --jq '.content' | base64 --decode
gh api repos/AbinavDWH/PACT/contents/REPO_CHECK.md --jq '.content' | base64 --decode
gh api repos/AbinavDWH/PACT/contents/android/app/src/main --jq '.[].name'
```

---

## ✅ M0 Done Criteria

M0 is complete only when all of these are true:

- GitHub repo checked.
- Latest commit checked.
- `android/` folder exists.
- `android/app/src/main` exists.
- `MainActivity.kt` exists.
- `class MainActivity` exists.
- `./gradlew :app:assembleDebug` passes.
- App opens Hello World screen.
- `STATUS.md` and `REPO_CHECK.md` are pushed to GitHub.

---

## 📱 Android Module Execution Plan

Use strict module execution. Do not jump ahead.

| Module | Name | Priority | Done Criteria |
|---|---|---|---|
| M0 | Repo + Hello World verification | Mandatory | App builds and runs. Repo verified. |
| M1 | App shell + home navigation | Mandatory | Home screen with buttons exists. |
| M2 | Field report form | Mandatory | User can enter need report. |
| M3 | Online API submission | Mandatory | Report can POST to FastAPI backend. |
| M4 | Offline queue storage | Mandatory | Failed report is stored locally. |
| M5 | SMS encoder fallback | Mandatory | Report becomes canonical SMS payload. |
| M6 | SMS fallback screen | Mandatory | SMS payload can be viewed/copied. |
| M7 | SMS decoder demo | High | Pasted SMS can be decoded. |
| M8 | Offline map marker demo | High / Optional | SMS marker updates map. |
| M9 | Delivery status update | Medium | Status SMS can be generated. |
| M10 | Sync worker + demo polish | High | Offline queue syncs when internet returns. |

Hackathon MVP minimum:

```text
M0 + M1 + M2 + M3 + M4 + M5 + M6
```

If time remains:

```text
M7 + M8 + M9 + M10
```

---

## 🧭 Module Execution Rule

For every module:

```text
1. Check GitHub/local repo
2. Create feature branch
3. Create required files
4. Implement required functions
5. Check files/folders/functions with grep/find
6. Build app
7. Test app
8. Commit and push
9. Verify on GitHub
10. Only then start next module
```

---

## 📦 Expected Android Files After MVP

After full Android MVP, expected package structure should look similar to:

```text
android/app/src/main/java/<package>/
├── MainActivity.kt
├── models/
│   └── FieldReport.kt
├── ui/
│   ├── HomeScreen.kt
│   ├── FieldReportScreen.kt
│   ├── SmsFallbackScreen.kt
│   ├── SmsInboxDemoScreen.kt
│   ├── OfflineMapScreen.kt
│   └── StatusScreen.kt
├── network/
│   ├── ApiClient.kt
│   └── ResiLinkApi.kt
├── data/
│   └── NeedRepository.kt
├── offline/
│   ├── OfflineQueue.kt
│   └── QueueStorage.kt
├── sms/
│   ├── SmsEncoder.kt
│   ├── SmsDecoder.kt
│   ├── Checksum.kt
│   └── SmsCodes.kt
├── map/
│   └── MarkerStore.kt
└── sync/
    └── SyncWorker.kt
```

If using XML instead of Compose, expected screens may be Activities:

```text
MainActivity.kt
FieldReportActivity.kt
SmsFallbackActivity.kt
SmsInboxDemoActivity.kt
MapActivity.kt
StatusActivity.kt
```

---

## 📱 Required SMS Behavior

Follow `sms.md`.

Canonical need SMS format:

```text
N|SEQ|ORG|LOC|RESOURCE|QTY|URGENCY|CRC
```

Example:

```text
N|001|NGO01|RA|F|300|H|B3
```

Canonical marker SMS format:

```text
M|SEQ|LOC|MARKER_TYPE|SEVERITY|DATA|CRC
```

Example:

```text
M|008|23.2599,77.4126|CR|9|F300|B4
```

Canonical status SMS format:

```text
S|SEQ|PLAN|STATUS|CRC
```

Example:

```text
S|004|PLAN101|3|A1
```

Checksum rule:

```text
Use XOR checksum over the message before the final checksum field.
```

Example:

```text
message = "N|001|NGO01|RA|F|300|H"
checksum = xor_checksum(message)
final_message = message + "|" + checksum
```

---

## 🚫 Out of My Scope Now

I am only building the Android app.

Do not assign me these unless asked:

- Backend Redis worker implementation
- Need Assessment Agent
- Resource Matching Agent
- Coordination Agent
- Web dashboard UI
- PostgreSQL/PostGIS setup
- Production Keycloak setup
- Real telecom SMS gateway
- Advanced optimization algorithm

These belong to teammate/backend scope.

---

## 👨‍💻 Teammate Scope

Teammate should continue:

```text
FastAPI backend → Redis → Need Assessment Agent → Resource Matching Agent → Coordination Agent → PostgreSQL → Web Dashboard
```

Teammate immediate task:

```text
Connect FastAPI backend to Redis and trigger the Need Assessment Agent to process decoded JSON.
```

Expected backend queues:

```text
sms_incoming_queue
need_assessment_queue
resource_matching_queue
coordination_queue
replanning_queue
sms_outgoing_queue
```

---

## 📅 Next Milestones

- [ ] Milestone 1: End-to-End Web Flow  
  Owner: Teammate  
  Flow:

  ```text
  Web Input -> Redis -> Agent -> DB -> Web Dashboard
  ```

- [ ] Milestone 2: SMS Fallback Demo  
  Owner: Teammate + Me  
  Flow:

  ```text
  Web SMS Simulator -> SMS Parser -> Agent -> Dashboard
  ```

- [ ] Milestone 3: Android App Offline Sync & SMS Encoding  
  Owner: Me  
  Flow:

  ```text
  Android Field Report -> Offline Queue -> SMS Payload -> SMS Simulator -> Backend
  ```

- [ ] Milestone 4: Pitch Deck & Demo Video Recording  
  Owner: All teammates

---

## 🧾 Current Likely Task

The current likely task is:

```text
Start M0: verify GitHub repo, verify Android Hello World app, build successfully, push STATUS.md and REPO_CHECK.md.
```

Do not begin M1 until M0 is verified on GitHub.
```
