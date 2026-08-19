# Source this before any Gradle / adb work:  . .\android\env.ps1
#
# Everything lives on E: -- nothing was installed to C:, and no system
# environment variables were changed. This script is per-session only.

$env:JAVA_HOME        = "E:\PACT\tools\jdk17"
$env:ANDROID_HOME     = "E:\PACT\tools\android-sdk"
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
$env:GRADLE_USER_HOME = "E:\PACT\tools\gradle-home"   # keeps the Gradle cache off C:
$env:Path = "$env:JAVA_HOME\bin;E:\PACT\tools\gradle\bin;$env:ANDROID_HOME\platform-tools;$env:ANDROID_HOME\cmdline-tools\latest\bin;$env:Path"

Write-Output "java   : $((java -version 2>&1)[0])"
Write-Output "gradle : $((gradle --version 2>$null | Select-String '^Gradle'))"
Write-Output "adb    : $((adb version 2>$null)[0])"
Write-Output "sdk    : $env:ANDROID_HOME"
