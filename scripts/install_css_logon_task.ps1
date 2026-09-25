param(
    [string]$TaskName = "CapitalStrataSystems-CanonicalRuntime",
    [switch]$StartNow
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$StartScript = Join-Path $RepoRoot "scripts\start_css_canonical.ps1"

if (-not (Test-Path $StartScript)) { throw "CSS canonical start script not found: $StartScript" }

$PowerShell = (Get-Command powershell.exe -ErrorAction Stop).Source
$QuotedScript = '"' + $StartScript + '"'
$Action = New-ScheduledTaskAction -Execute $PowerShell -Argument "-NoProfile -ExecutionPolicy Bypass -File $QuotedScript -Foreground"
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 3650)
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description "Starts the fail-closed CSS canonical runtime supervisor and managed mobile launcher at user logon." -Force | Out-Null

Write-Host "Installed scheduled task: $TaskName"
Write-Host "CSS will start via the canonical runtime launcher at user logon."
Write-Host "Execution remains governed by CSS fail-closed controls."

if ($StartNow) {
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "Started scheduled task: $TaskName"
}
