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
$BootstrapLog = Join-Path $RepoRoot "runtime\logs\css_canonical_runtime.bootstrap.log"
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
    if ([int64]$info.LastTaskResult -eq 267009) {
        Pass "Task Scheduler reports the canonical runtime task is currently running"
    }
    Write-Host "       Last run: $($info.LastRunTime)"
    Write-Host "       Next run: $($info.NextRunTime)"
    foreach ($action in @($task.Actions)) {
        Write-Host "       Execute: $($action.Execute)"
        Write-Host "       Arguments: $($action.Arguments)"
        Write-Host "       Working directory: $($action.WorkingDirectory)"
    }
} catch {
    Fail "Scheduled task is missing or unreadable: $TaskName"
}

# Canonical owner process.
# Windows venv launchers may briefly/persistently present as a direct parent Python
# shim with the same canonical command line as the child interpreter. Collapse
# only a proven direct parent->child pair with the same normalized target.
$canonicalRaw = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match '^(?i)pythonw?(\d+(\.\d+)*)?\.exe
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
    if (Test-Path $BootstrapLog) {
        Write-Host ""
        Write-Host "--- Latest canonical PowerShell bootstrap failure ---"
        Get-Content -Path $BootstrapLog -Tail 80 -ErrorAction SilentlyContinue
    }

    try {
        $schedulerEvents = Get-WinEvent -FilterHashtable @{
            LogName = "Microsoft-Windows-TaskScheduler/Operational"
            StartTime = (Get-Date).AddMinutes(-15)
        } -ErrorAction SilentlyContinue | Where-Object {
            $_.Message -and $_.Message -match [regex]::Escape($TaskName)
        } | Select-Object -First 8
        if ($schedulerEvents) {
            Write-Host ""
            Write-Host "--- Recent Task Scheduler events ---"
            foreach ($evt in $schedulerEvents) {
                Write-Host ("[{0}] Event {1}: {2}" -f $evt.TimeCreated, $evt.Id, (($evt.Message -replace "\r?\n"," ") -replace "\s+"," "))
            }
        }
    } catch {}

    if (Test-Path $StdOut) {
        Write-Host ""
        Write-Host "--- Latest canonical runtime stdout (last completed launcher process; may be historical while current task is Running) ---"
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
 -and
    $_.CommandLine -and
    (
        $_.CommandLine -match 'launcher[\\/]css_runtime_launcher\.py' -or
        $_.CommandLine -match '-m\s+launcher\.css_runtime_launcher'
    )
})

$canonical = @($canonicalRaw)
if ($canonicalRaw.Count -gt 1) {
    $byPid = @{}
    foreach ($proc in $canonicalRaw) {
        $byPid[[int]$proc.ProcessId] = $proc
    }

    $shimPids = New-Object System.Collections.Generic.HashSet[int]
    foreach ($child in $canonicalRaw) {
        $parentPid = [int]$child.ParentProcessId
        if (-not $byPid.ContainsKey($parentPid)) { continue }

        $parent = $byPid[$parentPid]
        $parentCmd = ([string]$parent.CommandLine).ToLowerInvariant().Replace('"','').Trim()
        $childCmd = ([string]$child.CommandLine).ToLowerInvariant().Replace('"','').Trim()

        $sameScriptTarget = (
            ($parentCmd -match 'launcher[\\/]css_runtime_launcher\.py' -and
             $childCmd -match 'launcher[\\/]css_runtime_launcher\.py') -or
            ($parentCmd -match '-m\s+launcher\.css_runtime_launcher' -and
             $childCmd -match '-m\s+launcher\.css_runtime_launcher')
        )

        if ($sameScriptTarget) {
            [void]$shimPids.Add([int]$parent.ProcessId)
        }
    }

    if ($shimPids.Count -gt 0) {
        $canonical = @($canonicalRaw | Where-Object { -not $shimPids.Contains([int]$_.ProcessId) })
        Write-Host "       Collapsed interpreter shim PID(s): $(@($shimPids) -join ', ')"
    }
}

if ($canonical.Count -eq 1) {
    Pass "Exactly one effective canonical runtime owner is running (PID $($canonical[0].ProcessId))"
} elseif ($canonical.Count -eq 0) {
    Fail "No canonical runtime owner is running"
} else {
    Fail "Multiple independent canonical runtime owners are running: $($canonical.ProcessId -join ', ')"
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
    if (Test-Path $BootstrapLog) {
        Write-Host ""
        Write-Host "--- Latest canonical PowerShell bootstrap failure ---"
        Get-Content -Path $BootstrapLog -Tail 80 -ErrorAction SilentlyContinue
    }

    try {
        $schedulerEvents = Get-WinEvent -FilterHashtable @{
            LogName = "Microsoft-Windows-TaskScheduler/Operational"
            StartTime = (Get-Date).AddMinutes(-15)
        } -ErrorAction SilentlyContinue | Where-Object {
            $_.Message -and $_.Message -match [regex]::Escape($TaskName)
        } | Select-Object -First 8
        if ($schedulerEvents) {
            Write-Host ""
            Write-Host "--- Recent Task Scheduler events ---"
            foreach ($evt in $schedulerEvents) {
                Write-Host ("[{0}] Event {1}: {2}" -f $evt.TimeCreated, $evt.Id, (($evt.Message -replace "\r?\n"," ") -replace "\s+"," "))
            }
        }
    } catch {}

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
