```md
# ResiLink - Project Status

Project: Privacy-Preserving Multi-Agent Humanitarian Coordination Platform  
Hackathon: Phoenix Hacks - Track 6  
Repo: https://github.com/AbinavDWH/PACT  
Last Updated: August 18, 2026  
Overall MVP Progress: In Progress - Android core modules M0 to M3 verified on `testabi8`. M4 offline queue and M5 SMS encoder implemented locally and pending final verification/push. M6 is the next module.

---

## Repo Verification Summary

Before doing any work, follow:

```text
REPO_CHECK.md
```

Required local checks:

```bash
git fetch --all --prune
git branch --show-current
git status --short
git log --oneline --date=short -5
```

Required GitHub checks:

```text
https://github.com/AbinavDWH/PACT
https://github.com/AbinavDWH/PACT/commits/testabi8
https://github.com/AbinavDWH/PACT/blob/testabi8/STATUS.md
https://github.com/AbinavDWH/PACT/tree/testabi8/android/app/src/main
```

Required Android package detection:

```bash
NAMESPACE=$(grep -E "namespace" android/app/build.gradle.kts | sed -E 's/.*"(.+)".*/\1/')
PKG_DIR=android/app/src/main/java/$(echo $NAMESPACE | tr '.' '/')

echo "NAMESPACE=$NAMESPACE"
echo "PKG_DIR=$PKG_DIR"
```

Known package:

```text
org.humanitarian.fieldapp
```

Known Android source path:

```text
android/app/src/main/java/org/humanitarian/fieldapp/
```

---

## Current Work Split

| Area | Owner | Status | Specific Focus |
| --- | --- | --- | --- |
| Android App | Me | In Progress | Android MVP modules M0 to M5 done locally. Verify and push M4/M5. Start M6 next. |
| Backend API + Redis + Agents | Teammate | In Progress | Connect FastAPI to Redis and trigger Need Assessment Agent. |
| Web Dashboard | Teammate | Pending | Dashboard panels, SMS simulator, map panel. |
| Database / PostGIS | Teammate | In Progress | Schema and spatial queries. |
| SMS Protocol | Shared / Backend | Done | Canonical and legacy parsing, XOR checksum implemented. |

---

## Completed Android Modules

| Module | Name | Status | Notes |
| --- | --- | --- | --- |
| M0 | Repo + Hello World verification | Done | Android project exists and builds. Repo docs added. |
| M1 | App shell + home navigation | Done | Home screen with navigation buttons exists. Clean UI theme added. |
| M2 | Field report form | Done | User can enter a need report using dropdowns and radio buttons. |
| M3 | Online API submission | Done | Field report can POST to FastAPI backend using `ApiClient.kt`. |
| M4 | Offline queue storage | Implemented locally | Failed API submissions are saved locally using `OfflineQueue.kt`. Needs final push/verification. |
| M5 | SMS encoder fallback | Implemented locally | Failed reports can be converted into canonical SMS payload. Needs final push/verification. |

---

## Specific DO THIS NOW

Current Active Module:

```text
M5 verification and push
```

Do not start M6 until M4 and M5 are verified on GitHub.

### M4 and M5 Verification Checklist

1. Check branch:

```bash
git checkout testabi8
git pull origin testabi8
```

2. Check M4 offline queue file:

```bash
find android/app/src/main -type f -name "OfflineQueue.kt"
```

Expected:

```text
android/app/src/main/java/org/humanitarian/fieldapp/offline/OfflineQueue.kt
```

3. Check M5 SMS files:

```bash
find android/app/src/main -type f -name "Checksum.kt"
find android/app/src/main -type f -name "SmsCodes.kt"
find android/app/src/main -type f -name "SmsEncoder.kt"
```

Expected:

```text
android/app/src/main/java/org/humanitarian/fieldapp/sms/Checksum.kt
android/app/src/main/java/org/humanitarian/fieldapp/sms/SmsCodes.kt
android/app/src/main/java/org/humanitarian/fieldapp/sms/SmsEncoder.kt
```

4. Check required functions:

```bash
grep -R "fun encodeNeed" -n android/app/src/main
grep -R "fun xorChecksum" -n android/app/src/main
grep -R "fun resourceCode" -n android/app/src/main
grep -R "fun urgencyCode" -n android/app/src/main
grep -R "fun locationCode" -n android/app/src/main
grep -R "fun addReport" -n android/app/src/main
```

Expected: at least one match for each.

5. Build Android app:

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

6. Test offline queue and SMS encoder:

- Stop backend or enable airplane mode.
- Open Field Report.
- Submit a valid report.
- Expected result:
  - Report saved to offline queue.
  - SMS fallback payload displayed.
  - Payload format:

```text
N|SEQ|ORG|LOC|RESOURCE|QTY|URGENCY|CRC
```

Example:

```text
N|001|NGO01|RA|F|300|H|XX
```

7. Commit and push:

```bash
git add android/app/src/main/java/org/humanitarian/fieldapp/offline/
git add android/app/src/main/java/org/humanitarian/fieldapp/sms/
git add android/app/src/main/java/org/humanitarian/fieldapp/ui/FieldReportScreen.kt

