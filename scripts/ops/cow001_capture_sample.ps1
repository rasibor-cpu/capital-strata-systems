param(
    [Parameter(Mandatory=$true)]
    [string]$Label,
    [string]$EvidenceRoot = "artifacts/cow001"
)

$ErrorActionPreference = "Stop"

$activeFile = Join-Path $EvidenceRoot "ACTIVE_EVIDENCE_DIR.txt"
if (-not (Test-Path $activeFile)) {
    throw "No active COW-001 evidence directory. Run cow001_preflight.ps1 first."
}

$dir = (Get-Content $activeFile -Raw).Trim()
if (-not (Test-Path $dir)) {
    throw "Active evidence directory not found: $dir"
}

$safeLabel = ($Label -replace '[^A-Za-z0-9_-]', '_')
$sampleDir = Join-Path $dir $safeLabel
New-Item -ItemType Directory -Force -Path $sampleDir | Out-Null

$now = (Get-Date).ToUniversalTime().ToString("o")
@(
    "LABEL=$safeLabel",
    "UTC=$now",
    "BRANCH=$((git branch --show-current).Trim())",
    "HEAD=$((git rev-parse HEAD).Trim())"
) | Set-Content -Encoding UTF8 (Join-Path $sampleDir "sample_meta.txt")

if (Test-Path "runtime/css_supervisor_state.json") {
    Copy-Item "runtime/css_supervisor_state.json" (Join-Path $sampleDir "supervisor_state.json")
} else {
    "SUPERVISOR_STATE_MISSING=True" | Set-Content -Encoding UTF8 (Join-Path $sampleDir "supervisor_state_missing.txt")
}

$runtimeProcesses = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -match "dashboard\.web\.web_app:app" -or
        $_.CommandLine -match "dashboard\.runtime\.runtime_supervisor"
    } |
    Select-Object ProcessId, ParentProcessId, Name, CommandLine
$runtimeProcesses | Format-List | Out-File -Encoding UTF8 (Join-Path $sampleDir "runtime_processes.txt")

$resourceRows = @()
foreach ($proc in $runtimeProcesses) {
    try {
        $p = Get-Process -Id $proc.ProcessId -ErrorAction Stop
        $resourceRows += [PSCustomObject]@{
            process_id = $p.Id
            process_name = $p.ProcessName
            cpu_seconds = $p.CPU
            working_set_bytes = $p.WorkingSet64
            private_memory_bytes = $p.PrivateMemorySize64
            started_at = $p.StartTime.ToUniversalTime().ToString("o")
        }
    } catch {}
}
$resourceSummary = [ordered]@{
    recorded_at_utc = $now
    process_count = $resourceRows.Count
    total_working_set_bytes = ($resourceRows | Measure-Object -Property working_set_bytes -Sum).Sum
    total_private_memory_bytes = ($resourceRows | Measure-Object -Property private_memory_bytes -Sum).Sum
    processes = $resourceRows
}
$resourceSummary | ConvertTo-Json -Depth 6 |
    Set-Content -Encoding UTF8 (Join-Path $sampleDir "resource_usage.json")

try {
    python scripts/css_session_analyzer.py *>&1 |
        Out-File -Encoding UTF8 (Join-Path $sampleDir "session_analyzer.txt")
} catch {
    $_ | Out-File -Encoding UTF8 (Join-Path $sampleDir "session_analyzer_error.txt")
}

$hashTargets = @(
    "runtime/css_supervisor_state.json",
    "artifacts/css_extended_paper_test_summary.json",
    "artifacts/css_open_positions.json",
    "artifacts/css_closed_trades.json"
)

$hashRows = foreach ($target in $hashTargets) {
    if (Test-Path $target) {
        $h = Get-FileHash -Algorithm SHA256 $target
        [PSCustomObject]@{
            path = $target
            sha256 = $h.Hash
            length = (Get-Item $target).Length
        }
    }
}
$hashRows | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 (Join-Path $sampleDir "file_hashes.json")

$net = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue |
    Select-Object LocalAddress, LocalPort, OwningProcess, State
$net | Format-List | Out-File -Encoding UTF8 (Join-Path $sampleDir "port_8765.txt")

function Capture-ReadOnlyApi([string]$Uri, [string]$Name) {
    try {
        $payload = Invoke-RestMethod -Method Get -Uri $Uri -TimeoutSec 5
        $payload | ConvertTo-Json -Depth 12 |
            Set-Content -Encoding UTF8 (Join-Path $sampleDir $Name)
    } catch {
        @{
            ok = $false
            uri = $Uri
            error = $_.Exception.Message
            captured_at_utc = $now
        } | ConvertTo-Json -Depth 4 |
            Set-Content -Encoding UTF8 (Join-Path $sampleDir ($Name -replace "\.json$", "_error.json"))
    }
}

Capture-ReadOnlyApi "http://127.0.0.1:8765/api/v1/runtime-health" "runtime_health.json"
Capture-ReadOnlyApi "http://127.0.0.1:8765/api/v1/broker-continuity" "broker_continuity.json"

Write-Host "COW001_SAMPLE_CAPTURED=$safeLabel"
Write-Host "UTC=$now"
Write-Host "PATH=$sampleDir"
