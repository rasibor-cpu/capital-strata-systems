param(
    [string]$BaseUrl = "http://127.0.0.1:8765"
)

$ErrorActionPreference = "Stop"

function Get-Json([string]$Path) {
    $uri = $BaseUrl.TrimEnd("/") + $Path
    try {
        return Invoke-RestMethod -Uri $uri -Method Get -UseBasicParsing -TimeoutSec 10
    } catch {
        throw "Unable to read $uri : $($_.Exception.Message)"
    }
}

Write-Host "=== CSS LIVE CERTIFICATION AUDIT ==="

$state = Get-Json "/mission-control/api/state"
$final = Get-Json "/mission-control/api/final-certification"
$health = Get-Json "/mission-control/api/health"
$runtime = Get-Json "/mission-control/api/runtime"

$overall = [string]$final.overall
$blockers = @($final.blockers)
$checks = @($final.checks)

$overallDisplay = if ([string]::IsNullOrWhiteSpace($overall)) { "UNAVAILABLE" } else { $overall }
$runtimeStatusDisplay = if ([string]::IsNullOrWhiteSpace([string]$runtime.runtime_status)) { "UNAVAILABLE" } else { [string]$runtime.runtime_status }
$heartbeatStatusDisplay = if ([string]::IsNullOrWhiteSpace([string]$runtime.heartbeat_status)) { "UNAVAILABLE" } else { [string]$runtime.heartbeat_status }

Write-Host ("Final certification : {0}" -f $overallDisplay)
Write-Host ("Runtime status      : {0}" -f $runtimeStatusDisplay)
Write-Host ("Heartbeat status    : {0}" -f $heartbeatStatusDisplay)
Write-Host ("State hash present  : {0}" -f [bool]($state.state_hash))
Write-Host ("Runtime hash present: {0}" -f [bool]($state.runtime.state_hash))
Write-Host ("Safety execution    : {0}" -f $state.safety.execution_allowed)
Write-Host ("Safety live blocked : {0}" -f $state.safety.live_trading_blocked)
Write-Host ("Broker armed        : {0}" -f $state.safety.broker_execution_armed)
Write-Host ("Advisory only       : {0}" -f $state.safety.advisory_only)

if ($blockers.Count -eq 0 -and $overall -eq "CERTIFIED") {
    Write-Host ""
    Write-Host "[PASS] Mission Control final certification reports CERTIFIED."
} else {
    Write-Host ""
    Write-Host ("[INFO] Certification blockers ({0}):" -f $blockers.Count)
    foreach ($name in $blockers) {
        $check = $checks | Where-Object { $_.area -eq $name } | Select-Object -First 1
        if ($null -ne $check) {
            Write-Host ("  - {0}: {1} ({2})" -f $check.area, $check.status, $check.reason)
        } else {
            Write-Host ("  - {0}" -f $name)
        }
    }
}

$prod = $state.production_readiness
if ($null -ne $prod) {
    Write-Host ""
    Write-Host "Production readiness:"
    Write-Host ("  status                : {0}" -f $prod.status)
    Write-Host ("  certification_score   : {0}" -f $prod.certification_score)
    Write-Host ("  governance_score      : {0}" -f $prod.governance_score)
    Write-Host ("  broker_readiness      : {0}" -f $prod.broker_readiness)
    Write-Host ("  runtime_readiness     : {0}" -f $prod.runtime_readiness)
    Write-Host ("  evidence_completeness : {0}" -f $prod.evidence_completeness)
    Write-Host ("  deployment_authorized : {0}" -f $prod.deployment_authorized)
    Write-Host ("  deployment_blockers   : {0}" -f (@($prod.deployment_blockers).Count))
    Write-Host ("  outstanding_risks     : {0}" -f (@($prod.outstanding_risks).Count))
}

Write-Host ""
Write-Host "This audit is read-only. It does not authorize deployment, trading, or execution."
Write-Host "===================================="
