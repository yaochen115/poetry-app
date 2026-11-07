param(
    [ValidateSet('pilot','full')][string]$Phase='full',
    [switch]$Offline,
    [switch]$Preview,
    [int]$MaxRequests=1800,
    [int]$Workers=4,
    [double]$Interval=0.5
)
$ErrorActionPreference='Stop'
$taskPython=$env:HONGZHUANG_PYTHON
if (-not $taskPython) {
    $runtimePython=Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    if (Test-Path -LiteralPath $runtimePython) { $taskPython=$runtimePython }
}
if (-not $taskPython) {
    $existingPython=Get-Command python.exe -ErrorAction SilentlyContinue
    if ($existingPython) { $taskPython=$existingPython.Source }
}
if (-not $taskPython) { throw 'Set HONGZHUANG_PYTHON to an existing Python executable; this script installs nothing.' }
$taskArguments=@('-B',(Join-Path $PSScriptRoot 'sync_poetry_api_v1_0_1.py'),'--phase',$Phase,'--workers',"$Workers",'--interval',"$Interval",'--max-requests',"$MaxRequests")
if ($Offline) { $taskArguments+='--offline' }
if ($Preview) { $taskArguments+='--preview' }
Push-Location (Split-Path $PSScriptRoot -Parent)
try { & $taskPython @taskArguments; $taskResult=$LASTEXITCODE }
finally { Pop-Location }
exit $taskResult
