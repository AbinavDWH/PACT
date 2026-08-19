# PACT Android

Built without Android Studio — JDK, Gradle, and the Android command-line tools
are enough, and deployment goes straight to a physical device over USB.

## Layout

```
android/
├── settings.gradle.kts
├── codec/                 pure JVM Kotlin module
│   ├── src/main/kotlin/org/pact/codec/     PactCodec.kt, Tables.kt
│   ├── src/main/assets/                    synced from shared/codec/
│   └── src/test/kotlin/org/pact/codec/     ParityTest.kt
└── app/                   Android module (not built yet)
```

`codec` is a **plain JVM module on purpose**. The cross-language parity test
needs only a JDK — no Android SDK, no device, no emulator — so the codec can be
verified long before any app exists. The `app` module consumes the same sources.

## Stage 1 — verify the codec (JDK only)

```powershell
winget install EclipseAdoptium.Temurin.17.JDK
# reopen the terminal so JAVA_HOME is picked up
cd android
gradle wrapper            # once, if gradle is on PATH; otherwise use ./gradlew
./gradlew :codec:test
```

Expected: `parity OK: 11 vectors`.

That test reads the **same** `shared/codec/vectors.json` the Python pytest suite
reads. If a table edit or a rounding difference makes Kotlin disagree with
Python by one character, it fails here rather than producing an SMS the backend
rejects mid-demo. It is the highest-value test in the Android effort.

## Stage 2 — build and install the APK

```powershell
winget install Google.AndroidCLI          # sdkmanager, adb
sdkmanager "platform-tools" "platforms;android-35" "build-tools;35.0.0"
```

Set `ANDROID_HOME` to the SDK directory, then:

```powershell
./gradlew :app:assembleDebug
adb devices                                # confirm the phone is listed
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

### On the phone, once

1. Settings → About phone → tap **Build number** seven times.
2. Settings → Developer options → enable **USB debugging**.
3. Plug in over USB, then **accept the RSA fingerprint prompt** on the phone.

`adb devices` showing `unauthorized` means step 3 has not been accepted yet.

## Permissions the app needs

| Permission | For |
|---|---|
| `SEND_SMS`, `RECEIVE_SMS`, `READ_SMS` | the SMS fallback transport |
| `ACCESS_FINE_LOCATION` | GPS for the PACK10 coordinate |
| `INTERNET`, `ACCESS_NETWORK_STATE` | the HTTP path and connectivity detection |

SMS permissions are runtime-granted and Play Store policy restricts them
heavily. Irrelevant for a sideloaded demo build; it would matter for release.

## Talking to a dev backend from the phone

The phone is not on `localhost`. Point the app at the machine's LAN address:

```
NEXT_PUBLIC_API_BASE_URL / BuildConfig.API_BASE = http://192.168.x.x:8000
```

Both servers must bind `0.0.0.0`, and `next.config.ts` already allowlists the
private LAN ranges — Next 16 blocks cross-origin dev resources by default, which
otherwise returns 403 on every chunk and looks like a broken app rather than a
config block.

## Status

- `codec/` — **compiles and passes.** `gradle :codec:test --rerun-tasks` prints
  `parity OK: 11 vectors`. (This section previously said "written, never
  compiled"; that was true before the JDK landed on `E:`.)
- `app/` — **builds.** `gradle :app:assembleDebug` produces a 9.6 MB
  `app-debug.apk`. 13 JVM unit tests pass.
- **Not installed on a phone.** The vivo V2336 was not plugged in during the
  build session, so `adb devices` was empty and nothing has run on real
  hardware. Everything below the APK line is verified; the app's behaviour on a
  device is not. See "What is unverified".

## The app module

```
app/src/main/kotlin/org/pact/app/
  MainActivity.kt      permissions up front, wiring
  Session.kt           uid / token / seq, SharedPreferences
  Api.kt               HttpURLConnection, no Retrofit
  Outbox.kt            append-only JSON-lines send queue
  Transport.kt         HTTP, then SMS, then queue
  Loc.kt               LocationManager (not Play Services)
  Options.kt           chip taxonomy, read from the codec tables
  ui/                  Compose screens
