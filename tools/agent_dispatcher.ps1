param(
    [Parameter(Position = 0)]
    [ValidateSet("discover", "status", "dispatch", "review", "dry-run")]
    [string]$Mode = "status",

    [string]$Repo = ".",
    [string]$AuditDir = "",
    [string]$ImplementationFamily = "",
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    $python = "python"
}

$argsList = @(
    "-m",
    "tools.agent_dispatcher",
    $Mode,
    "--repo",
    $Repo
)

if ($AuditDir -ne "") {
    $argsList += @("--audit-dir", $AuditDir)
}

if ($ImplementationFamily -ne "") {
    $argsList += @("--implementation-family", $ImplementationFamily)
}

if ($NoLaunch) {
    $argsList += "--no-launch"
}

& $python @argsList
exit $LASTEXITCODE
