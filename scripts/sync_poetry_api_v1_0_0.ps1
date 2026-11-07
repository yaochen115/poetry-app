param(
    [switch]$Offline,
    [switch]$Preview,
    [int]$MaxRequests = 2000,
    [int]$Workers = 2,
    [double]$Interval = 1
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$taskPython = $env:HONGZHUANG_PYTHON
if (-not $taskPython) {
    $existingPython = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($existingPython) { $taskPython = $existingPython.Source }
}
if (-not $taskPython) {
    $runtimePython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    if (Test-Path -LiteralPath $runtimePython) { $taskPython = $runtimePython }
}
if (-not $taskPython) { throw 'Python not found. Set HONGZHUANG_PYTHON to an existing python.exe; this script installs nothing.' }
$taskArguments = @('-B', (Join-Path $PSScriptRoot 'sync_poetry_api_v1_0_0.py'), '--workers', "$Workers", '--interval', "$Interval", '--max-requests', "$MaxRequests")
if ($Offline) { $taskArguments += '--offline' }
if (-not $Preview) { $taskArguments += '--apply' }
Push-Location $projectRoot
try { & $taskPython @taskArguments; $taskResult = $LASTEXITCODE }
finally { Pop-Location }
exit $taskResult