app/src/test/kotlin/   SelectionTest: the encoding contract, no device needed
```

### Dependency policy

Deliberately mean, because every library is a download that has to succeed on
venue wifi the morning of a demo:

| Not used | Used instead | Why |
|---|---|---|
| Retrofit / OkHttp | `java.net.HttpURLConnection` | four verbs and a bearer header |
| kotlinx.serialization | `org.json` | ships with Android |
| Room | append-only JSON-lines file | the queue needs four operations |
| Play Services location | `android.location.LocationManager` | fused location leans on network positioning; this app must produce a fix with **no data at all** |

Compose stays: the alternative is several hundred lines of XML.

### The taxonomy is not duplicated

Every chip is generated from `shared/codec/pact_tables.v1.json`, copied into
assets at build time by `syncCodecTables`. There is no list of situations or
injury levels written out in the UI layer. A second copy would drift, and the
failure would be a chip that encodes to a code the backend rejects — surfacing
as a rejected emergency, not a UI bug.

## Stage 2 — build and install the APK

```bash
source android/env.sh
cd android
gradle :app:assembleDebug

# Point it at this machine's LAN address, not localhost:
gradle :app:assembleDebug -PpactApiBase=http://192.168.1.6:8000

adb devices                      # confirm the phone is listed
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

`-PpactApiBase` and `-PpactSmsTo` override `BuildConfig.API_BASE` and
`BuildConfig.SMS_TO`. The backend must be started with `--host 0.0.0.0`, or the
phone cannot reach it however correct the address is.

## Gateway mode — real SMS, no vendor

Install the **same APK** on a second handset with a SIM, open it, and tap
*"Use this phone as the SMS gateway"* on the sign-up screen. Grant RECEIVE_SMS
and switch gateway mode on. Point `BuildConfig.API_BASE` at the backend as
usual.

That phone now catches the inbound SMS off the cellular network and POSTs PACT
frames to `/api/v1/sms/webhook`. The seeker phone's airplane-mode message
becomes a real end-to-end path instead of a string someone pastes into the
simulator.

### Why not Twilio or MSG91

Outbound A2P SMS in India requires DLT registration with TRAI — entity, header
and template approval, taking days to weeks — and inbound SMS on an Indian
virtual number is not sold to unregistered entities at all. No vendor
integration can be made to work on a hackathon timeline at any price. Two
ordinary SIMs carry the same real cellular SMS with nothing to register.

### What the gateway will not forward

A gateway handset still receives banking OTPs, delivery codes and private
messages. `SmsGateway.looksLikePact` forwards only messages whose first field
is a protocol frame type (`Q`, `G`, `C`, `S`) **and** which carry at least four
fields. Everything else is dropped without being logged in full.

The filter is deliberately asymmetric: wrongly ignoring a real request costs
one retry from an app that already retries; wrongly forwarding someone's OTP is
irreversible. `SmsGatewayTest` has 12 tests, most of which assert **refusal** —
OTPs, personal messages, pipe-heavy marketing spam, transaction alerts, and
lowercase frames.

## What is unverified

Honest list, because none of this has run on hardware:

- Every Compose screen. They compile; they have never been rendered.
- The runtime permission flow.
- A real GPS fix from `LocationManager`.
- An actual `SmsManager.sendTextMessage`.
- The outbox surviving a real process death.

What **is** verified without a device:

- The APK builds.
- `SelectionTest` (13 tests) round-trips every chip the UI can offer through
  the codec, checks the frame is one GSM-7 segment, and asserts an incomplete
  selection throws rather than emitting a frame with a meaningful zero in it.
- The parity test proves the Kotlin codec is byte-identical to Python.
- The exact string that selection produces was posted at the live backend and
  accepted, decoding to the right situation, injury, mobility, urgency, needs
  and vulnerability.
