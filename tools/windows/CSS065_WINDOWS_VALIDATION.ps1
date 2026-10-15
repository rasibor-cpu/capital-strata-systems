<#
CSS-065 Windows-host validation (FINANCE). Read-only toward production.

Performs steps 2-10 of the CSS-065 validation order:
  - production snapshot BEFORE/AFTER (HEAD, tracked status, data\users.json SHA-256);
  - remote + commit verification and diff capture for the independent reviewer;
  - disposable worktree at the exact CSS-065 commit under C:\CSS_Evidence;
  - Python 3.11 venv; targeted CSS-065 / CSS-064 ledger / AntiBleed tests;
  - a REAL msvcrt probe: wraps msvcrt.locking, proves real cross-process contention,
    a fail-closed timeout and recovery after the holder is killed;
  - full regression with exact counts, compared with CSS_WINCERT_20261015T061652Z;
  - smoke-gate patch in a SEPARATE worktree, with R14F tests, proving production
    data\users.json is untouched;
  - production safety flags via HTTP GET only.

Never: checks out the branch in production, writes production files, starts or
restarts services, changes flags, places orders, merges, pushes or runs the 72 h run.
Disclosed metadata effects on the production .git: `git fetch` of the CSS-065 branch
and two registered worktrees (remove afterwards with `git worktree remove --force`).

Usage:  powershell -ExecutionPolicy Bypass -File .\CSS065_WINDOWS_VALIDATION.ps1
#>
[CmdletBinding()]
param(
    [string]$RepoPath = "C:\rasib\source\capital-strata-systems",
    [string]$TargetSha = "609f7ffde63936c0e64838757301333282096c17",
    [string]$TargetBranch = "claude/css-065-windows-ledger-lock",
    [string]$FrozenBaseline = "9bc3c52aaf96457c52cff3ec4fe346894c22a7ee",
    [string]$PrevCert = "C:\CSS_Evidence\CSS_WINCERT_20261015T061652Z",
    [string]$PatchFile = "",
    [string]$BaseUrl = "http://127.0.0.1:8765"
)
$ErrorActionPreference = "Continue"
$env:GIT_OPTIONAL_LOCKS = "0"
$env:GIT_CONFIG_COUNT = "1"; $env:GIT_CONFIG_KEY_0 = "core.autocrlf"; $env:GIT_CONFIG_VALUE_0 = "false"
$env:PYTHONUTF8 = "1"
$PatchSha = "1D31B7861BF8E97D6621849862C24CADD6D3A18C17103CB9AE5A99C300D965A7"
$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$Root  = "C:\CSS_Evidence\CSS065_WINVAL_$Stamp"
$Wt    = Join-Path $Root "wt"
$SmWt  = Join-Path $Root "smoke_wt"
$Venv  = Join-Path $Root "venv311"
$Py    = Join-Path $Venv "Scripts\python.exe"
New-Item -ItemType Directory -Force -Path $Root | Out-Null

