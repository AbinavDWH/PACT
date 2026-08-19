// Plain Gradle build, no Android Studio required.
//
// `codec` is a pure JVM Kotlin module on purpose: the cross-language parity
// test needs only a JDK, so the codec can be verified long before an Android
// SDK, a device, or an emulator exists. The `app` module (added later) consumes
// the same sources.

pluginManagement {
    repositories {
        gradlePluginPortal()
        google()
        mavenCentral()
    }
}

dependencyResolutionManagement {
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "pact"

include(":codec")