git commit -m "feat(android): add M4 offline queue and M5 SMS encoder"
git push origin testabi8
```

8. Verify on GitHub:

```text
https://github.com/AbinavDWH/PACT/tree/testabi8/android/app/src/main/java/org/humanitarian/fieldapp/offline
https://github.com/AbinavDWH/PACT/tree/testabi8/android/app/src/main/java/org/humanitarian/fieldapp/sms
```

---

## Android Module Execution Plan

Use strict module execution. Do not jump ahead.

| Module | Name | Priority | Status | Done Criteria |
| --- | --- | --- | --- | --- |
| M0 | Repo + Hello World verification | Mandatory | Done | App builds and runs. Repo verified. |
| M1 | App shell + home navigation | Mandatory | Done | Home screen with buttons exists. |
| M2 | Field report form | Mandatory | Done | User can enter need report. |
| M3 | Online API submission | Mandatory | Done | Report can POST to FastAPI backend. |
| M4 | Offline queue storage | Mandatory | Needs verification | Failed report is stored locally. |
| M5 | SMS encoder fallback | Mandatory | Needs verification | Report becomes canonical SMS payload. |
| M6 | SMS fallback screen | Mandatory | Pending | SMS payload can be viewed and copied. |
| M7 | SMS decoder demo | High | Pending | Pasted SMS can be decoded. |
| M8 | Offline map marker demo | High / Optional | Pending | SMS marker updates map. |
| M9 | Delivery status update | Medium | Pending | Status SMS can be generated. |
| M10 | Sync worker + demo polish | High | Pending | Offline queue syncs when internet returns. |

Hackathon MVP minimum:

```text
M0 + M1 + M2 + M3 + M4 + M5 + M6
```

If time remains:

```text
M7 + M8 + M9 + M10
```

---

## Current Android File State

Expected files already created:

```text
android/app/src/main/java/org/humanitarian/fieldapp/
├── MainActivity.kt
├── models/
│   └── FieldReport.kt
├── network/
│   └── ApiClient.kt
├── offline/
│   └── OfflineQueue.kt
├── sms/
│   ├── Checksum.kt
│   ├── SmsCodes.kt
│   └── SmsEncoder.kt
└── ui/
    ├── FieldReportScreen.kt
    ├── HomeScreen.kt
    ├── PlaceholderScreen.kt
    └── theme/
        ├── Color.kt
        └── Theme.kt
```

Expected manifest permission:

```xml
<uses-permission android:name="android.permission.INTERNET" />
```

Expected local HTTP support for backend testing:

```xml
android:usesCleartextTraffic="true"
```

---

## UI and UX Rules

Use clean UI only.

Do not use emojis in the app UI.

Use this palette:

```text
Background: rgb(255, 250, 243)
Surface: rgb(255, 242, 219)
Accent: rgb(255, 229, 191)
Primary action: rgb(246, 36, 64)
```

Compose color values:

```kotlin
val PactBackground = Color(0xFFFFFAF3)
val PactSurface = Color(0xFFFFF2DB)
val PactAccent = Color(0xFFFFE5BF)
val PactPrimary = Color(0xFFF62440)
```

---

## Required SMS Behavior

Follow:

```text
sms.md
```

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

Use XOR checksum over the message before the final checksum field.

Example:

```text
message = "N|001|NGO01|RA|F|300|H"
checksum = xor_checksum(message)
final_message = message + "|" + checksum
```

---

## Next Module After M5

Next module:

```text
M6 - SMS fallback screen
```

M6 goal:

```text
User can view and copy queued SMS payloads.
```

Expected M6 files:

```text
android/app/src/main/java/org/humanitarian/fieldapp/ui/SmsFallbackScreen.kt
```

Expected M6 behavior:

- Show number of queued reports.
- Show each queued report as a canonical SMS payload.
- Allow user to copy SMS payload.
- Keep clean UI using the project palette.
- No emojis.
- Update `MainActivity.kt` to open `SmsFallbackScreen` from home.

M6 done criteria:

- `SmsFallbackScreen.kt` exists.
- Queued SMS payloads can be viewed.
- SMS payload can be copied.
- App builds successfully.
- Code pushed to GitHub.

---

## Module Execution Rule

For every module:

1. Check GitHub/local repo.
2. Create or use feature branch.
3. Create required files.
4. Implement required functions.
5. Check files, folders, and functions with `grep` and `find`.
6. Build app.
7. Test app.
8. Commit and push.
9. Verify on GitHub.
10. Only then start the next module.

---

## Out of My Scope Now

I am only building the Android app.

Do not assign these unless asked:

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

## Teammate Scope

Teammate should continue:

```text
FastAPI backend -> Redis -> Need Assessment Agent -> Resource Matching Agent -> Coordination Agent -> PostgreSQL -> Web Dashboard
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

## Next Milestones

### Milestone 1: End-to-End Web Flow

Owner: Teammate

Flow:

```text
Web Input -> Redis -> Agent -> DB -> Web Dashboard
```

### Milestone 2: SMS Fallback Demo

Owner: Teammate + Me

Flow:

```text
Web SMS Simulator -> SMS Parser -> Agent -> Dashboard
```

### Milestone 3: Android App Offline Sync and SMS Encoding

Owner: Me

Flow:

```text
Android Field Report -> Offline Queue -> SMS Payload -> SMS Simulator -> Backend
```

### Milestone 4: Pitch Deck and Demo Video Recording

Owner: All teammates

---

## Current Likely Task

The current likely task is:

```text
Verify and push M4 offline queue and M5 SMS encoder, then start M6 SMS fallback screen.
```

Do not begin M6 until M4 and M5 are verified on GitHub.
```