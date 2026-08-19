#!/usr/bin/env bash
# Source this before any Gradle / adb work:  source android/env.sh
#
# Everything lives on E: -- nothing was installed to C:, and no system
# environment variables were changed. This script is per-session only.

export JAVA_HOME="/e/PACT/tools/jdk17"
export ANDROID_HOME="/e/PACT/tools/android-sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export GRADLE_USER_HOME="/e/PACT/tools/gradle-home"   # keeps the Gradle cache off C:
export PATH="$JAVA_HOME/bin:/e/PACT/tools/gradle/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"

echo "java   : $(java -version 2>&1 | head -1)"
echo "gradle : $(gradle --version 2>/dev/null | grep '^Gradle')"
echo "adb    : $(adb version 2>/dev/null | head -1)"
echo "sdk    : $ANDROID_HOME"
