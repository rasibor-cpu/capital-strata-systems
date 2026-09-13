param(
    [string]$ExpectedBranch = "css-cow001-controlled-operating-window",
    [string]$EvidenceRoot = "artifacts/cow001"
)

$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
    Write-Host "COW001_PREFLIGHT=FAIL" -ForegroundColor Red
    Write-Error $Message
    exit 1
}

$branch = (git branch --show-current).Trim()
if ($branch -ne $ExpectedBranch) {
    Fail "Expected branch '$ExpectedBranch' but found '$branch'."
}

$status = git status --porcelain
if ($status) {
    Write-Host $status
    Fail "Working tree must be clean before COW-001."
}

$head = (git rev-parse HEAD).Trim()
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss")
$dir = Join-Path $EvidenceRoot $stamp
New-Item -ItemType Directory -Force -Path $dir | Out-Null

@(
    "COW001_PREFLIGHT=PASS",
    "UTC_START=$((Get-Date).ToUniversalTime().ToString('o'))",
    "BRANCH=$branch",
    "HEAD=$head",
    "PYTHON_VERSION=$(python --version 2>&1)"
) | Set-Content -Encoding UTF8 (Join-Path $dir "00_preflight.txt")

git status --short | Out-File -Encoding UTF8 (Join-Path $dir "01_git_status.txt")
git log -1 --oneline | Out-File -Encoding UTF8 (Join-Path $dir "02_head.txt")

if (Test-Path "runtime/css_supervisor_state.json") {
    Copy-Item "runtime/css_supervisor_state.json" (Join-Path $dir "03_supervisor_state_initial.json")
}

$manifest = @{
    schema_version = "css.cow001.manifest.v1"
    evidence_dir = $dir
    started_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    branch = $branch
    head = $head
    required_hours = 24
    live_execution_authorized = $false
    money_movement_authorized = $false
} | ConvertTo-Json -Depth 5

$manifest | Set-Content -Encoding UTF8 (Join-Path $dir "manifest.json")
$dir | Set-Content -Encoding UTF8 (Join-Path $EvidenceRoot "ACTIVE_EVIDENCE_DIR.txt")

Write-Host "COW001_PREFLIGHT=PASS"
Write-Host "EVIDENCE_DIR=$dir"
Write-Host "NEXT=Start the existing certified runtime in PAPER/advisory mode, then run cow001_capture_sample.ps1 -Label T00"
