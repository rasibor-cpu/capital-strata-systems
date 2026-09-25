param(
    [switch]$Foreground
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Launcher = Join-Path $RepoRoot "launcher\css_runtime_launcher.py"
$LogDir = Join-Path $RepoRoot "runtime\logs"
$StdOut = Join-Path $LogDir "css_canonical_runtime.out.log"
$StdErr = Join-Path $LogDir "css_canonical_runtime.err.log"

if (-not (Test-Path $Python)) { throw "CSS virtual environment Python not found: $Python" }
if (-not (Test-Path $Launcher)) { throw "Canonical CSS runtime launcher not found: $Launcher" }

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$existing = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match '^(?i)pythonw?(\d+(\.\d+)*)?\.exe$' -and
    $_.CommandLine -and
    (
        $_.CommandLine -match 'launcher[\\/]css_runtime_launcher\.py' -or
        $_.CommandLine -match '-m\s+launcher\.css_runtime_launcher'
    )
}

foreach ($proc in @($existing)) {
    try { $exePath = [IO.Path]::GetFullPath($proc.ExecutablePath).ToLowerInvariant() } catch { $exePath = "" }
    if ($exePath -eq [IO.Path]::GetFullPath($Python).ToLowerInvariant()) {
        Write-Host "CSS canonical runtime already running (PID $($proc.ProcessId))."
        exit 0
    }
}

$portInUse = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if ($portInUse) {
    throw "Port 8765 is already in use. Refusing to start a second or ambiguous CSS mobile owner."
}

Set-Location $RepoRoot

if ($Foreground) {
    & $Python $Launcher
    exit $LASTEXITCODE
}

$process = Start-Process -FilePath $Python -ArgumentList @($Launcher) -WorkingDirectory $RepoRoot -WindowStyle Hidden -RedirectStandardOutput $StdOut -RedirectStandardError $StdErr -PassThru

Write-Host "CSS canonical runtime started (PID $($process.Id))."
Write-Host "stdout: $StdOut"
Write-Host "stderr: $StdErr"
