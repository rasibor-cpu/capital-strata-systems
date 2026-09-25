param(
    [string]$TaskName = "CapitalStrataSystems-CanonicalRuntime",
    [int]$HeartbeatFreshSeconds = 120
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$StateFile = Join-Path $RepoRoot "runtime\supervisor\css_runtime_supervisor_state.json"
$ExpectedPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$StartScript = Join-Path $RepoRoot "scripts\start_css_canonical.ps1"
$StdOut = Join-Path $RepoRoot "runtime\logs\css_canonical_runtime.out.log"
$StdErr = Join-Path $RepoRoot "runtime\logs\css_canonical_runtime.err.log"
$Failures = New-Object System.Collections.Generic.List[string]

function Pass([string]$Message) { Write-Host "[PASS] $Message" }
function Warn([string]$Message) { Write-Host "[WARN] $Message" }
function Fail([string]$Message) { Write-Host "[FAIL] $Message"; $Failures.Add($Message) }

Write-Host "=== CSS PERSISTENT RUNTIME VERIFICATION ==="

if (Test-Path $ExpectedPython) {
    Pass "Repository virtual-environment Python exists"
} else {
    Fail "Repository virtual-environment Python is missing: $ExpectedPython"
}

if (Test-Path $StartScript) {
    $tokens = $null
    $parseErrors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile(
        $StartScript,
        [ref]$tokens,
        [ref]$parseErrors
    )
    if (@($parseErrors).Count -eq 0) {
        Pass "Canonical startup wrapper parses successfully"
    } else {
        foreach ($parseError in @($parseErrors)) {
            Fail ("Canonical startup wrapper parse error: " + $parseError.Message)
        }
    }
} else {
    Fail "Canonical startup wrapper is missing: $StartScript"
}

# Scheduled task
try {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    Pass "Scheduled task exists: $TaskName"
    $info = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction Stop
    Write-Host "       State: $($task.State)"
    Write-Host "       Last result: $($info.LastTaskResult)"
} catch {
    Fail "Scheduled task is missing or unreadable: $TaskName"
}

# Canonical owner process
$canonical = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match '^(?i)pythonw?(\d+(\.\d+)*)?\.exe$' -and
    $_.CommandLine -and
    (
        $_.CommandLine -match 'launcher[\\/]css_runtime_launcher\.py' -or
        $_.CommandLine -match '-m\s+launcher\.css_runtime_launcher'
    )
})

if ($canonical.Count -eq 1) {
    Pass "Exactly one canonical runtime owner is running (PID $($canonical[0].ProcessId))"
} elseif ($canonical.Count -eq 0) {
    Fail "No canonical runtime owner is running"
} else {
    Fail "Multiple canonical runtime owners are running: $($canonical.ProcessId -join ', ')"
}

# Port 8765
$listeners = @(Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)
if ($listeners.Count -ge 1) {
    Pass "Port 8765 is listening"
} else {
    Fail "Port 8765 is not listening"
}

# Supervisor state and heartbeat
if (-not (Test-Path $StateFile)) {
    Fail "Supervisor state file is missing: $StateFile"
} else {
    try {
        $state = Get-Content -Raw -Path $StateFile | ConvertFrom-Json
        $status = [string]$state.status
        $heartbeatText = [string]$state.last_heartbeat_at
        if ($status -eq "RUNNING") { Pass "Supervisor status is RUNNING" } else { Fail "Supervisor status is $status" }
        if ([string]::IsNullOrWhiteSpace($heartbeatText)) {
            Fail "Supervisor heartbeat is missing"
        } else {
            $heartbeat = [DateTimeOffset]::Parse($heartbeatText)
            $age = ([DateTimeOffset]::UtcNow - $heartbeat.ToUniversalTime()).TotalSeconds
            Write-Host ("       Heartbeat age: {0:N1}s" -f $age)
            if ($age -le $HeartbeatFreshSeconds) {
                Pass "Supervisor heartbeat is fresh"
            } else {
                Fail ("Supervisor heartbeat is stale ({0:N1}s > {1}s)" -f $age, $HeartbeatFreshSeconds)
            }
        }
    } catch {
        Fail "Supervisor state could not be parsed: $($_.Exception.Message)"
    }
}

# Mobile endpoint
try {
    $response = Invoke-WebRequest "http://127.0.0.1:8765/mobile-launcher" -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Pass "Mobile launcher endpoint returned HTTP 200"
    } else {
        Fail "Mobile launcher endpoint returned HTTP $($response.StatusCode)"
    }
} catch {
    Fail "Mobile launcher endpoint is unreachable: $($_.Exception.Message)"
}

if ($Failures.Count -gt 0) {
    if (Test-Path $StdOut) {
        Write-Host ""
        Write-Host "--- Latest canonical runtime stdout ---"
        Get-Content -Path $StdOut -Tail 80 -ErrorAction SilentlyContinue
    }
    if (Test-Path $StdErr) {
        Write-Host ""
        Write-Host "--- Latest canonical runtime stderr ---"
        Get-Content -Path $StdErr -Tail 80 -ErrorAction SilentlyContinue
    }
}

Write-Host "==========================================="
if ($Failures.Count -gt 0) {
    Write-Host "CSS persistent runtime verification FAILED with $($Failures.Count) issue(s)."
    exit 1
}

Write-Host "CSS persistent runtime verification PASSED."
exit 0
