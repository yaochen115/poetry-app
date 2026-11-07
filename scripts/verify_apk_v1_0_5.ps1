$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$workspaceRoot=Split-Path (Split-Path $projectRoot -Parent) -Parent
if (Test-Path 'R:/') { throw 'R: is occupied; refusing to replace it.' }
& subst R: $workspaceRoot
if ($LASTEXITCODE -ne 0) { throw 'Cannot create temporary workspace alias.' }
try {
    $out=Join-Path $projectRoot 'expansion/release-audits'
    New-Item -ItemType Directory -Path $out -Force | Out-Null
    $newApk='R:/.tools/hz-build/build/app/outputs/flutter-apk/app-release.apk'
    & 'R:/android-sdk/build-tools/36.0.0/aapt2.exe' dump badging $newApk > (Join-Path $out 'apk-v1.0.5-badging.txt')
    if ($LASTEXITCODE -ne 0) { throw 'APK badging failed.' }
    New-Item -ItemType Directory -Path 'R:/.tools/apk-verification' -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $projectRoot 'release/红妆-v1.0.4.apk') -Destination 'R:/.tools/apk-verification/old-v1.0.4.apk' -Force
    $env:JAVA_HOME='R:/.tools/jdk17/jdk-17.0.20.1+1'
    $env:PATH="$env:JAVA_HOME/bin;$env:PATH"
    & 'R:/android-sdk/build-tools/36.0.0/apksigner.bat' verify --print-certs $newApk > (Join-Path $out 'apk-v1.0.5-signature.txt')
    if ($LASTEXITCODE -ne 0) { throw 'New APK signature verification failed.' }
    & 'R:/android-sdk/build-tools/36.0.0/apksigner.bat' verify --print-certs 'R:/.tools/apk-verification/old-v1.0.4.apk' > (Join-Path $out 'apk-v1.0.4-signature-check.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Old APK signature verification failed.' }
} finally { & subst R: /D }
