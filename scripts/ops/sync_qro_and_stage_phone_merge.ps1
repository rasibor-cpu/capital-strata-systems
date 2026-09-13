param(
    [string]$QroPath = "C:\rasib\source\capital-strata-systems-QRO001",
    [string]$ExpectedQroHead = "feaa42bd036bf1dc945aef09c306b6d28f82530f",
    [string]$QroBranch = "css-qro001-questrade-readonly-provider",
    [string]$PhoneBranch = "css-phone-remote-work-2026-09-13",
    [string]$IntegrationBranch = "css-qro004x-integration-2026-09-13"
)

$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
    Write-Error $Message
    exit 1
}

if (-not (Test-Path -LiteralPath $QroPath)) {
    Fail "QRO worktree not found: $QroPath"
}

Set-Location -LiteralPath $QroPath

$inside = git rev-parse --is-inside-work-tree 2>$null
if ($inside -ne "true") {
    Fail "Not a Git worktree: $QroPath"
}

$status = git status --porcelain
if ($status) {
    Write-Host "Working tree is not clean:" -ForegroundColor Yellow
    $status | ForEach-Object { Write-Host $_ }
    Fail "Stop: preserve local work before synchronization."
}

$currentBranch = (git branch --show-current).Trim()
if ($currentBranch -ne $QroBranch) {
    Fail "Expected branch '$QroBranch' but found '$currentBranch'."
}

$currentHead = (git rev-parse HEAD).Trim()
if ($currentHead -ne $ExpectedQroHead) {
    Fail "Expected QRO HEAD $ExpectedQroHead but found $currentHead. Do not merge until reconciled."
}

Write-Host "PRECHECK_PASS=True"
Write-Host "QRO_HEAD=$currentHead"
Write-Host "QRO_BRANCH=$currentBranch"

git fetch origin --prune
if ($LASTEXITCODE -ne 0) { Fail "git fetch failed." }

git push -u origin $QroBranch
if ($LASTEXITCODE -ne 0) { Fail "QRO branch push failed." }

$remoteQro = (git rev-parse "origin/$QroBranch").Trim()
if ($remoteQro -ne $ExpectedQroHead) {
    Fail "Remote QRO SHA mismatch after push: $remoteQro"
}

git fetch origin $PhoneBranch
if ($LASTEXITCODE -ne 0) { Fail "Phone branch fetch failed." }

$phoneHead = (git rev-parse "origin/$PhoneBranch").Trim()
Write-Host "PHONE_BRANCH_HEAD=$phoneHead"

$existingIntegration = git branch --list $IntegrationBranch
if ($existingIntegration) {
    Fail "Integration branch already exists locally: $IntegrationBranch"
}

git switch -c $IntegrationBranch $ExpectedQroHead
if ($LASTEXITCODE -ne 0) { Fail "Could not create integration branch." }

git merge --no-ff --no-commit "origin/$PhoneBranch"
if ($LASTEXITCODE -ne 0) {
    Write-Host "MERGE_CONFLICT=True" -ForegroundColor Yellow
    git status --short
    Write-Host "Resolve conflicts manually. Do NOT commit until reviewed."
    exit 2
}

$protected = git diff --cached --name-only | Where-Object {
    $_ -eq "runtime_supervisor.json" -or $_ -eq "runtime/css_supervisor_state.json"
}
if ($protected) {
    git merge --abort
    Fail "Protected runtime file entered merge staging. Merge aborted."
}

$secretScan = git diff --cached -U0 | Select-String -Pattern "(?i)(authorization:\s*bearer|refresh[_-]?token\s*[:=]|client[_-]?secret\s*[:=]|api[_-]?secret\s*[:=]|private[_-]?key\s*[:=])"
if ($secretScan) {
    git merge --abort
    Fail "Potential secret material detected in staged merge. Merge aborted."
}

Write-Host "MERGE_STAGED_CLEAN=True"
Write-Host "INTEGRATION_BRANCH=$IntegrationBranch"
Write-Host "NEXT_ACTION=Review staged diff, run focused safety tests and full regression, then commit explicitly."
git status --short
