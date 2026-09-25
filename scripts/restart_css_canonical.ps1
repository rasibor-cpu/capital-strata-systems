param(
    [string]$TaskName = "CapitalStrataSystems-CanonicalRuntime",
    [int]$WaitSeconds = 15
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Verifier = Join-Path $RepoRoot "scripts\verify_css_persistent_runtime.ps1"

if (-not (Test-Path $Verifier)) {
    throw "CSS persistent runtime verifier not found: $Verifier"
}

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -eq $task) {
    throw "Scheduled task '$TaskName' is not installed. Run scripts\install_css_logon_task.ps1 first."
}

Write-Host "=== CSS CANONICAL RUNTIME RESTART ==="
Write-Host "Stopping scheduled canonical runtime task..."
Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Retire only recognized CSS Python processes from this repository.
$repoNeedle = $RepoRoot.ToLowerInvariant()
$recognized = @(
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -match '^(?i)pythonw?(\d+(\.\d+)*)?\.exe$' -and
        $_.CommandLine -and
        ([string]$_.CommandLine).ToLowerInvariant().Contains($repoNeedle) -and
        (
            $_.CommandLine -match 'launcher[\\/]css_runtime_launcher\.py' -or
            $_.CommandLine -match '-m\s+launcher\.css_runtime_launcher' -or
            $_.CommandLine -match 'launcher[\\/]css_mobile_launcher\.py' -or
            $_.CommandLine -match '-m\s+launcher\.css_mobile_launcher' -or
            $_.CommandLine -match 'scripts[\\/]css_live_dashboard\.py'
        )
    }
)

foreach ($proc in $recognized) {
    Write-Host "Retiring recognized CSS process PID $($proc.ProcessId)..."
    Stop-Process -Id ([int]$proc.ProcessId) -Force -ErrorAction SilentlyContinue
}

$deadline = (Get-Date).AddSeconds(10)
do {
    $listeners = @(Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)
    if ($listeners.Count -eq 0) { break }
    Start-Sleep -Milliseconds 500
} while ((Get-Date) -lt $deadline)

$listeners = @(Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)
if ($listeners.Count -gt 0) {
    $owners = ($listeners | Select-Object -ExpandProperty OwningProcess -Unique) -join ", "
    throw "Port 8765 is still occupied after retiring recognized CSS processes. Refusing unsafe takeover. Owner PID(s): $owners"
}

Write-Host "Starting scheduled canonical runtime task..."
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds $WaitSeconds

Write-Host ""
Write-Host "Verifying canonical runtime..."
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Verifier
$verifyExit = $LASTEXITCODE

if ($verifyExit -eq 0) {
    Write-Host "CSS canonical runtime restart PASSED."
} else {
    Write-Host "CSS canonical runtime restart FAILED verification."
}

exit $verifyExit
