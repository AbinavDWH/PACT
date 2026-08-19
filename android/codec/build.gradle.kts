// Plain JVM module so the parity test runs without an Android SDK or emulator.
// The same sources are consumed by the Android app module; only the asset
// loading differs (Tables.loadFromText(assets.open(...)) there).
plugins {
    kotlin("jvm") version "2.0.21"
}

repositories { mavenCentral() }

dependencies {
    testImplementation(kotlin("test"))
}

kotlin { jvmToolchain(17) }

sourceSets {
    main { kotlin.srcDirs("src/main/kotlin") }
    test { kotlin.srcDirs("src/test/kotlin") }
}

tasks.test {
    useJUnitPlatform()
    testLogging { showStandardStreams = true }
}

// Keeps the Android asset copy in step with the shared source of truth.
val syncCodecTables by tasks.registering(Copy::class) {
    from(rootProject.layout.projectDirectory.dir("../shared/codec"))
    include("pact_tables.v1.json", "vectors.json")
    into("src/main/assets")
}
tasks.named("processResources") { dependsOn(syncCodecTables) }
