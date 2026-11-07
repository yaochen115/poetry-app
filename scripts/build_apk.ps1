# 构建「红妆」release APK
# 前提：源码已同步到 ASCII 构建目录 D:\hz-app（见《交接文档》§构建环境，或先跑 build_sync.ps1）。
# 用法：powershell -ExecutionPolicy Bypass -File scripts\build_apk.ps1
$ErrorActionPreference = "Stop"

$BUILD_DIR   = "D:\hz-app"
$RELEASE_DIR = "D:\WORK\丢给ai玩\诗词软件\hongzhuang-project\release"

# 三个 ASCII 工具链（中文路径会导致 Dart 原生工具链与 Kotlin 增量编译报错）
$env:JAVA_HOME       = "D:\jdk17\jdk-17.0.20.1+1"
$env:PATH            = "D:\jdk17\jdk-17.0.20.1+1\bin;$env:PATH"
$env:ANDROID_HOME    = "D:\android-sdk"
$env:ANDROID_SDK_ROOT = "D:\android-sdk"

Push-Location $BUILD_DIR
try {
    & "D:\flutter\bin\flutter" build apk --release
    if ($LASTEXITCODE -ne 0) { throw "flutter build failed: $LASTEXITCODE" }
} finally { Pop-Location }

New-Item -ItemType Directory -Force $RELEASE_DIR | Out-Null
Copy-Item "$BUILD_DIR\build\app\outputs\flutter-apk\app-release.apk" "$RELEASE_DIR\红妆-v1.0.2.apk" -Force
Write-Output "OK: $RELEASE_DIR\红妆-v1.0.2.apk"
