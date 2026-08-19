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

- `codec/` — **written, never compiled.** No JDK was available on the build
  machine. Expect to fix compile errors on the first `gradlew test`.
- `app/` — not started.
