param(
    [string]$RepoPath = "C:\rasib\source\capital-strata-systems-QRO001",
    [string]$ExpectedBranch = "css-qro004x-integration-2026-09-13"
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
    Fail "Not inside a Git worktree."
}

$branch = (git branch --show-current).Trim()
if ($branch -ne $ExpectedBranch) {
    Fail "Expected integration branch '$ExpectedBranch' but found '$branch'."
}

$unmerged = git diff --name-only --diff-filter=U
if ($unmerged) {
    Write-Host "UNRESOLVED_CONFLICTS=True" -ForegroundColor Yellow
    $unmerged | ForEach-Object { Write-Host $_ }
    Fail "Resolve merge conflicts before validation."
}

$protected = @(
    "runtime_supervisor.json",
    "runtime/css_supervisor_state.json"
)
$staged = @(git diff --cached --name-only)
foreach ($file in $protected) {
    if ($staged -contains $file) {
        Fail "Protected runtime file is staged: $file"
    }
}

Write-Host "=== QRO PHONE INTEGRATION VALIDATION ==="
Write-Host "BRANCH=$branch"
Write-Host "HEAD=$(git rev-parse HEAD)"
Write-Host "STAGED_COUNT=$($staged.Count)"

$secretPattern = "(?i)(authorization:\s*bearer|refresh[_-]?token\s*[:=]|client[_-]?secret\s*[:=]|api[_-]?secret\s*[:=]|private[_-]?key\s*[:=])"
$diffText = git diff --cached -U0
if ($diffText | Select-String -Pattern $secretPattern) {
    Fail "Potential secret material detected in staged diff."
}
Write-Host "SECRET_SCAN=PASS"

$python = Get-Command python -ErrorAction Stop
Write-Host "PYTHON=$($python.Source)"

Write-Host "=== COMPILE ==="
python -m compileall -q backend dashboard engine tests
if ($LASTEXITCODE -ne 0) { Fail "compileall failed." }
Write-Host "COMPILE=PASS"

$baseTemp = Join-Path $env:TEMP ("css_qro_integration_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $baseTemp -Force | Out-Null

try {
    $focused = @()

    if (Test-Path "tests\test_qro001_questrade_readonly_core.py") {
        $focused += "tests\test_qro001_questrade_readonly_core.py"
    }

    $focused += Get-ChildItem -Path tests -File -Filter "test_qro*.py" -ErrorAction SilentlyContinue |
        ForEach-Object { $_.FullName }

    $focused += Get-ChildItem -Path tests -Recurse -File -Filter "*questrade*.py" -ErrorAction SilentlyContinue |
        ForEach-Object { $_.FullName }

    $focused += Get-ChildItem -Path tests -File -Filter "test_css_simulator_academy*.py" -ErrorAction SilentlyContinue |
        ForEach-Object { $_.FullName }

    $focused = $focused | Sort-Object -Unique

    if ($focused.Count -gt 0) {
        Write-Host "=== FOCUSED TESTS ==="
        $focused | ForEach-Object { Write-Host $_ }
        python -m pytest -q @focused --basetemp (Join-Path $baseTemp "focused")
        if ($LASTEXITCODE -ne 0) { Fail "Focused integration tests failed." }
        Write-Host "FOCUSED_TESTS=PASS"
    } else {
        Write-Host "FOCUSED_TESTS=NONE_DISCOVERED"
    }

    Write-Host "=== FULL REGRESSION ==="
    python -m pytest -q --basetemp (Join-Path $baseTemp "full")
    if ($LASTEXITCODE -ne 0) { Fail "Full regression failed." }
    Write-Host "FULL_REGRESSION=PASS"
}
finally {
    Remove-Item -LiteralPath $baseTemp -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "=== STATIC EXECUTION SAFETY SCAN ==="
$qPaths = @(
    "backend\brokers",
    "backend\app\brokers",
    "dashboard\runtime"
) | Where-Object { Test-Path $_ }

$mutatingPattern = "(?i)def\s+(place_order|submit_order|cancel_order|replace_order|withdraw|transfer|deposit|fund_account|move_money)\b"
$hits = @()
foreach ($path in $qPaths) {
    $hits += Get-ChildItem -Path $path -Recurse -File -Filter "*.py" |
        Select-String -Pattern $mutatingPattern
}

if ($hits) {
    Write-Host "NOTE: Mutating-method names exist somewhere in broker/runtime code. Manual review required."
    $hits | ForEach-Object { Write-Host "$($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
} else {
    Write-Host "STATIC_MUTATION_NAME_SCAN=NO_HITS"
}

Write-Host "=== FINAL GATE ==="
Write-Host "INTEGRATION_VALIDATION=PASS"
Write-Host "NEXT_ACTION=Review staged diff and safety-scan notes before explicit integration commit."
