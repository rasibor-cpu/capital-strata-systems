# Mission Control-only host. Does not Start-Process uvicorn.
# Delegates to launcher.css_mission_control_host so the child can break away
# from the invoking job/console and keep 127.0.0.1:8765 alive.
param(
    [ValidateSet("start", "status", "stop")]
    [string]$Command = "start"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $RepoRoot
$env:PYTHONPATH = $RepoRoot
$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
}
& $python -m launcher.css_mission_control_host $Command
exit $LASTEXITCODE
