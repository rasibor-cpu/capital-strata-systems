# ops/kill_now.ps1
# Creates the kill switch file to force the engine to stop safely (fail-closed).

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== REA KILL NOW (PowerShell) ==="
Write-Host "==="

if (!(Test-Path ".\runtime")) {
  New-Item -ItemType Directory -Path ".\runtime" | Out-Null
}

$killPath = ".\runtime\kill.switch"
"kill" | Out-File -FilePath $killPath -Encoding ascii -Force

Write-Host "KILL SET: $killPath"
Write-Host "If the engine is running, it should stop on its next gate/check."
