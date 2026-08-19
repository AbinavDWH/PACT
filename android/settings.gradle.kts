// Plain Gradle build, no Android Studio required.
//
// `codec` is a pure JVM Kotlin module on purpose: the cross-language parity
// test needs only a JDK, so the codec can be verified long before an Android
// SDK, a device, or an emulator exists. The `app` module consumes the same
// sources through a project dependency -- there is exactly one codec, and the
// thing the phone sends is the thing the parity test checked.

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
include(":app")
