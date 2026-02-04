# ops/start_live.ps1
# REA Capital Trading Engine — LIVE launcher (PowerShell)
# Fail-closed: requires explicit typed confirmation.
# Also blocks if runtime\kill.switch exists.

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== REA START LIVE (PowerShell) ===" -ForegroundColor Yellow
Write-Host "Repo: $(Get-Location)"
Write-Host ""

if (!(Test-Path ".\run_live_guarded.py")) {
  Write-Host "ABORT: run_live_guarded.py not found. Run this from repo root." -ForegroundColor Red
  exit 2
}

if (Test-Path ".\runtime\kill.switch") {
  Write-Host "ABORT: kill switch is set (runtime\kill.switch). Clear it first." -ForegroundColor Red
  exit 3
}

if (!(Test-Path ".\runtime")) {
  New-Item -ItemType Directory -Path ".\runtime" | Out-Null
}

# Authoritative LIVE settings
$env:REA_ENGINE_ENTRYPOINT = "engine.run_engine:main"
$env:REA_ENGINE_MODE = "LIVE"

Write-Host "REA_ENGINE_ENTRYPOINT=$env:REA_ENGINE_ENTRYPOINT"
Write-Host "REA_ENGINE_MODE=$env:REA_ENGINE_MODE"
Write-Host ""

$phrase = "I UNDERSTAND LIVE TRADING RISK"
$inputPhrase = Read-Host "TYPE EXACTLY: $phrase"

if ($inputPhrase -ne $phrase) {
  Write-Host "ABORT: confirmation phrase mismatch. LIVE not started." -ForegroundColor Red
  exit 4
}

Write-Host ""
Write-Host "CONFIRMED. Starting LIVE guarded engine..." -ForegroundColor Yellow
python .\run_live_guarded.py
$exitCode = $LASTEXITCODE

Write-Host ""
Write-Host "=== REA START LIVE DONE === exitCode=$exitCode"
exit $exitCode
