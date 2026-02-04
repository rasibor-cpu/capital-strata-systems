# ops/start_test.ps1
# REA Capital Trading Engine — TEST launcher (PowerShell)
# Starts guarded wrapper in TEST mode with a deterministic entrypoint.
# Fail-closed: stops if key env vars cannot be set.

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== REA START TEST (PowerShell) ==="
Write-Host "Repo: $(Get-Location)"
Write-Host ""

# Ensure we are running from repo root (best-effort)
if (!(Test-Path ".\run_live_guarded.py")) {
  Write-Host "ABORT: run_live_guarded.py not found. Run this from repo root." -ForegroundColor Red
  exit 2
}

# Runtime dir (required by kill switch and user registry)
if (!(Test-Path ".\runtime")) {
  New-Item -ItemType Directory -Path ".\runtime" | Out-Null
}

# Authoritative TEST settings
$env:REA_ENGINE_ENTRYPOINT = "engine.run_engine:main"
$env:REA_ENGINE_MODE = "TEST"

# Optional: show current values
Write-Host "REA_ENGINE_ENTRYPOINT=$env:REA_ENGINE_ENTRYPOINT"
Write-Host "REA_ENGINE_MODE=$env:REA_ENGINE_MODE"
Write-Host ""

# Start
python .\run_live_guarded.py
$exitCode = $LASTEXITCODE

Write-Host ""
Write-Host "=== REA START TEST DONE === exitCode=$exitCode"
exit $exitCode