$Lines = New-Object System.Collections.Generic.List[string]
$Fails = New-Object System.Collections.Generic.List[string]
function L([string]$s) { $Lines.Add($s) | Out-Null; Write-Host $s }
function Check([string]$name, [bool]$ok, [string]$detail) {
    if (-not $ok) { $Fails.Add($name) | Out-Null }
    L ("  [" + $(if ($ok) { "PASS" } else { "FAIL" }) + "] " + $name + " - " + $detail)
}
function Run([string]$cmd, [string]$log, [string]$dir) {
    L ("  `$ (cd " + $dir + ") " + $cmd + "  > " + (Split-Path -Leaf $log))
    Push-Location $dir
    try { cmd /c "$cmd > `"$log`" 2>&1"; return $LASTEXITCODE } finally { Pop-Location }
}
function Snapshot([string]$label) {
    $h = (git -C $RepoPath rev-parse HEAD) 2>&1
    $m = @(git -C $RepoPath status --porcelain --untracked-files=no 2>&1).Count
    $u = Join-Path $RepoPath "data\users.json"
    $us = $(if (Test-Path $u) { (Get-FileHash $u -Algorithm SHA256).Hash } else { "ABSENT" })
    L ("  " + $label + ": HEAD=" + $h + " tracked_modifications=" + $m + " users.json_sha256=" + $us)
    return "$h|$m|$us"
}
function JunitCounts([string]$xml) {
    if (-not (Test-Path $xml)) { return $null }
    $x = [xml](Get-Content -Raw $xml)
    $s = @($x.SelectNodes("//testsuite"))[0]
    return @{ tests = [int]$s.tests; failures = [int]$s.failures; errors = [int]$s.errors; skipped = [int]$s.skipped }
}
function LogSummary([string]$log) {
    if (-not (Test-Path $log)) { return @{ line = "LOG NOT FOUND"; collection = -1; warnings = -1 } }
    $line = (Select-String -Path $log -Pattern '\d+ (passed|failed|error|errors|skipped).* in [\d\.]+s' | Select-Object -Last 1)
    $txt = $(if ($line) { $line.Line.Trim("= ").Trim() } else { "SUMMARY NOT FOUND" })
    $coll = @(Select-String -Path $log -Pattern '^ERROR collecting ').Count
    $w = [regex]::Match($txt, '(\d+) warnings?'); $wc = $(if ($w.Success) { [int]$w.Groups[1].Value } else { 0 })
    return @{ line = $txt; collection = $coll; warnings = $wc }
}

L "CSS-065 WINDOWS-HOST VALIDATION (privacy-safe: no user data, credentials or secrets recorded)"
L ("Generated (UTC): " + (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") + "  host=" + $env:COMPUTERNAME)
L ("Evidence: " + $Root)
L "execution_allowed=false | live_trading_blocked=true | advisory_only=true (not modified)"
L ""
L "A. PRODUCTION SNAPSHOT (before)"
$before = Snapshot "before"
$bh = $before.Split("|")
Check "production_at_frozen_baseline" ($bh[0] -eq $FrozenBaseline) ("HEAD " + $bh[0])
Check "production_no_tracked_modifications" ($bh[1] -eq "0") ($bh[1] + " modified tracked file(s)")

L ""
L "B. TARGET COMMIT"
cmd /c "git -C `"$RepoPath`" fetch origin $TargetBranch > `"$Root\git_fetch.log`" 2>&1"
$remote = ((git -C $RepoPath ls-remote origin $TargetBranch) 2>&1 | Select-Object -First 1)
Check "remote_branch_points_to_target" ("$remote" -like "$TargetSha*") ("" + $remote)
$type = (git -C $RepoPath cat-file -t $TargetSha) 2>&1
Check "target_commit_present" ($type -eq "commit") ("cat-file -t: " + $type)
cmd /c "git -C `"$RepoPath`" diff $TargetSha^ $TargetSha > `"$Root\css065_full.diff`" 2>&1"
cmd /c "git -C `"$RepoPath`" diff --stat $TargetSha^ $TargetSha > `"$Root\css065_diffstat.txt`" 2>&1"
L ("  diff for independent review: css065_full.diff (sha256 " + (Get-FileHash "$Root\css065_full.diff" -Algorithm SHA256).Hash + ")")
Get-Content "$Root\css065_diffstat.txt" | ForEach-Object { L ("    " + $_) }

L ""
L "C. DISPOSABLE WORKTREE + PYTHON 3.11"
cmd /c "git -C `"$RepoPath`" worktree add --detach `"$Wt`" $TargetSha > `"$Root\wt.log`" 2>&1"
$wh = (git -C $Wt rev-parse HEAD) 2>&1
$wclean = @(git -C $Wt status --porcelain 2>&1).Count
Check "worktree_at_target_and_clean" (($wh -eq $TargetSha) -and ($wclean -eq 0)) ("HEAD=$wh changes=$wclean")
$pv = (& py -3.11 --version) 2>&1
Check "python_3_11" ($LASTEXITCODE -eq 0) "$pv"
cmd /c "py -3.11 -m venv `"$Venv`" > `"$Root\venv.log`" 2>&1"
$rc = Run "`"$Py`" -m pip install -r requirements.txt" "$Root\pip.log" $Wt
Check "dependencies_installed" ($rc -eq 0) ("pip exit " + $rc)

L ""
L "D. REAL msvcrt PROBE (not simulated)"
@'
import json, os, subprocess, sys, time
import msvcrt
import backend.runtime.interprocess_lock as m
calls = {"n": 0}
real = msvcrt.locking
def counting(fd, mode, nbytes):
    calls["n"] += 1
    return real(fd, mode, nbytes)
msvcrt.locking = counting
path = sys.argv[1]
hold = "import sys\nfrom backend.runtime.interprocess_lock import exclusive_file_lock\nwith exclusive_file_lock(sys.argv[1]):\n    print('locked', flush=True)\n    sys.stdin.readline()\n"
child = subprocess.Popen([sys.executable, "-c", hold, path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
ready = child.stdout.readline().strip() == "locked"
t0 = time.monotonic()
try:
    with m.exclusive_file_lock(path, timeout_seconds=0.5):
        contended = "ACQUIRED_WHILE_HELD"
except m.InterprocessLockTimeout:
    contended = "TIMEOUT"
waited = round(time.monotonic() - t0, 3)
child.kill(); child.wait()
with m.exclusive_file_lock(path, timeout_seconds=5):
    after_kill = "ACQUIRED_AFTER_HOLDER_KILLED"
print(json.dumps({"backend": m.LOCK_BACKEND, "child_ready": ready, "contended": contended,
                  "waited_s": waited, "after_kill": after_kill, "msvcrt_locking_calls": calls["n"],
                  "lock_file_size": os.path.getsize(path)}))
'@ | Out-File -Encoding ascii "$Root\msvcrt_probe.py"
$env:PYTHONPATH = $Wt
$probe = (& $Py "$Root\msvcrt_probe.py" (Join-Path $Root "probe.lock")) 2>&1 | Select-Object -Last 1
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
"$probe" | Out-File -Encoding utf8 "$Root\msvcrt_probe.json"
try {
    $p = "$probe" | ConvertFrom-Json
    $ok = ($p.backend -eq "msvcrt") -and $p.child_ready -and ($p.contended -eq "TIMEOUT") -and ($p.waited_s -ge 0.45) -and ($p.after_kill -eq "ACQUIRED_AFTER_HOLDER_KILLED") -and ($p.msvcrt_locking_calls -ge 3) -and ($p.lock_file_size -eq 0)
    Check "real_msvcrt_locking_exercised" $ok ("" + $probe)
} catch { Check "real_msvcrt_locking_exercised" $false ("probe output not parseable: " + $probe) }

L ""
L "E. TARGETED TESTS (real Windows multiprocessing)"
$env:CSS_TEST_MODE = "1"
$targeted = "tests/test_css065_interprocess_lock.py tests/test_pilot_authorization_ledger.py tests/test_antibleed_pilot_min_size_exception.py tests/test_css064_endurance_package.py tests/test_antibleed_guard_integration.py"
$rc = Run "`"$Py`" -m pytest -q -p no:cacheprovider -rA --junitxml=`"$Root\junit_targeted.xml`" $targeted" "$Root\pytest_targeted.log" $Wt
$tc = JunitCounts "$Root\junit_targeted.xml"; $ts = LogSummary "$Root\pytest_targeted.log"
Check "targeted_tests" (($rc -eq 0) -and $tc -and ($tc.failures -eq 0) -and ($tc.errors -eq 0)) ($ts.line)
$names = @("test_backend_matches_platform_and_never_requires_fcntl_on_windows", "test_other_process_holding_lock_causes_timeout_then_release_allows",
           "test_crashed_holder_never_leaves_a_stale_lock", "test_simultaneous_writers_keep_one_intact_chain",
           "test_duplicate_authorization_attempts_succeed_exactly_once", "test_ledger_lock_contention_fails_closed_without_appending",
           "test_interrupted_write_fails_closed", "test_writer_killed_while_holding_ledger_lock_does_not_block_or_corrupt",
           "test_concurrent_processes_consume_once")
foreach ($n in $names) {
    $hit = Select-String -Path "$Root\pytest_targeted.log" -Pattern ("^PASSED .*::" + $n + "$") -Quiet
    Check ("windows_multiprocess " + $n) $hit $(if ($hit) { "PASSED on Windows" } else { "not PASSED (see pytest_targeted.log)" })
}

L ""
L "F. FULL WINDOWS REGRESSION"
$rc = Run "`"$Py`" -m pytest -q -p no:cacheprovider -rfEs --junitxml=`"$Root\junit_full.xml`" tests" "$Root\pytest_full.log" $Wt
Remove-Item Env:CSS_TEST_MODE -ErrorAction SilentlyContinue
$fc = JunitCounts "$Root\junit_full.xml"; $fs = LogSummary "$Root\pytest_full.log"
$CollectionErrors = $fs.collection
L ("  summary: " + $fs.line)
if ($fc) { L ("  junit: tests=" + $fc.tests + " failures=" + $fc.failures + " errors=" + $fc.errors + " skipped=" + $fc.skipped + " warnings=" + $fs.warnings + " collection_errors=" + $CollectionErrors) }
Check "full_regression_no_collection_errors" ($CollectionErrors -eq 0) ("collection errors: " + $CollectionErrors)
Check "full_regression_no_failures" ($fc -and ($fc.failures -eq 0) -and ($fc.errors -eq 0)) ("failures/errors: " + $(if ($fc) { "" + $fc.failures + "/" + $fc.errors } else { "n/a" }))
Select-String -Path "$Root\pytest_full.log" -Pattern '^(FAILED|ERROR) ' | ForEach-Object { L ("    " + $_.Line) }
L "  Comparison with previous certification:"
foreach ($f in @("pytest_full.log", "pytest_css064_ledger.log", "pytest_windows24.log")) {
    $prev = LogSummary (Join-Path $PrevCert $f)
    L ("    " + $f + " (CSS_WINCERT_20261015T061652Z): " + $prev.line + "; collection_errors=" + $prev.collection)
}

L ""
L "G. SMOKE-GATE PATCH IN A SEPARATE WORKTREE"
if ($PatchFile -eq "") {
    $cand = Get-ChildItem "C:\CSS_Evidence" -Recurse -File -Filter "CSS_SMOKE_GATE_REPAIR.patch" -ErrorAction SilentlyContinue |
        Where-Object { (Get-FileHash $_.FullName -Algorithm SHA256).Hash -eq $PatchSha } | Select-Object -First 1
    if ($cand) { $PatchFile = $cand.FullName }
}
if ($PatchFile -eq "" -or -not (Test-Path $PatchFile)) { Check "smoke_patch_found" $false "CSS_SMOKE_GATE_REPAIR.patch with expected SHA-256 not found under C:\CSS_Evidence" }
else {
    $usersBefore = (Snapshot "users-before-smoke").Split("|")[2]
    cmd /c "git -C `"$RepoPath`" worktree add --detach `"$SmWt`" $TargetSha > `"$Root\smoke_wt.log`" 2>&1"
    cmd /c "git -C `"$SmWt`" apply --check `"$PatchFile`" > `"$Root\patch_check.log`" 2>&1"
    $applies = ($LASTEXITCODE -eq 0)
    Check "smoke_patch_applies_cleanly" $applies "git apply --check on $TargetSha (separate worktree)"
    if ($applies) {
        cmd /c "git -C `"$SmWt`" apply `"$PatchFile`" > `"$Root\patch_apply.log`" 2>&1"
        $env:CSS_BOOTSTRAP_ADMIN_PASSWORD = "Syn-" + ([guid]::NewGuid().ToString("N"))
        try {
            foreach ($m in "dashboard.auth.css_sign_on_smoke_test", "dashboard.mobile.mobile_smoke_test", "dashboard.runtime.runtime_smoke_test", "dashboard.web.web_smoke_test") {
                $rc = Run "`"$Py`" -m $m" (Join-Path $Root "smoke_$m.log") $SmWt
                Check ("smoke " + $m) ($rc -eq 0) ((Get-Content (Join-Path $Root "smoke_$m.log") -Tail 1))
            }
        } finally { Remove-Item Env:CSS_BOOTSTRAP_ADMIN_PASSWORD -ErrorAction SilentlyContinue }
        $env:CSS_TEST_MODE = "1"
        $rc = Run "`"$Py`" -m pytest -q -p no:cacheprovider tests/test_r14f_profitability_gate_regression.py" "$Root\pytest_r14f.log" $SmWt
        Remove-Item Env:CSS_TEST_MODE -ErrorAction SilentlyContinue
        Check "r14f_regression" ($rc -eq 0) ((LogSummary "$Root\pytest_r14f.log").line)
    }
    $usersAfter = (Snapshot "users-after-smoke").Split("|")[2]
    Check "production_users_json_untouched_by_smoke" ($usersBefore -eq $usersAfter) "sha256 before == after"
}

L ""
L "H. PRODUCTION SAFETY FLAGS (HTTP GET only; nothing started)"
foreach ($ep in "/api/v1/safety-flags", "/mission-control/api/health") {
    try {
        $r = Invoke-WebRequest -Uri ($BaseUrl + $ep) -Method Get -UseBasicParsing -TimeoutSec 10
        $j = $r.Content | ConvertFrom-Json
        $r.Content | Out-File -Encoding utf8 (Join-Path $Root ("http" + ($ep -replace '[/\-]', '_') + ".json"))
        if ($ep -eq "/api/v1/safety-flags") { Check "safety_flags_verdict_safe" (($j.verdict -eq "SAFE") -and ($j.fail_closed -eq $false)) ("verdict=" + $j.verdict + " fail_closed=" + $j.fail_closed) }
        else { Check "mission_control_read_only" (($j.read_only -eq $true) -and ($j.execution_allowed -eq $false) -and ($j.live_trading_blocked -eq $true) -and ($j.advisory_only -eq $true)) ("read_only=" + $j.read_only + " execution_allowed=" + $j.execution_allowed + " live_trading_blocked=" + $j.live_trading_blocked + " advisory_only=" + $j.advisory_only) }
    } catch { L ("  [BLOCKED] GET " + $ep + " - runtime not reachable at " + $BaseUrl + "; not started") }
}

L ""
L "I. PRODUCTION SNAPSHOT (after)"
$after = Snapshot "after"
$Unchanged = ($before -eq $after)
Check "production_checkout_unchanged" $Unchanged "HEAD, tracked status and users.json SHA-256 identical before/after"

L ""
L "J. INDEPENDENT REVIEW"
L "  This script cannot perform an independent review. A reviewer other than the CSS-065 author must"
L "  review css065_full.diff (and CSS_065_SELF_REVIEW.txt) and record PASS/FAIL separately."
$verdict = $(if ($Fails.Count -eq 0) { "PASS" } else { "FAIL" })
L ""
L ("Failed checks: " + $(if ($Fails.Count) { $Fails -join ", " } else { "none" }))
L ("CSS065_WINDOWS_VALIDATION=" + $verdict)
L "CSS065_INDEPENDENT_REVIEW=PENDING (record reviewer verdict separately)"
L ("WINDOWS_COLLECTION_ERRORS=" + $CollectionErrors)
L ("PRODUCTION_CHECKOUT_UNCHANGED=" + $(if ($Unchanged) { "TRUE" } else { "FALSE" }))
L "LIVE_TRADING_ALLOWED=FALSE"
L "PRODUCTION_GO=NO"
$report = Join-Path $Root "CSS065_WINDOWS_VALIDATION_REPORT.txt"
$Lines | Out-File -Encoding utf8 $report
Get-ChildItem $Root -File | Get-FileHash -Algorithm SHA256 | ForEach-Object { "{0}  {1}" -f $_.Hash, (Split-Path -Leaf $_.Path) } | Out-File -Encoding ascii (Join-Path $Root "SHA256SUMS.txt")
Write-Host ("Report: " + $report)
Start-Process notepad.exe -ArgumentList "`"$report`""
if ($verdict -eq "PASS") { exit 0 } else { exit 1 }
