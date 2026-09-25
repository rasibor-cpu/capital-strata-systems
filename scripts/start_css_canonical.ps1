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
$BootstrapLog = Join-Path $LogDir "css_canonical_runtime.bootstrap.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

trap {
    $message = @(
        "timestamp=$([DateTimeOffset]::Now.ToString('o'))",
        "message=$($_.Exception.Message)",
        "type=$($_.Exception.GetType().FullName)",
        "position=$($_.InvocationInfo.PositionMessage)",
        "script=$($_.InvocationInfo.ScriptName)",
        "line=$($_.InvocationInfo.ScriptLineNumber)"
    ) -join [Environment]::NewLine
    $utf8Trap = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($BootstrapLog, [string]$message, $utf8Trap)
    Write-Error $message -ErrorAction Continue
    exit 1
}

if (-not (Test-Path $Python)) { throw "CSS virtual environment Python not found: $Python" }
if (-not (Test-Path $Launcher)) { throw "Canonical CSS runtime launcher not found: $Launcher" }

Set-Location $RepoRoot

# If the canonical runtime is already running under the repo venv, do nothing.
$existingCanonical = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match '^(?i)pythonw?(\d+(\.\d+)*)?\.exe$' -and
    $_.CommandLine -and
    (
        $_.CommandLine -match 'launcher[\\/]css_runtime_launcher\.py' -or
        $_.CommandLine -match '-m\s+launcher\.css_runtime_launcher'
    )
})

foreach ($proc in $existingCanonical) {
    try {
        $exePath = [IO.Path]::GetFullPath([string]$proc.ExecutablePath).ToLowerInvariant()
        $expectedPath = [IO.Path]::GetFullPath($Python).ToLowerInvariant()
    } catch {
        $exePath = ""
        $expectedPath = "__invalid__"
    }
    if ($exePath -eq $expectedPath) {
        Write-Host "CSS canonical runtime already running (PID $($proc.ProcessId))."
        exit 0
    }
}

# Port 8765 may still be held by an old standalone CSS mobile launcher.
# Retire it only when both process identity and HTTP identity prove it is ours.
$portListeners = @(Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)
if ($portListeners.Count -gt 0) {
    $listenerOwnerPids = @($portListeners | Select-Object -ExpandProperty OwningProcess -Unique)
    $safeStandaloneOwners = @()

    foreach ($listenerOwnerPid in $listenerOwnerPids) {
        $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$listenerOwnerPid" -ErrorAction SilentlyContinue
        if ($null -eq $owner -or -not $owner.CommandLine) { continue }

        $isPython = [string]$owner.Name -match '^(?i)pythonw?(\d+(\.\d+)*)?\.exe$'
        $isStandaloneMobile = (
            [string]$owner.CommandLine -match 'launcher[\\/]css_mobile_launcher\.py' -or
            [string]$owner.CommandLine -match '-m\s+launcher\.css_mobile_launcher'
        )
        $isCanonicalRuntime = (
            [string]$owner.CommandLine -match 'launcher[\\/]css_runtime_launcher\.py' -or
            [string]$owner.CommandLine -match '-m\s+launcher\.css_runtime_launcher'
        )

        if ($isPython -and $isStandaloneMobile -and -not $isCanonicalRuntime) {
            $safeStandaloneOwners += $owner
        }
    }

    $endpointIdentifiedAsCss = $false
    try {
        $probe = Invoke-WebRequest "http://127.0.0.1:8765/mobile-launcher" -UseBasicParsing -TimeoutSec 3
        $endpointIdentifiedAsCss = (
            $probe.StatusCode -eq 200 -and
            [string]$probe.Content -match 'CSS Mobile Launcher'
        )
    } catch {
        $endpointIdentifiedAsCss = $false
    }

    if (
        $endpointIdentifiedAsCss -and
        $safeStandaloneOwners.Count -eq $listenerOwnerPids.Count -and
        $safeStandaloneOwners.Count -gt 0
    ) {
        foreach ($owner in $safeStandaloneOwners) {
            Write-Host "Retiring legacy standalone CSS mobile launcher (PID $($owner.ProcessId))..."
            Stop-Process -Id ([int]$owner.ProcessId) -Force -ErrorAction Stop
        }
        Start-Sleep -Seconds 2
        $remaining = @(Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)
        if ($remaining.Count -gt 0) {
            throw "Port 8765 remained occupied after retiring the recognized standalone CSS mobile launcher."
        }
        Write-Host "Legacy standalone CSS mobile launcher retired; canonical runtime may take ownership."
    } else {
        throw "Port 8765 is already in use by an unknown or ambiguous owner. Refusing unsafe takeover."
    }
}

if ($Foreground) {
    Write-Host "Starting CSS canonical runtime in foreground mode..."
    Write-Host "stdout: $StdOut"
    Write-Host "stderr: $StdErr"

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Python
    $psi.Arguments = '"' + $Launcher + '"'
    $psi.WorkingDirectory = $RepoRoot
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    $null = $proc.Start()

    $stdoutTask = $proc.StandardOutput.ReadToEndAsync()
    $stderrTask = $proc.StandardError.ReadToEndAsync()
    $proc.WaitForExit()
    $stdout = $stdoutTask.Result
    $stderr = $stderrTask.Result

    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($StdOut, [string]$stdout, $utf8)
    [System.IO.File]::WriteAllText($StdErr, [string]$stderr, $utf8)
    if ($stdout) { Write-Host $stdout }
    if ($stderr) { Write-Error $stderr -ErrorAction Continue }
    Write-Host "CSS canonical runtime exited with code $($proc.ExitCode)."
    exit $proc.ExitCode
}

$process = Start-Process `
    -FilePath $Python `
    -ArgumentList @($Launcher) `
    -WorkingDirectory $RepoRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $StdOut `
    -RedirectStandardError $StdErr `
    -PassThru

Write-Host "CSS canonical runtime started (PID $($process.Id))."
Write-Host "stdout: $StdOut"
Write-Host "stderr: $StdErr"
