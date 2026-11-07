# Physical SDKs, dependencies, caches and build outputs all remain under 丢给ai玩.
# A temporary drive letter only provides ASCII command arguments to native tools.
param(
    [ValidateSet('analyze','test','apk')][string]$Action='analyze',
    [ValidateSet('all','android-arm64')][string]$TargetPlatform='all'
)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$workspaceRoot=Split-Path (Split-Path $projectRoot -Parent) -Parent
$toolsRoot=Join-Path $workspaceRoot '.tools'
$buildRoot=Join-Path $toolsRoot 'hz-build'
$createdDrive=$false
$previousLocation=Get-Location
$exitCode=0

function Copy-Cache([string]$Source,[string]$Destination) {
    if (Test-Path -LiteralPath "$Destination/.workspace-cache-seed-complete") { return }
    if (Test-Path -LiteralPath $Source) {
        & robocopy $Source $Destination /E /XJ /NFL /NDL /NJH /NJS /NC /NS /NP /R:1 /W:1 | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "Cache copy failed: $Source" }
        Set-Content -LiteralPath "$Destination/.workspace-cache-seed-complete" -Value 'Copied existing cache; future writes remain in the workspace.' -Encoding ascii
    }
}

try {
    if (Test-Path 'R:/') {
        throw 'R: is in use. Refusing to replace an existing drive; choose another free alias in this script.'
    }
    & subst R: $workspaceRoot
    if ($LASTEXITCODE -ne 0) { throw 'Cannot create temporary workspace alias.' }
    $createdDrive=$true
    New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
    & robocopy (Join-Path $projectRoot 'app') $buildRoot /E /XD build .dart_tool .gradle /NFL /NDL /NJH /NJS /NC /NS /NP /R:1 /W:1 | Out-Null
    if ($LASTEXITCODE -ge 8) { throw 'Application source copy failed.' }

    # Read old caches, but direct all subsequent writes to the workspace copy.
    Write-Output 'Preparing local dependency caches inside the workspace...'
    Copy-Cache "$env:LOCALAPPDATA/Pub/Cache" "$toolsRoot/pub-cache"
    Copy-Cache "$env:USERPROFILE/.gradle" "$toolsRoot/gradle-cache"
    $env:PUB_CACHE='R:/.tools/pub-cache'
    $env:GRADLE_USER_HOME='R:/.tools/gradle-cache'
    $env:JAVA_HOME='R:/.tools/jdk17/jdk-17.0.20.1+1'
    $env:PATH="$env:JAVA_HOME/bin;$env:PATH"
    $env:ANDROID_HOME='R:/android-sdk'
    $env:ANDROID_SDK_ROOT='R:/android-sdk'
    $env:ANDROID_USER_HOME='R:/.tools/android-user'
    $env:FLUTTER_ROOT='R:/flutter-sdk/flutter'
    $env:APPDATA='R:/.tools/user-state/roaming'
    $env:LOCALAPPDATA='R:/.tools/user-state/local'
    $env:TEMP='R:/.tools/tmp'
    $env:TMP=$env:TEMP
    New-Item -ItemType Directory -Path "$toolsRoot/tmp" -Force | Out-Null
    New-Item -ItemType Directory -Path "$toolsRoot/user-state/roaming","$toolsRoot/user-state/local","$toolsRoot/android-user" -Force | Out-Null
    @'
sdk.dir=R:/android-sdk
flutter.sdk=R:/flutter-sdk/flutter
'@ | Set-Content -LiteralPath "$buildRoot/android/local.properties" -Encoding ascii
    Set-Location 'R:/.tools/hz-build'
    & 'R:/flutter-sdk/flutter/bin/flutter.bat' pub get --offline
    if ($LASTEXITCODE -ne 0) { throw 'Offline pub get failed; inspect missing packages before downloading.' }
    if ($Action -eq 'apk') {
        $apkArguments=@('build','apk','--release','--no-pub')
        if ($TargetPlatform -ne 'all') {
            $apkArguments+=@('--target-platform',$TargetPlatform)
        }
        & 'R:/flutter-sdk/flutter/bin/flutter.bat' @apkArguments
    } elseif ($Action -eq 'test') {
        & 'R:/flutter-sdk/flutter/bin/flutter.bat' test --no-pub
    } else {
        & 'R:/flutter-sdk/flutter/bin/flutter.bat' analyze --no-pub
    }
    $exitCode=$LASTEXITCODE
    if ($exitCode -ne 0) { throw "Flutter $Action failed: $exitCode" }
    # Publishing is deliberately separate: an intermediate build is not a release.
} finally {
    Set-Location $previousLocation
    if ($createdDrive) { & subst R: /D }
}
exit $exitCode
