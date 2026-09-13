param(
    [string]$EvidenceRoot = "artifacts/cow001"
)

$ErrorActionPreference = "Stop"

$activeFile = Join-Path $EvidenceRoot "ACTIVE_EVIDENCE_DIR.txt"
if (-not (Test-Path $activeFile)) {
    throw "No active COW-001 evidence directory."
}

$dir = (Get-Content $activeFile -Raw).Trim()
if (-not (Test-Path $dir)) {
    throw "Evidence directory not found: $dir"
}

$manifestPath = Join-Path $dir "manifest.json"
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
$start = [DateTimeOffset]::Parse($manifest.started_at_utc)
$end = [DateTimeOffset]::UtcNow
$hours = ($end - $start).TotalHours

$sampleDirs = Get-ChildItem $dir -Directory |
    Where-Object { $_.Name -match '^T[0-9]{2}$' } |
    Sort-Object Name

$supervisorStates = @()
foreach ($sample in $sampleDirs) {
    $statePath = Join-Path $sample.FullName "supervisor_state.json"
    if (Test-Path $statePath) {
        try {
            $state = Get-Content $statePath -Raw | ConvertFrom-Json
            $supervisorStates += [PSCustomObject]@{
                label = $sample.Name
                status = $state.status
                restart_count = $state.restart_count
                unexpected_restart_count = $state.unexpected_restart_count
                last_exit_code = $state.last_exit_code
                last_observed_at_utc = $state.last_observed_at_utc
                manual_intervention_required = $state.manual_intervention_required
            }
        } catch {}
    }
}

$criticalSupervisorState = $supervisorStates | Where-Object {
    $_.manual_intervention_required -eq $true -or
    $_.status -eq "MANUAL_INTERVENTION_REQUIRED"
}

$durationPass = $hours -ge 24.0
$samplesPass = $sampleDirs.Count -ge 25
$supervisorPass = -not $criticalSupervisorState

$automaticDisposition = if ($durationPass -and $samplesPass -and $supervisorPass) {
    "AUTOMATED_GATES_PASS_OPERATOR_REVIEW_REQUIRED"
} else {
    "AUTOMATED_GATES_INCOMPLETE_OR_FAIL"
}

$summary = [ordered]@{
    schema_version = "css.cow001.final.v1"
    started_at_utc = $manifest.started_at_utc
    ended_at_utc = $end.ToString("o")
    elapsed_hours = [Math]::Round($hours, 4)
    sample_count = $sampleDirs.Count
    duration_gate_pass = $durationPass
    sample_count_gate_pass = $samplesPass
    supervisor_gate_pass = $supervisorPass
    automated_disposition = $automaticDisposition
    operator_review_required = $true
    live_execution_authorized = $false
    money_movement_authorized = $false
}

$summary | ConvertTo-Json -Depth 6 |
    Set-Content -Encoding UTF8 (Join-Path $dir "COW001_FINAL_SUMMARY.json")

$supervisorStates | ConvertTo-Json -Depth 6 |
    Set-Content -Encoding UTF8 (Join-Path $dir "COW001_SUPERVISOR_TIMELINE.json")

python scripts/css_session_analyzer.py *>&1 |
    Out-File -Encoding UTF8 (Join-Path $dir "COW001_FINAL_SESSION_ANALYZER.txt")

git status --short |
    Out-File -Encoding UTF8 (Join-Path $dir "COW001_FINAL_GIT_STATUS.txt")

Write-Host "COW001_FINALIZED=True"
Write-Host "ELAPSED_HOURS=$([Math]::Round($hours, 4))"
Write-Host "SAMPLE_COUNT=$($sampleDirs.Count)"
Write-Host "AUTOMATED_DISPOSITION=$automaticDisposition"
Write-Host "OPERATOR_REVIEW_REQUIRED=True"
