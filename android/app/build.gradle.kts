// The seeker/helper app.
//
// Dependency policy is deliberately mean. Every library added here is a
// download that has to succeed on venue wifi the morning of a demo, so:
//
//   - no Retrofit/OkHttp  -> java.net.HttpURLConnection on Dispatchers.IO
//   - no kotlinx.serialization plugin -> org.json, which ships with Android
//   - no Room             -> the outbox is an append-only JSON-lines file
//   - no Play Services    -> android.location.LocationManager, which also
//                            keeps GPS working with no network at all, which
//                            is the entire point of this app
//
// Compose stays, because the alternative is several hundred lines of XML.

import java.util.Properties

plugins {
    id("com.android.application") version "8.7.3"
    kotlin("android") version "2.0.21"
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.21"
    // Reads google-services.json and generates the Firebase config resources.
    // Applied conditionally below: the build must not break for anyone who
    // clones without the file.
    id("com.google.gms.google-services") version "4.4.2" apply false
}

// FCM is optional at build time. Without google-services.json the app still
// compiles and runs -- dispatch simply falls back to the outbox, which is what
// it did before push existed. A hard dependency here would mean nobody can
// build the app without a Firebase project of their own.
val hasFirebase = file("google-services.json").exists()
if (hasFirebase) {
    apply(plugin = "com.google.gms.google-services")
} else {
    logger.lifecycle("google-services.json absent: building without FCM push")
}

// Machine-local build settings.
//
// Gradle does NOT expose local.properties as project properties -- the Android
// plugin reads it only for sdk.dir. So a value written there was silently
// ignored and the build fell back to the hardcoded defaults below, which is
// indistinguishable from a working build until the phone cannot reach the
// server. Read it explicitly, and let -P still win so a one-off override
// works without editing the file.
val localProps = Properties().apply {
    val f = rootProject.file("local.properties")
    if (f.exists()) f.inputStream().use { p -> load(p) }
}

fun setting(name: String, fallback: String): String =
    (project.findProperty(name) as String?) ?: localProps.getProperty(name) ?: fallback

android {
    namespace = "org.pact.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "org.pact.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1"

        // The phone is not on localhost. Override per machine in
        // android/local.properties or with -PpactApiBase=...
        val apiBase = setting("pactApiBase", "http://192.168.1.6:8000")
        buildConfigField("String", "API_BASE", "\"$apiBase\"")

        // Where an SMS-fallback message is sent when there is no data. A real
        // deployment uses a shortcode; the demo uses a second handset or the
        // backend's /sms/webhook via the simulator.
        val smsTo = setting("pactSmsTo", "+919999999999")
        buildConfigField("String", "SMS_TO", "\"$smsTo\"")

        // Lets the app skip the FCM code paths entirely when it was built
        // without a Firebase project, rather than catching NoClassDefFoundError.
        buildConfigField("boolean", "HAS_FCM", file("google-services.json").exists().toString())

        // Diagnostic only: send a plain ASCII body instead of the codec string,
        // to separate "the modem rejects this content" from "the modem rejects
        // this app's sends". Never enabled in a normal build.
        val plainTest = (project.findProperty("pactSmsPlainTest") as String?) == "true"
        buildConfigField("boolean", "SMS_PLAIN_TEST", plainTest.toString())

        // Diagnostic only: take the SMS path even when data is available.
        // Needed because on an IMS/VoLTE network SMS rides the data bearer, so
        // "turn data off to force SMS" can disable SMS itself -- the two cannot
        // be tested independently without this.
        val forceSms = (project.findProperty("pactForceSms") as String?) == "true"
        buildConfigField("boolean", "FORCE_SMS", forceSms.toString())
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    buildTypes {
        debug { isMinifyEnabled = false }
        release { isMinifyEnabled = false }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    sourceSets {
        named("main") { kotlin.srcDirs("src/main/kotlin") }
        named("test") { kotlin.srcDirs("src/test/kotlin") }
    }

    // Plain JVM unit tests, deliberately not instrumented tests. The encoding
    // contract between the chip screen and the codec has to be verifiable with
    // no device attached; otherwise its first real exercise is a phone in
    // someone's hand at a demo.
    testOptions { unitTests.isReturnDefaultValues = true }

    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
}

kotlin { jvmToolchain(17) }

dependencies {
    // One codec, shared with the JVM parity test. What the phone sends is what
    // that test verified byte-for-byte against Python.
    implementation(project(":codec"))

    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")

    // The library is unconditional so Push.kt always compiles; only the
    // google-services *plugin* above needs the JSON. Without it, Firebase is
    // simply never initialised and BuildConfig.HAS_FCM gates every call site.
    implementation(platform("com.google.firebase:firebase-bom:33.7.0"))
    implementation("com.google.firebase:firebase-messaging")

    val composeBom = platform("androidx.compose:compose-bom:2024.10.01")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")

    testImplementation(kotlin("test"))
}

tasks.withType<Test>().configureEach {
    useJUnitPlatform()
    testLogging { showStandardStreams = true }
}

// The tables the app encodes with must be the same file the backend and the
// parity test read. Copying at build time rather than committing a second copy
// is what stops the two drifting.
val syncCodecTables by tasks.registering(Copy::class) {
    from(rootProject.layout.projectDirectory.dir("../shared/codec"))
    include("pact_tables.v1.json")
    into("src/main/assets")
}
tasks.named("preBuild") { dependsOn(syncCodecTables) }
