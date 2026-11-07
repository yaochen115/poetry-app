# 把源码 app/ 同步到 ASCII 构建目录 D:\hz-app，并写回 ASCII 专用配置。
# 之后用 build_apk.ps1 构建。用法：powershell -ExecutionPolicy Bypass -File scripts\build_sync.ps1
$ErrorActionPreference = "Stop"

$SRC = "D:\WORK\丢给ai玩\诗词软件\hongzhuang-project\app"
$DST = "D:\hz-app"

# /MIR 镜像（排除生成物 build/.dart_tool），保证 D:\hz-app 与 app/ 源码一致
robocopy $SRC $DST /MIR /XD build .dart_tool /NFL /NDL /NJH /NJS /NC /NS /NP /R:1 /W:1 | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed: $LASTEXITCODE" }

# local.properties 必须指向 ASCII 工具链（中文路径会让 Dart 原生工具链崩）
@"
sdk.dir=D:/android-sdk
flutter.sdk=D:/flutter
flutter.buildMode=release
flutter.versionName=1.0.2
flutter.versionCode=3
"@ | Set-Content -Path "$DST\android\local.properties" -Encoding ascii

Write-Output "OK: 已同步到 $DST"
