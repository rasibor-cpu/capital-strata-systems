param(
    [string]$RepoPath = "C:\rasib\source\capital-strata-systems-QRO001",
    [string]$ExpectedIntegrationBranch = "css-qro004x-integration-2026-09-13",
    [string]$ExpectedQroBase = "feaa42bd036bf1dc945aef09c306b6d28f82530f"
)

$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
    Write-Error $Message
    exit 1
}

if (-not (Test-Path -LiteralPath $RepoPath)) {
    Fail "Repository path not found: $RepoPath"
}

Set-Location -LiteralPath $RepoPath

if ((git rev-parse --is-inside-work-tree 2>$null) -ne "true") {
    Fail "Not a Git worktree."
}

$branch = (git branch --show-current).Trim()
if ($branch -ne $ExpectedIntegrationBranch) {
    Fail "Expected integration branch '$ExpectedIntegrationBranch' but found '$branch'."
}

$mergeBase = (git merge-base HEAD $ExpectedQroBase).Trim()
if ($mergeBase -ne $ExpectedQroBase) {
    Fail "Integration branch is not descended from expected QRO base $ExpectedQroBase."
}

$status = git status --porcelain
if (-not $status) {
    Write-Host "NOTE=Working tree clean. If merge was committed already, verify commit evidence before QRO-004X."
} else {
    Write-Host "WORKTREE_STATUS_BEGIN"
    $status | ForEach-Object { Write-Host $_ }
    Write-Host "WORKTREE_STATUS_END"
}

$requiredPaths = @(
    "backend/brokers/questrade_client.py",
    "backend/brokers/questrade_account_provider.py",
    "dashboard/runtime/mission_control_state.py",
    "dashboard/runtime/api_bridge.py",
    "backend/reconciliation/questrade_activity_reconciliation.py"
)

$missing = @()
foreach ($path in $requiredPaths) {
    if (-not (Test-Path -LiteralPath $path)) {
        $missing += $path
    }
}

if ($missing.Count -gt 0) {
    Write-Host "MISSING_REQUIRED_PATHS_BEGIN"
    $missing | ForEach-Object { Write-Host $_ }
    Write-Host "MISSING_REQUIRED_PATHS_END"
    Fail "QRO-004X prerequisites are incomplete."
}

$protected = git status --porcelain | Where-Object {
    $_ -match "runtime_supervisor\.json" -or $_ -match "runtime/css_supervisor_state\.json"
}
if ($protected) {
    Fail "Protected runtime files are modified/staged."
}

$secretPatterns = @(
    "Authorization:\s*Bearer\s+",
    "refresh[_-]?token\s*[:=]",
    "client[_-]?secret\s*[:=]",
    "api[_-]?secret\s*[:=]",
    "private[_-]?key\s*[:=]"
)

$diff = git diff --cached -U0
foreach ($pattern in $secretPatterns) {
    if ($diff | Select-String -Pattern $pattern -CaseSensitive:$false) {
        Fail "Potential secret material found in staged diff."
    }
}

Write-Host "QRO004X_PREREQ_GATE=PASS"
Write-Host "EXPECTED_QRO_BASE=$ExpectedQroBase"
Write-Host "INTEGRATION_BRANCH=$branch"
Write-Host "NEXT=Implement QRO-004X only after this gate passes."
