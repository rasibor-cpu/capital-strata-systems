# ops/clear_kill.ps1
# Removes the kill switch file so engine can run again.

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== REA CLEAR KILL (PowerShell) ==="
Write-Host "==="

$killPath = ".\runtime\kill.switch"

if (Test-Path $killPath) {
  Remove-Item -LiteralPath $killPath -Force
  Write-Host "KILL CLEARED: $killPath"
} else {
  Write-Host "KILL NOT PRESENT: $killPath"
}
