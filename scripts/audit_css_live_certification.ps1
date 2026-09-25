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

Write-Host ""
Write-Host "Runtime evidence:"
Write-Host ("  source                : {0}" -f $state.runtime.source)
Write-Host ("  source_status         : {0}" -f $state.runtime.source_status)
Write-Host ("  source_freshness      : {0}" -f $state.runtime.source_freshness)
Write-Host ("  source_confidence     : {0}" -f $state.runtime.source_confidence)
Write-Host ("  runtime_health        : {0}" -f $state.platform.runtime_health)
Write-Host ("  supervisor_state      : {0}" -f $state.runtime.supervisor_state)
Write-Host ("  selected_broker       : {0}" -f $state.brokers.active_broker.selected_broker)
Write-Host ("  broker_health         : {0}" -f $state.brokers.active_broker.broker_health)
Write-Host ("  broker_connection     : {0}" -f $state.brokers.active_broker.connection_status)
Write-Host ("  broker_authentication : {0}" -f $state.brokers.active_broker.authentication_status)
Write-Host ("  broker_account        : {0}" -f $state.brokers.active_broker.account_status)
Write-Host ("  broker_market_data    : {0}" -f $state.brokers.active_broker.market_data_status)
Write-Host ("  broker_failure_reason : {0}" -f $state.runtime_snapshot.broker.failure_reason)
$brokerWarnings = @($state.brokers.active_broker.warnings)
if ($brokerWarnings.Count -gt 0) {
    Write-Host "  broker warnings:"
    foreach ($item in $brokerWarnings) {
        Write-Host ("    - {0}" -f $item)
    }
}
Write-Host ("  rc1_certification     : {0}" -f $state.runtime_snapshot.certification.rc1_certification)
Write-Host ("  rc1_operational       : {0}" -f $state.runtime_snapshot.certification.rc1_operational_readiness)
Write-Host ("  runtime_readiness     : {0}" -f $state.runtime_snapshot.certification.runtime_readiness)
Write-Host ("  broker_readiness      : {0}" -f $state.runtime_snapshot.certification.broker_readiness)

$runtimeBlockers = @($state.runtime_snapshot.certification.blockers)
if ($runtimeBlockers.Count -gt 0) {
    Write-Host "  runtime blockers:"
    foreach ($item in $runtimeBlockers) {
        Write-Host ("    - {0}" -f $item)
    }
}

$prod = $state.production_readiness
$contradictions = @()
if ($overall -eq "CERTIFIED") {
    if ($runtimeStatusDisplay -in @("RED", "FAILED", "DEGRADED", "STOPPED", "NOT_READY", "UNAVAILABLE")) {
        $contradictions += "certified_with_runtime_$($runtimeStatusDisplay.ToLower())"
    }
    if ($null -eq $prod) {
        $contradictions += "certified_without_production_readiness"
    } else {
        if ([string]$prod.status -ne "CERTIFIED") {
            $contradictions += "certified_with_production_readiness_$([string]$prod.status)"
        }
        if ([string]$prod.broker_readiness -in @("", "EVIDENCE_MISSING", "UNAVAILABLE", "UNKNOWN", "NOT_READY")) {
            $contradictions += "certified_with_broker_evidence_missing"
        }
        if ([string]$prod.runtime_readiness -in @("", "EVIDENCE_MISSING", "UNAVAILABLE", "UNKNOWN", "NOT_READY")) {
            $contradictions += "certified_with_runtime_evidence_missing"
        }
        if ([double]$prod.evidence_completeness -lt 100) {
            $contradictions += "certified_with_incomplete_evidence"
        }
        if ($prod.deployment_authorized -ne $true) {
            $contradictions += "certified_without_deployment_authorization"
        }
    }
}

if ($contradictions.Count -gt 0) {
    Write-Host ""
    Write-Host "[FAIL] Certification response is internally inconsistent and is treated as FAIL_CLOSED by this audit."
    foreach ($reason in $contradictions) {
        Write-Host ("  - {0}" -f $reason)
    }
} elseif ($blockers.Count -eq 0 -and $overall -eq "CERTIFIED") {
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
    $deploymentBlockers = @($prod.deployment_blockers)
    Write-Host ("  deployment_blockers   : {0}" -f $deploymentBlockers.Count)
    if ($deploymentBlockers.Count -gt 0) {
        foreach ($item in $deploymentBlockers) {
            Write-Host ("    - {0}" -f $item)
        }
    }
    Write-Host ("  outstanding_risks     : {0}" -f (@($prod.outstanding_risks).Count))
}

Write-Host ""
Write-Host "This audit is read-only. It does not authorize deployment, trading, or execution."
Write-Host "===================================="

if ($contradictions.Count -gt 0) {
    exit 2
}
